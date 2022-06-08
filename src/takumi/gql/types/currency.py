from graphene import ObjectType

from takumi.gql import fields


class Currency(ObjectType):
    value = fields.Float()
    formatted_value = fields.String()
    symbol = fields.String()
    currency = fields.String()
