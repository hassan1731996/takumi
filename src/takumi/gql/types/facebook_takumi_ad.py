from graphene import ObjectType

from takumi.gql import fields


class FacebookTakumiAd(ObjectType):
    id = fields.String(description="The ID of the ad")
    ad_id = fields.String(description="Facebook Ad ID")
    campaign_id = fields.String(description="Facebook Campaign ID")
    adset_id = fields.String(description="Facebook AdSet ID")
    account_id = fields.String(description="Facebook AdAccount ID")
    url = fields.String(description="URL in Ads Manager")
    error = fields.String(description="Error message")
