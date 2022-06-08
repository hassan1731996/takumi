from graphene import Interface, ObjectType

from takumi import reports
from takumi.gql import fields
from takumi.models import Currency


class Impressions(ObjectType):
    home = fields.Int()
    profile = fields.Int()
    hashtags = fields.Int()
    location = fields.Int()
    explore = fields.Int()
    other = fields.Int()
    total = fields.Int()
    from_followers = fields.Field("Percent")
    from_non_followers = fields.Field("Percent")


class Engagements(ObjectType):
    likes = fields.Int()
    comments = fields.Int()
    saves = fields.Int()
    replies = fields.Int()
    shares = fields.Int()
    total = fields.Int()


class Reach(ObjectType):
    total = fields.Int()
    from_followers = fields.Field("Percent")
    from_non_followers = fields.Field("Percent")


class Actions(ObjectType):
    link_clicks = fields.Int()
    profile_visits = fields.Int()
    website_clicks = fields.Int()
    sticker_taps = fields.Int()
    replies = fields.Int()
    shares = fields.Int()
    total = fields.Int()


class Report(ObjectType):
    campaign = fields.Field("Campaign")


class CampaignReport(ObjectType):
    budget = fields.Field("Currency")

    def resolve_budget(report, root):
        campaign = report.campaign
        currency = campaign.market.currency
        return Currency(amount=campaign.price, currency=currency)

    insights = fields.Int()

    # ii.a)
    influencers = fields.Int(
        description="Total number of participating influencers in the campaign",
        source="participating_influencer_count",
    )

    submissions = fields.Int(
        description="Total number of live posts from the influencers", source="live_gig_count"
    )

    assets = fields.Int(
        description="Total number of assets from the influencers (story frames, gallery media etc. etc)",
        source="live_media_count",
    )

    # ii.b)
    followers = fields.Int(
        description="Sum of followers of the influencers upon them being accepted onto the campaign",
        source="accepted_followers",
    )

    combined_followers = fields.Int(
        description="Sum of followers for each post in the campaign", source="live_gig_followers"
    )

    # ii.c)
    engagement_rate = fields.Field(  # XXX: REVISIT
        "Percent", description="The engagement rate of the campaign, excluding stories"
    )

    # ii.d)
    cpe = fields.String(description="The CPE of the campaign, excluding stories")


class PostReportInterface(Interface):
    assets = fields.Int()
    submissions = fields.Int()
    processed_submissions = fields.Int()
    followers = fields.Int()
    reach = fields.Int()

    profile_visits = fields.Int()
    website_clicks = fields.Int()

    frequency = fields.Float()

    @classmethod
    def resolve_type(cls, report, info):
        if type(report) is reports.StandardPostReport:
            return StandardPostReport
        if type(report) is reports.StoryPostReport:
            return StoryPostReport
        if type(report) is reports.VideoPostReport:
            return VideoPostReport


class StandardPostReport(ObjectType):
    class Meta:
        interfaces = (PostReportInterface,)

    @classmethod
    def is_type_of(cls, report, info):
        return type(report) is reports.StandardPostReport

    engagements = fields.Field(Engagements)
    engagement_rate = fields.Field("Percent")
    impressions = fields.Field(Impressions)
    projected_cpe = fields.Field("Currency", description="The projected cost per engagement")

    def resolve_projected_cpe(report, info):
        cpe = report.projected_cpe
        if cpe:
            currency = report.post.campaign.market.currency
            return Currency(amount=cpe, currency=currency, currency_digits=True)


class StoryPostReport(ObjectType):
    class Meta:
        interfaces = (PostReportInterface,)

    @classmethod
    def is_type_of(cls, report, info):
        return type(report) is reports.StoryPostReport

    actions = fields.Field(Actions)
    story_impressions = fields.Int(source="impressions")
    projected_cpe = fields.Field("Currency", description="The projected cost per engagement")

    def resolve_projected_cpe(report, info):
        cpe = report.projected_cpe
        if cpe:
            currency = report.post.campaign.market.currency
            return Currency(amount=cpe, currency=currency, currency_digits=True)


class VideoPostReport(ObjectType):
    class Meta:
        interfaces = (PostReportInterface,)

    @classmethod
    def is_type_of(cls, report, info):
        return type(report) is reports.VideoPostReport

    engagements = fields.Field(Engagements)
    engagement_rate = fields.Field("Percent")
    impressions = fields.Field(Impressions)
    video_views = fields.Int()
    video_view_rate = fields.Field("Percent")
    projected_cpv = fields.Field("Currency", description="The projected cost per view")

    def resolve_projected_cpv(report, info):
        cpv = report.projected_cpv
        if cpv:
            currency = report.post.campaign.market.currency
            return Currency(amount=cpv, currency=currency, currency_digits=True)
