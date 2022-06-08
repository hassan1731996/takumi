from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Node


class TimeZone(ObjectType):
    class Meta:
        interfaces = (Node,)

    name = fields.String()
    utc_offset = fields.Int()
