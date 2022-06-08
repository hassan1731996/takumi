class NotificationException(Exception):
    pass


class UnknownPlatform(NotificationException):
    pass


class UnparsableToken(NotificationException):
    pass


class NoDeviceException(NotificationException):
    pass


class ExpoException(NotificationException):
    pass
