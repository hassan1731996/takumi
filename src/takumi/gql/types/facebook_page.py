from graphene import ObjectType

from takumi.gql import fields


class FacebookPage(ObjectType):
    id = fields.String(description="The ID of the facebook page")
    name = fields.String(description="The name of the facebook page")
    active = fields.Boolean()
    profile_picture = fields.String(description="Profile Picture of the facebook page")

    instagram_account = fields.Field("InstagramAccount")
