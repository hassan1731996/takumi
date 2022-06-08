from graphene import ObjectType

from takumi.gql import arguments, fields
from takumi.gql.interfaces import InstagramUserInterface
from takumi.gql.relay import Connection, Node
from takumi.models import Currency
from takumi.models.address import Address
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.utils import uuid4_str

from .instagram_account import FollowersHistory, FollowersHistoryAnomaly


class Interest(ObjectType):
    id = fields.ID()
    name = fields.String()


def _resolve_enable_audience_submit(influencer, info):
    """Only allow valid influencers to submit audience insights

    Influencer is only allowed to submit audience insights when:
        1. They support insights
        2. They have been reviewed
        3. They are eligible
    if not influencer.supports_insights:
        return False
    if influencer.state not in (INFLUENCER_STATES.REVIEWED, INFLUENCER_STATES.VERIFIED):
        return False
    return SubmitAudienceInsightsFlag(influencer.user).enabled
    """
    return False


class Influencer(ObjectType):
    class Meta:
        interfaces = (Node, InstagramUserInterface)

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models import Influencer
        from takumi.search.influencer import InfluencerInfo

        return isinstance(root, Influencer) or isinstance(root, InfluencerInfo)

    # Public fields
    id = fields.ID(required=True)
    profile_picture = fields.String()

    instagram_account = fields.Field("InstagramAccount")

    disabled = fields.Boolean()

    deletion_date = fields.DateTime()

    has_accepted_latest_terms = fields.Boolean()
    has_accepted_latest_privacy = fields.Boolean()

    # Read-only for sales
    is_signed_up = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)
    has_facebook_page = fields.ViewInfluencerInfoField(fields.Boolean)
    has_tiktok_account = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)
    has_interests = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)
    has_youtube_channel = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)
    vat_number = fields.ViewInfluencerInfoField(fields.String, allow_self=True)
    is_vat_registered = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)

    last_login = fields.ViewInfluencerInfoField(
        fields.DateTime, resolver=fields.deep_source_resolver("user.last_login")
    )
    full_name = fields.ViewInfluencerInfoField(
        fields.String, resolver=fields.deep_source_resolver("user.full_name"), allow_self=True
    )
    dashboard_full_name = fields.String(
        resolver=fields.deep_source_resolver("user.full_name"),
        description="Influencer's full name viewed in the Dashboard",
    )
    gender = fields.ViewInfluencerInfoField(
        fields.String, resolver=fields.deep_source_resolver("user.gender"), allow_self=True
    )
    birthday = fields.ViewInfluencerInfoField(
        fields.Date, resolver=fields.deep_source_resolver("user.birthday"), allow_self=True
    )
    interests = fields.ViewInfluencerInfoField(fields.List(Interest))
    participating_campaign_ids = fields.List(fields.UUID)
    invited_campaign_ids = fields.List(fields.UUID)
    active_reservation_count = fields.ViewInfluencerInfoField(fields.Int)
    target_region = fields.ViewInfluencerInfoField("Region")
    state = fields.ViewInfluencerInfoField(fields.String)
    cooldown_ends = fields.ViewInfluencerInfoField(fields.DateTime)
    user_created = fields.ViewInfluencerInfoField(
        fields.DateTime, resolver=fields.deep_source_resolver("user.created")
    )
    has_device = fields.ViewInfluencerInfoField(fields.Boolean)
    gig_engagement = fields.ViewInfluencerInfoField("Percent")
    disabled_reason = fields.ViewInfluencerInfoField(fields.String)

    tiktok_username = fields.ViewInfluencerInfoField(fields.String, allow_self=True)
    youtube_channel_url = fields.ViewInfluencerInfoField(fields.String, allow_self=True)

    social_accounts_chosen = fields.ViewInfluencerInfoField(fields.Boolean, allow_self=True)

    # Private fields
    email = fields.ManageInfluencersField(
        fields.String, resolver=fields.deep_source_resolver("user.email"), allow_self=True
    )
    address = fields.ManageInfluencersField("Address", allow_self=True)
    total_rewards = fields.ManageInfluencersField("Currency", allow_self=True)
    total_rewards_breakdown = fields.ManageInfluencersField("RewardBreakdown", allow_self=True)
    current_region = fields.ManageInfluencersField("Region")
    device = fields.ManageInfluencersField("Device")

    information = fields.ViewInfluencerInfoField("InfluencerInformation", allow_self=True)

    has_information = fields.Boolean()
    last_active = fields.DateTime(resolver=fields.deep_source_resolver("user.last_active"))

    # ---- DEPRECATED FIELDS START ----

    # InstagramAccount
    username = fields.String(deprecation_reason="Use instagramAccount")
    followers = fields.Int(deprecation_reason="Use instagramAccount")
    engagement = fields.Field("Percent", deprecation_reason="Use instagramAccount")
    biography = fields.String(
        resolver=fields.deep_source_resolver("instagram_account.ig_biography"),
        deprecation_reason="Use instagramAccount",
    )
    is_private = fields.Boolean(
        resolver=fields.deep_source_resolver("instagram_account.ig_is_private"),
        deprecation_reason="Use instagramAccount",
    )
    media_count = fields.Int(
        resolver=fields.deep_source_resolver("instagram_account.media_count"),
        deprecation_reason="Use instagramAccount",
    )
    estimated_engagements_per_post = fields.Int(deprecation_reason="Use instagramAccount")
    followers_history_anomalies = fields.ViewInfluencerInfoField(
        fields.List(FollowersHistoryAnomaly),
        resolver=fields.deep_source_resolver("instagram_account.followers_history_anomalies"),
        deprecation_reason="Use instagramAccount",
    )
    is_business_account = fields.ViewInfluencerInfoField(
        fields.Boolean,
        resolver=fields.deep_source_resolver("instagram_account.ig_is_business_account"),
        deprecation_reason="Use instagramAccount",
    )
    is_verified = fields.ViewInfluencerInfoField(
        fields.Boolean,
        resolver=fields.deep_source_resolver("instagram_account.ig_is_verified"),
        deprecation_reason="Use instagramAccount",
    )
    boosted = fields.ManageInfluencersField(
        fields.Boolean,
        resolver=fields.deep_source_resolver("instagram_account.boosted"),
        description="Whether the account has had follower numbers boosted for demo/development purposes",
        deprecation_reason="Use instagramAccount",
    )
    instagram_audience_insight = fields.ViewInfluencerInfoField(
        "InstagramAudienceInsight",
        allow_self=True,
        deprecation_reason="Use instagramAccount",
    )
    followers_history = fields.ViewInfluencerInfoField(
        fields.List(FollowersHistory), deprecation_reason="Use instagramAccount"
    )
    estimated_impressions = fields.ViewInfluencerInfoField(
        fields.Int, deprecation_reason="Use instagramAccount"
    )
    impressions_ratio = fields.ViewInfluencerInfoField(
        "Percent", deprecation_reason="Use instagramAccount"
    )

    # No longer relevant
    supports_insights = fields.Boolean(
        resolver=_resolve_enable_audience_submit, deprecation_reason="Use enableAudienceSubmit"
    )
    audit = fields.ViewInfluencerInfoField(
        "Audit",
        resolver=fields.deep_source_resolver("latest_audit"),
        deprecation_reason="Audits have been deprecated",
    )
    audience_insight = fields.ViewInfluencerInfoField(
        "AudienceInsight",
        allow_self=True,
        deprecation_reason="Use instagramAccount.audienceInsight",
    )
    enable_audience_submit = fields.Boolean(
        resolver=_resolve_enable_audience_submit,
        deprecation_reason="Audience Insights no longer submitted",
    )
    audience_insight_expires = fields.ViewInfluencerInfoField(
        fields.DateTime, deprecation_reason="Audience Insights no longer submitted"
    )
    has_valid_audience_insight = fields.ViewInfluencerInfoField(
        fields.Boolean, deprecation_reason="Audience Insights no longer submitted"
    )

    # ---- DEPRECATED FIELDS END ----

    def resolve_is_signed_up(influencer, info):
        return influencer.is_signed_up

    def resolve_id(influencer, info):
        # need to override the InstagramUserInterface id
        return influencer.id

    def resolve_followers_history(influencer, info):
        if not influencer.instagram_account:
            return None

        return influencer.instagram_account.followers_history

    def resolve_disabled(influencer, info):
        return influencer.state == INFLUENCER_STATES.DISABLED

    def resolve_address(influencer, info):
        if not influencer.address:
            return dict(
                **Address.get_default_address_data_for_influencer(influencer), id=uuid4_str()
            )
        return influencer.address

    def resolve_participating_campaign_ids(influencer, info):
        if hasattr(influencer, "participating_campaign_ids"):
            return influencer.participating_campaign_ids
        if hasattr(influencer, "offers"):
            offers = [
                offer
                for offer in influencer.offers
                if offer.state
                not in (
                    OFFER_STATES.INVITED,
                    OFFER_STATES.PENDING,
                    OFFER_STATES.REQUESTED,
                    OFFER_STATES.REJECTED,
                    OFFER_STATES.REVOKED,
                    OFFER_STATES.REJECTED_BY_BRAND,
                )
            ]
            campaign_ids = [offer.campaign_id for offer in offers]
            return campaign_ids
        return []

    def resolve_engagement(influencer, info):
        return influencer.engagement

    def resolve_gig_engagement(influencer, info):
        return influencer.gig_engagement or 0

    def resolve_invited_campaign_ids(influencer, info):
        if hasattr(influencer, "invited_campaign_ids"):
            return influencer.invited_campaign_ids
        if hasattr(influencer, "offers"):
            offers = [
                offer
                for offer in influencer.offers
                if offer.state
                in (
                    OFFER_STATES.INVITED,
                    OFFER_STATES.PENDING,
                    OFFER_STATES.REQUESTED,
                    OFFER_STATES.REJECTED,
                    OFFER_STATES.REVOKED,
                    OFFER_STATES.REJECTED_BY_BRAND,
                )
            ]
            campaign_ids = [offer.campaign_id for offer in offers]
            return campaign_ids
        return []

    def resolve_has_information(influencer, info):
        if influencer.skip_self_tagging:
            return True
        return influencer.information is not None

    def resolve_total_rewards_breakdown(influencer, info):
        reward_breakdown = influencer.total_rewards_breakdown

        if influencer.target_region and influencer.target_region.market:
            currency = influencer.target_region.market.currency
        else:
            currency = "GBP"

        for key in ["net_value", "vat_value", "total_value"]:
            reward_breakdown[key] = Currency(
                reward_breakdown[key], currency=currency, currency_digits=True
            )
        reward_breakdown["show_net_and_vat"] = bool(influencer.vat_number)
        return reward_breakdown


InfluencerCountByValues = type(
    "InfluencerCountByValues",
    (arguments.Enum,),
    {
        param: param
        for param in [
            "gender",
            "is_signed_up",
            "interests",
            "followers",
            "following",
            "state",
            "estimated_engagements_per_post",
            "device_model",
            "media_count",
            "total_rewards",
            "user_created",
            "last_login",
            "participating_campaign_count",
            "age",
            "region",
        ]
    },
)


class CountByResults(ObjectType):
    key = fields.String()
    followers = fields.Int()
    count = fields.Int()


class CountBy(ObjectType):
    field = fields.String()
    results = fields.List(CountByResults)


class InfluencerConnection(Connection):
    count_by = fields.Field(fields.List(CountBy), fields=fields.List(InfluencerCountByValues))

    class Meta:
        node = Influencer


class InfluencerEvent(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    type = fields.String()
    text = fields.String()
    user = fields.Field("User")


class InfluencerEventsConnection(Connection):
    class Meta:
        node = InfluencerEvent
