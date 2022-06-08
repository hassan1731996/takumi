import time
from io import StringIO

import mock
from freezegun import freeze_time

from core.config import Config, MissingEnvironmentVariables, ProtectedConfig

from takumi.app import create_app
from takumi.config import Production, production
from takumi.constants import API_ROLLOVER_INTERVAL_MINUTES


def test_create_app_exits_and_prints_if_missing():
    with mock.patch(
        "flask.config.Config.from_object", side_effect=MissingEnvironmentVariables("VARIABLE_NAME")
    ):
        with mock.patch("sys.stderr", new_callable=StringIO) as stderr:
            with mock.patch("sys.exit") as exit:
                create_app()
                assert "ERROR" in stderr.getvalue()
                assert "VARIABLE_NAME" in stderr.getvalue()
                assert exit.called


def test_production_config_is_a_protected_config_instance():
    assert isinstance(Production(), ProtectedConfig)
    assert isinstance(production, ProtectedConfig)


def test_production_config_tiger_schedule_tasks_override():
    class TestConfig(Config):
        TIGER_SCHEDULE_TASKS = False

    p = Production() + TestConfig()
    assert p.TIGER_SCHEDULE_TASKS == False


def test_production_config_redis_backend_url_override():
    class TestConfig(Config):
        REDIS_BACKEND_URL = "1234"

    p = Production()
    assert p.REDIS_BACKEND_URL != "1234"

    p = Production() + TestConfig()
    assert p.REDIS_BACKEND_URL == "1234"


@freeze_time("2018-08-13")
def test_production_config_base_api_url_is_dynamic():
    p = Production()
    assert p.API_BASE_URL == "https://t{expected}.api.takumi.com".format(
        expected=int(time.time() / (API_ROLLOVER_INTERVAL_MINUTES * 60))
    )
