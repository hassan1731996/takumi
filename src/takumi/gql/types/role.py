from graphene import ObjectType

from takumi.gql import fields


class Role(ObjectType):
    name = fields.String()
    needs = fields.List(fields.String)

    def resolve_needs(role, info):
        return (need.value for need in role.needs)
