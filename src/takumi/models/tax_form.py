from typing import TYPE_CHECKING, Literal, Type

from sqlalchemy import func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString
from core.common.utils import States

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class FORM_NUMBER:
    W9 = "w9"
    W8BEN = "w8ben"

    @staticmethod
    def values():
        return [FORM_NUMBER.W9, FORM_NUMBER.W8BEN]


class STATES(States):
    PENDING: Literal["pending"] = "pending"
    COMPLETED: Literal["completed"] = "completed"
    INVALID: Literal["invalid"] = "invalid"


class TaxForm(db.Model):
    __tablename__ = "tax_form"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    modified = db.Column(
        UtcDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    state = db.Column(
        SoftEnum(*STATES.values()), index=True, server_default=STATES.PENDING, nullable=False
    )

    signature_date = db.Column(UtcDateTime)
    token = db.Column(db.String)
    name = db.Column(db.String)
    business_name = db.Column(db.String)
    sender_email = db.Column(db.String)
    number = db.Column(SoftEnum(*FORM_NUMBER.values()), nullable=False)
    url = db.Column(db.String)

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="cascade"), nullable=False
    )
    influencer = relationship("Influencer", backref=backref("tax_forms"))

    def __repr__(self) -> str:
        if self.signature_date:
            return f"<TaxForm (signed {self.signature_date.year}) {self.id}>"
        return f"<TaxForm (not signed) {self.id}>"
