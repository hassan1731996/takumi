from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class Interest(db.Model):
    __tablename__ = "interest"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    name = db.Column(db.String)

    def __repr__(self):
        return f"<Interest: {self.name} ({self.id})>"
