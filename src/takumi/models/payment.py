from typing import TYPE_CHECKING, Type

from sqlalchemy import Column, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString
from core.common.utils import States

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Offer  # noqa


class STATES(States):
    PENDING = "pending"
    REQUESTED = "requested"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"


class Payment(db.Model):
    __tablename__ = "payment"
    __table_args__ = (
        Index(
            "ix_one_successful_payment_per_offer",
            "offer_id",
            unique=True,
            postgresql_where=Column("successful") != False,  # type: ignore
        ),
        Index("ix_payment_offer_id", "offer_id"),
    )

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, nullable=False, primary_key=True, default=uuid4_str)
    type = db.Column(SoftEnum("adyen", "dwolla", "revolut", "takumi"), nullable=False)

    created = db.Column(UtcDateTime, nullable=False, server_default=func.now())
    modified = db.Column(
        UtcDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    requested = db.Column(UtcDateTime, nullable=True)

    state = db.Column(SoftEnum(*STATES.values()), nullable=False, server_default=STATES.PENDING)

    destination = db.Column(db.String)
    reference = db.Column(db.String)
    successful = db.Column(db.Boolean)
    approved = db.Column(db.Boolean, server_default="f")

    currency = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, nullable=False)

    offer_id = db.Column(UUIDString, db.ForeignKey("offer.id", ondelete="restrict"), nullable=False)
    offer = relationship("Offer", backref=backref("payments", uselist=True))

    events = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    details = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    country = db.Column(db.String)

    def __repr__(self):
        return "<Payment({}): {} (Offer: {}) ({status})".format(
            self.type,
            self.id,
            self.offer_id,
            status={None: "pending", True: "successful", False: "failed"}[self.successful],
        )

    # Payment.successful(None, False, True) = (pending, failed, successful) interface
    @hybrid_property
    def is_pending(self):
        return self.successful == None  # noqa: E711

    @hybrid_property
    def is_failed(self):
        return self.successful == False

    @hybrid_property
    def is_successful(self):
        return self.successful == True
