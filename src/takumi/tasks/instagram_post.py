import datetime as dt
import json
from unicodedata import normalize

import requests
from flask import current_app
from itp import itp
from sentry_sdk import capture_exception
from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from core.facebook.instagram import InstagramError, InstagramMediaNotFound, InstagramUnknownError

from takumi.extensions import instascrape, tiger
from takumi.facebook_account import unlink_on_permission_error
from takumi.ig.instascrape import InstascrapeUnavailable, NoResponse, NotFound
from takumi.models.influencer import FacebookPageDeactivated, MissingFacebookPage
from takumi.sentiment import CommentTooShort, SentimentAnalyser, UnsupportedLanguage
from takumi.tasks import TaskException
from takumi.utils import has_analyzable_text
from takumi.utils.emojis import find_emojis

INDICO_SENTIMENT_URL = "https://apiv2.indico.io/sentimenthq"


class NoInstagramAccount(Exception):
    pass


@tiger.task(unique=True)
def scrape_and_update_instagram_post_media(instagram_post_id):  # noqa: C901
    from takumi.services import InstagramPostService, OfferService

    instagram_post = InstagramPostService.get_by_id(instagram_post_id)
    if instagram_post is None:
        raise TaskException(f'InstagramPost with id "{instagram_post_id}" not found')
    if instagram_post.gig is None:
        # instagram_post has been unlinked
        return

    influencer = instagram_post.gig.offer.influencer

    with InstagramPostService(instagram_post) as service:
        service.update_scraped(dt.datetime.now(dt.timezone.utc))
        try:
            if influencer.instagram_account is None:
                raise NoInstagramAccount()
            if influencer.instagram_account.facebook_page is None:
                raise MissingFacebookPage()
            if not influencer.instagram_account.facebook_page.active:
                raise FacebookPageDeactivated()

            with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                media = influencer.instagram_api.get_media_by_ig_id(
                    instagram_post.ig_post_id, nocache=True
                )
                insights = influencer.instagram_api.get_media_insights(media["id"], nocache=True)
                comments = influencer.instagram_api.get_media_comments(
                    media["id"], nocache=True, limit=50
                )
                comment_count = media["comments_count"]
                like_count = media["like_count"]
                caption = media["caption"]
                username = media["username"]
                video_views = insights.get("video_views")
        except (
            MissingFacebookPage,
            InstagramError,
            InstagramMediaNotFound,
            FacebookPageDeactivated,
            InstagramUnknownError,
            NoInstagramAccount,
        ) as e:
            fb_api_not_found = False
            if isinstance(e, InstagramMediaNotFound):
                # Don't report media not found errors, it will fall back to instascrape
                fb_api_not_found = True
            elif isinstance(e, InstagramError):
                capture_exception()
            try:
                media = instascrape.get_media(instagram_post.ig_post_id, nocache=True)
                comments = media.get("comments", {}).get("nodes")
                comment_count = media["comments"]["count"]
                like_count = media["likes"]["count"]
                caption = media["caption"]
                username = media["owner"]["username"]
                video_views = media.get("video_view_count", None)
            except (NotFound, NoResponse):
                if fb_api_not_found:
                    # Not found through official api nor by scraping, likely deleted
                    with InstagramPostService(instagram_post) as service:
                        service.update_media_deleted(True)
                    return
                # Any other fb api error, retry
                raise RetryException(method=fixed(delay=600, max_retries=5))
            except InstascrapeUnavailable:
                # Try again later
                raise RetryException(method=fixed(delay=600, max_retries=5))

    if comments is None:
        raise RetryException(method=fixed(delay=600, max_retries=5))

    update_instagram_post_comments.delay(instagram_post.id, comments)
    with InstagramPostService(instagram_post) as service:
        engagements_before = instagram_post.engagements
        service.update_media_deleted(False)  # update every time, in case account was private
        service.update_comments(comment_count)
        service.update_likes(like_count)
        service.update_caption(caption)
        if engagements_before != instagram_post.engagements:
            OfferService(instagram_post.gig.offer).update_engagements_per_post()

        if video_views:
            service.update_video_views(video_views)

        if instagram_post.followers is None or instagram_post.followers == 0:
            # Set instagram_post followers for the first time
            try:
                with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                    profile = influencer.instagram_api.get_profile()
                    followers = profile["followers_count"]
            except (
                MissingFacebookPage,
                InstagramError,
                FacebookPageDeactivated,
            ) as e:
                if isinstance(e, InstagramError):
                    capture_exception()
                try:
                    profile = instascrape.get_user(username)
                    followers = profile["followers"]
                except InstascrapeUnavailable:
                    # Will be done next time
                    return
            service.update_followers(followers)
    if (
        influencer.instagram_account
        and influencer.instagram_account.facebook_page
        and influencer.instagram_account.facebook_page.active
    ):
        try:
            with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                instagram_post.update_instagram_insights()
        except InstagramUnknownError:
            capture_exception()
        except FacebookPageDeactivated:
            pass


