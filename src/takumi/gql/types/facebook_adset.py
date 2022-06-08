from graphene import ObjectType

from takumi.gql import fields


class FacebookAdSet(ObjectType):
    id = fields.String(description="The ID of the adset")
    name = fields.String(description="The name of the adset")
    takumi_creative = fields.Boolean(description="Does this adset include ads from Takumi")
    insights = fields.Field("Insights")
