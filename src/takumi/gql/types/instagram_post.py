import uuid

from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.interfaces import ContentInterface
from takumi.gql.types.instagram_content import InstagramContentInterface
from takumi.roles import permissions
from takumi.roles.needs import manage_influencers


class InstagramPost(ObjectType):
    class Meta:
        interfaces = (ContentInterface, InstagramContentInterface)

    ig_post_id = fields.String()

    sponsors = fields.List(fields.String)

    shortcode = fields.String()
    link = fields.String()
    deleted = fields.AuthenticatedField(fields.Boolean, needs=manage_influencers)

    likes = fields.Int()
    comments = fields.Int()
    video_views = fields.Int()
    sentiment = fields.Float()
    engagement = fields.Field("Percent")

    instagram_post_insight = fields.Field(
        "InstagramPostInsight", fetch_if_not_available=fields.Boolean()
    )

    reach = fields.Int(deprecation_reason="Use followers", source="followers")

    def resolve_id(root, info):
        return uuid.UUID(int=int(root.ig_post_id))

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.instagram_post import InstagramPost

        return isinstance(root, InstagramPost)

    def resolve_instagram_post_insight(root, info, fetch_if_not_available=False):
        if not permissions.team_member.can():
            return None
        if not root.instagram_post_insight and fetch_if_not_available:
            root.update_instagram_insights()
        return root.instagram_post_insight
