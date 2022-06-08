from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Campaign, Device  # noqaa


class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    sent = db.Column(UtcDateTime, server_default=func.now())

    device_id = db.Column(
        UUIDString, db.ForeignKey("device.id", ondelete="cascade"), nullable=False
    )
    device = relationship("Device", backref=backref("notifications", order_by="Notification.sent"))

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="cascade"), index=True, nullable=False
    )
    campaign = relationship(
        "Campaign", backref=backref("notifications", order_by="Notification.sent")
    )
    message = db.Column(db.String)
