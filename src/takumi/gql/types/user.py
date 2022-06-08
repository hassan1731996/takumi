from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection, Node


class Settings(ObjectType):
    instagram_username = fields.String()


class User(ObjectType):
    class Meta:
        interfaces = (Node,)

    full_name = fields.String()
    birthday = fields.String()
    email = fields.String(resolver=fields.deep_source_resolver("email_login.email"))
    has_accepted_invite = fields.Boolean(
        resolver=fields.deep_source_resolver("email_login.verified")
    )
    invite_ttl = fields.Int(resolver=fields.deep_source_resolver("email_login.time_to_live"))
    has_invitation_sent = fields.Boolean(
        resolver=fields.deep_source_resolver("email_login.has_invitation_sent")
    )
    has_facebook_account = fields.Boolean()
    profile_picture = fields.String()
    role_name = fields.String()
    ig_username = fields.String()
    settings = fields.Field(Settings)
    email_notification_preference = fields.String()
    influencer = fields.Field("Influencer")
    feature_flags = fields.GenericScalar()

    theme = fields.Field("Theme")

    facebook_account = fields.Field("FacebookAccount")

    def resolve_facebook_account(user, info):
        facebook_account = user.facebook_account
        if facebook_account and facebook_account.active:
            return facebook_account
        return None


class UserConnection(Connection):
    class Meta:
        node = User


class UserCount(ObjectType):
    user = fields.Field(User)
    count = fields.Int()
