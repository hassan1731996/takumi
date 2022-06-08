from typing import TYPE_CHECKING, Type

from sqlalchemy import DDL, Index, and_, case, event, func, join, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import backref, column_property, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString, deprecated_column
from core.common.utils import States

from takumi.extensions import db
from takumi.models.gig import Gig
from takumi.models.offer import Offer
from takumi.models.post import Post, PostTypes
from takumi.utils import uuid4_str

from .helpers import hybrid_property_expression

if TYPE_CHECKING:
    from takumi.models import Media, User  # noqa


class TYPES(States):
    STORY_INSIGHT = "story_insight"
    POST_INSIGHT = "post_insight"


class STATES(States):
    SUBMITTED = "submitted"
    REQUIRES_RESUBMIT = "requires_resubmit"
    APPROVED = "approved"


class Insight(db.Model):
    __tablename__ = "insight"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    promoted = db.Column(db.Boolean)

    state = db.Column(
        SoftEnum(*STATES.values()), server_default=STATES.SUBMITTED, nullable=False, index=True
    )

    followers = db.Column(db.Integer)
    follows = db.Column(db.Integer)

    reach = db.Column(db.Integer)

    profile_visits = db.Column(db.Integer)
    website_clicks = db.Column(db.Integer)
    shares = db.Column(db.Integer)
    replies = db.Column(db.Integer)
    emails = db.Column(db.Integer)
    get_directions = db.Column(db.Integer)

    ocr_values = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    @hybrid_property_expression  # type: ignore
    def resubmit_reason(cls):
        return (
            select([InsightEvent.event["reason"]], limit=1)
            .where(and_(InsightEvent.insight_id == cls.id, InsightEvent.type == "request_resubmit"))
            .order_by(InsightEvent.created.desc())
            .label("resubmit_reason")
        )

    @hybrid_property
    def influencer_id(self):
        return self.gig.offer.influencer_id

    @influencer_id.expression  # type: ignore
    def influencer_id(cls):
        return (
            select([Offer.influencer_id])
            .select_from(join(Offer, Gig, Offer.id == Gig.offer_id))
            .where(Gig.id == cls.gig_id)
            .label("influencer_id")
        )

    media = relationship(
        "Media",
        primaryjoin="and_(Insight.id == foreign(Media.owner_id), Media.owner_type == 'insight')",
        backref="insight",
    )

    gig_id = db.Column(
        UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), nullable=False, unique=True
    )
    gig = relationship("Gig", back_populates="insight")

    type = column_property(
        select(
            [
                case(
                    [(Post.post_type == PostTypes.story, TYPES.STORY_INSIGHT)],
                    else_=TYPES.POST_INSIGHT,
                )
            ]
        )
        .select_from(join(Post, Gig, Post.id == Gig.post_id))  # type: ignore
        .where(Gig.id == gig_id)
        .label("type")
    )

    __mapper_args__ = {"polymorphic_identity": "insight", "polymorphic_on": type}

    @property
    def processed(self):
        """Legacy property for removed processed field"""
        return self.state == STATES.APPROVED


# fmt: off
insight_triggers = DDL("""
CREATE TRIGGER cascade_insight_delete_media
AFTER DELETE ON insight
FOR EACH ROW EXECUTE PROCEDURE delete_related_media('insight');

CREATE TRIGGER cascade_insight_update_media
AFTER UPDATE ON insight
FOR EACH ROW EXECUTE PROCEDURE update_related_media('insight');
""")
# fmt: on
event.listen(Insight.__table__, "after_create", insight_triggers.execute_if(dialect="postgresql"))  # type: ignore


