from typing import TYPE_CHECKING, List

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SoftEnum, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Campaign  # noqa


class PromptTypes:
    confirm = "confirm"
    multiple_choice = "multiple_choice"
    single_choice = "single_choice"
    text_input = "text_input"

    @staticmethod
    def get_types() -> List[str]:
        return [
            PromptTypes.confirm,
            PromptTypes.multiple_choice,
            PromptTypes.single_choice,
            PromptTypes.text_input,
        ]


class Prompt(db.Model):
    __tablename__ = "prompt"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    value = db.Column(db.String, nullable=False)
    type = db.Column(SoftEnum(*PromptTypes.get_types()), nullable=False)
    choices = db.Column(MutableList.as_mutable(JSONB))
    archived = db.Column(db.Boolean, server_default="f")
    brand_visible = db.Column(db.Boolean, server_default="f")

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="cascade"), nullable=False, index=True
    )
    campaign = relationship("Campaign", backref=backref("influencer_prompts"))

    def __repr__(self) -> str:
        value = self.value if len(self.value) < 27 else f"{self.value[:27]}..."
        return f'<Prompt: [{self.type}] "{value}" (Campaign: {self.campaign.id})>'
