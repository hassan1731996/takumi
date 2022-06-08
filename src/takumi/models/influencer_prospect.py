from typing import TYPE_CHECKING

from sqlalchemy import Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Campaign, Region  # noqa


class MissingTypeException(Exception):
    pass


class UnsupportedTypeException(Exception):
    pass


class RegionRequiredException(Exception):
    pass


class CampaignRequiredException(Exception):
    pass


TYPE_WHITELIST = ("suggestion", "recruit", "dismiss")


class InfluencerProspect(db.Model):
    """A potential influencer that has been identified for recruiting"""

    __tablename__ = "influencer_prospect"

    __table_args__ = (
        Index("ix_influencer_prospect_ig_username_lower", text("lower(ig_username)")),
        Index("ix_influencer_prospect_type", "type"),
        UniqueConstraint("ig_user_id", "type", name="uc_influencer_prospect_ig_user_id_type"),
    )

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    ig_username = db.Column(db.String, nullable=False)
    ig_user_id = db.Column(db.String, nullable=False)

    front_conversation_id = db.Column(db.String)

    type = db.Column(db.String, nullable=True)
    context = db.Column(db.String)
    info = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    __mapper_args__ = {"polymorphic_on": context}

    def __init__(self, *args, **kwargs):
        prospect_type = kwargs.get("type")
        if prospect_type not in TYPE_WHITELIST:
            raise UnsupportedTypeException()

        return super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<InfluencerProspect ({self.ig_username})>"


class RegionInfluencerProspect(InfluencerProspect):
    __mapper_args__ = {"polymorphic_identity": "region"}

    region_id = db.Column(UUIDString, db.ForeignKey("region.id"))
    region = relationship("Region")

    def __init__(self, *args, **kwargs):
        if kwargs.get("region") is None and kwargs.get("region_id") is None:
            raise RegionRequiredException()

        return super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<RegionInfluencerProspect ({self.ig_username}, {self.region.name})>"


class CampaignInfluencerProspect(InfluencerProspect):
    __mapper_args__ = {"polymorphic_identity": "campaign"}

    campaign_id = db.Column(UUIDString)
    campaign = relationship(
        "Campaign",
        foreign_keys=[campaign_id],
        primaryjoin="Campaign.id == CampaignInfluencerProspect.campaign_id",
    )

    def __init__(self, *args, **kwargs):
        prospect_type = kwargs.get("type")
        if prospect_type not in TYPE_WHITELIST:
            raise UnsupportedTypeException()

        if kwargs.get("campaign") is None and kwargs.get("campaign_id") is None:
            raise RegionRequiredException()

        return super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<CampaignInfluencerProspect ({self.ig_username}, {self.campaign.name})>"
