from sqlalchemy.orm import relationship

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class AdvertiserIndustry(db.Model):
    __tablename__ = "advertiser_industry"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    title = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, server_default="t")
    parent_id = db.Column(UUIDString, db.ForeignKey("advertiser_industry.id"))
    children = relationship("AdvertiserIndustry", backref=db.backref("parent", remote_side=[id]))

    def __repr__(self):
        return f"<Advertiser Industry: {self.id} ({self.title})>"
