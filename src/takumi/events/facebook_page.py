from takumi.events import ColumnLog, Event


class Activate(Event):
    def apply(self, facebook_page):
        facebook_page.active = True


class Deactivate(Event):
    def apply(self, facebook_page):
        facebook_page.active = False


class FacebookPageLog(ColumnLog):
    type_map = {"activate": Activate, "deactivate": Deactivate}
