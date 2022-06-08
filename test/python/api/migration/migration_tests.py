import pytest
from alembic import command
from alembicverify.util import (
    get_current_revision,
    get_head_revision,
    prepare_schema_from_migrations,
)
from sqlalchemy import create_engine
from sqlalchemydiff import compare
from sqlalchemydiff.util import prepare_schema_from_models

from takumi.alembic.utils import get_alembic_config, get_heads, get_stored_heads
from takumi.extensions import db


def _set_uri(app, uri):
    # Create extensions in temp databases
    engine = create_engine(uri)
    engine.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    engine.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    app.config["SQLALCHEMY_DATABASE_URI"] = uri


@pytest.mark.usefixtures("new_db_left")
def test_migrations_upgrade_and_downgrade(app, uri_left):
    """Test all migrations up and down.

    Tests that we can apply all migrations from a brand new empty
    database, and also that we can remove them all.
    """
    _set_uri(app, uri_left)
    alembic_config_left = get_alembic_config()

    engine, script = prepare_schema_from_migrations(uri_left, alembic_config_left)

    head = get_head_revision(alembic_config_left, engine, script)
    current = get_current_revision(alembic_config_left, engine, script)

    assert head == current

    while current is not None:
        command.downgrade(alembic_config_left, "-1")
        current = get_current_revision(alembic_config_left, engine, script)


@pytest.mark.usefixtures("new_db_left")
@pytest.mark.usefixtures("new_db_right")
def test_migrations_model_and_migration_schemas_are_the_same(app, uri_left, uri_right):
    """Compare two databases.

    Compares the database obtained with all migrations against the
    one we get out of the models.
    """
    _set_uri(app, uri_left)
    alembic_config_left = get_alembic_config()

    engine, script = prepare_schema_from_migrations(uri_left, alembic_config_left)
    prepare_schema_from_models(uri_right, db.Model)

    result = compare(uri_left, uri_right, set(["alembic_version"]))

    assert result.errors == {}
    assert result.is_match


def test_migrations_head_file_contains_head(app):
    assert get_stored_heads() == get_heads()
