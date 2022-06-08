import pytest
from sqlalchemydiff.util import get_temporary_uri

from ..conftest import _app  # noqa


def _get_temporary_uri(app):
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    return get_temporary_uri(db_uri)


@pytest.fixture(scope="function")
def app():
    yield from _app()


@pytest.fixture
def alembic_root():
    return "./migrations"


@pytest.fixture
def uri_left(app):
    return _get_temporary_uri(app)


@pytest.fixture
def uri_right(app):
    return _get_temporary_uri(app)
