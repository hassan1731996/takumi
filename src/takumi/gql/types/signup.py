from graphene import ObjectType

from takumi.gql import fields


class NextSignup(ObjectType):
    count = fields.Int()
    next = fields.String()
