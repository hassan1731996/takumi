from marshmallow import Schema, fields


class EmailLoginSchema(Schema):
    email = fields.String()
    verified = fields.Boolean()
    time_to_live = fields.Integer(required=False)
