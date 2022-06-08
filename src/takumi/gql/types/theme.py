from graphene import ObjectType

from takumi.gql import fields


class Theme(ObjectType):
    id = fields.UUID()
    logo_url = fields.String()