class StoryInsight(Insight):
    views = db.Column(db.Integer)

    impressions = db.Column(db.Integer)

    link_clicks = db.Column(db.Integer)
    sticker_taps = db.Column(db.Integer)

    back_navigations = db.Column(db.Integer)
    forward_navigations = db.Column(db.Integer)
    next_story_navigations = db.Column(db.Integer)
    exited_navigations = db.Column(db.Integer)

    __mapper_args__ = {"polymorphic_identity": TYPES.STORY_INSIGHT}

    def __repr__(self):
        return f"<StoryInsight: ({self.id})>"

    @hybrid_property
    def interactions(self):
        return (
            (self.link_clicks or 0)
            + (self.shares or 0)
            + (self.replies or 0)
            + (self.profile_visits or 0)
            + (self.website_clicks or 0)
            + (self.sticker_taps or 0)
        )

    @interactions.expression  # type: ignore
    def interactions(cls):
        return (
            func.coalesce(cls.link_clicks, 0)
            + func.coalesce(cls.shares, 0)
            + func.coalesce(cls.replies, 0)
            + func.coalesce(cls.profile_visits, 0)
            + func.coalesce(cls.website_clicks, 0)
            + func.coalesce(cls.sticker_taps, 0)
        )

    @hybrid_property
    def navigations(self):
        return (
            (self.back_navigations or 0)
            + (self.forward_navigations or 0)
            + (self.next_story_navigations or 0)
            + (self.exited_navigations or 0)
        )

    @navigations.expression  # type: ignore
    def navigations(cls):
        return (
            func.coalesce(cls.back_navigations, 0)
            + func.coalesce(cls.forward_navigations, 0)
            + func.coalesce(cls.next_story_navigations, 0)
            + func.coalesce(cls.exited_navigations, 0)
        )


class PostInsight(Insight):
    likes = db.Column(db.Integer)
    comments = db.Column(db.Integer)
    bookmarks = db.Column(db.Integer)

    non_followers_reach = db.Column(db.Float)
    reach_not_following = deprecated_column(db.Float)

    calls = db.Column(db.Integer)

    from_hashtags_impressions = db.Column(db.Integer)
    from_home_impressions = db.Column(db.Integer)
    from_profile_impressions = db.Column(db.Integer)
    from_explore_impressions = db.Column(db.Integer)
    from_location_impressions = db.Column(db.Integer)
    from_other_impressions = db.Column(db.Integer)

    # Promoted fields
    promotion_clicks = db.Column(db.Integer)
    profile_visits_from_promotion = db.Column(db.Float)
    website_clicks_from_promotion = db.Column(db.Float)
    emails_from_promotion = db.Column(db.Float)
    impressions_from_promotion = db.Column(db.Float)
    total_impressions = db.Column(db.Integer)
    reach_from_promotion = db.Column(db.Float)

    __mapper_args__ = {"polymorphic_identity": TYPES.POST_INSIGHT}

    def __repr__(self):
        return f"<PostInsight: ({self.id})>"

    @hybrid_property
    def interactions(self):
        return (self.profile_visits or 0) + (self.website_clicks or 0) + (self.calls or 0)

    @interactions.expression  # type: ignore
    def interactions(cls):
        return (
            func.coalesce(cls.profile_visits, 0)
            + func.coalesce(cls.website_clicks, 0)
            + func.coalesce(cls.calls, 0)
        )

    @hybrid_property
    def impressions(self):
        if self.promoted:
            return self.total_impressions
        return (
            (self.from_hashtags_impressions or 0)
            + (self.from_home_impressions or 0)
            + (self.from_profile_impressions or 0)
            + (self.from_other_impressions or 0)
            + (self.from_explore_impressions or 0)
            + (self.from_location_impressions or 0)
        )

    @impressions.expression  # type: ignore
    def impressions(cls):
        return case(
            [(cls.promoted == True, cls.total_impressions)],
            else_=(
                func.coalesce(cls.from_hashtags_impressions, 0)
                + func.coalesce(cls.from_home_impressions, 0)
                + func.coalesce(cls.from_profile_impressions, 0)
                + func.coalesce(cls.from_other_impressions, 0)
                + func.coalesce(cls.from_explore_impressions, 0)
                + func.coalesce(cls.from_location_impressions, 0)
            ),
        )


class InsightEvent(db.Model):
    __tablename__ = "insight_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"), index=True)
    creator_user = relationship("User", lazy="joined")

    insight_id = db.Column(
        UUIDString, db.ForeignKey("insight.id", ondelete="restrict"), index=True, nullable=False
    )
    insight = relationship(
        "Insight",
        backref=backref("events", uselist=True, order_by="InsightEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index("ix_insight_event_insight_type_created", "insight_id", "type", "created"),
    )

    def __repr__(self):
        created = self.created.strftime("%Y-%m-%d %H:%M:%S")
        return f"<InsightEvent: {self.id} ({created} {self.type})>"
