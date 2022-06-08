import datetime as dt

from dateutil.relativedelta import relativedelta
from marshmallow import Schema, ValidationError, fields, pre_load


def validate_birthday(value):
    if value > (dt.date.today() - relativedelta(years=18)):
        raise ValidationError("Must be at least 18 years old")
    if value < dt.date(1900, 1, 1):
        raise ValidationError("You must be alive to use Takumi")


class SignupFormSchema(Schema):
    full_name = fields.String(default=None)
    profile_picture = fields.String(default=None)
    gender = fields.String(default=None, allow_none=True)
    birthday = fields.Date(validate=validate_birthday, default=None)
    email = fields.Email(default=None)
    app_uri = fields.String(load_from="appUri")

    youtube_channel_url = fields.String(default=None)
    tiktok_username = fields.String(default=None)

    @pre_load
    def strip(self, item):
        if item.get("email"):
            item["email"] = item["email"].strip()
        return item
