from marshmallow import Schema, fields


class TransferDestination(Schema):
    type = fields.String(required=True, choices=("iban", "dwolla"))
    value = fields.String(required=True)
