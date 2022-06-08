import os

import alembic
from alembicverify.util import prepare_schema_from_migrations
from flask import current_app


def get_alembic_config():
    return current_app.extensions["migrate"].migrate.get_config()


def get_heads():
    script = alembic.script.ScriptDirectory.from_config(get_alembic_config())
    return [
        res.replace(" (head)", "").strip()
        for res in (
            rev.cmd_format(False, include_branches=True, tree_indicators=False)
            for rev in script.get_revisions("heads")
        )
    ]


def get_stored_heads():
    root = os.getcwd()
    return open(f"{root}/migrations/HEAD").read().strip().split(",")


def store_current_heads():
    head_str = ",".join(get_heads())
    with open("migrations/HEAD", "w") as headfile:
        headfile.write(f"{head_str}\n")


# Alembic version of db.create_all()
def create_all(db):
    prepare_schema_from_migrations(db.engine.url, get_alembic_config())
