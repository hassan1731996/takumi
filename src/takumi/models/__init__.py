# flake8: noqa
from sqlalchemy_searchable import make_searchable

from .address import Address
from .advertiser import Advertiser, AdvertiserConfig
from .advertiser_industry import AdvertiserIndustry
from .announcement import Announcement
from .answer import Answer
from .api_task import ApiTask
from .audience_insight import AudienceInsight, AudienceInsightEvent, AudienceSection
from .audit import Audit
from .campaign import Campaign, CampaignEvent, CampaignMetric
from .children_targeting import ChildrenTargeting
from .comment import Comment
from .config import Config
from .currency import Currency
from .device import Device
from .email_leads import EmailLead
from .email_login import EmailLogin
from .facebook_account import FacebookAccount
from .facebook_ad import FacebookAd
from .facebook_page import FacebookPage
from .gig import Gig, GigEvent
from .influencer import Influencer, InfluencerEvent
from .influencer_information import InfluencerChild, InfluencerInformation
from .influencer_prospect import (
    CampaignInfluencerProspect,
    InfluencerProspect,
    RegionInfluencerProspect,
)
from .insight import Insight, InsightEvent, PostInsight, StoryInsight
from .instagram_account import InstagramAccount, InstagramAccountEvent
from .instagram_audience_insight import InstagramAudienceInsight
from .instagram_post import InstagramPost, InstagramPostEvent
from .instagram_post_comment import InstagramPostComment
from .instagram_post_insight import InstagramPostInsight
from .instagram_reel import InstagramReel
from .instagram_story import InstagramStory, InstagramStoryEvent
from .instagram_story_frame_insight import InstagramStoryFrameInsight
from .interest import Interest
from .many_to_many import (
    advertiser_industries_table,
    advertiser_region_table,
    targeting_region_table,
)
from .market import Market
from .media import Image, Media, Video
from .notification import Notification
from .offer import Offer, OfferEvent
from .payment import Payment
from .payment_authorization import PaymentAuthorization, PaymentAuthorizationEvent
from .post import Post
from .prompt import Prompt
from .region import Region
from .revolut import RevolutToken
from .story_frame import StoryFrame
from .submission import Submission
from .targeting import Targeting, TargetingEvent
from .tax_form import TaxForm
from .theme import Theme
from .tiktok_account import TikTokAccount, TikTokAccountEvent
from .tiktok_post import TiktokPost
from .user import TargetingUpdate, User
from .user_advertiser_association import UserAdvertiserAssociation
from .user_comment_association import UserCommentAssociation

make_searchable(options={"regconfig": "pg_catalog.simple"})
