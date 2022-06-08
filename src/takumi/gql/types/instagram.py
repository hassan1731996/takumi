from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.interfaces import InstagramUserInterface
from takumi.gql.relay import Connection


class InstagramUser(ObjectType):
    class Meta:
        interfaces = (InstagramUserInterface,)

    @classmethod
    def is_type_of(cls, root, info):
        # XXX: Instascrape should return types
        return isinstance(root, dict)


class InstagramUserConnection(Connection):
    class Meta:
        node = InstagramUser


class InstagramMedia(ObjectType):
    id = fields.String()
    type = fields.String()
    created = fields.String()
    code = fields.String()

    caption = fields.String()
    comments = fields.Int()
    likes = fields.Int()

    def resolve_comments(root, info):
        return root["comments"]["count"]

    def resolve_likes(root, info):
        return root["likes"]["count"]

    sponsors = fields.String()
    link = fields.String()
    url = fields.String()

    # XXX: Likely more, look into it
