from graphene import ObjectType

from takumi.gql import fields


class AdvertiserConfig(ObjectType):
    id = fields.UUID()
    advertiser_id = fields.UUID()
    impressions = fields.Boolean()
    engagement_rate = fields.Boolean()
    benchmarks = fields.Boolean()
    campaign_type = fields.Boolean()
    budget = fields.Boolean()
    view_rate = fields.Boolean()
    brand_campaigns_page = fields.Boolean()
    dashboard_page = fields.Boolean()
