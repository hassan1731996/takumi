import datetime as dt

from flask import current_app
from sentry_sdk import capture_exception
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import backref
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString
from core.facebook import FacebookAdsAPI, GraphAPI

from takumi.constants import FACEBOOK_REVIEW_FACEBOOK_ACCOUNT_ID
from takumi.extensions import db
from takumi.models import Config
from takumi.utils import uuid4_str

from .user import User


def extend_access_token(graph):
    return graph.extend_access_token(
        current_app.config["FACEBOOK_APP_ID"], current_app.config["FACEBOOK_APP_SECRET"]
    )


facebook_account_users = db.Table(
    "facebook_account_users",
    db.Model.metadata,
    db.Column(
        "facebook_account_id",
        UUIDString,
        db.ForeignKey("facebook_account.id"),
        primary_key=True,
        index=True,
    ),
    db.Column("user_id", UUIDString, db.ForeignKey("user.id"), primary_key=True, index=True),
)


class FacebookAccount(db.Model):
    __tablename__ = "facebook_account"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    active = db.Column(db.Boolean, nullable=False, server_default="t")
    events = db.Column(
        MutableList.as_mutable(JSONB), nullable=False, default=[], server_default="[]"
    )

    facebook_name = db.Column(db.String, nullable=False)
    facebook_user_id = db.Column(db.String, nullable=False)

    token = db.Column(db.String, nullable=False)
    token_expires = db.Column(UtcDateTime)

    permissions = db.Column(
        MutableList.as_mutable(ARRAY(db.String)), server_default=text("ARRAY[]::varchar[]")
    )

    user_id = db.Column(UUIDString, db.ForeignKey(User.id, ondelete="restrict"), index=True)

    users = db.relationship(
        "User",
        secondary=facebook_account_users,
        lazy="joined",
        backref=backref("facebook_account", uselist=False),
    )

    def __repr__(self):
        return f"<FacebookAccount: {self.id} ({self.facebook_user_id})>"

    def set_token(self, token_obj):
        expires_in = token_obj.get("expires_in", None)
        if expires_in:
            expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
                seconds=token_obj["expires_in"]
            )
        else:
            expires = None
        self.token = token_obj["access_token"]
        self.token_expires = expires

    def refresh_info(self):
        user_info = self.graph_api.get_object(id="me")
        permissions_resp = self.graph_api.request("/me/permissions")
        permissions = [x["permission"] for x in permissions_resp["data"]]

        self.facebook_name = user_info.get("name", "")
        self.facebook_user_id = user_info["id"]
        self.permissions = permissions

    def update_using_token(self, token):
        graph = GraphAPI(token)
        token_obj = extend_access_token(graph)
        self.set_token(token_obj)
        self.refresh_info()

    def renew_token(self):
        graph = GraphAPI(self.token)
        token_obj = extend_access_token(graph)
        self.set_token(token_obj)

    def renew_token_if_needed(self):
        now = dt.datetime.now(dt.timezone.utc)
        if self.token_expires <= (now + dt.timedelta(days=2)):
            self.renew_token()
            self.refresh_info()
            db.session.add(self)
            db.session.commit()

    def revoke_permissions_on_facebook(self):
        if self.id == FACEBOOK_REVIEW_FACEBOOK_ACCOUNT_ID and Config.get("FACEBOOK_HARDCODE").value:
            # Do not revoke permissions for test account during review season
            return
        try:
            self.graph_api.request("/me/permissions", method="DELETE")
        except Exception as e:
            if "Error validating access token: The user has not authorized application" in str(e):
                # We can ignore this
                pass
            else:
                capture_exception()

    @classmethod
    def by_token(cls, token):
        facebook_user_id = cls.get_user_id_from_token(token)
        facebook_account = cls.by_facebook_user_id(facebook_user_id)
        facebook_account.update_using_token(token)
        return facebook_account

    @classmethod
    def get_user_id_from_token(cls, token):
        return GraphAPI(token).get_object(id="me")["id"]

    @classmethod
    def by_facebook_user_id(cls, facebook_user_id):
        return cls.query.filter(cls.facebook_user_id == facebook_user_id).first() or cls(
            facebook_user_id=facebook_user_id
        )

    @property
    def graph_api(self):
        if self.token_expires:
            self.renew_token_if_needed()
        return GraphAPI(self.token)

    @property
    def ads_api(self):
        if self.token_expires:
            self.renew_token_if_needed()
        return FacebookAdsAPI(self.token)
