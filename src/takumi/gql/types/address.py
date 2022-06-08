from graphene import ObjectType

from takumi.gql import fields


class Address(ObjectType):
    id = fields.UUID()
    name = fields.String()
    address1 = fields.String()
    address2 = fields.String()
    city = fields.String()
    postal_code = fields.String()
    phonenumber = fields.String()
    country = fields.String()
    state = fields.String()
    is_commercial = fields.Boolean()
    is_pobox = fields.Boolean()
