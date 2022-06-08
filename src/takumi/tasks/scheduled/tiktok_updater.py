import datetime as dt
from typing import Optional

import tasktiger
from sqlalchemy import and_, or_
from tasktiger.schedule import periodic

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, puppet, tiger
from takumi.models import TikTokAccount
from takumi.services import TikTokAccountService
from takumi.tasks.cdn import upload_media_to_cdn
from takumi.utils import uuid4_str
from takumi.utils.tiktok import store_feed_dump

TIKTOK_QUEUE = f"{MAIN_QUEUE_NAME}.tiktok"


@tiger.scheduled(periodic(hours=24, start_date=dt.datetime(2000, 1, 1, 5)))  # Run 5:00 GMT
def update_tiktok_accounts_daily():
    # Update 1k+ follower influencers nightly
    update_tiktok_accounts(min_followers=1000, min_days_since_scrape=1)


@tiger.scheduled(
    periodic(hours=24 * 7, start_date=dt.datetime(2000, 1, 2, 1))
)  # Run 1:00 GMT, every Sunday
def update_tiktok_accounts_weekly():
    # Update <1k follower influencers once a week
    update_tiktok_accounts(max_followers=1000, min_days_since_scrape=7)


def update_tiktok_accounts(
    *,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
    min_days_since_scrape: int = 1,
) -> None:
    """Schedule updating of TikTok accounts

    Min followers and days since last scrape is used so that we can prioritise
    updating valid influencers regularly, while invalid ones not as often.
    For example, we want to update influencers with 1k+ followers daily, but <1k followers once a week
    """
    now = dt.datetime.now(dt.timezone.utc)

    q = db.session.query(TikTokAccount.id).filter(
        TikTokAccount.is_active,
        or_(
            TikTokAccount.last_scraped == None,
            and_(
                TikTokAccount.last_scraped != None,
                TikTokAccount.last_scraped < now - dt.timedelta(days=min_days_since_scrape),
            ),
        ),
    )

    if min_followers is not None:
        q = q.filter(TikTokAccount.followers >= min_followers)
    if max_followers is not None:
        q = q.filter(TikTokAccount.followers < max_followers)

    account_ids = [result.id for result in q]

    for idx, account_id in enumerate(account_ids):
        tiger.tiger.delay(
            update_tiktok_account,
            args=[account_id],
            queue=TIKTOK_QUEUE,
            retry_method=tasktiger.fixed(600, 5),
            unique=True,
            when=dt.timedelta(seconds=idx * 5),  # Spread by 5 seconds per account
        )


@tiger.task(queue=TIKTOK_QUEUE, unique=True)
def update_tiktok_account(account_id: str) -> None:
    account: TikTokAccount = TikTokAccount.query.get(account_id)
    if account is None:
        return

    user_response = puppet.get_user(account.username)
    if user_response is None:
        with TikTokAccountService(account) as service:
            service.set_is_active(False)
        return

    user_info = user_response["userInfo"]
    tiktok_profile = user_info["user"]

    if "avatarLarger" in tiktok_profile:
        original_cover: str = tiktok_profile["avatarLarger"]
        if account.original_cover != original_cover:
            cover = upload_media_to_cdn(original_cover, uuid4_str())
            tiktok_profile["avatarLarger"] = cover
    else:
        original_cover = ""

    with TikTokAccountService(account) as service:
        service.update(user_info=user_info, original_cover=original_cover)

    # Persist their feed for now on S3
    feed = puppet.get_user_feed(account.username)
    if feed is None:
        return
    store_feed_dump(account.username, data=feed)

    # Update base feed stats on the account
    with TikTokAccountService(account) as service:
        service.update_feed_info(feed)
