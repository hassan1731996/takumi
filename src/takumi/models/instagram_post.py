import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DDL, Float, Index, cast, event, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString
from core.facebook.instagram import InstagramMediaPostedBeforeBusinessAccountConversion

from takumi.extensions import db
from takumi.facebook_account import unlink_on_permission_error
from takumi.utils import uuid4_str

from .helpers import hybrid_property_subquery

if TYPE_CHECKING:
    from takumi.models import Gig, InstagramAccount, Media, User  # noqa


class InstagramPost(db.Model):
    __tablename__ = "instagram_post"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=True)
    modified = db.Column(UtcDateTime, onupdate=func.now())

    caption = db.Column(db.String)
    shortcode = db.Column(db.String)
    ig_post_id = db.Column(db.String)
    link = db.Column(db.String, nullable=False)
    deleted = db.Column(db.Boolean, server_default="f", nullable=False)
    sponsors = db.Column(MutableList.as_mutable(JSONB), server_default="[]")

    likes = db.Column(db.Integer, server_default=text("0"))
    comments = db.Column(db.Integer, server_default=text("0"))
    video_views = db.Column(db.Integer)
    posted = db.Column(UtcDateTime)

    followers = db.Column(db.Integer, server_default=text("0"))
    scraped = db.Column(UtcDateTime)
    sentiment = db.Column(db.Float)

    gig_id = db.Column(UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), unique=True)
    gig = relationship("Gig", back_populates="instagram_post")

    instagram_account_id = db.Column(
        UUIDString, db.ForeignKey("instagram_account.id", ondelete="restrict")
    )
    instagram_account = relationship(
        "InstagramAccount", backref=backref("instagram_posts", uselist=True)
    )

    media = relationship(
        "Media",
        primaryjoin="and_(InstagramPost.id == foreign(Media.owner_id), Media.owner_type == 'instagram_post')",
        order_by="Media.order",
        backref="instagram_post",
    )

    insights_unavailable = db.Column(db.Boolean)

    def __repr__(self):
        return f"<InstagramPost: {self.id} ({self.gig})>"

    @property
    def engagement(self):
        if not self.followers:
            return 0

        return float(self.engagements) / self.followers

    @hybrid_property
    def engagements(self):
        return self.likes + self.comments

    @engagements.expression  # type: ignore
    def engagements(self):
        return self.likes + self.comments

    @hybrid_property
    def reach(self):
        """int: In-feed reach taken from insights."""
        return (
            self.instagram_post_insights[0].reach
            if self.instagram_post_insights and self.instagram_post_insights[0].reach
            else 0
        )

    @hybrid_property
    def impressions(self):
        """int: In-feed impressions taken from insights."""
        return (
            self.instagram_post_insights[0].impressions
            if self.instagram_post_insights and self.instagram_post_insights[0].impressions
            else 0
        )

    @impressions.expression  # type: ignore
    def impressions(cls):
        from takumi.models.instagram_post_insight import InstagramPostInsight  # noqa

        return (
            select([InstagramPostInsight.impressions])
            .where(InstagramPostInsight.instagram_post_id == cls.id)
            .order_by(InstagramPostInsight.created.desc())
            .limit(1)
            .label("impressions")
        )

    @hybrid_property
    def engagements_insight(self):
        """int: In-feed engagements taken from insights."""
        return (
            self.instagram_post_insights[0].engagement
            if self.instagram_post_insights and self.instagram_post_insights[0].engagement
            else 0
        )

    @engagements_insight.expression  # type: ignore
    def engagements_insight(cls):
        from takumi.models.instagram_post_insight import InstagramPostInsight  # noqa

        return (
            select([cast(InstagramPostInsight.engagement, Float)])
            .where(InstagramPostInsight.instagram_post_id == cls.id)
            .order_by(InstagramPostInsight.created.desc())
            .limit(1)
            .label("engagements_insight")
        )

    @property
    def comment_sentiment(self):
        def _avg(values):
            return sum(values) / len(values) if len(values) else 0

        return _avg([comment.sentiment or 0 for comment in self.ig_comments])

    @property
    def is_stale(self):
        """Indicate if gig needs to be updated. Makes recently posted media more
        aggressively updated, moving from hourly first four days, to daily next
        26 days and then weekly thereafter.
        """

        if self.posted is None:
            return False
        if self.scraped is None:
            return True

        now = dt.datetime.now(dt.timezone.utc)
        hour = 60 * 60  # in seconds
        day = hour * 24  # in seconds
        if (now - self.posted).days < 4:
            if (now - self.scraped).total_seconds() > hour:
                return True
        elif (now - self.posted).days < 30:
            if (now - self.scraped).total_seconds() > day:
                return True
        else:
            if (now - self.scraped).total_seconds() > day * 7:
                return True
        return False

    def update_instagram_insights(self):
        from takumi.models import InstagramPostInsight

        if self.insights_unavailable:
            return

        influencer = self.gig.offer.influencer

        if not influencer.instagram_account:
            return

        facebook_page = influencer.instagram_account.facebook_page

        if not facebook_page or not facebook_page.active:
            return

        with unlink_on_permission_error(influencer.instagram_account.facebook_page):
            media_id = influencer.instagram_api.get_media_id_from_ig_media_id(self.ig_post_id)
            if media_id:
                try:
                    insight_data = influencer.instagram_api.get_media_insights(media_id)
                except InstagramMediaPostedBeforeBusinessAccountConversion:
                    self.insights_unavailable = True
                    db.session.commit()
                    return
                insight = InstagramPostInsight(instagram_post_id=self.id)

                insight.engagement = insight_data.get("engagement")
                insight.impressions = insight_data.get("impressions")
                insight.reach = insight_data.get("reach")
                insight.saved = insight_data.get("saved")

                insight.video_views = insight_data.get("video_views")

                insight.carousel_album_engagement = insight_data.get("carousel_album_engagement")
                insight.carousel_album_impressions = insight_data.get("carousel_album_impressions")
                insight.carousel_album_reach = insight_data.get("carousel_album_reach")
                insight.carousel_album_saved = insight_data.get("carousel_album_saved")

                db.session.add(insight)
                db.session.commit()

    @hybrid_property_subquery
    def instagram_post_insight_id(cls):
        from takumi.models import InstagramPostInsight

        AliasedInstagramPost = aliased(cls)

        return (
            db.session.query(InstagramPostInsight.id)
            .join(AliasedInstagramPost)
            .filter(AliasedInstagramPost.id == cls.id)
            .order_by(InstagramPostInsight.created.desc())
            .limit(1)
        )

    @property
    def instagram_post_insight(self):
        from takumi.models import InstagramPostInsight

        if not self.instagram_post_insight_id:
            return None

        return InstagramPostInsight.query.get(self.instagram_post_insight_id)


# fmt: off
instagram_post_triggers = DDL("""
CREATE TRIGGER cascade_instagram_post_delete_media
AFTER DELETE ON instagram_post
FOR EACH ROW EXECUTE PROCEDURE delete_related_media('instagram_post');

CREATE TRIGGER cascade_instagram_post_update_media
AFTER UPDATE ON instagram_post
FOR EACH ROW EXECUTE PROCEDURE update_related_media('instagram_post');
""")
# fmt: on
event.listen(
    InstagramPost.__table__,
    "after_create",
    instagram_post_triggers.execute_if(dialect="postgresql"),  # type: ignore
)


class InstagramPostEvent(db.Model):
    __tablename__ = "instagram_post_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    creator_user = relationship("User", lazy="joined")

    instagram_post_id = db.Column(
        UUIDString,
        db.ForeignKey("instagram_post.id", ondelete="restrict"),
        index=True,
        nullable=False,
    )
    instagram_post = relationship(
        "InstagramPost",
        backref=backref("events", uselist=True, order_by="InstagramPostEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_instagram_post_event_instagram_post_type_created",
            "instagram_post_id",
            "type",
            "created",
        ),
    )

    def __repr__(self):
        return "<InstagramPostEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "InstagramPostEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
