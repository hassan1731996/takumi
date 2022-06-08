from typing import TYPE_CHECKING, Optional

from sqlalchemy import Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .user import User

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class TikTokAccount(db.Model):
    __tablename__ = "tiktok_account"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    last_scraped = db.Column(UtcDateTime)

    user_id = db.Column(db.String, nullable=False, unique=True, index=True)
    username = db.Column(db.String, nullable=False, index=True)

    nickname = db.Column(db.String)
    cover = db.Column(db.String)
    original_cover = db.Column(db.String)
    signature = db.Column(db.String)
    is_verified = db.Column(db.Boolean)
    is_secret = db.Column(db.Boolean)
    is_active = db.Column(db.Boolean, server_default="t")

    verified = db.Column(db.Boolean, server_default="f")
    followers = db.Column(db.Integer, server_default=text("0"))
    following = db.Column(db.Integer, server_default=text("0"))
    likes = db.Column(db.Integer, server_default=text("0"))
    video_count = db.Column(db.Integer, server_default=text("0"))
    digg = db.Column(db.Integer, server_default=text("0"))

    # Feed
    median_plays = db.Column(db.Integer, server_default=text("0"))
    mean_plays = db.Column(db.Integer, server_default=text("0"))
    median_diggs = db.Column(db.Integer, server_default=text("0"))
    mean_diggs = db.Column(db.Integer, server_default=text("0"))
    median_shares = db.Column(db.Integer, server_default=text("0"))
    mean_shares = db.Column(db.Integer, server_default=text("0"))
    median_comments = db.Column(db.Integer, server_default=text("0"))
    mean_comments = db.Column(db.Integer, server_default=text("0"))

    # End of feed

    influencer_id = db.Column(UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"))
    influencer = relationship("Influencer", backref=backref("tiktok_account", uselist=False))

    __table_args__ = (Index("idx_username_lower", text("lower(username)"), unique=True),)

    @classmethod
    def by_username(cls, username: str) -> Optional["TikTokAccount"]:
        return cls.query.filter(func.lower(cls.username) == func.lower(username.strip())).first()

    def __repr__(self) -> str:
        return f"<TikTokAccount: {self.id} ({self.username})>"


class TikTokAccountEvent(db.Model):
    __tablename__ = "tiktok_account_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str, index=True)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey(User.id), index=True)
    creator_user = relationship(User, lazy="joined")

    tiktok_account_id = db.Column(
        UUIDString,
        db.ForeignKey("tiktok_account.id", ondelete="restrict"),
        index=True,
        nullable=False,
    )
    tiktok_account = relationship(
        "TikTokAccount",
        backref=backref("events", uselist=True),
        order_by="TikTokAccountEvent.created",
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_tiktok_account_event_tiktok_account_type_created",
            "tiktok_account_id",
            "type",
            "created",
        ),
    )

    def __repr__(self):
        created = self.created and self.created.strftime("%Y-%m-%d %H:%M:%S")
        return f"<TikTokAccountEvent: {self.id} ({created} {self.type})>"

    def __str__(self):
        return (
            "TikTokAccountEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
