from flask import current_app

from .fund import Fund


class CashFund(Fund):
    def is_reservable(self):
        return False

    def is_fulfilled(self):
        return True

    @property
    def min_followers(self):
        return current_app.config["MINIMUM_FOLLOWERS"]

    def get_progress(self):
        return {"total": 100, "reserved": 0, "submitted": 100}
