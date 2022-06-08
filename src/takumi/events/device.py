from takumi.events import Event, TableLog
from takumi.models.device import DeviceEvent


class DeviceSetToken(Event):
    def apply(self, device):
        device.device_token = self.properties["device_token"]


class DeviceSetModel(Event):
    def apply(self, device):
        device.device_model = self.properties["device_model"]


class DeviceSetOSVersion(Event):
    def apply(self, device):
        device.os_version = self.properties["os_version"]


class DeviceSetBuildVersion(Event):
    def apply(self, device):
        device.build_version = self.properties["build_version"]


class DeviceSetActive(Event):
    def apply(self, device):
        device.active = self.properties["active"]


class DeviceLog(TableLog):
    event_model = DeviceEvent
    relation = "device"
    type_map = {
        "set_token": DeviceSetToken,
        "set_device_model": DeviceSetModel,
        "set_os_version": DeviceSetOSVersion,
        "set_build_version": DeviceSetBuildVersion,
        "set_active": DeviceSetActive,
    }
