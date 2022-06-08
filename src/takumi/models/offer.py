import datetime as dt
from functools import cmp_to_key
from typing import TYPE_CHECKING, Optional, Type

from sqlalchemy import DDL, Index, UniqueConstraint, and_, case, event, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased, backref, column_property, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SoftEnum, UUIDString
from core.common.utils import States

from takumi.extensions import db
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.gig import Gig
from takumi.models.instagram_post import InstagramPost
from takumi.models.payment import Payment
from takumi.models.post import Post
from takumi.utils import uuid4_str

from .helpers import hybrid_property_expression

if TYPE_CHECKING:
    from takumi.models import Campaign, Comment, Influencer, User  # noqa

# Gate the actual engagements for 2 hours after posting, since they will start at 0
ENGAGEMENTS_GATE_HOURS = 2


class STATES(States):
    ACCEPTED = "accepted"
    INVITED = "invited"
    PENDING = "pending"
    REJECTED = "rejected"
    REQUESTED = "requested"
    REVOKED = "revoked"
    CANDIDATE = "candidate"
    APPROVED_BY_BRAND = "approved_by_brand"
    REJECTED_BY_BRAND = "rejected_by_brand"


STATES_MAP = {
    STATES.ACCEPTED: "Accepted",
    STATES.INVITED: "Invited to campaign",
    STATES.PENDING: "Invited to campaign",
    STATES.REJECTED: "Rejected by influencer",
    STATES.REQUESTED: "Participation requested",
    STATES.REVOKED: "Revoked by Takumi",
    STATES.CANDIDATE: "Brand match candidate",
    STATES.APPROVED_BY_BRAND: "Approved by brand",
    STATES.REJECTED_BY_BRAND: "Rejected by brand",
}


