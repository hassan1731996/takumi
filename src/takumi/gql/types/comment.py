from flask_login import current_user
from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Node


class Comment(ObjectType):
    class Meta:
        interfaces = (Node,)

    content = fields.String()
    creator = fields.Field("User")
    created = fields.String()
    seen = fields.Boolean()

    def resolve_seen(comment, info):
        return comment.seen_by_user(current_user.id)
