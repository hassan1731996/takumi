from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Index
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class Device(db.Model):
    __tablename__ = "device"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    last_used = db.Column(UtcDateTime, index=True)
    device_token = db.Column(db.String, unique=True)
    device_model = db.Column(db.String)
    os_version = db.Column(db.String)
    endpoint_arn = db.Column(db.String)
    build_version = db.Column(db.String)
    active = db.Column(db.Boolean, server_default="t")

    def __repr__(self):
        return f"<Device: {self.device_model} @ {self.device_token}>"


class DeviceEvent(db.Model):
    """
    A device event
    The device events are a log of all mutations to the device
    """

    __tablename__ = "device_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    device_id = db.Column(
        UUIDString, db.ForeignKey(Device.id, ondelete="restrict"), index=True, nullable=False
    )
    device = relationship(
        Device,
        backref=backref("events", uselist=True, order_by="DeviceEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (Index("ix_device_event_device_type_created", "device_id", "type", "created"),)

    def __repr__(self):
        return "<DeviceEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return "DeviceEvent\n" f"id: {self.id}\n" f"type: {self.type}\n" f"event: {self.event}\n"
