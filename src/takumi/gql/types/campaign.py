from flask_login import current_user
from graphene import ObjectType

from takumi.gql import arguments, constants, fields
from takumi.gql.db import (
    filter_campaigns,
    filter_campaigns_by_advertiser_name,
    filter_campaigns_by_campaign_filters,
    filter_campaigns_by_date_range,
    filter_campaigns_by_industry,
    filter_campaigns_by_region,
    filter_mine_campaigns,
    sort_campaigns_by_order,
)
from takumi.gql.relay import Connection, Node
from takumi.gql.types.percent import Percent
from takumi.gql.utils import get_brand_profile_user
from takumi.models import Currency
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.campaign import CampaignMetric, RewardModels
from takumi.reports import CampaignReport
from takumi.rewards import RewardCalculator
from takumi.roles import permissions
from takumi.roles.needs import advertiser_role, edit_campaign, team_member_role
from takumi.services.campaign import CampaignService, CompleteSchema, StashSchema
from takumi.services.validation import Validate


class ApplyFirstMetadata(ObjectType):
    total = fields.Int()
    accepted_units = fields.Int()
    selected_units = fields.Int()


class AccessibleData(ObjectType):
    id = fields.UUID()
    name = fields.String()
    impressions = fields.Int()
    engagement_rate = fields.Float()
    benchmark = fields.Float()
    type = fields.String()
    reach = fields.Int()
    assets = fields.Int()
    budget = fields.String()


class CampaignHighlights(ObjectType):
    engagement_rate = fields.Float()
    engagement_rate_static = fields.Float()
    engagement_rate_story = fields.Float()
    engagement_rate_static_from_total = fields.Float()
    engagement_rate_story_from_total = fields.Float()


class TotalCampaignsData(ObjectType):
    total_campaigns = fields.Int()
    total_creators = fields.Int()
    total_impressions = fields.Int()
    advertiser_names = fields.List(fields.String)


class CampaignPrompt(ObjectType):
    type = fields.String()
    text = fields.String()
    choices = fields.List(fields.String)
    brand_visible = fields.Boolean()


class Photo(ObjectType):
    url = fields.String()


class Photos(ObjectType):
    cover_photo = fields.Field(Photo)
    secondary_photos = fields.List(Photo)


class Progress(ObjectType):
    reserved = fields.Int()
    submitted = fields.Int()
    total = fields.Int()


class Count(ObjectType):
    value = fields.String()
    count = fields.Int()

    def resolve_value(root, info):
        return root[0]

    def resolve_count(root, info):
        return root[1]


class Participation(ObjectType):
    type = fields.String(source="state")
    count = fields.Int()


