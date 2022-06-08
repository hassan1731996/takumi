from graphene import ObjectType

from takumi.gql import fields


class Device(ObjectType):
    id = fields.UUID()
    active = fields.Boolean()
    build_version = fields.String()
    created = fields.DateTime()
    device_model = fields.String()
    last_used = fields.DateTime()
    os_version = fields.String()
    platform = fields.String()
