from graphene import ObjectType

from takumi.gql import fields


class FacebookCampaign(ObjectType):
    id = fields.String(description="The ID of the campaign")
    name = fields.String(description="The name of the campaign")
    takumi_creative = fields.Boolean(description="Does this campaign include ads from Takumi")
    insights = fields.Field("Insights")
