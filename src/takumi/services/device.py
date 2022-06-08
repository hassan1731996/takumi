from takumi.events.device import DeviceLog
from takumi.extensions import db
from takumi.models import Device
from takumi.services import Service


class DeviceService(Service):
    """
    Represents the business model for Device. This is the bridge between
    the database and the application.
    """

    SUBJECT = Device
    LOG = DeviceLog

    @property
    def device(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Device.query.get(id)

    @staticmethod
    def create_device(user, token):
        device = Device()
        device.device_token = token
        db.session.add(device)
        db.session.commit()

        return device

    # GET
    @staticmethod
    def get_by_token(token):
        return Device.query.filter(Device.device_token == token).one_or_none()

    def update_device_token(self, token):
        self.log.add_event("set_token", {"device_token": token})

    def update_device_model(self, model):
        self.log.add_event("set_device_model", {"device_model": model})

    def update_os_version(self, os_version):
        self.log.add_event("set_os_version", {"os_version": os_version})

    def update_build_version(self, build_version):
        self.log.add_event("set_build_version", {"build_version": build_version})

    def update_active(self, active):
        self.log.add_event("set_active", {"active": active})
