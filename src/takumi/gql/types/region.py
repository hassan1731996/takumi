from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Node


class Region(ObjectType):
    class Meta:
        interfaces = (Node,)

    id = fields.ID(required=True)
    country = fields.String()
    country_code = fields.String()
    locale_code = fields.String()
    name = fields.String()
    supported = fields.Boolean()
    targetable = fields.Boolean()
    path = fields.List(fields.String)
    market_slug = fields.String()
    is_leaf = fields.Boolean()
