from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.interfaces import ContentInterface


class Submission(ObjectType):
    class Meta:
        interfaces = (ContentInterface,)

    transcoded = fields.Boolean()
