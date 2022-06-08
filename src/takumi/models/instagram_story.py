import datetime as dt
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Index, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Gig, InstagramAccount, User  # noqa


class InstagramStory(db.Model):
    __tablename__ = "instagram_story"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=True)
    modified = db.Column(UtcDateTime, onupdate=func.now())

    followers = db.Column(db.Integer, server_default=text("0"))

    gig_id = db.Column(UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), unique=True)
    gig = relationship("Gig", back_populates="instagram_story")

    marked_posted = db.Column(UtcDateTime, nullable=True)

    instagram_account_id = db.Column(
        UUIDString, db.ForeignKey("instagram_account.id", ondelete="restrict")
    )
    instagram_account = relationship(
        "InstagramAccount", backref=backref("instagram_stories", uselist=True)
    )

    def __repr__(self):
        return f"<InstagramStory: {self.id} ({self.gig})>"

    @property
    def reach(self):
        """int: The sum of reach taken from the story frame insights."""
        return sum(
            [
                frame.instagram_story_frame_insights[0].reach
                if frame.instagram_story_frame_insights
                and frame.instagram_story_frame_insights[0].reach
                else 0
                for frame in self.story_frames
            ]
        )

    @hybrid_property
    def impressions(self):
        """int: Impressions calculated as sum the of story frames inssights' impressions."""
        return sum([frame.impressions for frame in self.story_frames])

    @impressions.expression  # type: ignore
    def impressions(cls):
        from takumi.models.story_frame import StoryFrame  # noqa

        return (
            select([func.sum(StoryFrame.impressions)])
            .where(StoryFrame.instagram_story_id == cls.id)
            .label("impressions")
        )

    @hybrid_property
    def engagements(self):
        """int: Engagements calculated as sum the of story frames inssights' replies."""
        return sum([frame.replies_insight for frame in self.story_frames])

    @engagements.expression  # type: ignore
    def engagements(cls):
        from takumi.models.story_frame import StoryFrame  # noqa

        return (
            select([func.sum(StoryFrame.replies_insight)])
            .where(StoryFrame.instagram_story_id == cls.id)
            .label("engagements")
        )

    @property
    def marked_posted_within_last_24_hours(self):
        if not self.marked_posted:
            return False
        return self.marked_posted >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)

    @property
    def media(self):
        return [frame.media for frame in self.story_frames]

    @hybrid_property
    def has_marked_frames(self):
        return len(self.story_frames) > 0

    @has_marked_frames.expression  # type: ignore
    def has_marked_frames(cls):
        from takumi.models import StoryFrame

        return (
            sa.select([sa.func.count(StoryFrame.id) > 0])
            .where(StoryFrame.instagram_story_id == cls.id)
            .label("has_marked_frames")
        )

    def update_instagram_insights(self):
        for frame in self.story_frames:
            frame.update_instagram_insights()

    @hybrid_property
    def posted(self) -> Optional[dt.datetime]:
        if self.has_marked_frames:
            return sorted(self.story_frames, key=lambda f: f.posted)[0].posted
        return None

    @posted.expression  # type: ignore
    def posted(cls) -> Optional[dt.datetime]:
        from takumi.models import StoryFrame

        return sa.case(
            [
                (
                    cls.has_marked_frames,
                    sa.select([sa.func.min(StoryFrame.posted)])
                    .where(StoryFrame.instagram_story_id == cls.id)
                    .label("posted"),
                )
            ],
            else_=None,
        )


class InstagramStoryEvent(db.Model):
    __tablename__ = "instagram_story_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    creator_user = relationship("User", lazy="joined")

    instagram_story_id = db.Column(
        UUIDString,
        db.ForeignKey("instagram_story.id", ondelete="cascade"),
        index=True,
        nullable=False,
    )
    instagram_story = relationship(
        "InstagramStory",
        backref=backref("events", uselist=True, order_by="InstagramStoryEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_instagram_story_event_instagram_story_type_created",
            "instagram_story_id",
            "type",
            "created",
        ),
    )

    def __repr__(self):
        return "<InstagramStoryEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "InstagramStoryEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
