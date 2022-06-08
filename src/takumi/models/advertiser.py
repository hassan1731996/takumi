import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import and_, extract, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SimpleTSVectorType, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .helpers import hybrid_method_subquery
from .many_to_many import advertiser_industries_table, advertiser_region_table
from .region import Region

if TYPE_CHECKING:
    from takumi.models import AdvertiserIndustry, Region, UserAdvertiserAssociation  # noqa


class Advertiser(db.Model):
    __tablename__ = "advertiser"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    profile_picture = db.Column(db.String)
    name = db.Column(db.String)
    domain = db.Column(db.String)

    archived = db.Column(db.Boolean, nullable=False, server_default="f")

    primary_region_id = db.Column(UUIDString, db.ForeignKey(Region.id))
    primary_region = relationship("Region")
    vat_number = db.Column(db.String)

    fb_ad_account_id = db.Column(db.String, unique=True)
    sf_account_id = db.Column(db.String, unique=True)

    influencer_cooldown = db.Column(db.Integer)

    regions = relationship("Region", secondary=advertiser_region_table, lazy="joined")
    advertiser_config = relationship("AdvertiserConfig", backref="advertiser", uselist=False)

    # A single user can have access to many Advertiser entities
    users_association = relationship("UserAdvertiserAssociation", back_populates="advertiser")

    # Advertiser industry
    advertiser_industries = relationship(
        "AdvertiserIndustry",
        secondary=advertiser_industries_table,
        lazy="subquery",
        backref=db.backref("advertisers", lazy=True),
    )

    @property
    def users(self):
        return [association.user for association in self.users_association]

    info = db.Column(JSONB, nullable=False, server_default="{}")

    search_vector = db.Column(SimpleTSVectorType("name", "domain"), index=True)

    def __repr__(self):
        return f"<Advertiser: {self.id} ({self.name})>"

    @classmethod
    def by_domain(cls, domain):
        return cls.query.filter(func.lower(cls.domain) == func.lower(domain)).first()

    @property
    def vat_percentage(self):
        if self.vat_number:
            if self.vat_number[:2] == "GB":
                return 0.2
            else:
                return 0.0
        else:
            return 0.2

    def administered_by_user(self, user):
        return user in self.users

    @hybrid_method_subquery
    def on_cooldown(cls, influencer):
        from . import Campaign, Influencer, Offer
        from .influencer import STATES as INFLUENCER_STATES
        from .offer import STATES as OFFER_STATES

        days_since_offer_accepted = func.trunc(
            (extract("epoch", dt.datetime.now(dt.timezone.utc)) - extract("epoch", Offer.accepted))
            / 86400
        )

        AliasedAdvertiser = aliased(cls)

        return (
            db.session.query(func.count(Influencer.id) > 0)
            .outerjoin(Offer)
            .outerjoin(Campaign)
            .outerjoin(AliasedAdvertiser)
            .filter(
                or_(
                    and_(
                        AliasedAdvertiser.id == cls.id,
                        Offer.state == OFFER_STATES.ACCEPTED,
                        Advertiser.influencer_cooldown != None,
                        Advertiser.influencer_cooldown != 0,
                        days_since_offer_accepted <= Advertiser.influencer_cooldown,
                    ),
                    Influencer.state == INFLUENCER_STATES.COOLDOWN,
                )
            )
            .filter(Influencer.id == influencer.id)
        )


class AdvertiserConfig(db.Model):
    __tablename__ = "advertiser_configuration"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    advertiser_id = db.Column(UUIDString, db.ForeignKey("advertiser.id"))
    # metrics config
    impressions = db.Column(db.Boolean, nullable=False, server_default="f")
    engagement_rate = db.Column(db.Boolean, nullable=False, server_default="f")
    benchmarks = db.Column(db.Boolean, nullable=False, server_default="f")
    campaign_type = db.Column(db.Boolean, nullable=False, server_default="f")
    budget = db.Column(db.Boolean, nullable=False, server_default="f")
    view_rate = db.Column(db.Boolean, nullable=False, server_default="f")
    # pages config
    brand_campaigns_page = db.Column(db.Boolean, nullable=False, server_default="f")
    dashboard_page = db.Column(db.Boolean, nullable=False, server_default="f")

    def __repr__(self):
        return f"<Advertiser ({self.advertiser_id}) Configuration: {self.id}>"
