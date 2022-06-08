from graphene import Interface

from takumi import models
from takumi.gql import fields
from takumi.gql.db import filter_influencers
from takumi.gql.fields import resolve_field_value
from takumi.ig.utils import calculate_engagement_median
from takumi.models import InstagramAccount


class InstagramUserInterface(Interface):
    id = fields.ID(required=True)
    username = fields.String()
    email = fields.String()
    profile_picture = fields.String()
    full_name = fields.String()
    is_private = fields.Boolean()
    biography = fields.String()
    followers = fields.Int()
    following = fields.Int()
    is_signed_up = fields.Boolean()
    engagement = fields.Field("Percent")

    def resolve_id(root, info):
        return root.get("username")

    def resolve_engagement(root, info):
        return calculate_engagement_median(root)

    def resolve_is_signed_up(root, info):
        username = resolve_field_value("username", root, info)

        if not username:
            return False

        influencer = (
            filter_influencers().filter(InstagramAccount.ig_username == username).one_or_none()
        )
        return influencer is not None and influencer.is_signed_up

    @classmethod
    def resolve_type(cls, instance, info):
        from takumi.gql.types import Influencer, InstagramUser

        if isinstance(instance, models.Influencer):
            return Influencer
        return InstagramUser
