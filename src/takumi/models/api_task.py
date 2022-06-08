from flask import url_for
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY

from core.common.sqla import MutableSet, UUIDString

from takumi.extensions import db


class ApiTask(db.Model):
    id = db.Column(UUIDString, primary_key=True)
    secret = db.Column(db.String, nullable=False)
    active = db.Column(db.Boolean, nullable=False, server_default="t")
    allowed_views = db.Column(
        MutableSet.as_mutable(ARRAY(db.String)),
        nullable=False,
        server_default=text("ARRAY[]::varchar[]"),
    )
    description = db.Column(db.String)

    def __repr__(self):
        return f"<ApiTask: ({self.id}) [{self.allowed_views}] '{self.description}'>"

    def urls(self, app):
        for view in self.allowed_views:
            yield "{}{}".format(app.config["API_BASE_URL"], url_for(view, task_id=self.id))