def analyze_text_sentiment(text):
    data = dict(api_key=current_app.config["INDICO_API_KEY"], data=text, url=False)

    response = requests.post(INDICO_SENTIMENT_URL, data=json.dumps(data))
    response.raise_for_status()

    response = json.loads(response.text)
    sentiment = response["results"]

    return sentiment


@tiger.task(unique=True)
def update_instagram_post_comments(instagram_post_id, comments):
    from takumi.services import InstagramPostCommentService, InstagramPostService

    instagram_post = InstagramPostService.get_by_id(instagram_post_id)
    if instagram_post is None:
        raise TaskException(f'InsagramPost with id "{instagram_post_id}" not found')
    elif instagram_post.gig is None:
        # instagram_post has been unlinked
        return

    # Some comments have replies, so add them to the comment list to process
    replies = []
    for comment in comments:
        if "replies" in comment:
            replies.extend(comment["replies"]["data"])
    comments.extend(replies)

    analyze = []
    for comment in comments:
        instagram_post_comment = InstagramPostCommentService.get_by_ig_comment_id(comment["id"])
        if instagram_post_comment is not None:
            if not instagram_post_comment.sentiment_checked:
                analyze.append(instagram_post_comment)
            # Update ig_post if associated to a different one
            with InstagramPostCommentService(instagram_post_comment) as service:
                service.set_instagram_post(instagram_post_id)
        else:
            text = itp.Parser().parse(normalize("NFC", comment["text"]))
            # Remove duplicates with set
            emojis = list(set(find_emojis(comment["text"])))
            hashtags = list(set(text.tags))

            instagram_post_comment = InstagramPostCommentService.create(
                ig_comment_id=comment["id"],
                username=comment.get("username", "N/A"),
                text=comment["text"],
                instagram_post_id=instagram_post.id,
                hashtags=hashtags,
                emojis=emojis,
                scraped=dt.datetime.now(dt.timezone.utc),
            )

            analyze.append(instagram_post_comment)

    if instagram_post.gig.post.campaign.market.sentiment_supported and len(analyze) > 0:
        for comment in analyze:
            update_comment_sentiment.delay(comment.id)


@tiger.task(unique=True)
def update_caption_sentiment(instagram_post_id, caption):
    from takumi.services import InstagramPostService

    # XXX: Temporary disable indico, as it's seems to have deprecated their API
    return

    instagram_post = InstagramPostService.get_by_id(instagram_post_id)
    if instagram_post is None:
        raise TaskException(f'InstagramPost with id "{instagram_post_id}" not found')

    if not has_analyzable_text(caption):
        return

    try:
        sentiment = analyze_text_sentiment(caption)
    except requests.exceptions.HTTPError as exc:
        if exc.response and exc.response.status_code >= 500:
            raise RetryException(method=fixed(delay=600, max_retries=5))
        raise exc

    with InstagramPostService(instagram_post) as service:
        service.update_sentiment(sentiment)


@tiger.task(unique=True)
def update_comment_sentiment(comment_id):
    from takumi.services import InstagramPostCommentService

    comment = InstagramPostCommentService.get_by_id(comment_id)
    if comment is None:
        raise TaskException(f'InstagramPostComment with id "{comment_id}" not found')

    if comment.sentiment_checked:
        return

    analyser = SentimentAnalyser()
    try:
        sentiment = analyser.analyse(comment.text)
    except (CommentTooShort, UnsupportedLanguage):
        with InstagramPostCommentService(comment) as service:
            service.set_sentiment_checked()
    else:
        with InstagramPostCommentService(comment) as service:
            service.update_sentiment(sentiment)
