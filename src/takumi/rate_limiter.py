import datetime as dt
from contextlib import contextmanager
from typing import Iterator, Type

from takumi.extensions import redis


class RateLimitReachedError(Exception):
    pass


RATE_LIMIT_KEY_PREFIX = "RATE_LIMIT:"


@contextmanager
def check_rate_limit(
    key: str,
    *,
    timeframe: dt.timedelta = None,
    limit: int = None,
    exc: Type[Exception] = RateLimitReachedError,
) -> Iterator:

    if not timeframe or not limit:
        yield
        return

    prefixed_key = RATE_LIMIT_KEY_PREFIX + key

    conn = redis.get_connection()
    count = conn.get(prefixed_key)

    if count is None:
        conn.setex(prefixed_key, int(timeframe.total_seconds()), 1)
    elif int(count) >= limit:
        raise exc("Rate Limit Reached")
    else:
        conn.incr(prefixed_key)
    yield
