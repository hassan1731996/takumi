from takumi.events import Event, TableLog
from takumi.models.user import UserEvent


class UserSetDevice(Event):
    def apply(self, user):
        user.device_id = self.properties["device_id"]


class LinkFacebookAccountDebug(Event):
    def apply(self, user):
        pass


class LinkFacebookAccount(Event):
    def apply(self, user):
        pass


class UnLinkFacebookAccount(Event):
    def apply(self, user):
        pass


class UserLog(TableLog):
    event_model = UserEvent
    relation = "user"
    type_map = {
        "set_device": UserSetDevice,
        "link_facebook_account_debug": LinkFacebookAccountDebug,
        "link_facebook_account": LinkFacebookAccount,
        "unlink_facebook_account": UnLinkFacebookAccount,
    }
