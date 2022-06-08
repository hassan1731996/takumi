from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class Config(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    key = db.Column(db.String, nullable=False, unique=True, index=True)
    value = db.Column(JSONB, nullable=False)

    @classmethod
    def get(cls, key):
        return cls.query.filter(cls.key == key).one_or_none()

    def __repr__(self):
        return f"<Config: {self.key} = {self.value}>"
