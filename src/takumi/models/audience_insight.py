import datetime as dt
from typing import TYPE_CHECKING, Type

from sqlalchemy import Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SoftEnum, UUIDString
from core.common.utils import States

from takumi.extensions import db
from takumi.utils import uuid4_str

from .helpers import hybrid_property_subquery

if TYPE_CHECKING:
    from takumi.models import Influencer, Media, User  # noqa


class STATES(States):
    SUBMITTED = "submitted"
    PROCESSED = "processed"
    INVALID = "invalid"
    APPROVED = "approved"


class AudienceSection(db.Model):
    __tablename__ = "audience_section"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    media_path = db.Column(db.String, nullable=False)
    media_width = db.Column(db.Integer)
    media_height = db.Column(db.Integer)
    media_order = db.Column(db.Integer)

    followers = db.Column(db.Integer)

    values = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    errors = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    ocr_values = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    boundary = db.Column(MutableList.as_mutable(JSONB), nullable=True, default=[])


class AudienceInsight(db.Model):
    __tablename__ = "audience_insight"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    state = db.Column(
        SoftEnum(*STATES.values()), index=True, server_default=STATES.SUBMITTED, nullable=False
    )

    # Deprecate
    media = relationship(
        "Media",
        primaryjoin="and_(AudienceInsight.id == foreign(Media.owner_id), Media.owner_type == 'audience_insight')",
        backref="audience_insight",
        uselist=True,
    )

    # Joined sections for OCR
    ocr_media_path = db.Column(db.String, nullable=True)

    # Audience sections
    top_locations_id = db.Column(
        UUIDString, db.ForeignKey("audience_section.id", ondelete="restrict"), nullable=True
    )
    top_locations = relationship(
        "AudienceSection",
        primaryjoin="AudienceSection.id == AudienceInsight.top_locations_id",
        uselist=False,
    )

    ages_men_id = db.Column(
        UUIDString, db.ForeignKey("audience_section.id", ondelete="restrict"), nullable=True
    )
    ages_men = relationship(
        "AudienceSection",
        primaryjoin="AudienceSection.id == AudienceInsight.ages_men_id",
        uselist=False,
    )

    ages_women_id = db.Column(
        UUIDString, db.ForeignKey("audience_section.id", ondelete="restrict"), nullable=True
    )
    ages_women = relationship(
        "AudienceSection",
        primaryjoin="AudienceSection.id == AudienceInsight.ages_women_id",
        uselist=False,
    )

    gender_id = db.Column(
        UUIDString, db.ForeignKey("audience_section.id", ondelete="restrict"), nullable=True
    )
    gender = relationship(
        "AudienceSection",
        primaryjoin="AudienceSection.id == AudienceInsight.gender_id",
        uselist=False,
    )

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"), nullable=False
    )
    influencer = relationship(
        "Influencer",
        backref=backref("audience_insights", uselist=True),
        order_by="AudienceInsight.created",
    )

    @property
    def sections(self):
        return [self.top_locations, self.ages_men, self.ages_women, self.gender]

    @hybrid_property_subquery
    def expired(cls):
        AliasedAudienceInsight = aliased(cls)
        threemonthsago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3 * 30)

        return db.session.query(AliasedAudienceInsight.created < threemonthsago).filter(
            AliasedAudienceInsight.id == cls.id
        )


class AudienceInsightEvent(db.Model):
    __tablename__ = "audience_insight_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"), index=True)
    creator_user = relationship("User", lazy="joined")

    audience_insight_id = db.Column(
        UUIDString,
        db.ForeignKey("audience_insight.id", ondelete="restrict"),
        index=True,
        nullable=False,
    )
    audience_insight = relationship(
        "AudienceInsight",
        backref=backref("events", uselist=True, order_by="AudienceInsightEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_audience_insight_event_insight_type_created",
            "audience_insight_id",
            "type",
            "created",
        ),
    )

    def __repr__(self):
        created = self.created.strftime("%Y-%m-%d %H:%M:%S")
        return f"<AudienceInsightEvent: {self.id} ({created} {self.type})>"
