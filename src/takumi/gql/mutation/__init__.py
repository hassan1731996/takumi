import graphene

from .advertiser import AdvertiserMutation
from .advertiser_config import AdvertiserConfigFormMutation
from .advertiser_industry import AdvertiserIndustryMutation
from .announcement import AnnouncementMutation
from .apply_first import ApplyFirstMutation
from .audience_insight import AudienceInsightMutation
from .audit import AuditMutation
from .bank import BankMutation
from .campaign import CampaignMutation
from .config import ConfigMutation
from .device import DeviceMutation
from .facebook import FacebookMutation
from .finance import FinanceMutation
from .gig import GigMutation
from .influencer import InfluencerMutation
from .influencer_campaign import InfluencerCampaignMutation
from .influencer_information import InfluencerInformationMutation
from .insight import InsightMutation
from .instagram_story import InstagramStoryMutation
from .location import LocationMutation
from .offer import OfferMutation
from .payment import PaymentMutation
from .post import PostMutation
from .public.authentication import AuthenticationMutation
from .targeting import TargetingMutation
from .tax_form import TaxFormMutation
from .tiger import TigerMutation
from .transcode import TranscodeMutation
from .unstable import UnstableMutation
from .user import UserMutation


class PublicMutation(graphene.ObjectType, AuthenticationMutation):
    """The public takumi server mutations"""


class Mutation(
    PublicMutation,
    UnstableMutation,
    AdvertiserMutation,
    AdvertiserIndustryMutation,
    AnnouncementMutation,
    ApplyFirstMutation,
    AudienceInsightMutation,
    AuditMutation,
    BankMutation,
    CampaignMutation,
    ConfigMutation,
    AdvertiserConfigFormMutation,
    DeviceMutation,
    FacebookMutation,
    FinanceMutation,
    GigMutation,
    InfluencerCampaignMutation,
    InfluencerInformationMutation,
    InfluencerMutation,
    InsightMutation,
    InstagramStoryMutation,
    LocationMutation,
    OfferMutation,
    PaymentMutation,
    PostMutation,
    TargetingMutation,
    TigerMutation,
    TranscodeMutation,
    UserMutation,
    TaxFormMutation,
):
    """The takumi server mutations"""
