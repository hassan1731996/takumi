import datetime as dt
from typing import TYPE_CHECKING, Optional, Type

from sqlalchemy import Index, UniqueConstraint, and_, case, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString
from core.common.utils import States

from takumi.constants import NEW_EXTENDED_CLAIM_HOURS_DATE, WAIT_BEFORE_CLAIM_HOURS
from takumi.extensions import db
from takumi.schedule.period import DateTimePeriod
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import (  # noqa
        Insight,
        InstagramPost,
        InstagramStory,
        Offer,
        Post,
        Submission,
        TiktokPost,
        User,
    )


class STATES(States):
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REPORTED = "reported"
    REJECTED = "rejected"
    REQUIRES_RESUBMIT = "requires_resubmit"


class Gig(db.Model):
    __tablename__ = "gig"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    scheduled_jobs = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    offer_id = db.Column(UUIDString, db.ForeignKey("offer.id", ondelete="restrict"), nullable=False)
    offer = relationship("Offer", backref=backref("gigs", order_by="Gig.created"))

    post_id = db.Column(UUIDString, db.ForeignKey("post.id", ondelete="restrict"), nullable=False)
    post = relationship("Post", backref=backref("gigs", order_by="Gig.created"))
    is_posted = db.Column(db.Boolean, server_default="f", nullable=False)
    is_verified = db.Column(db.Boolean, server_default="f")

    state = db.Column(
        SoftEnum(*STATES.values()), index=True, server_default=STATES.SUBMITTED, nullable=False
    )
    post_serialized = db.Column(JSONB, nullable=False, server_default="{}")

    submissions = relationship(
        "Submission", uselist=True, order_by="Submission.created.desc()", back_populates="gig"
    )
    instagram_story = relationship("InstagramStory", uselist=False, back_populates="gig")
    instagram_post = relationship("InstagramPost", uselist=False, back_populates="gig")
    instagram_reel = relationship("InstagramReel", uselist=False, back_populates="gig")
    tiktok_post = relationship("TiktokPost", uselist=False, back_populates="gig")

    insight = relationship("Insight", uselist=False, back_populates="gig")
    skip_insights = db.Column(db.Boolean, server_default="f", nullable=False)

    autoreport = db.Column(db.Boolean, default=True, nullable=True)

    # TODO: REMOVE

    report_reason = db.Column(db.String)
    reject_reason = db.Column(db.String)
    resubmit_reason = db.Column(db.String)
    resubmit_explanation = db.Column(db.String)

    reviewer_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    reviewer = relationship("User", primaryjoin="User.id == Gig.reviewer_id")
    review_date = db.Column(UtcDateTime)

    approver_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    approver = relationship("User", primaryjoin="User.id == Gig.approver_id")
    approve_date = db.Column(UtcDateTime)

    # REMOVE END

    __table_args__ = (
        Index("ix_gig_offer_id_created", "offer_id", "created"),
        Index("ix_gig_offer_id_post_id_state_created", "offer_id", "post_id", "state", "created"),
        Index("ix_gig_post_id_offer_id_state_created", "post_id", "offer_id", "state", "created"),
        UniqueConstraint("offer_id", "post_id", deferrable=True, initially="DEFERRED"),
    )

    def __repr__(self):
        return f"<Gig: {self.id}>"

    @classmethod
    def from_url(cls, url):
        """Get gig based on an admin url"""
        import re

        pattern = r".*/gigs?/(?P<gig_id>[0-9a-fA-F\-]{36}).*"

        if match := re.match(pattern, url):
            return cls.query.get(match.group("gig_id"))
        return None

    @property
    def submission(self):
        if self.submissions:
            return self.submissions[0]

    @hybrid_property
    def engagements(self):
        if self.instagram_post is None:
            return 0
        return self.instagram_post.engagements

    @engagements.expression  # type: ignore
    def engagements(cls):
        from takumi.models.instagram_post import InstagramPost  # noqa

        return (
            select([func.sum(InstagramPost.engagements)])
            .where(InstagramPost.gig_id == cls.id)
            .label("engagements")
        )

    @hybrid_property
    def reach(self):
        if self.instagram_post is None:
            return 0
        return self.instagram_post.followers

    @reach.expression  # type: ignore
    def reach(cls):
        from takumi.models.instagram_post import InstagramPost  # noqa

        return (
            select([func.sum(InstagramPost.followers)])
            .where(InstagramPost.gig_id == cls.id)
            .label("reach")
        )

    @hybrid_property
    def reach_static(self):
        return self.instagram_post.reach if self.instagram_post else 0

    @hybrid_property
    def reach_story(self):
        return self.instagram_story.reach if self.instagram_story else 0

    @hybrid_property
    def impressions_static(self):
        """int: In-feed impressions taken from Instagram post."""
        return self.instagram_post.impressions if self.instagram_post else 0

    @impressions_static.expression  # type: ignore
    def impressions_static(cls):
        from takumi.models.instagram_post import InstagramPost  # noqa

        return (
            select([InstagramPost.impressions])
            .where(InstagramPost.gig_id == cls.id)
            .label("impressions_static")
        )

    @hybrid_property
    def impressions_story(self):
        """int: Story impressions taken from Instagram stories."""
        return self.instagram_story.impressions if self.instagram_story else 0

    @impressions_story.expression  # type: ignore
    def impressions_story(cls):
        from takumi.models.instagram_story import InstagramStory  # noqa

        return (
            select([InstagramStory.impressions])
            .where(InstagramStory.gig_id == cls.id)
            .label("impressions_story")
        )

    @hybrid_property
    def engagements_static(self):
        """int: In-feed engagements taken from Instagram post."""
        return self.instagram_post.engagements_insight if self.instagram_post else 0

    @engagements_static.expression  # type: ignore
    def engagements_static(cls):
        from takumi.models.instagram_post import InstagramPost  # noqa

        return (
            select([InstagramPost.engagements_insight])
            .where(InstagramPost.gig_id == cls.id)
            .label("engagements_static")
        )

    @hybrid_property
    def engagements_story(self):
        """int: Stories' engagements taken from Instagram story."""
        return self.instagram_story.engagements if self.instagram_story else 0

    @engagements_story.expression  # type: ignore
    def engagements_story(cls):
        from takumi.models.instagram_story import InstagramStory  # noqa

        return (
            select([InstagramStory.engagements])
            .where(InstagramStory.gig_id == cls.id)
            .label("engagements_story")
        )

    @property
    def report(self):
        if not self.report_reason:
            return dict(reason="", reported=False)
        else:
            return dict(reason=self.report_reason, reported=True)

    @property
    def reject(self):
        if not self.reject_reason:
            return dict(reason="", rejected=False)
        else:
            return dict(reason=self.reject_reason, rejected=True)

    @property
    def user(self):
        return self.offer.influencer.user

    @property
    def is_valid(self):
        """Valid gigs are gigs that could be claimable without necessarily being claimable at the moment.
        Valid gigs are all gigs that after their end of review period would be claimable.
        """
        return self.is_live or self.state == STATES.REJECTED

    @hybrid_property
    def is_live(self):
        return self.state == STATES.APPROVED and self.is_verified

    @is_live.expression  # type: ignore
    def is_live(cls):
        return and_(cls.state == STATES.APPROVED, cls.is_verified)  # noqa: E711

    @property
    def end_of_review_period(self) -> Optional[dt.datetime]:
        """End of gig review period

        Insights should be posted after this period when required
        """
        if self.state == STATES.REJECTED:
            return self.created

        if self.instagram_story:
            if self.is_verified:
                return DateTimePeriod(hours=24).after(self.instagram_story.posted)  # type: ignore
            return DateTimePeriod(hours=24).after(self.post.deadline)

        if self.instagram_post:
            return DateTimePeriod(hours=48).after(self.instagram_post.posted)

        # We're missing a story/post, but it's been marked as posted
        if self.is_verified:
            return self.created

        return None

    @property
    def claimable_time(self) -> Optional[dt.datetime]:
        """The time when the gig is claimable

        It will be none if the gig doesn't have live content
        """
        campaign = self.offer.campaign
        if campaign.started is None or campaign.started > NEW_EXTENDED_CLAIM_HOURS_DATE:
            period = DateTimePeriod(hours=WAIT_BEFORE_CLAIM_HOURS)
        else:
            period = DateTimePeriod(hours=30 * 24)

        if self.state == STATES.REJECTED:
            return period.after(self.created)

        if self.is_verified:
            if self.instagram_story and self.instagram_story.posted is not None:
                return period.after(self.instagram_story.posted)  # type: ignore
            elif self.instagram_post and self.instagram_post.posted:
                return period.after(self.instagram_post.posted)
            elif self.tiktok_post:
                return period.after(self.tiktok_post.posted)

        return None

    @hybrid_property
    def posted(self):
        """Return the earliest posted date if gig is live"""
        if not self.is_live:
            return None

        if self.instagram_post:
            return self.instagram_post.posted

        if self.instagram_story:
            return self.instagram_story.posted

        if self.tiktok_post:
            return self.tiktok_post.posted

    @posted.expression  # type: ignore
    def posted(cls):
        from takumi.models import Gig, InstagramPost, InstagramStory, TiktokPost  # noqa

        return case(
            [
                (~cls.is_live, None),
                (
                    cls.instagram_post != None,
                    select([InstagramPost.posted])
                    .where(InstagramPost.gig_id == cls.id)
                    .label("posted"),
                ),
                (
                    cls.instagram_story != None,
                    select([InstagramStory.posted])
                    .where(InstagramStory.gig_id == cls.id)
                    .label("posted"),
                ),
                (
                    cls.tiktok_post != None,
                    select([TiktokPost.posted]).where(TiktokPost.gig_id == cls.id).label("posted"),
                ),
            ],
            else_=None,
        )

    @property
    def can_post_to_instagram(self) -> bool:
        if not self.post.is_open:
            return False

        if not self.post.requires_review_before_posting:
            return self.state in (STATES.SUBMITTED, STATES.REVIEWED, STATES.APPROVED)

        if not self.post.campaign.brand_safety:
            return self.state in (STATES.REVIEWED, STATES.APPROVED)

        return self.state == STATES.APPROVED

    @property
    def is_passed_review_period(self) -> bool:
        if not self.is_verified:
            return False

        if self.end_of_review_period is None:
            return False

        return self.end_of_review_period < dt.datetime.now(dt.timezone.utc)

    @property
    def is_passed_claimable_time(self) -> bool:
        if not self.is_passed_review_period:
            return False

        if not self.is_verified:
            return False

        if self.claimable_time is None:
            return False

        return self.claimable_time < dt.datetime.now(dt.timezone.utc)

    @property
    def requires_insights(self) -> bool:
        if self.offer.campaign.require_insights:
            return not self.skip_insights

        return False

    @property
    def is_missing_insights(self) -> bool:
        from takumi.models.insight import STATES as INSIGHT_STATES

        if not self.requires_insights:
            return False

        if self.insight is None:
            return True

        return self.insight.state == INSIGHT_STATES.REQUIRES_RESUBMIT

    @property
    def has_valid_insights(self) -> bool:
        """Returns True if valid insights or if insights not required"""
        from takumi.models.insight import STATES as INSIGHT_STATES

        if self.requires_insights:
            if self.is_missing_insights:
                return False

            return self.insight.state == INSIGHT_STATES.APPROVED

        return True

    @property
    def is_claimable(self) -> bool:
        """A gig itself is not claimed, but all the gigs under an offer need to be
        claimable in order for the offer to become claimable.  That means the gig
        needs to be in the SUBMITTED state, and have passed the review period.
        """
        return self.state == STATES.REJECTED or (
            self.is_live and self.is_passed_claimable_time and self.has_valid_insights
        )

    @property
    def reporter(self):
        if self.state != STATES.REPORTED:
            return None
        latest_report = (
            GigEvent.query.filter(GigEvent.gig == self, GigEvent.type == "report").order_by(
                GigEvent.created.desc()
            )
        ).first()
        if not latest_report:
            return None
        return latest_report.creator_user


class GigEvent(db.Model):
    __tablename__ = "gig_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"), index=True)
    creator_user = relationship("User", lazy="joined")

    gig_id = db.Column(
        UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), index=True, nullable=False
    )
    gig = relationship(
        "Gig", backref=backref("events", uselist=True, order_by="GigEvent.created"), lazy="joined"
    )

    event = db.Column(JSONB)

    __table_args__ = (Index("ix_gig_event_gig_type_created", "gig_id", "type", "created"),)

    def __repr__(self):
        return "<GigEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "GigEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
