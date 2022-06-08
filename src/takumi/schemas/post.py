from marshmallow import Schema, fields

from .fields import PercentField
from .percent import PercentSchema
from .user import AdvertiserInfluencerUserSchema


class GigStateField(fields.String):
    """This is a mobile client facing state field intended to mask certain
    states which the client does not need to see, nor can display.  This
    allows us to add more states on the server side while hiding the complexity
    from the mobile clients.
    """

    client_state_mask = {"reported": "submitted", "payment_processing": "paid"}
    legacy_state_mask = {"awaiting_submission": "reserved", "awaiting_shipping": "await_shipping"}

    def _serialize(self, value, attr, obj):
        state_mask = self.client_state_mask.copy()

        # Mask out the new states for the mobile clients. When there's a final
        # version of the app that supports the new states, this state mask
        # should be behind a check for takumi.vsapi.get_request_version < (3, X, X)
        state_mask.update(self.legacy_state_mask)

        if value in state_mask:
            value = state_mask[value]
        return super()._serialize(value, attr, obj)


class ReportSchema(Schema):
    reason = fields.String()
    reported = fields.Bool()


class ConfirmSchema(Schema):
    reason = fields.String()
    confirmed = fields.Bool()


class RejectSchema(Schema):
    reason = fields.String()
    rejected = fields.Bool()


class PictureSchema(Schema):
    url = fields.String()


class ConditionSchema(Schema):
    type = fields.String()
    value = fields.String()
    max_position = fields.Integer()


class ValueCountSchema(Schema):
    count = fields.Integer()
    value = fields.String()


class GigSchema(Schema):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()
    media = fields.Function(lambda obj: len(obj.media) > 0 and obj.media or None)
    user = fields.Nested(AdvertiserInfluencerUserSchema())
    engagement = PercentField(PercentSchema())
    reject = fields.Nested(RejectSchema())
    state = GigStateField()
    address_missing = fields.Boolean()
    can_cancel = fields.Boolean()
    sentiment = PercentField(PercentSchema())
    is_overdue = fields.Boolean()

    class Meta:
        additional = ("reach", "likes", "comments")


class PushNotification(Schema):
    id = fields.UUID()
    message = fields.String()
