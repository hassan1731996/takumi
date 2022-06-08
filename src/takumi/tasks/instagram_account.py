import datetime as dt
from typing import List, TypedDict, cast

from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from core.common.crypto import get_human_random_string
from core.facebook.instagram import (
    FacebookPermissionDenied,
    InstagramAPI,
    InstagramMediaPostedBeforeBusinessAccountConversion,
    InstagramTokenInvalidated,
)
from core.tasktiger import MAIN_QUEUE_NAME

from takumi.events.instagram_account import InstagramAccountLog
from takumi.extensions import db, instascrape, tiger
from takumi.facebook_account import unlink_on_permission_error
from takumi.ig.instascrape import InstascrapeUnavailable, NotFound
from takumi.models import Config, InstagramAccount
from takumi.services.instagram_account import InstagramAccountService

RECENT_MEDIA_QUEUE = f"{MAIN_QUEUE_NAME}.recent_media"
RECENT_MEDIA_MIN_HOURS = 24


def set_instagram_account_username(account, new_username):
    """Update the username on an instagram_account

    If the new username is in use by someone else, the username is freed up and
    a username update scheduled for the old user
    """
    exists = InstagramAccount.by_username(new_username)
    if exists is not None:
        # Free up the username and schedule update for that account
        exists_log = InstagramAccountLog(exists)
        temp_username = "{}-invalid-{}".format(new_username, get_human_random_string(length=6))
        exists_log.add_event("username-change", {"username": temp_username})

        db.session.add(exists)
        db.session.commit()

        instagram_account_new_username.delay(exists.id)

    log = InstagramAccountLog(account)
    log.add_event("username-change", {"username": new_username})

    db.session.add(account)
    db.session.commit()


@tiger.task(unique=True)
def instagram_account_new_username(account_id):
    """Update an influencer username by looking them up by id"""
    account = InstagramAccount.query.get(account_id)

    try:
        scraped = instascrape.get_user_by_instagram_account(account, nocache=True)
    except NotFound:
        # Unable to find user on instagram
        return
    except InstascrapeUnavailable:
        # Try again later
        raise RetryException(method=fixed(delay=600, max_retries=5))

    new_username = scraped["username"]

    if account.ig_username == new_username:
        # Username hasn't changed, or already updated
        return

    set_instagram_account_username(account, new_username)


class InstagramMediaInsights(TypedDict, total=False):
    engagement: int
    impressions: int
    reach: int
    saved: int
    carousel_album_engagement: int
    carousel_album_impressions: int
    carousel_album_reach: int


class InstagramMedia(TypedDict, total=False):
    id: str
    caption: str
    comments_count: int
    like_count: int
    media_type: str
    media_url: str
    permalink: str
    timestamp: str
    insights: InstagramMediaInsights


@tiger.task(unique=True, lock_key="recent_media", queue=RECENT_MEDIA_QUEUE)
def update_latest_posts(account_id: str) -> None:
    """Get the latest instagram posts of a profile.

    Start by getting the id of their latest posts, then get each getting
    insights information for every post they have, with a short pause between
    each to not be too aggressive on requests.

    The task takes a lock as well, to prevent multiple tasks being run at the
    same time, causing too many parallel requests

    Profiles are not updated more than once every 24 hours
    """
    if Config.get("PROCESS_LATESTS_INSTAGRAM_POSTS").value is not True:
        # Processing is disabled
        return
    account = InstagramAccount.query.get(account_id)
    if account is None:
        return
    if account.facebook_page is None:
        # Not linked
        return
    if not account.facebook_page.active:
        # Deactivated
        return
    yesterday = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=RECENT_MEDIA_MIN_HOURS)
    if account.recent_media_updated is not None and account.recent_media_updated > yesterday:
        # Only update max once every RECENT_MEDIA_MIN_HOURS hours
        return

    api: InstagramAPI = account.facebook_page.instagram_api

    try:
        medias: List[InstagramMedia] = api.get_medias(
            limit=25,
            fields=[
                "id",
                "caption",
                "comments_count",
                "like_count",
                "media_type",
                "media_url",
                "permalink",
                "shortode",
                "timestamp",
            ],
        )
    except InstagramTokenInvalidated:
        # Invalid token, can't get info.
        account.recent_media_updated = dt.datetime.now(dt.timezone.utc)
        db.session.commit()
        return

    with unlink_on_permission_error(account.facebook_page):
        for media in medias:
            try:
                media["insights"] = cast(
                    InstagramMediaInsights, api.get_media_insights(media["id"])
                )
            except (InstagramMediaPostedBeforeBusinessAccountConversion, FacebookPermissionDenied):
                # Stop trying, as older posts will not work either
                break

    with InstagramAccountService(account) as service:
        service.update_recent_media(medias)
