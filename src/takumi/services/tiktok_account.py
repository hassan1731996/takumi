import datetime as dt
import statistics
from typing import Optional

from takumi.events.tiktok_account import TikTokAccountLog
from takumi.extensions import db
from takumi.models import Influencer, TikTokAccount
from takumi.services import Service
from takumi.tiktok.puppet.types import FeedResponse, UserInfo


class TikTokAccountService(Service):
    SUBJECT = TikTokAccount
    LOG = TikTokAccountLog

    @property
    def tiktok_account(self) -> TikTokAccount:
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id) -> Optional[TikTokAccount]:
        return TikTokAccount.query.get(id)

    @staticmethod
    def get_by_username(username) -> Optional[TikTokAccount]:
        return TikTokAccount.by_username(username)

    # POST
    @staticmethod
    def create_tiktok_account(user_info: UserInfo, influencer: Influencer) -> TikTokAccount:
        profile = user_info["user"]
        stats = user_info["stats"]

        tiktok_account = TikTokAccount(
            user_id=profile["id"],
            username=profile["uniqueId"],
            nickname=profile["nickname"],
            cover=profile["avatarLarger"],
            signature=profile["signature"],
            verified=profile["verified"],
            is_secret=profile["secret"],
            following=stats["followingCount"],
            followers=stats["followerCount"],
            likes=stats["heartCount"],
            video_count=stats["videoCount"],
            digg=stats["diggCount"],
            influencer=influencer,
        )

        db.session.add(tiktok_account)
        db.session.commit()

        return tiktok_account

    def set_is_active(self, is_active: bool) -> None:
        self.log.add_event("set-is-active", {"is_active": is_active})

    def update(self, user_info: UserInfo, original_cover: str) -> None:
        self.log.add_event(
            "tiktok-update",
            {
                "user_info": user_info,
                "original_cover": original_cover,
                "last_scraped": dt.datetime.now(dt.timezone.utc),
            },
        )

    def update_feed_info(self, feed: FeedResponse) -> None:
        if not len(feed):
            return

        plays = [item["stats"]["playCount"] for item in feed]
        diggs = [item["stats"]["diggCount"] for item in feed]
        shares = [item["stats"]["shareCount"] for item in feed]
        comments = [item["stats"]["commentCount"] for item in feed]

        median_plays, mean_plays = statistics.median(plays), statistics.mean(plays)
        median_diggs, mean_diggs = statistics.median(diggs), statistics.mean(diggs)
        median_shares, mean_shares = statistics.median(shares), statistics.mean(shares)
        median_comments, mean_comments = statistics.median(comments), statistics.mean(comments)

        self.log.add_event(
            "tiktok-update-feed",
            {
                "median_plays": median_plays,
                "mean_plays": mean_plays,
                "median_diggs": median_diggs,
                "mean_diggs": mean_diggs,
                "median_shares": median_shares,
                "mean_shares": mean_shares,
                "median_comments": median_comments,
                "mean_comments": mean_comments,
            },
        )
