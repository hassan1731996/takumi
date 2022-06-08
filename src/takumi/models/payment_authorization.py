import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Index, UniqueConstraint
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.models.user import User
from takumi.payments.authorization_checkers import PaymentAuthorizationChecker
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class PaymentAuthorization(db.Model):

    __tablename__ = "payment_authorization"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    slug = db.Column(db.String, nullable=False)

    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    modified = db.Column(
        UtcDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    expires = db.Column(UtcDateTime)

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="cascade"), nullable=False
    )
    influencer = relationship(
        "Influencer",
        backref=backref("payment_authorizations", order_by="PaymentAuthorization.created"),
    )

    def __repr__(self):
        return "<PaymentAuthorization: {}, influencer: {}, expires: {}>".format(
            self.id, self.influencer_id, self.expires
        )

    def valid(self, payment):
        return PaymentAuthorizationChecker.from_payment_authorization(self).valid(payment)

    def is_expired(self):
        if self.expires is None:
            return False
        return self.expires < dt.datetime.now(dt.timezone.utc)

    __table_args__ = (UniqueConstraint("influencer_id", "slug"),)


class PaymentAuthorizationEvent(db.Model):
    """A payment authorization event

    The payment authorization events are a log of all mutations to the payment authorization
    """

    __tablename__ = "payment_authorization_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey(User.id, ondelete="restrict"), index=True)
    creator_user = relationship(User, lazy="joined")

    payment_authorization_id = db.Column(
        UUIDString,
        db.ForeignKey(PaymentAuthorization.id, ondelete="restrict"),
        nullable=False,
        index=True,
    )
    payment_authorization = relationship(
        PaymentAuthorization,
        backref=backref("events", uselist=True, order_by="PaymentAuthorizationEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_pay_auth_event_pay_auth_type_created", "payment_authorization_id", "type", "created"
        ),
    )

    def __repr__(self):
        return "<PaymentAuthorizationEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "PaymentAuthorizationEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
