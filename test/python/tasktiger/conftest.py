import mock
import pytest
from redis import Redis

from core.tasktiger import TaskTiger
from core.testing.utils import add_two

from takumi.config.test import Testing


@pytest.yield_fixture()
def redis():
    url = getattr(Testing(), "REDIS_BACKEND_URL")
    # Default tasktiger tests to db 5
    url = url.replace("/0", "/5")

    redis = Redis.from_url(url)

    # Make sure there are no keys in the redis test db, just to be safe
    assert redis.dbsize() == 0

    yield redis

    # Cleanup after using redis to make sure there are no lingering keys
    redis.flushdb()
    assert redis.dbsize() == 0


@pytest.yield_fixture()
def tiger(redis):
    mock_app = mock.Mock(
        config={
            "GITHASH": "current_version",
            "TASK_TIGER_LOCAL_DEV": True,
            "TIGER_SCHEDULE_TASKS": False,
            "statsd": None,
        }
    )
    tiger = TaskTiger()
    tiger.init(mock_app, redis=redis)

    yield tiger


@pytest.yield_fixture()
def old_tiger(redis):
    """A tiger instance pointing to an "old" githash"""
    mock_app = mock.Mock(
        config={
            "GITHASH": "old_version",
            "TASK_TIGER_LOCAL_DEV": True,
            "TIGER_SCHEDULE_TASKS": False,
            "statsd": None,
        }
    )
    tiger = TaskTiger()
    tiger.init(mock_app, redis=redis)

    yield tiger


@pytest.yield_fixture()
def task(tiger):
    yield tiger.task()(add_two)


@pytest.yield_fixture()
def old_task(old_tiger):
    yield old_tiger.task()(add_two)
