from takumi.events import ColumnLog, Event


class Activate(Event):
    def apply(self, facebook_account):
        facebook_account.active = True


class Deactivate(Event):
    def apply(self, facebook_account):
        facebook_account.active = False


class FacebookAccountLog(ColumnLog):
    type_map = {"activate": Activate, "deactivate": Deactivate}
