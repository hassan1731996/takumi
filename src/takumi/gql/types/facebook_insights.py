from graphene import ObjectType

from takumi.gql import fields


class Insights(ObjectType):
    cpm = fields.String()
    reach = fields.String()
