from typing import TYPE_CHECKING

from sqlalchemy import func, text
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Gig, Media  # noqa


class TiktokPost(db.Model):
    __tablename__ = "tiktok_post"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=True)
    modified = db.Column(UtcDateTime, onupdate=func.now())

    caption = db.Column(db.String)

    tiktok_post_id = db.Column(db.String)
    link = db.Column(db.String, nullable=False)
    deleted = db.Column(db.Boolean, server_default="f", nullable=False)

    likes = db.Column(db.Integer, server_default=text("0"))
    comments = db.Column(db.Integer, server_default=text("0"))
    shares = db.Column(db.Integer, server_default=text("0"))
    video_views = db.Column(db.Integer)
    posted = db.Column(UtcDateTime)

    followers = db.Column(db.Integer, server_default=text("0"))
    scraped = db.Column(UtcDateTime)
    sentiment = db.Column(db.Float)

    gig_id = db.Column(UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), unique=True)
    gig = relationship("Gig", back_populates="tiktok_post")

    media = relationship(
        "Media",
        primaryjoin="and_(TiktokPost.id == foreign(Media.owner_id), Media.owner_type == 'tiktok_post')",
        order_by="Media.order",
        backref="tiktok_post",
    )

    def __repr__(self):
        return f"<TiktokPost: {self.id} ({self.gig})>"
