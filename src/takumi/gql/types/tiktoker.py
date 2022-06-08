from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection, Node


class Tiktoker(ObjectType):
    class Meta:
        interfaces = (Node,)

    # Public fields
    id = fields.ID(required=True)
    username = fields.String()
    nickname = fields.String()
    cover = fields.String()
    original_cover = fields.String()
    signature = fields.String()

    followers = fields.Int()
    following = fields.Int()
    digg = fields.Int()
    likes = fields.Int()
    video_count = fields.Int()

    is_verified = fields.Boolean()
    is_secret = fields.Boolean()

    # Non public
    is_active = fields.ViewInfluencerInfoField(fields.Boolean)

    median_plays = fields.ViewInfluencerInfoField(fields.Int)
    mean_plays = fields.ViewInfluencerInfoField(fields.Int)
    median_diggs = fields.ViewInfluencerInfoField(fields.Int)
    mean_diggs = fields.ViewInfluencerInfoField(fields.Int)
    median_shares = fields.ViewInfluencerInfoField(fields.Int)
    mean_shares = fields.ViewInfluencerInfoField(fields.Int)
    median_comments = fields.ViewInfluencerInfoField(fields.Int)
    mean_comments = fields.ViewInfluencerInfoField(fields.Int)


class CountByResults(ObjectType):
    key = fields.String()
    followers = fields.Int()
    count = fields.Int()


class CountBy(ObjectType):
    field = fields.String()
    results = fields.List(CountByResults)


class TiktokerConnection(Connection):
    class Meta:
        node = Tiktoker
