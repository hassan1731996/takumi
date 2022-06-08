import datetime as dt

import tasktiger
from sentry_sdk import capture_exception
from tasktiger.schedule import periodic

from core.common.chunks import chunks
from core.facebook.exceptions import InstagramError
from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, instascrape, tiger
from takumi.facebook_account import unlink_on_permission_error
from takumi.models import Config, Influencer, InstagramAccount, Offer, Post
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.services import InstagramStoryService

DAYS_PAST_DEADLINE = 180
SECONDS_BETWEEN_CHUNKS = 5 * 60

STORIES_QUEUE = f"{MAIN_QUEUE_NAME}.stories"


@tiger.scheduled(periodic(hours=3))
def download_story_frames():
    now = dt.datetime.now(dt.timezone.utc)

    campaigns_subq = (
        db.session.query(Post.campaign_id)
        .filter(
            Post.post_type == PostTypes.story,
            Post.deadline > now - dt.timedelta(days=DAYS_PAST_DEADLINE),
        )
        .distinct(Post.campaign_id)
    ).subquery()

    ig_user_ids = (
        db.session.query(InstagramAccount.ig_user_id)
        .join(Influencer)
        .join(Offer)
        .filter(
            Offer.state == OFFER_STATES.ACCEPTED,
            Offer.campaign_id.in_(campaigns_subq),
            Offer.payable == None,
        )
        .distinct(Offer.influencer_id)
    )

    ig_user_ids = [_[0] for _ in ig_user_ids]

    for idx, id_chunk in enumerate(chunks(ig_user_ids, 15)):
        # Schedule chunks of 15 at a time
        tiger.tiger.delay(
            download_multiple_stories,
            args=[id_chunk],
            queue=STORIES_QUEUE,
            retry_method=tasktiger.fixed(600, 5),
            unique=True,
            when=dt.timedelta(seconds=idx * SECONDS_BETWEEN_CHUNKS),
        )


@tiger.task(queue=STORIES_QUEUE, unique=True)
def download_multiple_stories(ig_user_ids):
    config = Config.get("SCRAPE_STORIES")
    scrape_stories = config.value is True

    if scrape_stories:
        stories = instascrape.get_multiple_stories(ig_user_ids)["data"]
    else:
        stories = []
        for ig_user_id in ig_user_ids:
            account = InstagramAccount.query.filter(
                InstagramAccount.ig_user_id == ig_user_id
            ).first()
            if account.facebook_page is None or account.facebook_page.instagram_api is None:
                continue
            fb_api = account.facebook_page.instagram_api
            try:
                with unlink_on_permission_error(account.facebook_page):
                    user_story = fb_api.get_stories()
            except InstagramError:
                continue

            stories.append(
                {
                    "items": [
                        {
                            **item,
                            "tappable_objects": [],
                        }
                        for item in user_story
                    ],
                    "id": ig_user_id,
                }
            )

    for story in stories:
        ig_user_id = story["id"]
        account = InstagramAccount.query.filter(InstagramAccount.ig_user_id == ig_user_id).first()

        try:
            InstagramStoryService._create_story_frames_from_download(
                {"data": story}, account.influencer
            )
        except Exception:
            capture_exception()


@tiger.task(queue=STORIES_QUEUE, unique=True)
def download_influencer_story_frames(influencer_id):
    InstagramStoryService.download_story_frames(influencer_id)