class Offer(db.Model):
    __tablename__ = "offer"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    accepted = db.Column(UtcDateTime, index=True)
    payable = db.Column(UtcDateTime)
    submission_deadline = db.Column(UtcDateTime)

    state = db.Column(SoftEnum(*STATES.values()), server_default=STATES.INVITED, nullable=False)

    in_transit = db.Column(db.Boolean, nullable=False, server_default="f")
    tracking_code = db.Column(db.String)

    reward = db.Column(db.Integer, nullable=True, server_default=text("0"))
    followers_per_post = db.Column(db.Integer)
    engagements_per_post = db.Column(db.Integer)
    estimated_engagements_per_post = db.Column(db.Integer)

    scheduled_jobs = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="cascade"), nullable=False
    )
    influencer = relationship("Influencer", backref=backref("offers", order_by="Offer.created"))

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="cascade"), nullable=False
    )
    campaign = relationship("Campaign", backref=backref("offers", order_by="Offer.created"))

    is_claimable = db.Column(db.Boolean, server_default="f")
    is_selected = db.Column(db.Boolean, server_default="f")
    answers = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")

    is_reserved = column_property(state == STATES.ACCEPTED)

    comments = relationship(
        "Comment",
        primaryjoin="and_(Offer.id == foreign(Comment.owner_id), Comment.owner_type == 'offer')",
        order_by="Comment.created",
        backref="offer",
    )
    vat_percentage = db.Column(db.Float, default=0)

    @property
    def facebook_link_missing(self):
        return self.campaign.requires_facebook and not self.influencer.has_facebook_page

    @hybrid_property_expression  # type: ignore
    def is_influencers_first_accepted_offer(cls):
        AliasedOffer = aliased(Offer)
        return db.session.query(
            and_(cls.state == "accepted", func.count(AliasedOffer.id) == 0)
        ).filter(
            cls.id != AliasedOffer.id,
            AliasedOffer.state == "accepted",
            AliasedOffer.influencer_id == cls.influencer_id,
            AliasedOffer.created <= Offer.created,
        )

    @hybrid_property
    def submitted_gig_count(self):
        return len([gig for gig in self.gigs if gig.state != GIG_STATES.REQUIRES_RESUBMIT])

    @submitted_gig_count.expression  # type: ignore
    def submitted_gig_count(cls):
        return (
            select([func.count(Gig.id)])
            .where(and_(Gig.offer_id == cls.id, Gig.state != GIG_STATES.REQUIRES_RESUBMIT))
            .label("submitted_gig_count")
        )

    @hybrid_property
    def engagements_progress(self):
        minimum_time_passed = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            hours=ENGAGEMENTS_GATE_HOURS
        )
        if self.live_gig_count > 0 and minimum_time_passed > self.live_since:
            return self.engagements_per_post
        else:
            return self.estimated_engagements_per_post

    @engagements_progress.expression  # type: ignore
    def engagements_progress(cls):
        minimum_time_passed = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            hours=ENGAGEMENTS_GATE_HOURS
        )
        return case(
            [
                (
                    and_(cls.live_gig_count > 0, minimum_time_passed > cls.live_since),
                    cls.engagements_per_post,
                )
            ],
            else_=cls.estimated_engagements_per_post,
        )

    @hybrid_property
    def followers_influencer(self):
        """:obj:`int`: The number of subscribers of Creator related to this offer."""
        return self.influencer.followers if self.influencer.followers else 0

    @followers_influencer.expression  # type: ignore
    def followers_influencer(cls):
        from takumi.models.influencer import Influencer  # noqa

        return (
            select([Influencer.followers])
            .where(Influencer.id == cls.influencer_id)
            .correlate(cls)
            .label("followers_influencer")
        )

    @hybrid_property
    def engagement_rate_static(self):
        """:obj:`float | int`: Engagement rate in-feed calculated by the formula:
        the sum of engagements in-feed of all gigs of a particular offer
        divided by the number of the Creator's subscribers and multiplied by one hundred.
        """
        try:
            return (
                sum([gig.engagements_static for gig in self.gigs]) / self.followers_influencer * 100
            )
        except ZeroDivisionError:
            return 0

    @engagement_rate_static.expression  # type: ignore
    def engagement_rate_static(cls):
        from takumi.models.gig import Gig  # noqa

        return (
            select([func.sum(Gig.engagements_static) / cls.followers_influencer * 100])
            .where(Gig.offer_id == cls.id)
            .label("engagement_rate_static")
        )

    @property
    def engagement_rate_story(self):
        """:obj:`float | int`: Engagement rate in-feed calculated by the formula:
        the sum of story engagements of all gigs of a particular offer
        divided by the number of the Creator's subscribers and multiplied by one hundred.
        """
        try:
            return (
                sum([gig.engagements_story for gig in self.gigs]) / self.followers_influencer * 100
            )
        except ZeroDivisionError:
            return 0

    @property
    def reach(self):
        """:obj:`float | int`: If the Creator has published multiple posts in this campaign,
        the average post reach is calculated (from both Instagram posts and Instagram stories).
        Otherwise, reach from this post.
        """
        return (
            sum(
                [
                    getattr(gig, "reach_story", 0) or getattr(gig, "reach_static", 0)
                    for gig in self.gigs
                ]
            )
            / len(self.gigs)
            if self.gigs
            else 0
        )

    @property
    def total_impressions(self):
        return (
            sum(
                [
                    getattr(gig, "impressions_story", 0) or getattr(gig, "impressions_static", 0)
                    for gig in self.gigs
                ]
            )
            / len(self.gigs)
            if self.gigs
            else 0
        )

    @property
    def impressions(self):
        """The average impressions for all gigs in an offer

        Uses the estimated impressions if a gig doesn't have impressions stats
        """
        from takumi.models.insight import STATES as INSIGHT_STATES

        if not len(self.gigs):
            return self.influencer.estimated_impressions

        total_impressions = 0
        for gig in self.gigs:
            if (
                not gig.is_missing_insights
                and gig.insight
                and gig.insight.state == INSIGHT_STATES.APPROVED
                and gig.insight.impressions > 0
            ):
                total_impressions += gig.insight.impressions
            else:
                total_impressions += self.influencer.estimated_impressions

        return total_impressions / len(self.gigs)

    @property
    def reward_breakdown(self):
        vat_percentage = self.vat_percentage or 0
        net_value = self.reward / (1.0 + vat_percentage)
        vat_value = self.reward - net_value
        return {
            "net_value": net_value,
            "vat_value": vat_value,
            "total_value": self.reward,
        }

    @hybrid_property
    def live_since(self):
        return min([gig.instagram_post.posted for gig in self.gigs if gig.is_live])

    @live_since.expression  # type: ignore
    def live_since(cls):
        return (
            select([func.min(InstagramPost.posted)])
            .where(and_(InstagramPost.gig_id == Gig.id, Gig.offer_id == cls.id))
            .label("live_since")
        )

    @hybrid_property
    def live_gig_count(self):
        return len([gig for gig in self.gigs if gig.is_live])

    @live_gig_count.expression  # type: ignore
    def live_gig_count(cls):
        return (
            select([func.count(Gig.id)])
            .where(and_(Gig.offer_id == cls.id, Gig.is_live))
            .label("live_gig_count")
        )

    def has_all_gigs(self):
        valid_gig_count = len([gig for gig in self.gigs if gig.is_valid])
        return valid_gig_count == self.campaign.post_count

    def has_all_gigs_claimable(self):
        claimable_gig_count = len([gig for gig in self.gigs if gig.is_claimable])
        return claimable_gig_count == self.campaign.post_count

    def get_claimable_time(self) -> Optional[dt.datetime]:
        """Get's the claimable time based on latest gig claimable date"""
        max_claim = None
        gig: Gig
        for gig in self.gigs:
            claimable_time = gig.claimable_time
            if not claimable_time:
                return None

            if not max_claim or max_claim < claimable_time:
                max_claim = claimable_time

        return max_claim

    def calculate_engagements_per_post(self):
        total_engagements = 0
        wanted = self.campaign.post_count
        for gig in self.gigs:
            if gig.is_live:
                total_engagements += gig.engagements
                wanted -= 1
        total_engagements += self.influencer.estimated_engagements_per_post * wanted
        return total_engagements / self.campaign.post_count

    @hybrid_property
    def is_submitted(self):
        return self.is_reserved and self.live_gig_count >= self.campaign.post_count

    @is_submitted.expression  # type: ignore
    def is_submitted(cls):
        # XXX: Not able to use Campaign.post_count here for some reason
        post_count = select([func.count(Post.id)]).where(
            and_(Post.campaign_id == cls.campaign_id, Post.archived != True)  # noqa: E711
        )

        return and_(
            cls.is_reserved, case([((cls.live_gig_count >= post_count), True)], else_=False)
        )

    @hybrid_property
    def is_paid(self):
        """is_paid also returns true if the payment is pending"""
        if self.payment:
            return not self.payment.is_failed
        return False

    @is_paid.expression  # type: ignore
    def is_paid(cls):
        """is_paid also returns true if the payment is pending"""
        return (
            select([func.count(Payment.id) > 0])
            .where(and_(Payment.offer_id == cls.id, ~Payment.is_failed))
            .label("is_paid")
        )

    __table_args__ = (
        UniqueConstraint("influencer_id", "campaign_id"),
        Index("ix_offer_campaign_id", "campaign_id"),
    )

    def __repr__(self):
        return f"<Offer: {self.id} ({self.state})>"

    def iter_post_gigs(self):
        """Yield `(post, gig)` tuples for the offer. Gig is `None` when there is
        not gig or the gig was rejected.
        """

        gigs = Gig.query.join(Offer).filter(
            Offer.influencer == self.influencer,
            Offer.id == self.id,
            ~Gig.state.in_((GIG_STATES.REJECTED, GIG_STATES.REQUIRES_RESUBMIT)),
        )

        def _first_gig(post):
            for gig in gigs:
                if gig.post == post:
                    return gig

        posts = Post.query.filter(Post.campaign == self.campaign, ~Post.archived)
        for post in posts.order_by(Post.deadline):
            yield post, _first_gig(post)

    @property
    def address_missing(self):
        if not self.campaign.shipping_required:
            return False

        address = self.influencer.address
        if not address:
            return True

        if address.age_in_seconds > self.age_in_seconds:
            # address must have been confirmed after gig was created
            return True

        return False

    @property
    def age_in_seconds(self):
        return int((dt.datetime.now(dt.timezone.utc) - self.created).total_seconds())

    def can_reject(self):
        if self.state in (STATES.INVITED, STATES.REQUESTED, STATES.PENDING):
            return True
        if self.state == STATES.ACCEPTED:
            if self.gigs:
                return False
            if self.in_transit:
                return False
            if self.campaign.apply_first:
                return False
            if self.accepted > dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1):
                return True
        return False

    @hybrid_property
    def claimed(self) -> Optional[dt.datetime]:
        if self.payment and not self.payment.is_failed:
            return self.payment.created

    @claimed.expression  # type: ignore
    def claimed(cls):
        return (
            select([Payment.created], limit=1)
            .where(and_(Payment.offer_id == cls.id, ~Payment.successful.is_(False)))
            .order_by(Payment.created.desc())
            .label("claimed")
        )

    @property
    def cancel_reason(self):
        cancel_event = self.get_event("delete")

        if cancel_event:
            return cancel_event["reason"]
        return None

    @property
    def payment(self):
        def failed_processing_paid(payment, other_payment):
            if other_payment.successful == payment.successful:
                return 0
            if other_payment.is_successful and not payment.successful:
                return -1
            if payment.is_failed and other_payment.is_pending:
                return -1
            return 1

        try:
            return sorted(self.payments, key=cmp_to_key(failed_processing_paid)).pop()
        except IndexError:
            return None

    def get_event(self, type):
        return (
            OfferEvent.query.filter(OfferEvent.type == type, OfferEvent.offer == self)
            .order_by(OfferEvent.created.desc())
            .first()
        )

    @property
    def tax_info_missing(self):
        """Check if a given offer will require the influencer to submit tax information.

        This is only required for 1099 tax filings in the US, and only for influencers
        receiving $600 or more in payments from Takumi within a particular tax year.
        """
        if self.campaign.market.currency != "USD":
            return False
        if self.influencer.has_w9_info():
            return False

        # XXX: Temporary
        remaining = self.influencer.remaining_usd_before_1099 - self.reward
        return remaining <= 0

    @hybrid_property_expression  # type: ignore
    def request_participation_ts(cls):
        return (
            select([OfferEvent.created], limit=1)
            .where(and_(OfferEvent.offer_id == cls.id, OfferEvent.type == "request_participation"))
            .order_by(OfferEvent.created.desc())
            .label("request_participation_ts")
        )


# fmt: off
offer_triggers = DDL("""
CREATE TRIGGER cascade_offer_delete_comment
AFTER DELETE ON offer
FOR EACH ROW EXECUTE PROCEDURE delete_related_comment('offer');

CREATE TRIGGER cascade_offer_update_comment
AFTER UPDATE ON offer
FOR EACH ROW EXECUTE PROCEDURE update_related_comment('offer');
""")
# fmt: on
event.listen(Offer.__table__, "after_create", offer_triggers.execute_if(dialect="postgresql"))  # type: ignore


class OfferEvent(db.Model):
    __tablename__ = "offer_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"), index=True)
    creator_user = relationship("User", lazy="joined")

    offer_id = db.Column(
        UUIDString, db.ForeignKey("offer.id", ondelete="restrict"), index=True, nullable=False
    )
    offer = relationship(
        "Offer",
        backref=backref("events", uselist=True, order_by="OfferEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (Index("ix_offer_event_offer_type_created", "offer_id", "type", "created"),)

    def __repr__(self):
        return "<OfferEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "OfferEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
