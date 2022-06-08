from marshmallow import Schema, fields

"""Schema class for user settings, to provide logic behing default setting values
"""


class InfluencerInfoSchema(Schema):
    """The schema should define all fields that can be in the user settings dictionary

    Fields can define a logic behind the default value by using a `fields.Method()` method,
    where they can access the user data through `self.context['user']`
    """

    has_accepted_latest_terms = fields.Method("get_latest_terms_bool")
    has_accepted_latest_privacy = fields.Method("get_latest_privacy_bool")

    def get_latest_terms_bool(self, obj):
        return self.context["user"].influencer.has_accepted_latest_terms

    def get_latest_privacy_bool(self, obj):
        return self.context["user"].influencer.has_accepted_latest_privacy