class Campaign(ObjectType):
    class Meta:
        interfaces = (Node,)

    created = fields.DateTime()
    started = fields.DateTime()

    name = fields.String(description="The name of the campaign")
    description = fields.String(
        description=(
            "Description of the campaign, usually the history of the brand and/or the product"
        )
    )
    state = fields.String(description="The state of the campaign")
    pre_approval = fields.Boolean(
        description="Whether the campaign is a pre-approval campaign or not"
    )
    apply_first = fields.Boolean(
        description="Whether the campaign is a apply-first campaign or not"
    )
    brand_match = fields.AdvertiserField(
        fields.Boolean, description="Whether the campaign is a brand-match campaign or not"
    )
    pro_bono = fields.AdvertiserField(
        fields.Boolean, description="Whether the campaign is pro bono or not"
    )
    brand_safety = fields.AdvertiserField(
        fields.Boolean,
        description="Whether the campaign needs an external review or not (from client)",
    )
    extended_review = fields.AdvertiserField(
        fields.Boolean,
        description="The client has 5 working days to review, and posts are not automatically approved",
    )
    require_insights = fields.Boolean(
        description="Whether to require insights to be submitted before the influencer can claim their reward"
    )
    archived = fields.AdvertiserField(
        fields.Boolean, description="Whether the campaign is archived"
    )

    shipping_required = fields.Boolean()

    requires_tiktok_account = fields.Boolean()

    reward_model = fields.AdvertiserField(fields.String)
    market_slug = fields.String()

    advertiser = fields.Field("Advertiser")

    participation = fields.AdvertiserField(
        fields.List(Participation, description="The participation summary of the campaign")
    )

    prompts = fields.List(
        CampaignPrompt, description="Prompts for the influencer when applying for the campaign"
    )
    has_brand_visible_prompts = fields.Boolean()

    insights_count = fields.AdvertiserField(fields.Int)
    reach = fields.AdvertiserField(
        fields.Int, description="Total reach for all posts in this campaign"
    )
    reach_total = fields.Int(
        description="Total reach for all posts (Stories, Videos, Posts)",
    )
    impressions_total = fields.Int(
        description="Total impressions for all posts (Stories, Videos, Posts)",
    )
    engagements_total = fields.Int(
        description="Total engagements for all posts (Stories, Videos, Posts)",
    )
    followers_total = fields.Int(
        description="Total number of the follower from all accepted influencers",
        source="number_of_accepted_followers",
    )
    likes = fields.AdvertiserField(
        fields.Int, description="Total likes for all posts in this campaign"
    )
    comments = fields.AdvertiserField(
        fields.Int, description="Total comments for all posts in this campaign"
    )
    video_views = fields.AdvertiserField(
        fields.Int, description="Total video views for all posts in this campaign"
    )
    video_engagement = fields.AdvertiserField(
        Percent, description="Average engagement rate based on video views"
    )
    engagements = fields.AdvertiserField(
        fields.Int, description="Total engagements for all posts in this campaign"
    )
    engagement = fields.AdvertiserField(
        Percent, description="Average engagement for all posts in this campaign"
    )
    engagement_rate = fields.AdvertiserField(Percent, description="(Likes+Comments)/Followers*100%")
    impressions = fields.AdvertiserField(
        fields.Int, description="The total impressions for all posts in this campaign"
    )

    cost_per_engagement = fields.AdvertiserField(
        "Currency", description="Total cost per engagement across the whole campaign"
    )
    projected_cost_per_engagement = fields.AdvertiserField(
        "Currency",
        description="Projected cost per engagement across the whole campaign, based on current submissions",
    )

    units = fields.AdvertiserField(fields.Int, description="Minimum number of gigs per post")
    posts = fields.List("Post")

    min_followers = fields.AdvertiserField(
        fields.Int,
        description="The minimum followers each influencer has to have",
        deprecation_reason="Use absolute minimum in targeting",
    )

    photos = fields.Field(Photos)

    owner = fields.AdvertiserField("User")
    campaign_manager = fields.AdvertiserField("User")
    secondary_campaign_manager_id = fields.AdvertiserField("User")
    community_manager = fields.AdvertiserField("User")

    targeting = fields.AdvertiserField("Targeting")

    has_nda = fields.AdvertiserField(fields.Boolean)
    industry = fields.AdvertiserField(fields.String)

    posts_per_influencer = fields.Int(source="post_count")

    push_notification_message = fields.AdvertiserField(fields.String)
    opportunity_product_id = fields.AdvertiserField(fields.String)

    interest_ids = fields.AdvertiserField(
        fields.List(fields.UUID, resolver=fields.deep_source_resolver("targeting.interest_ids"))
    )
    public = fields.AdvertiserField(fields.Boolean)

    price = fields.AdvertiserField("Currency")
    list_price = fields.AdvertiserField("Currency")
    client_budget = fields.AdvertiserField(
        "Currency", deprecation_reason="Use price instead", source="price"
    )

    custom_reward_units = fields.AdvertiserField(fields.Int)
    has_custom_reward = fields.AdvertiserField(fields.Boolean)

    progress = fields.AdvertiserField(Progress)

    tags = fields.AuthenticatedField(
        fields.List(fields.String), needs=[edit_campaign, advertiser_role]
    )
    emojis = fields.AdvertiserField(fields.List(Count))
    hashtags = fields.AdvertiserField(fields.List(Count))
    caption_sentiment = fields.AdvertiserField(Percent)
    comment_sentiment = fields.AdvertiserField(Percent)

    report_token = fields.AdvertiserField(fields.UUID)
    submissions_token = fields.AdvertiserField(fields.UUID)
    insights_token = fields.AuthenticatedField(fields.UUID, needs=team_member_role)

    is_fully_reserved = fields.AdvertiserField(fields.Boolean)

    can_be_completed = fields.AdvertiserField(fields.Boolean)
    can_be_stashed = fields.AdvertiserField(fields.Boolean)

    total_submissions = fields.AdvertiserField(fields.Int)

    is_multipost = fields.Boolean()

    hash = fields.AdvertiserField(fields.String, source="candidates_hash")

    report = fields.AdvertiserField(
        "CampaignReport", description="The overall report of a campaign"
    )
    report_summary = fields.AdvertiserField(fields.String)

    submission_deadline = fields.DateTime(
        description="The earliest submission deadline in the campaign"
    )
    deadline = fields.DateTime(description="The earliest deadline in the campaign")
    accessible_data = fields.Field(AccessibleData)
    total_creators = fields.Int(description="Amount of total creators")
    campaign_highlights = fields.Field(
        CampaignHighlights, description="Highlights: campaign KPIs calculated and shown as Fact"
    )

    def resolve_impressions(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if brand_user_profile:
            if (
                brand_user_profile.advertiser.advertiser_config
                and brand_user_profile.advertiser.advertiser_config.impressions
            ):
                return campaign.impressions
            return None
        return campaign.impressions

    def resolve_impressions_total(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if brand_user_profile:
            if (
                brand_user_profile.advertiser.advertiser_config
                and brand_user_profile.advertiser.advertiser_config.impressions
            ):
                return campaign.impressions_total
            return None
        return campaign.impressions_total

    def resolve_reward_model(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if brand_user_profile:
            if (
                brand_user_profile.advertiser.advertiser_config
                and brand_user_profile.advertiser.advertiser_config.campaign_type
            ):
                return campaign.reward_model
            return None
        return campaign.reward_model

    def resolve_engagement(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if brand_user_profile:
            if (
                brand_user_profile.advertiser.advertiser_config
                and brand_user_profile.advertiser.advertiser_config.engagement_rate
            ):
                return campaign.engagement
            return None
        return campaign.engagement

    def resolve_total_creators(campaign, info):
        total_creators = CampaignService.get_number_of_accepted_influencers([campaign.id])
        return total_creators

    def resolve_min_followers(campaign, info):
        return campaign.targeting.absolute_min_followers

    def resolve_report(campaign, info):
        if not permissions.view_post_reports.can():
            # Temporarily require permission to see these new reports
            return None

        if campaign.state == CAMPAIGN_STATES.DRAFT:
            # No report in draft campaigns
            return None

        return CampaignReport(campaign)

    def resolve_photos(campaign, info):
        return {
            "secondary_photos": campaign.pictures[1:] if len(campaign.pictures) > 1 else [],
            "cover_photo": campaign.pictures[0] if len(campaign.pictures) > 0 else None,
        }

    def resolve_participation(campaign, info):
        return CampaignService.get_participation(campaign.id)

    def resolve_has_custom_reward(campaign, info):
        return campaign.custom_reward_units is not None

    def resolve_can_be_completed(campaign, info):
        return len(Validate(campaign, CompleteSchema)) == 0

    def resolve_can_be_stashed(campaign, info):
        return len(Validate(campaign, StashSchema)) == 0

    def resolve_cost_per_engagement(campaign, info):
        return Currency(
            amount=campaign.cost_per_engagement,
            currency=campaign.market.currency,
            currency_digits=True,
        )

    def resolve_projected_cost_per_engagement(campaign, info):
        return Currency(
            amount=campaign.projected_cost_per_engagement,
            currency=campaign.market.currency,
            currency_digits=True,
        )

    def resolve_price(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        currency = Currency(amount=campaign.price, currency=campaign.market.currency)
        if brand_user_profile:
            if (
                brand_user_profile.advertiser.advertiser_config
                and brand_user_profile.advertiser.advertiser_config.budget
            ):
                return currency
            return None
        return currency

    def resolve_list_price(campaign, info):
        if permissions.team_member.can():
            list_price = campaign.list_price
        else:
            list_price = 0

        currency = campaign.market.currency
        return Currency(amount=list_price, currency=currency)

    def resolve_progress(campaign, info):
        return campaign.fund.get_progress()

    def resolve_total_submissions(campaign, info):
        return CampaignService.get_submissions_count(campaign.id)

    def resolve_is_multipost(campaign, info):
        return len(campaign.posts) > 1

    def resolve_has_brand_visible_prompts(campaign, info):
        return len([p for p in campaign.prompts if p.get("brand_visible", False)]) > 0

    def resolve_accessible_data(campaign, info):
        campaigns_data = dict(
            id=campaign.id,
            name=campaign.name,
            impressions=None,
            engagement_rate=None,
            benchmark=None,
            type=None,
            reach=None,
            assets=None,
            budget=None,
        )

        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if brand_user_profile and not brand_user_profile.advertiser.advertiser_config:
            return campaigns_data

        campaigns_data["benchmark"] = (
            0
            if not brand_user_profile or brand_user_profile.advertiser.advertiser_config.benchmarks
            else None
        )

        campaigns_data["type"] = (
            campaign.reward_model
            if not brand_user_profile
            or brand_user_profile.advertiser.advertiser_config.campaign_type
            else None
        )

        budget = (
            Currency(amount=campaign.price, currency=campaign.market.currency)
            if not brand_user_profile or brand_user_profile.advertiser.advertiser_config.budget
            else None
        )
        campaigns_data["budget"] = budget.formatted_value if budget else None

        if not campaign.campaign_metric:
            return {
                **campaigns_data,
                "impressions": 0,
                "engagement_rate": 0,
                "reach": 0,
                "assets": 0,
            }

        campaigns_data["impressions"] = (
            campaign.campaign_metric.impressions_total
            if not brand_user_profile or brand_user_profile.advertiser.advertiser_config.impressions
            else None
        )
        campaigns_data["engagement_rate"] = (
            campaign.campaign_metric.engagement_rate_total
            if not brand_user_profile
            or brand_user_profile.advertiser.advertiser_config.engagement_rate
            else None
        )

        campaigns_data["assets"] = (
            campaign.campaign_metric.assets
            if campaign.reward_model == RewardModels.assets
            else None
        )
        campaigns_data["reach"] = (
            campaign.campaign_metric.reach_total
            if campaign.reward_model == RewardModels.reach
            else None
        )
        return campaigns_data

    def resolve_campaign_highlights(campaign, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, campaign)
        if (
            not brand_user_profile
            or brand_user_profile.advertiser.advertiser_config.engagement_rate
        ):
            engagement_rate = 0
            engagement_rate_static = 0
            engagement_rate_story = 0
            engagement_rate_static_from_total = 0
            engagement_rate_story_from_total = 0
            if campaign_metrics := CampaignMetric.query.filter(
                CampaignMetric.campaign_id == campaign.id
            ).first():
                engagement_rate = campaign_metrics.engagement_rate_total
                engagement_rate_static = campaign_metrics.engagement_rate_static
                engagement_rate_story = campaign_metrics.engagement_rate_story
                if engagement_rate:
                    engagement_rate_static_from_total = (
                        engagement_rate_static / engagement_rate * 100
                    )
                    engagement_rate_story_from_total = engagement_rate_story / engagement_rate * 100
            return dict(
                engagement_rate=engagement_rate,
                engagement_rate_static=engagement_rate_static,
                engagement_rate_story=engagement_rate_story,
                engagement_rate_static_from_total=engagement_rate_static_from_total,
                engagement_rate_story_from_total=engagement_rate_story_from_total,
            )
        return dict(
            engagement_rate=None,
            engagement_rate_static=None,
            engagement_rate_story=None,
            engagement_rate_static_from_total=None,
            engagement_rate_story_from_total=None,
        )


class CampaignNotification(ObjectType):
    influencer = fields.Field("Influencer", source="Influencer")
    notification_count = fields.Int(source="notification_count")
    last_notification_sent = fields.DateTime(source="last_notification_sent")
    offer = fields.Field("Offer", source="Offer")
    reward = fields.Field("Currency")

    def resolve_reward(root, info):
        if root.Offer:
            reward = root.Offer.reward
        else:
            reward = RewardCalculator(root.Campaign).calculate_reward_for_influencer(
                root.Influencer
            )

        return Currency(amount=reward, currency=root.Campaign.market.currency)


class CampaignStatsResult(ObjectType):
    key = fields.String()
    value = fields.Int()

    def resolve_key(root, info):
        return root[0]

    def resolve_value(root, info):
        return root[1]


class CampaignStatsRegionResult(ObjectType):
    region_name = fields.String()
    results = fields.Field(fields.SortedList(CampaignStatsResult, key=lambda x: x[0]))

    def resolve_region_name(root, info):
        return root[0]

    def resolve_results(root, info):
        return root[1].items()


class CampaignStatsBudgetResult(CampaignStatsResult):
    value = fields.Field("Currency")


class CampaignStatsRegionBudgetResult(CampaignStatsRegionResult):
    results = fields.Field(fields.SortedList(CampaignStatsBudgetResult, key=lambda x: x[0]))


class CampaignStats(ObjectType):
    campaign_reward_model_distribution = fields.SortedList(
        CampaignStatsResult, key=lambda x: x[1], reverse=True
    )
    campaign_interests = fields.SortedList(CampaignStatsResult, key=lambda x: x[1], reverse=True)
    campaigns_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    gigs_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    instagram_post_impressions_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    instagram_story_impressions_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    unique_participants_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    new_participants_by_month = fields.Field(fields.List(CampaignStatsRegionResult))
    budget_by_month = fields.Field(fields.List(CampaignStatsRegionBudgetResult))
    payments_by_month = fields.Field(fields.List(CampaignStatsRegionBudgetResult))
    margin_by_month = fields.Field(fields.List(CampaignStatsRegionBudgetResult))
    participants_by_quarter = fields.SortedList(CampaignStatsResult, key=lambda x: x[0])
    campaigns_by_quarter = fields.SortedList(CampaignStatsResult, key=lambda x: x[0])
    gigs_by_quarter = fields.SortedList(CampaignStatsResult, key=lambda x: x[0])
    campaign_count = fields.Int()
    running_campaign_count = fields.Int()
    gig_count = fields.Int()
    submitted_gig_count = fields.Int()
    active_gig_count = fields.Int()


class CampaignNotificationConnection(Connection):
    class Meta:
        node = CampaignNotification


class CampaignConnection(Connection):
    total_campaigns_data = fields.Field(
        TotalCampaignsData,
        region_id=arguments.UUID(),
        mine=arguments.Boolean(),
        order=fields.String(),
        start_date=fields.String(),
        end_date=fields.String(),
        search_advertiser=fields.String(),
        **constants.campaign_filters,
    )

    class Meta:
        node = Campaign

    def resolve_total_campaigns_data(
        root,
        info,
        region_id=None,
        mine=False,
        order=None,
        start_date=None,
        end_date=None,
        search_advertiser=None,
        **filters,
    ):
        query = filter_campaigns()
        if start_date and end_date:
            query = filter_campaigns_by_date_range(start=start_date, end=end_date, query=query)
        campaigns_with_current_region = filter_campaigns_by_region(query, region_id)
        mine_campaigns = filter_mine_campaigns(campaigns_with_current_region, mine)

        advertiser_industries_ids = filters.pop("advertiser_industries_ids", None)
        campaigns_with_current_industries = filter_campaigns_by_industry(
            mine_campaigns, advertiser_industries_ids
        )

        filtered_campaigns = filter_campaigns_by_campaign_filters(
            campaigns_with_current_industries, **filters
        )
        filtered_campaigns_by_advertiser_name = filter_campaigns_by_advertiser_name(
            filtered_campaigns, search_advertiser
        )

        ordered_campaigns = sort_campaigns_by_order(filtered_campaigns_by_advertiser_name, order)
        campaign_ids, advertiser_names = [], set()
        for campaign in ordered_campaigns:
            campaign_ids.append(campaign.id)
            advertiser_names.add(
                campaign.advertiser.name if campaign.advertiser.name else campaign.advertiser.domain
            )
        number_of_accepted_influencers = CampaignService.get_number_of_accepted_influencers(
            campaign_ids
        )
        impressions = CampaignService.get_campaigns_impressions(campaign_ids)
        return dict(
            total_campaigns=len(campaign_ids),
            total_creators=number_of_accepted_influencers,
            total_impressions=impressions,
            advertiser_names=sorted(advertiser_names),
        )
