import graphene

from takumi.gql.history import history_types
from takumi.gql.mutation import Mutation, PublicMutation
from takumi.gql.query import PublicQuery, Query
from takumi.gql.types.brief import brief_types
from takumi.gql.types.insight import PostInsight, StoryInsight
from takumi.gql.types.instagram_story import InstagramStory
from takumi.gql.types.report import StandardPostReport, StoryPostReport, VideoPostReport

schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
    types=[
        *history_types,
        *brief_types,
        PostInsight,
        StoryInsight,
        StandardPostReport,
        StoryPostReport,
        VideoPostReport,
    ],
)
public_schema = graphene.Schema(
    query=PublicQuery, mutation=PublicMutation, types=[*brief_types, InstagramStory]
)
