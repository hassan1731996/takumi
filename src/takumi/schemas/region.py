from marshmallow import Schema, fields


class RegionSchema(Schema):
    id = fields.UUID()
    path = fields.List(fields.UUID())
    locale_code = fields.String()
    country = fields.String()
    country_code = fields.String()
    name = fields.String()
