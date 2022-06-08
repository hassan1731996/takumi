from graphene import ObjectType

from takumi.gql import fields


class FacebookAd(ObjectType):
    id = fields.String(description="The ID of the ad")
    name = fields.String(description="The name of the ad")
    takumi_creative = fields.Boolean(description="Does this ad include ads from Takumi")
    insights = fields.Field("Insights")
