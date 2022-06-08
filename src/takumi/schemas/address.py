from marshmallow import Schema, fields


class InfluencerAddressSchema(Schema):
    id = fields.UUID()
    name = fields.String(default="")
    address1 = fields.String(default="")
    address2 = fields.String(default="")
    city = fields.String(default="")
    postal_code = fields.String(default="")
    country = fields.String(default="")
    state = fields.String(default="", allow_none=True)
    phonenumber = fields.String(default="", allow_none=True)
    is_pobox = fields.Boolean(default=False)
