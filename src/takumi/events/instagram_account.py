from sqlalchemy.orm.attributes import flag_modified

from takumi.events import Event, TableLog
from takumi.models.instagram_account import InstagramAccountEvent


class InstagramAccountInfoUpdated(Event):
    def apply(self, instagram_account):
        instagram_account.engagement = self.properties["engagement"]
        instagram_account.followers = self.properties["followers"]
        instagram_account.follows = self.properties["following"]
        instagram_account.ig_biography = self.properties.get("biography", "")
        instagram_account.ig_is_private = self.properties["is_private"]
        instagram_account.ig_is_business_account = self.properties.get("is_business_account")
        instagram_account.ig_is_verified = self.properties.get("is_verified")
        instagram_account.media_count = self.properties["media_count"]
        instagram_account.scraped_email = self.properties.get("email")
        instagram_account.boosted = self.properties.get("boosted")

        if not instagram_account.supports_insights and (
            instagram_account.ig_is_business_account or instagram_account.ig_is_verified
        ):
            # Set accounts to support insights if they have ever been business accounts
            # This is temporary until we can ask influencers if they are creator accounts or not
            instagram_account.supports_insights = True


class InfluencerUsernameChange(Event):
    def apply(self, instagram_account):
        instagram_account.ig_username = self.properties["username"]


class DismissFollowersAnomalies(Event):
    def apply(self, instagram_account):
        for anomaly in instagram_account.followers_history_anomalies:
            anomaly["ignore"] = True
        flag_modified(instagram_account, "followers_history_anomalies")


class VerifyMediaForAccount(Event):
    def apply(self, instagram):
        """A debug event to capture the data used for verification during signup"""
        pass


class UpdateRecentMedia(Event):
    def apply(self, instagram_account):
        instagram_account.recent_media = self.properties["recent_media"]
        instagram_account.recent_media_updated = self.properties["now"]


class InstagramAccountLog(TableLog):
    event_model = InstagramAccountEvent
    relation = "instagram_account"
    type_map = {
        "instagram-update": InstagramAccountInfoUpdated,
        "username-change": InfluencerUsernameChange,
        "dismiss-followers-anomalies": DismissFollowersAnomalies,
        "verify-media-for-account": VerifyMediaForAccount,
        "update-recent-media": UpdateRecentMedia,
    }
