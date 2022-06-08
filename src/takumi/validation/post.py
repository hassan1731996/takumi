import datetime as dt

import dateutil.parser

from takumi.validation import Validator
from takumi.validation.errors import TooEarlyError, ValidationError


class PostTimeValidator(Validator):
    def __init__(self, opened):
        self.opened = opened

    def _parse_to_datetime(self, obj):
        if isinstance(obj, dt.datetime):
            return obj

        timestamp = None
        if isinstance(obj, str):
            try:
                timestamp = float(obj)
            except ValueError:
                try:
                    return dateutil.parser.parse(obj).replace(tzinfo=dt.timezone.utc)
                except ValueError:
                    raise ValidationError(f"Invalid timestamp: {obj}")

        if isinstance(obj, int) or isinstance(obj, float):
            timestamp = float(obj)

        if timestamp:
            return dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=dt.timezone.utc)

        raise ValidationError(f"Invalid timestamp: {obj}")

    def validate(self, created):
        parsed = self._parse_to_datetime(created)
        if self.opened and self.opened > parsed:
            raise TooEarlyError(self.opened)
