# flake8: noqa

from marshmallow import Schema

from .address import InfluencerAddressSchema
from .bank import TransferDestination
from .email_login import EmailLoginSchema
from .fields import IbanField
from .influencer import InfluencerSchema
from .instagram_account import InstagramAccountSchema
from .post import GigSchema
from .region import RegionSchema
from .signup import SignupFormSchema
from .user import (
    AdvertiserInfluencerUserSchema,
    SelfInfluencerSchema,
    SelfUserSchema,
    UserSettingsSchema,
)
