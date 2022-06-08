from flask import current_app
from sqlalchemy import case, func

from takumi.extensions import db
from takumi.models import Offer

from .fund import Fund


class AssetsFund(Fund):
    def is_reservable(self):
        return self.reserved_offer_count < self.campaign.units

    def can_reserve_units(self, units):
        if not self.is_reservable():
            return False
        return self.reserved_offer_count + units <= self.campaign.units

    def is_fulfilled(self):
        claimable_offers = [o for o in self.campaign.offers if o.is_claimable]
        return len(claimable_offers) >= self.campaign.units

    @property
    def min_followers(self):
        return current_app.config["MINIMUM_FOLLOWERS"]

    def get_progress(self):
        count_offers = lambda column: func.coalesce(
            func.sum(case([((column == True), 1)], else_=0)), 0
        )
        reserved_count, submitted_count = (
            db.session.query(
                count_offers(Offer.is_reserved), count_offers(Offer.is_submitted)
            ).filter(Offer.campaign_id == self.campaign.id, Offer.is_reserved)
        ).first()

        return {
            "total": self.campaign.units,
            "reserved": reserved_count,
            "submitted": submitted_count,
        }

    def get_reward(self, followers):
        campaign = self.campaign

        if campaign.custom_reward_units is None:
            shipping_cost = 0
            if campaign.shipping_required:
                shipping_cost = campaign.market.shipping_cost * campaign.units

            return (
                (campaign.list_price - shipping_cost)
                * (1 - campaign.market.margins.asset)
                / float(campaign.units)
            )
        else:
            return campaign.custom_reward_units

    def get_offer_units(self, offer):
        return 1

    def get_remaining_reach(self):
        return self.campaign.units - self.reserved_offer_count
