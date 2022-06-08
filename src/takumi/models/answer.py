from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Influencer, Prompt  # noqa


class Answer(db.Model):
    __tablename__ = "answer"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    values = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    prompt_id = db.Column(
        UUIDString, db.ForeignKey("prompt.id", ondelete="cascade"), nullable=False, index=True
    )
    prompt = relationship("Prompt", backref=backref("answers"))

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"), nullable=False
    )
    influencer = relationship("Influencer")

    def __repr__(self) -> str:
        value = self.value if len(self.value) < 27 else self.value
        return f'<Prompt: "{value}" ({self.campaign})>'
