from graphene import ObjectType

from takumi.gql import fields


class TaxForm(ObjectType):
    id = fields.UUID()
    state = fields.String()
    number = fields.String()
    url = fields.String()
    influencer = fields.Field("Influencer")
