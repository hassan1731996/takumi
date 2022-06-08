from sqlalchemy import func
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class Theme(db.Model):
    __tablename__ = "theme"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    name = db.Column(db.String, nullable=False)

    logo_url = db.Column(db.String, nullable=False)
