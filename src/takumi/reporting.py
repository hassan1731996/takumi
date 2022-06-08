import csv
from contextlib import contextmanager
from io import StringIO

from sqlalchemy import func

from takumi.extensions import db
from takumi.models import Gig, InstagramPost, InstagramPostComment, InstagramStory, Post
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes
from takumi.roles import permissions

GIG_FIELDS = ("url", "posted", "reach")
POST_FIELDS = ("comments", "likes", "engagement", "caption_sentiment", "comment_sentiment")


def _get_gig_posts_query(post):
    visible_states = [GIG_STATES.REVIEWED, GIG_STATES.APPROVED]

    if permissions.see_reported_gigs.can():
        visible_states += [GIG_STATES.REPORTED]

    return (
        db.session.query(Gig, func.coalesce(func.avg(InstagramPostComment.sentiment), None))
        .join(Post)
        .join(InstagramPost, InstagramPost.gig_id == Gig.id)
        .outerjoin(InstagramPostComment, InstagramPostComment.instagram_post_id == InstagramPost.id)
        .filter(Gig.state.in_(visible_states), Gig.post == post)
        .group_by(Gig, InstagramPost.posted)
        .order_by(InstagramPost.posted)
    )


def _get_gig_stories_query(post):
    visible_states = [GIG_STATES.REVIEWED, GIG_STATES.APPROVED]

    if permissions.see_reported_gigs.can():
        visible_states += [GIG_STATES.REPORTED]

    return (
        db.session.query(Gig)
        .join(Post)
        .join(InstagramStory, InstagramStory.gig_id == Gig.id)
        .filter(Gig.state.in_(visible_states), Gig.post == post)
        .group_by(Gig)
    )


def _insert_new_line(title="", x=""):
    return dict(
        [("username", title)] + [(key, x) for key in GIG_FIELDS] + [(key, x) for key in POST_FIELDS]
    )


def _iter_story_stats(post):
    for gig in _get_gig_stories_query(post):
        instagram_story = gig.instagram_story
        if not instagram_story or not instagram_story.has_marked_frames:
            continue
        yield {
            "username": gig.offer.influencer.username,
            "url": instagram_story.story_frames[0].media.url.replace(
                "lemonade.imgix.net", "takumi.imgix.net"
            ),
            "posted": instagram_story.story_frames[0].posted.strftime("%Y-%m-%d"),
            "reach": instagram_story.followers,
        }
        for frame in instagram_story.story_frames[1:]:
            yield {
                "url": frame.media.url.replace("lemonade.imgix.net", "takumi.imgix.net"),
                "posted": frame.posted.strftime("%Y-%m-%d"),
            }


def _iter_post_stats(post):
    for gig, comment_sentiment in _get_gig_posts_query(post):
        instagram_post = gig.instagram_post
        if not instagram_post:
            continue
        yield {
            "username": gig.offer.influencer.username,
            "url": instagram_post.media[0].url.replace("lemonade.imgix.net", "takumi.imgix.net"),
            "posted": instagram_post.posted.strftime("%Y-%m-%d"),
            "reach": instagram_post.followers,
            "comments": instagram_post.comments,
            "likes": instagram_post.likes,
            "engagement": instagram_post.engagement,
            "caption_sentiment": instagram_post.sentiment,
            "comment_sentiment": float(comment_sentiment) if comment_sentiment else None,
        }
        # If there is more media, add the urls as new rows
        for media in instagram_post.media[1:]:
            yield {"url": media.url.replace("lemonade.imgix.net", "takumi.imgix.net")}


def _iter_gig_stats(posts):
    posts_length = len(posts)
    for i, post in enumerate(posts):
        yield _insert_new_line("Post {}".format(i + 1), "---")

        if post.post_type == PostTypes.story:
            yield from _iter_story_stats(post)
        else:
            yield from _iter_post_stats(post)

        if i != posts_length - 1:
            yield _insert_new_line()


@contextmanager
def get_posts_gigs_stats_csv(posts):
    output = StringIO()

    sheet = csv.DictWriter(output, fieldnames=("username",) + GIG_FIELDS + POST_FIELDS)
    sheet.writeheader()

    for row in _iter_gig_stats(posts):
        sheet.writerow(row)
    yield output.getvalue()
    output.close()
