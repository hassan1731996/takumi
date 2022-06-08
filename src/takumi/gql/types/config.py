from graphene import ObjectType

from takumi.gql import fields


class Config(ObjectType):
    created = fields.DateTime()
    modified = fields.DateTime()

    key = fields.String()
    value = fields.GenericScalar()
