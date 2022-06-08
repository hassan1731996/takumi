from graphene import ObjectType

from takumi.gql import fields


class Market(ObjectType):
    slug = fields.String()
    name = fields.String()
    regions = fields.List("Region")
    default_locale = fields.String()
    default_timezone = fields.String()
    timezone_choices = fields.List(fields.String)

    currency = fields.String()
