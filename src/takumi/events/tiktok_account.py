from takumi.events import Event, TableLog
from takumi.models.tiktok_account import TikTokAccount, TikTokAccountEvent
from takumi.tiktok.puppet.types import UserInfo


class TikTokAccountInfoUpdated(Event):
    def apply(self, account: TikTokAccount):
        user_info: UserInfo = self.properties["user_info"]

        stats = user_info["stats"]
        profile = user_info["user"]

        account.username = profile["uniqueId"]
        account.nickname = profile["nickname"]
        account.cover = profile["avatarLarger"]
        account.signature = profile["signature"]
        account.verified = profile["verified"]
        account.is_secret = profile["secret"]
        account.following = stats["followingCount"]
        account.followers = stats["followerCount"]
        account.likes = stats["heartCount"]
        account.video_count = stats["videoCount"]
        account.digg = stats["diggCount"]

        account.last_scraped = self.properties["last_scraped"]
        account.original_cover = self.properties["original_cover"]


class TikTokAccountFeedUpdated(Event):
    def apply(self, account: TikTokAccount):
        account.median_plays = self.properties["median_plays"]
        account.mean_plays = self.properties["mean_plays"]
        account.median_diggs = self.properties["median_diggs"]
        account.mean_diggs = self.properties["mean_diggs"]
        account.median_shares = self.properties["median_shares"]
        account.mean_shares = self.properties["mean_shares"]
        account.median_comments = self.properties["median_comments"]
        account.mean_comments = self.properties["mean_comments"]


class TikTokAccountSetIsActive(Event):
    def apply(self, account):
        account.is_active = self.properties["is_active"]


class TikTokAccountLog(TableLog):
    event_model = TikTokAccountEvent
    relation = "tiktok_account"
    type_map = {
        "tiktok-update": TikTokAccountInfoUpdated,
        "tiktok-update-feed": TikTokAccountFeedUpdated,
        "set-is-active": TikTokAccountSetIsActive,
    }
