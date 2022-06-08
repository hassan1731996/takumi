from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy import text as sqlalchemy_text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import InstagramPost  # noqa


class InstagramPostComment(db.Model):
    __tablename__ = "instagram_post_comment"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    scraped = db.Column(UtcDateTime)
    ig_comment_id = db.Column(db.String, nullable=False, unique=True)
    username = db.Column(db.String, nullable=False)
    text = db.Column(db.String, nullable=False)

    hashtags = db.Column(
        MutableList.as_mutable(ARRAY(db.String)),
        server_default=sqlalchemy_text("ARRAY[]::varchar[]"),
    )
    emojis = db.Column(
        MutableList.as_mutable(ARRAY(db.String)),
        server_default=sqlalchemy_text("ARRAY[]::varchar[]"),
    )

    sentiment = db.Column(db.Float)  # XXX: Old Indico sentiment

    # Comprehend sentiment
    sentiment_type = db.Column(db.String)
    sentiment_language_code = db.Column(db.String)
    sentiment_positive_score = db.Column(db.Float)
    sentiment_neutral_score = db.Column(db.Float)
    sentiment_negative_score = db.Column(db.Float)
    sentiment_mixed_score = db.Column(db.Float)
    sentiment_checked = db.Column(db.Boolean, server_default="f")  # Flag to not retry

    instagram_post_id = db.Column(
        UUIDString,
        db.ForeignKey("instagram_post.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    instagram_post = relationship("InstagramPost", backref="ig_comments")

    def __repr__(self):
        return "<InstagramPostComment: ({}, {})>".format(self.id, self.text[:50])
