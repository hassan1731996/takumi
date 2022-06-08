from graphene import ObjectType

from takumi.gql import fields


class AdvertiserIndustryChild(ObjectType):
    id = fields.UUID()
    title = fields.String()
    active = fields.Boolean()


class AdvertiserIndustry(ObjectType):
    id = fields.UUID()
    title = fields.String()
    children = fields.List(lambda: AdvertiserIndustryChild)
