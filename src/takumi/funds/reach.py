import math

from sqlalchemy import case, func

from takumi.constants import (
    MAX_FOLLOWERS_BEYOND_REWARD_POOL,
    MILLE,
    MIN_INSTAGRAM_FOLLOWERS_REACH,
    REACH_PER_ASSET,
)
from takumi.extensions import db
from takumi.models import Offer
from takumi.models.post import PostTypes

from .fund import Fund


def _sum_reach(column):
    return func.coalesce(func.sum(case([((column == True), Offer.followers_per_post)], else_=0)), 0)


class ReachFund(Fund):
    @property
    def _reach(self):
        return self.campaign.units

    def _get_reach(self, column):
        return (
            db.session.query(_sum_reach(column))
            .filter(Offer.campaign_id == self.campaign.id)
            .scalar()
        )

    def _reserved_reach(self):
        return self._get_reach(Offer.is_reserved)

    def _submitted_reach(self):
        return self._get_reach(Offer.is_submitted)

    def _remaining_reach(self):
        return max(0, self._reach - self._reserved_reach())

    @property
    def minimum_reservations(self):
        return math.ceil(self._reach / REACH_PER_ASSET)

    def minimum_reservations_met(self):
        return self.reserved_offer_count >= self.minimum_reservations

    def is_reservable(self):
        if not self.minimum_reservations_met():
            return True
        return self._remaining_reach() != 0

    def can_reserve_units(self, units):
        """Check if it's possible to reserve an amount of units"""
        if not self.is_reservable():
            return False

        return self._remaining_reach() + MAX_FOLLOWERS_BEYOND_REWARD_POOL - units >= 0

    def is_fulfilled(self):
        """Check if the claimable reach per post is above the campaign units"""
        for post in self.campaign.posts:
            if post.post_type == PostTypes.story:
                claimable_reach = sum(
                    gig.instagram_story
                    and gig.instagram_story.followers
                    or gig.offer.followers_per_post
                    for gig in post.gigs
                    if gig.is_claimable
                )
            else:
                claimable_reach = sum(
                    gig.instagram_post
                    and gig.instagram_post.followers
                    or gig.offer.followers_per_post
                    for gig in post.gigs
                    if gig.is_claimable
                )

            if claimable_reach < self.campaign.units:
                return False
        return True

    @property
    def min_followers(self):
        return MIN_INSTAGRAM_FOLLOWERS_REACH

    def get_progress(self):
        reserved_reach, submitted_reach = (
            db.session.query(_sum_reach(Offer.is_reserved), _sum_reach(Offer.is_submitted)).filter(
                Offer.campaign_id == self.campaign.id, Offer.is_reserved
            )
        ).first()

        return {"total": self._reach, "reserved": reserved_reach, "submitted": submitted_reach}

    @property
    def unit_mille(self):
        return self.campaign.units / MILLE

    def get_offer_units(self, offer):
        return offer.followers_per_post

    def get_remaining_reach(self):
        reserved_offers = Offer.query.filter(
            Offer.campaign_id == self.campaign.id, Offer.is_reserved
        )

        reserved_units = sum([offer.followers_per_post for offer in reserved_offers])
        remaining_units = max(0, self.campaign.units - reserved_units)

        return remaining_units
