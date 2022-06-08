from graphene import ObjectType

from takumi.gql import fields


class InstagramAPIMediaInsights(ObjectType):
    engagement = fields.Int(required=False)
    impressions = fields.Int(required=False)
    reach = fields.Int(required=False)
    saved = fields.Int(required=False)


class InstagramAPIMedia(ObjectType):
    comments_count = fields.Int(required=True)
    like_count = fields.Int(required=True)
    id = fields.String(required=True)
    media_url = fields.String(required=True)
    timestamp = fields.String(required=True)
    permalink = fields.String(required=True)
    insights = fields.Field(InstagramAPIMediaInsights, required=True)


class InstagramAPIProfile(ObjectType):
    biography = fields.String(required=True)
    id = fields.String(required=True)
    followers_count = fields.Int(required=True)
    follows_count = fields.Int(required=True)
    media_count = fields.Int(required=True)
    name = fields.String(required=True)
    profile_picture_url = fields.String(required=True)
    username = fields.String(required=True)
    website = fields.String(required=True)
    media = fields.List(InstagramAPIMedia, required=True)
