from graphene import ObjectType

from takumi.gql import fields


class InstagramPostInsight(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()

    # Post
    engagement = fields.Int()
    impressions = fields.Int()
    reach = fields.Int()
    saved = fields.Int()

    # Video
    video_views = fields.Int()

    # Album
    carousel_album_engagement = fields.Int()
    carousel_album_impressions = fields.Int()
    carousel_album_reach = fields.Int()
    carousel_album_saved = fields.Int()
