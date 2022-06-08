import graphene

from .advertiser import AdvertiserQuery
from .advertiser_config import AdvertiserConfigQuery
from .advertiser_industry import AdvertiserIndustryQuery
from .announcement import AnnouncementQuery
from .apply_first import ApplyFirstQuery
from .campaign import CampaignQuery
from .config import ConfigQuery
from .country import CountryQuery
from .debug import DebugQuery
from .facebook import (
    FacebookAdAccountQuery,
    FacebookAdQuery,
    FacebookAdSetQuery,
    FacebookAppQuery,
    FacebookCampaignQuery,
    FacebookPagesQuery,
    FacebookTakumiAdQuery,
)
from .finance import FinanceQuery
from .gig import GigQuery
from .influencer import InfluencerQuery
from .influencer_campaign import InfluencerCampaignQuery
from .influencer_tags import InfluencerTagsQuery
from .insight import InsightQuery
from .instagram import InstagramQuery
from .market import MarketQuery
from .media import MediaQuery
from .offer import OfferQuery
from .post import PostQuery
from .profile import ProfileQuery
from .public.report import ReportQuery
from .region import RegionQuery
from .reward_suggestion import RewardSuggestionQuery
from .role import RoleQuery
from .salesforce import AccountQuery, OpportunityProductQuery, OpportunityQuery
from .sentiment import SentimentQuery
from .signup import SignupsQuery
from .statements import StatementQuery
from .story_frame import StoryFrameQuery
from .targeting import TargetingEstimateQuery
from .tax_form import TaxFormQuery
from .tiger import TigerQuery
from .tiktoker import TiktokerQuery
from .timeline import TimelineQuery
from .timezone import TimeZoneQuery
from .user import UserQuery


class PublicQuery(graphene.ObjectType, ReportQuery, FacebookAppQuery):
    """The public takumi server queries"""


class Query(
    PublicQuery,  # Always extend the public query
    AccountQuery,
    AnnouncementQuery,
    AdvertiserQuery,
    AdvertiserIndustryQuery,
    AdvertiserConfigQuery,
    ApplyFirstQuery,
    CampaignQuery,
    ConfigQuery,
    CountryQuery,
    DebugQuery,
    FacebookAdAccountQuery,
    FacebookAdQuery,
    FacebookAdSetQuery,
    FacebookAppQuery,
    FacebookCampaignQuery,
    FacebookPagesQuery,
    FacebookTakumiAdQuery,
    FinanceQuery,
    GigQuery,
    InfluencerCampaignQuery,
    InfluencerQuery,
    InfluencerTagsQuery,
    InsightQuery,
    InstagramQuery,
    MarketQuery,
    MediaQuery,
    OfferQuery,
    OpportunityProductQuery,
    OpportunityQuery,
    PostQuery,
    ProfileQuery,
    RegionQuery,
    RewardSuggestionQuery,
    RoleQuery,
    SentimentQuery,
    SignupsQuery,
    StatementQuery,
    StoryFrameQuery,
    TargetingEstimateQuery,
    TigerQuery,
    TiktokerQuery,
    TimeZoneQuery,
    TimelineQuery,
    UserQuery,
    TaxFormQuery,
):
    """The takumi server queries"""
