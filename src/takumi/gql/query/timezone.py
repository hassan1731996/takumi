import datetime as dt

import pytz

from takumi.gql import arguments, fields
from takumi.models.market import Market
from takumi.roles import permissions


def _yield_timezones():
    for market in Market.get_all_supported_markets():
        for tz in market.timezone_choices:
            yield pytz.timezone(tz)


class _TimeZone:
    def __init__(self, tz):
        now = dt.datetime.utcnow()
        self.utc_offset = int(tz.utcoffset(now).total_seconds())
        self.name = tz.zone
        self.id = tz.zone  # XXX: Change default id field in the graphene type?


class TimeZoneQuery:
    timezone = fields.Field("TimeZone", zone=arguments.String(required=True))
    timezones = fields.List("TimeZone")

    @permissions.public.require()
    def resolve_timezone(root, info, zone):
        for tz in _yield_timezones():
            if tz.zone == zone:
                return _TimeZone(tz)

    @permissions.public.require()
    def resolve_timezones(root, info):
        timezones = [_TimeZone(tz) for tz in _yield_timezones()]
        timezones = sorted(timezones, key=lambda tz: tz.utc_offset)
        return timezones
