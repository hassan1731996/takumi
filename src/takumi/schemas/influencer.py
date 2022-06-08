from marshmallow import Schema, fields

from .address import InfluencerAddressSchema
from .instagram_account import InstagramAccountSchema


class TotalRewardsSchema(Schema):
    amount = fields.Integer(attribute="value")
    currency = fields.String()
    formatted_amount = fields.String(attribute="formatted_value")


class InfluencerSchema(Schema):
    id = fields.UUID()
    instagram_account = fields.Nested(InstagramAccountSchema())
    username = fields.String()
    provider_alias = fields.String()
    address = fields.Nested(InfluencerAddressSchema())
    has_address = fields.Boolean()
    total_rewards = fields.Nested(TotalRewardsSchema())
    deletion_date = fields.DateTime()
    is_signed_up = fields.Boolean()

    followers = fields.Integer()
    engagement = fields.Float()
    ig_biography = fields.String()
    media_count = fields.Integer()
