import math

from sqlalchemy import case, func, select

from takumi.constants import (
    IMPRESSIONS_PER_ASSET,
    MAX_FOLLOWERS_BEYOND_REWARD_POOL,
    MEDIAN_IMPRESSIONS_RATIO,
    MILLE,
    MIN_INSTAGRAM_FOLLOWERS_REACH,
)
from takumi.extensions import db
from takumi.models import Influencer, Offer

from .fund import Fund

# Campaign.units -> Impressions -> 250k for a 1 million "reach" campaign


def _sum_estimated_impressions(column):
    return func.coalesce(
        func.sum(
            case(
                [
                    (
                        (column == True),
                        select([Influencer.estimated_impressions])
                        .where(Influencer.id == Offer.influencer_id)
                        .label("estimated_impressions"),
                    )
                ],
                else_=0,
            )
        ),
        0,
    )


class ImpressionsFund(Fund):
    @property
    def minimum_reservations(self):
        return math.ceil(self.campaign.units / IMPRESSIONS_PER_ASSET)

    @property
    def _reserved_impressions(self):
        return sum(o.impressions for o in self.campaign.reserved_offers)

    @property
    def _remaining_impressions(self):
        return max(0, self.campaign.units - self._reserved_impressions)

    @property
    def min_followers(self):
        return MIN_INSTAGRAM_FOLLOWERS_REACH

    def minimum_reservations_met(self):
        return self.reserved_offer_count >= self.minimum_reservations

    def is_reservable(self):
        if not self.minimum_reservations_met():
            return True
        return self._remaining_impressions != 0

    def can_reserve_units(self, units):
        """Check if it's possible to reserve an amount of units"""
        if not self.is_reservable():
            return False

        return self._remaining_impressions + MAX_FOLLOWERS_BEYOND_REWARD_POOL - units >= 0

    def is_fulfilled(self):
        for post in self.campaign.posts:
            claimable_impressions = 0
            for gig in [g for g in post.gigs if g.is_claimable]:
                if not gig.is_missing_insights and gig.insight.impressions > 0:
                    claimable_impressions += gig.insight.impressions
                else:
                    claimable_impressions += gig.offer.influencer.estimated_impressions

            if claimable_impressions < self.campaign.units:
                return False
        return True

    def get_progress(self):
        reserved_impressions, submitted_impressions = (
            db.session.query(
                _sum_estimated_impressions(Offer.is_reserved),
                _sum_estimated_impressions(Offer.is_submitted),
            ).filter(Offer.campaign_id == self.campaign.id, Offer.is_reserved)
        ).first()

        return {
            "total": self.campaign.units,
            "reserved": reserved_impressions,
            "submitted": submitted_impressions,
        }

    @property
    def unit_mille(self):
        return self.campaign.units / MEDIAN_IMPRESSIONS_RATIO / MILLE

    def get_offer_units(self, offer):
        return offer.influencer.estimated_impressions

    def get_remaining_reach(self):
        reserved_offers = Offer.query.filter(
            Offer.campaign_id == self.campaign.id, Offer.is_reserved
        )

        reserved_units = sum([offer.influencer.estimated_impressions for offer in reserved_offers])
        remaining_units = max(0, self.campaign.units - reserved_units) / MEDIAN_IMPRESSIONS_RATIO

        return remaining_units
