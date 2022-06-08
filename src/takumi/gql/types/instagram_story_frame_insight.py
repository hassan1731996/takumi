from graphene import ObjectType

from takumi.gql import fields


class InstagramStoryFrameInsight(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()

    # Story
    exits = fields.Int()
    impressions = fields.Int()
    reach = fields.Int()
    replies = fields.Int()
    taps_forward = fields.Int()
    taps_back = fields.Int()
