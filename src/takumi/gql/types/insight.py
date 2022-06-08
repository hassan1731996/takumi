from graphene import Interface, ObjectType
from graphene.utils.str_converters import to_camel_case

from takumi.gql import arguments, fields
from takumi.gql.relay import Connection
from takumi.models.insight import TYPES
from takumi.services.insight import InsightService


class InsightInterface(Interface):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()

    media = fields.Field("MediaResult")
    gig = fields.Field("Gig")
    processed = fields.Boolean()
    state = fields.String()

    reach = fields.Int()

    impressions = fields.Int()
    interactions = fields.Int()
    profile_visits = fields.Int()

    follows = fields.Int()

    ocr_values = fields.GenericScalar()

    def resolve_media(insight, info):
        media_length = len(insight.media)
        if media_length > 1:
            return insight.media
        elif media_length == 1:
            return insight.media[0]
        return None

    def resolve_type(insight, info):
        if insight.type == TYPES.STORY_INSIGHT:
            return "StoryInsight"

        if insight.type == TYPES.POST_INSIGHT:
            return "PostInsight"

        return None

    def resolve_ocr_values(insight, info):
        return {to_camel_case(key): value for key, value in insight.ocr_values.items()}


class StoryInsight(ObjectType):
    class Meta:
        interfaces = (InsightInterface,)

    views = fields.Int()

    shares = fields.Int()
    replies = fields.Int()

    link_clicks = fields.Int()
    sticker_taps = fields.Int()

    impressions = fields.Int()

    back_navigations = fields.Int()
    forward_navigations = fields.Int()
    next_story_navigations = fields.Int()
    exited_navigations = fields.Int()
    website_clicks = fields.Int()
    emails = fields.Int()

    @classmethod
    def is_type_of(cls, insight, info):
        from takumi.models.insight import StoryInsight

        return isinstance(insight, StoryInsight)


class PostInsight(ObjectType):
    class Meta:
        interfaces = (InsightInterface,)

    non_followers_reach = fields.Float()

    def resolve_non_followers_reach(insight, info):
        """Clients use the non followers reach as whole percent numbers"""
        if insight.non_followers_reach is None:
            return None
        return insight.non_followers_reach * 100

    likes = fields.Int()
    comments = fields.Int()
    shares = fields.Int()
    bookmarks = fields.Int()

    website_clicks = fields.Int()
    replies = fields.Int()
    calls = fields.Int()
    emails = fields.Int()
    get_directions = fields.Int()

    from_hashtags_impressions = fields.Int()
    from_home_impressions = fields.Int()
    from_profile_impressions = fields.Int()
    from_explore_impressions = fields.Int()
    from_location_impressions = fields.Int()
    from_other_impressions = fields.Int()

    total_impressions = fields.Int()

    def resolve_total_impressions(insight, info):
        return (
            insight.from_hashtags_impressions
            + insight.from_home_impressions
            + insight.from_profile_impressions
            + insight.from_explore_impressions
            + insight.from_location_impressions
            + insight.from_other_impressions
        )

    @classmethod
    def is_type_of(cls, insight, info):
        from takumi.models.insight import PostInsight

        return isinstance(insight, PostInsight)


class InsightConnection(Connection):
    class Meta:
        node = InsightInterface

    insights_count = fields.Int(
        args=dict(
            processed=arguments.Boolean(description="Filter by processed or not"),
            campaign_id=arguments.UUID(description="Filter by campaign id"),
            post_id=arguments.UUID(description="Filter by post id"),
            mine=arguments.Boolean(description="Filter by insights in my campaigns"),
            region=arguments.UUID(description="Filter by insights by country"),
        )
    )

    def resolve_insights_count(insights, info, **kwargs):
        """Get all insights count by filters.

        Args:
            insights: All insights.
            info: Graphql additional info.
            kwargs: Provided filters.

        Retruns:
            Count of all filtered insights.
        """
        return InsightService.get_insights(kwargs).count()
