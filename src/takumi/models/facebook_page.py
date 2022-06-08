from sentry_sdk import capture_exception
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString
from core.facebook.instagram import InstagramAPI

from takumi.cache import RedisCache
from takumi.constants import FACEBOOK_REVIEW_FACEBOOK_PAGE_ID
from takumi.events.facebook_page import FacebookPageLog
from takumi.extensions import db
from takumi.facebook_account import unlink_on_permission_error
from takumi.i18n import gettext as _
from takumi.i18n import locale_context
from takumi.models import Config
from takumi.models.influencer import FacebookPageDeactivated
from takumi.notifications import NotificationClient
from takumi.utils import uuid4_str

from .facebook_account import FacebookAccount


class FacebookPage(db.Model):
    __tablename__ = "facebook_page"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    active = db.Column(db.Boolean, nullable=False, server_default="t")

    facebook_account_id = db.Column(
        UUIDString, db.ForeignKey(FacebookAccount.id, ondelete="cascade"), index=True  # type: ignore
    )
    facebook_account = relationship(
        FacebookAccount,
        backref=backref("facebook_pages", uselist=True, cascade="all,delete"),
        lazy="joined",
    )

    events = db.Column(
        MutableList.as_mutable(JSONB), nullable=False, default=[], server_default="[]"
    )

    name = db.Column(db.String, nullable=False)
    page_id = db.Column(db.String, nullable=False)
    business_account_id = db.Column(db.String, nullable=False)
    page_access_token = db.Column(db.String, nullable=False)

    @property
    def instagram_api(self):
        return InstagramAPI(
            self.page_access_token, self.business_account_id, cache=RedisCache("InstagramAPI")
        )

    def deactivate(self, reason="", notify_influencer=False):
        if self.id == FACEBOOK_REVIEW_FACEBOOK_PAGE_ID and Config.get("FACEBOOK_HARDCODE").value:
            # XXX: Just during facebook review season
            return
        log = FacebookPageLog(self)
        log.add_event(
            "deactivate",
            {
                "reason": reason,
                "facebook_user_id": self.facebook_account.facebook_user_id,
                "facebook_page_id": self.page_id,
                "business_account_id": self.business_account_id,
                "permissions": self.facebook_account.permissions,
            },
        )
        db.session.commit()

        if self.instagram_account and self.instagram_account.influencer:
            influencer = self.instagram_account.influencer
            if notify_influencer and influencer.has_device:
                with locale_context(influencer.user.request_locale):
                    client = NotificationClient.from_influencer(influencer)
                    client.send_relink_facebook(
                        _(
                            "We've detected problems accessing your data through Facebook. "
                            "Please re-link your Facebook Page."
                        )
                    )

    @property
    def profile_picture(self):
        try:
            with unlink_on_permission_error(self):
                return self.instagram_api.get_object(self.page_id + "/picture")["url"]
        except FacebookPageDeactivated:
            return None
        except Exception:
            capture_exception()
            return None
