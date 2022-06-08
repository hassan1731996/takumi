import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class Audit(db.Model):
    __tablename__ = "audit"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"), nullable=False, index=True
    )
    influencer = relationship(
        "Influencer",
        backref=backref("audits", uselist=True, order_by="desc(Audit.created)"),
        lazy="joined",
    )
    pdf = db.Column(db.String)

    # Quality
    audience_quality_score = db.Column(db.Float, nullable=False)

    # Engagement rates
    engagement_rate = db.Column(db.Float, nullable=False)
    ad_engagement_rate = db.Column(db.Float)

    # User
    average_likes = db.Column(db.Float, nullable=False)
    average_comments = db.Column(db.Float, nullable=False)
    average_posts_per_week = db.Column(db.Float)
    average_ad_posts_per_week = db.Column(db.Float)

    likes_spread = db.Column(db.Float, nullable=False)
    likes_comments_ratio = db.Column(db.Float, nullable=False)

    # Followers
    followers_languages = db.Column(JSONB, server_default="{}", nullable=False)
    followers_quality = db.Column(db.Float, nullable=False)
    followers_reach = db.Column(JSONB, server_default="{}", nullable=False)
    followers_reachability = db.Column(db.Float, nullable=True)
    followers_geography = db.Column(JSONB, server_default="{}", nullable=False)
    followers_demography = db.Column(JSONB, server_default="{}", nullable=False)

    # Likers
    likers_languages = db.Column(JSONB, server_default="{}", nullable=True)
    likers_quality = db.Column(db.Float, nullable=True)
    likers_reach = db.Column(JSONB, server_default="{}", nullable=True)

    # Charts
    followers_chart = db.Column(JSONB, server_default="[]")
    following_chart = db.Column(JSONB, server_default="[]")

    # Growth
    growth_title = db.Column(db.String)
    growth_description = db.Column(db.String)

    # Other
    audience_thematics = db.Column(JSONB, server_default="{}", nullable=False)
    followers_count = db.Column(db.Integer, nullable=False)
    followings_count = db.Column(db.Integer, nullable=False)

    @property
    def age(self):
        """Return the report age in days

        Useful for deciding if to get a new report or not
        """
        if self.modified:
            return (dt.datetime.now(dt.timezone.utc) - self.modified).days
        elif self.created:
            return (dt.datetime.now(dt.timezone.utc) - self.created).days
        return 0

    def __repr__(self):
        if self.created:
            date = self.created.replace(microsecond=0).isoformat()
        else:
            date = "Not created"

        return f"<Audit: ({self.influencer.username}: {date})>"
