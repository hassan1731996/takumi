from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.db import filter_campaigns
from takumi.gql.relay import Connection, Node
from takumi.models import Campaign


class Advertiser(ObjectType):
    class Meta:
        interfaces = (Node,)

    name = fields.String(description="Name")
    domain = fields.String(description="Url-safe slug")
    profile_picture = fields.String(description="Profile picture")
    archived = fields.Boolean()
    vat_number = fields.String(description="Vat number")
    fb_ad_account_id = fields.AdvertiserField(fields.String)
    sf_account_id = fields.AdvertiserField(fields.String)
    primary_region = fields.Field("Region")
    influencer_cooldown = fields.AdvertiserField(
        fields.Int,
        description="An influencer must wait this many days before reserving another campaign by this brand",
    )
    campaigns = fields.List("Campaign")
    instagram_user = fields.String()

    def resolve_campaigns(root, info):
        campaign_query = Campaign.query.filter(Campaign.advertiser == root)
        return filter_campaigns(campaign_query)

    def resolve_instagram_user(root, info):
        return root.info.get("instagram", {}).get("user", None)


class AdvertiserConnection(Connection):
    class Meta:
        node = Advertiser
