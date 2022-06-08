from sqlalchemy import func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class InstagramStoryFrameInsight(db.Model):
    __tablename__ = "instagram_story_frame_insight"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    # Story
    exits = db.Column(db.Integer)
    impressions = db.Column(db.Integer)
    reach = db.Column(db.Integer)
    replies = db.Column(db.Integer)
    taps_forward = db.Column(db.Integer)
    taps_back = db.Column(db.Integer)

    story_frame_id = db.Column(
        UUIDString,
        db.ForeignKey("story_frame.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    story_frame = relationship(
        "StoryFrame",
        backref=backref(
            "instagram_story_frame_insights",
            order_by="desc(InstagramStoryFrameInsight.created)",
        ),
    )
