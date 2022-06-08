from marshmallow import Schema, fields

from .fields import PercentField
from .percent import PercentSchema


class InstagramAccountSchema(Schema):
    username = fields.String(attribute="ig_username")
    biography = fields.String(attribute="ig_biography")

    is_private = fields.Boolean(attribute="ig_is_private")

    followers = fields.Integer()
    following = fields.Integer(attribute="follows")  # TODO: Rename this in the model
    media_count = fields.Integer()
    scraped_email = fields.String(default=None)

    engagement = PercentField(PercentSchema())
    hashtags = fields.Dict()
