import datetime as dt
from typing import Optional

from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class RevolutToken(db.Model):
    __tablename__ = "revolut_token"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    expires = db.Column(UtcDateTime, nullable=False)
    type = db.Column(SoftEnum("access", "refresh"), nullable=False, unique=True)
    value = db.Column(db.String, nullable=False)

    @hybrid_property
    def expired(self):
        return self.expires < dt.datetime.now(dt.timezone.utc)

    @classmethod
    def get(cls, type: str) -> Optional["RevolutToken"]:
        return cls.query.filter(cls.type == type).one_or_none()

    @classmethod
    def set(cls, type: str, value: str, expires: dt.datetime) -> "RevolutToken":
        token = cls.get(type)
        if not token:
            token = cls(type=type)

        token.value = value
        token.expires = expires

        db.session.add(token)
        db.session.commit()

        return token

    def __repr__(self) -> str:
        return f"<RevolutToken: ({self.type})>"
