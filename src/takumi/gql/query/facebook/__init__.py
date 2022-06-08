from flask import current_app
from graphene import ObjectType

from takumi.constants import FACEBOOK_INFLUENCER_SCOPE
from takumi.gql import fields
from takumi.roles import permissions

from .facebook_ad import FacebookAdQuery  # noqa
from .facebook_ad_account import FacebookAdAccountQuery  # noqa
from .facebook_adset import FacebookAdSetQuery  # noqa
from .facebook_campaign import FacebookCampaignQuery  # noqa
from .facebook_page import FacebookPagesQuery  # noqa
from .facebook_takumi_ad import FacebookTakumiAdQuery  # noqa


class FacebookApp(ObjectType):
    id = fields.String(description="APP ID")
    influencer_scope = fields.List(fields.String)


class FacebookAppQuery:
    facebook_app = fields.Field(FacebookApp)

    @permissions.public.require()
    def resolve_facebook_app(root, info):
        return dict(
            id=current_app.config["FACEBOOK_APP_ID"], influencer_scope=FACEBOOK_INFLUENCER_SCOPE
        )
