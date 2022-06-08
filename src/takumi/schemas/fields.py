import datetime as dt

from marshmallow import fields, validate


class StrippedStringField(fields.String):
    def _serialize(self, value, attr, obj):
        return super()._serialize(self._strip(value), attr, obj)

    def _deserialize(self, value, attr, data):
        return super()._deserialize(self._strip(value), attr, data)

    def _strip(self, value):
        if isinstance(value, str):
            value = value.strip()
        return value


class RemovedWhitespaceStringField(fields.String):
    def _serialize(self, value, attr, obj):
        return super()._serialize(self._remove_white_spaces(value), attr, obj)

    def _deserialize(self, value, attr, data):
        return super()._deserialize(self._remove_white_spaces(value), attr, data)

    def _remove_white_spaces(self, value):
        if isinstance(value, str):
            value = value.replace(" ", "").strip()
        return value


class PercentField(fields.Nested):
    def _serialize(self, value, attr, obj):
        if value is None:
            value = 0
        return super()._serialize(dict(value=value), attr, obj)


class IbanField(RemovedWhitespaceStringField):
    def __init__(self, *args, **kwargs):
        kwargs["validate"] = validate.Regexp(r"^[A-Z]{2}[A-Z0-9]+$")
        return super().__init__(*args, **kwargs)


class UnixTimestampField(fields.DateTime):
    def _serialize(self, value, attr, obj):
        return super()._serialize(dt.datetime.fromtimestamp(value), attr, obj)
