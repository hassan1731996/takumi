from sqlalchemy import func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class InstagramPostInsight(db.Model):
    __tablename__ = "instagram_post_insight"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    # Post
    engagement = db.Column(db.Integer)
    impressions = db.Column(db.Integer)
    reach = db.Column(db.Integer)
    saved = db.Column(db.Integer)

    # Video
    video_views = db.Column(db.Integer)

    # Album
    carousel_album_engagement = db.Column(db.Integer)
    carousel_album_impressions = db.Column(db.Integer)
    carousel_album_reach = db.Column(db.Integer)
    carousel_album_saved = db.Column(db.Integer)

    instagram_post_id = db.Column(
        UUIDString,
        db.ForeignKey("instagram_post.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    instagram_post = relationship(
        "InstagramPost",
        backref=backref(
            "instagram_post_insights",
            order_by="desc(InstagramPostInsight.created)",
        ),
    )
