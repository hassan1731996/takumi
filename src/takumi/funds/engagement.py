from sqlalchemy import case, func

from takumi.constants import (
    ENGAGEMENT_PER_ASSET,
    MAX_FOLLOWERS_BEYOND_REWARD_POOL,
    MILLE,
    PESSIMISTIC_ENGAGEMENT_RATE,
)
from takumi.extensions import db
from takumi.funds.reach import ReachFund
from takumi.models import Offer


def _sum_engagement(column):
    return func.coalesce(
        func.sum(case([((column == True), Offer.engagements_progress)], else_=0)), 0
    )


class EngagementFund(ReachFund):
    def _get_engagement(self, column):
        return (
            db.session.query(_sum_engagement(column)).filter(Offer.campaign_id == self.campaign.id)
        ).scalar()

    def _reserved_engagement(self):
        return self._get_engagement(Offer.is_reserved)

    def _submitted_engagement(self):
        return self._get_engagement(Offer.is_submitted)

    def _remaining_engagement(self):
        return max(0, self.campaign.units - self._reserved_engagement())

    def _remaining_reach(self):
        """Extrapolate a sensible approximation of how much more reach this campaign
        needs to fulfil the remaining engagement

        XXX: this should be removed when we decouple (pricing, rewards, progress)
        - this is overloading a private method on ReachFund and a comment is needed to explain why
        - a uniform interface for progress, and pricing, would allow "reach pricing" to clamp the
          reward based on a more abstract progress interface.
        """
        return self._remaining_engagement() / PESSIMISTIC_ENGAGEMENT_RATE

    @property
    def minimum_reservations(self):
        return self.campaign.units / ENGAGEMENT_PER_ASSET

    def minimum_reservations_met(self):
        return self.reserved_offer_count >= self.minimum_reservations

    def is_reservable(self):
        if not self.minimum_reservations_met():
            return True
        return self._remaining_engagement() != 0

    def can_reserve_units(self, units):
        """Check if it's possible to reserve an amount of units"""
        if not self.is_reservable():
            return False

        return self._remaining_engagement() + MAX_FOLLOWERS_BEYOND_REWARD_POOL - units >= 0

    def is_fulfilled(self):
        for post in self.campaign.posts:
            post_claimable_engagement = [
                (g.instagram_post.likes + g.instagram_post.comments)
                for g in post.gigs
                if g.is_claimable
            ]
            if not sum(post_claimable_engagement) >= self.campaign.units:
                return False
        return True

    def get_progress(self):
        reserved_engagement, submitted_engagement = (
            db.session.query(
                _sum_engagement(Offer.is_reserved), _sum_engagement(Offer.is_submitted)
            ).filter(Offer.campaign_id == self.campaign.id, Offer.is_reserved)
        ).first()

        return {
            "total": self.campaign.units,
            "reserved": reserved_engagement,
            "submitted": submitted_engagement,
        }

    @property
    def unit_mille(self):
        return self.campaign.units / PESSIMISTIC_ENGAGEMENT_RATE / MILLE

    def get_offer_units(self, offer):
        return offer.influencer.estimated_engagements_per_post

    def get_remaining_reach(self):
        reserved_offers = Offer.query.filter(
            Offer.campaign_id == self.campaign.id, Offer.is_reserved
        )

        reserved_units = sum([offer.engagements_progress for offer in reserved_offers])
        remaining_units = max(0, self.campaign.units - reserved_units) / PESSIMISTIC_ENGAGEMENT_RATE

        return remaining_units
