from graphene import Interface, ObjectType

from takumi.extensions import instascrape
from takumi.gql import fields
from takumi.gql.relay import Connection, Node
from takumi.ig.instascrape import NotFound


def get_media(influencer):
    try:
        return instascrape.get_user_media(influencer.username)["data"]
    except NotFound:
        return []


class InfluencerWithMediaInterface(Interface):
    influencer = fields.Field("InstagramUser")
    media = fields.List("InstagramMedia")


class InfluencerWithMedia(ObjectType):
    class Meta:
        interfaces = (Node, InfluencerWithMediaInterface)


class ReviewedInfluencer(ObjectType):
    class Meta:
        interfaces = (Node, InfluencerWithMediaInterface)

    def resolve_influencer(influencer, info):
        return influencer

    def resolve_media(influencer, info):
        return get_media(influencer)


class Suggestion(ObjectType):
    class Meta:
        interfaces = (Node, InfluencerWithMediaInterface)

    def resolve_influencer(influencer, info):
        return influencer.info["data"]

    def resolve_media(influencer, info):
        return influencer.info["data"]["media"]["nodes"]


class IdentifiedInfluencer(ObjectType):
    class Meta:
        interfaces = (Node,)

    influencer = fields.Field("InstagramUser")
    next = fields.String()


class SuggestionConnection(Connection):
    class Meta:
        node = Suggestion


class InfluencerWithMediaConnection(Connection):
    class Meta:
        node = InfluencerWithMedia


class ReviewedInfluencerConnection(Connection):
    class Meta:
        node = ReviewedInfluencer
