from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.interfaces import ContentInterface
from takumi.gql.types.instagram_content import InstagramContentInterface


class InstagramReel(ObjectType):
    class Meta:
        interfaces = (ContentInterface, InstagramContentInterface)

    link = fields.String()

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.instagram_reel import InstagramReel

        return isinstance(root, InstagramReel)
