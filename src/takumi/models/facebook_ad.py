from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import backref, relationship

from core.common.sqla import MutableList, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .facebook_account import FacebookAccount
from .gig import Gig

FB_AD_URL = "https://www.facebook.com/ads/manager/account/ads/?act={}&selected_ad_ids={}&open_tray=EDITOR_DRAWER"


class FacebookAd(db.Model):
    __tablename__ = "facebook_ad"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)

    ad_id = db.Column(db.String, nullable=True)
    campaign_id = db.Column(db.String, nullable=False)
    adset_id = db.Column(db.String, nullable=False)
    account_id = db.Column(db.String, nullable=False)

    error = db.Column(db.String, nullable=True)

    gig_ids = db.Column(
        MutableList.as_mutable(ARRAY(UUIDString)), server_default=text("ARRAY[]::uuid[]")
    )

    facebook_account_id = db.Column(
        UUIDString, db.ForeignKey(FacebookAccount.id, ondelete="restrict")  # type: ignore
    )
    facebook_account = relationship(FacebookAccount, backref=backref("facebook_ads"), lazy="joined")

    @property
    def gigs(self):
        return Gig.query.filter(Gig.id.in_(self.gig_ids)).all()

    @property
    def url(self):
        if self.ad_id:
            return FB_AD_URL.format(self.account_id, self.ad_id)
        return None

    def __repr__(self):
        return f"<FacebookAd: {self.id} ({self.ad_id})>"
