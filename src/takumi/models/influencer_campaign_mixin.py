import datetime as dt

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased

from takumi.extensions import db

from .helpers import hybrid_method_subquery


class InfluencerCampaignMixin:
    @hybrid_method_subquery
    def campaign_count_for_advertiser(cls, advertiser):
        from takumi.models import Campaign, Offer

        return (
            db.session.query(func.count(func.distinct(Campaign.id)))
            .join(Offer)
            .filter(Offer.influencer_id == cls.id)
            .filter(or_(Offer.claimed != None, Offer.state == "accepted"))
            .filter(Campaign.advertiser_id == advertiser.id)
        )

    @hybrid_method_subquery
    def notification_count(cls, campaign):
        from takumi.models import Device, Notification, User

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(Notification.id))
            .join(Device)
            .join(User)
            .join(AliasedInfluencer)
            .filter(AliasedInfluencer.id == cls.id)
            .filter(Notification.campaign_id == campaign.id)
        )

    @hybrid_method_subquery
    def last_notification_sent(cls, campaign):
        from takumi.models import Device, Notification, User

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(Notification.sent)
            .join(Device)
            .join(User)
            .join(AliasedInfluencer)
            .filter(AliasedInfluencer.id == cls.id)
            .filter(Notification.campaign_id == campaign.id)
            .order_by(Notification.sent.desc())
            .limit(1)
        )

    @property
    def campaigns_with_offer(self):
        """Alternative to campaigns below for campaigns with existing offers

        Checking targeted public campaigns is slow, so it should only be used when needed
        """
        from takumi.models import Advertiser, Campaign, Offer, Targeting
        from takumi.models.campaign import STATES as CAMPAIGN_STATES

        Influencer = self.__class__
        return (
            db.session.query(Campaign, Influencer, Offer)
            .join(Targeting)
            .join(Advertiser)
            .outerjoin(
                Offer, and_(Offer.campaign_id == Campaign.id, Offer.influencer_id == self.id)
            )
            .filter(Influencer.id == self.id)
            .filter(~Campaign.state.in_((CAMPAIGN_STATES.STASHED, CAMPAIGN_STATES.DRAFT)))
            .filter(Offer.id != None)
            .order_by(Offer.created.desc(), Offer.id, Campaign.created.desc())
        )

    @property
    def campaigns(self):
        from takumi.models import Advertiser, Campaign, Offer, Targeting
        from takumi.models.campaign import STATES as CAMPAIGN_STATES
        from takumi.models.influencer import STATES as INFLUENCER_STATES

        Influencer = self.__class__
        return (
            db.session.query(Campaign, Influencer, Offer)
            .join(Targeting)
            .join(Advertiser)
            .outerjoin(
                Offer, and_(Offer.campaign_id == Campaign.id, Offer.influencer_id == self.id)
            )
            .filter(Influencer.id == self.id)
            .filter(~Campaign.state.in_((CAMPAIGN_STATES.STASHED, CAMPAIGN_STATES.DRAFT)))
            .filter(
                or_(
                    Offer.id != None,
                    and_(
                        Offer.id == None,
                        Influencer.state.in_(
                            [INFLUENCER_STATES.VERIFIED, INFLUENCER_STATES.REVIEWED]
                        ),
                        Campaign.public,
                        ~Advertiser.on_cooldown(self),
                        Influencer.is_eligible,
                        Targeting.targets_influencer(self),
                    ),
                )
            )
            .order_by(Offer.created.desc(), Offer.id, Campaign.created.desc())
        )

    @property
    def targeted_campaigns(self):
        from takumi.models import Campaign, Offer, Post
        from takumi.models.offer import STATES as OFFER_STATES

        return (
            self.campaigns.filter(Campaign.is_active)
            .filter(~Campaign.posts.any(Post.deadline < dt.datetime.now(dt.timezone.utc)))
            .filter(
                ~Campaign.posts.any(Post.submission_deadline < dt.datetime.now(dt.timezone.utc))
            )
            .filter(
                or_(Offer.id == None, Offer.state.in_((OFFER_STATES.INVITED, OFFER_STATES.PENDING)))
            )
        )

    @property
    def active_campaigns(self):
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        return self.campaigns_with_offer.filter(Offer.state == OFFER_STATES.ACCEPTED).filter(
            Offer.claimed == None
        )

    @property
    def requested_campaigns(self):
        from takumi.models import Campaign, Offer, Post
        from takumi.models.campaign import STATES as CAMPAIGN_STATES
        from takumi.models.offer import STATES as OFFER_STATES

        return (
            self.campaigns_with_offer.filter(Campaign.state == CAMPAIGN_STATES.LAUNCHED)
            .filter(~Campaign.posts.any(Post.deadline < dt.datetime.now(dt.timezone.utc)))
            .filter(
                Offer.state.in_(
                    (OFFER_STATES.REQUESTED, OFFER_STATES.APPROVED_BY_BRAND, OFFER_STATES.CANDIDATE)
                )
            )
        )

    @property
    def campaign_history(self):
        from takumi.models import Offer

        return self.campaigns_with_offer.filter(Offer.claimed != None)

    @property
    def revoked_or_rejected_campaigns(self):
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        return self.campaigns_with_offer.filter(
            Offer.state.in_(
                (OFFER_STATES.REVOKED, OFFER_STATES.REJECTED, OFFER_STATES.REJECTED_BY_BRAND)
            )
        )

    @property
    def expired_campaigns(self):
        from takumi.models import Campaign, Offer, Post
        from takumi.models.campaign import STATES as CAMPAIGN_STATES
        from takumi.models.offer import STATES as OFFER_STATES

        return self.campaigns.filter(
            or_(
                Campaign.state == CAMPAIGN_STATES.COMPLETED,
                Campaign.posts.any(Post.deadline < dt.datetime.now(dt.timezone.utc)),
            )
        ).filter(
            or_(
                Offer.id == None,
                Offer.state.in_(
                    (OFFER_STATES.INVITED, OFFER_STATES.PENDING, OFFER_STATES.REQUESTED)
                ),
            )
        )
