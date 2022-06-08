"""Schema classes with the `Admin` prefix are meant for team member admin
endpoints.

"""


from marshmallow import Schema, fields, pre_dump

from takumi.roles.needs import access_app_development_menu

from .email_login import EmailLoginSchema
from .influencer import InfluencerSchema
from .influencer_info import InfluencerInfoSchema
from .region import RegionSchema


class UserSchema(Schema):
    id = fields.UUID()
    birthday = fields.Date()
    gender = fields.String(allow_none=True)
    full_name = fields.String()
    profile_picture = fields.Method("get_profile_picture")

    tiktok_username = fields.String()
    youtube_channel_url = fields.String()

    def get_profile_picture(self, obj):
        if obj.influencer:
            return obj.influencer.profile_picture
        return None


class UserSettingsSchema(Schema):
    default_region = fields.Nested(RegionSchema(only=("id",)), allow_none=True, default=None)
    demo_mode = fields.Boolean(default=False)
    instagram_username = fields.String()
    calendly_username = fields.String()


class AdvertiserInfluencerUserSchema(UserSchema):
    """Only used when advertisers are viewing gigs."""

    influencer = fields.Nested(InfluencerSchema())


class NeedSchema(Schema):
    value = fields.String()


class RoleSchema(Schema):
    name = fields.String()
    needs = fields.Nested(NeedSchema, only=("value",), many=True)


class SelfUserSchema(UserSchema):
    email_login = fields.Nested(EmailLoginSchema())
    is_advertiser = fields.Boolean(default=True)
    is_influencer = fields.Boolean(default=False)
    settings = fields.Nested(UserSettingsSchema())
    role = fields.Nested(RoleSchema())


class FeatureFlags(Schema):
    USE_REVOLUT = fields.Boolean(default=False)


class SelfInfluencerSchema(UserSchema):
    influencer = fields.Nested(InfluencerSchema())

    # Promote `user.influencer.info` to `user.settings`.
    settings = fields.Nested(InfluencerInfoSchema())
    email = fields.String()

    is_disabled = fields.Boolean(default=False)
    is_advertiser = fields.Boolean(default=False)
    is_influencer = fields.Boolean(default=True)
    is_team_member = fields.Boolean(default=False)

    feature_flags = fields.Nested(FeatureFlags)

    @pre_dump
    def pull_disabled(self, obj):
        if hasattr(obj, "influencer"):
            if hasattr(obj.influencer, "disabled"):
                setattr(obj, "is_disabled", obj.influencer.disabled)

    @pre_dump
    def pull_is_team_member(self, obj):
        """XXX: this is a potential legacy feature for the mobile clients which check
        is_team_member on their user object to see if they should give access to the
        dev menu (and show some more details on the about screen).
        """
        setattr(obj, "is_team_member", obj.can(access_app_development_menu))
