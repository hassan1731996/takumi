import datetime as dt

from takumi.extensions import redis


class RedisCache:
    def __init__(self, name, default_ttl=int(dt.timedelta(minutes=10).total_seconds())):
        self.cache_prefix = "CACHED:" + name + ":"
        self.default_ttl = default_ttl

    def get(self, key):
        conn = redis.get_connection()
        return conn.get(self.cache_prefix + key)

    def set(self, key, value, ttl=None):
        if not ttl:
            ttl = self.default_ttl
        conn = redis.get_connection()
        conn.setex(self.cache_prefix + key, ttl, value)
