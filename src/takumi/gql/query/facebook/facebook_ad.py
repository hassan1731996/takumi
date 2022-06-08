from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookAdQuery:
    facebook_ad = fields.Field("FacebookAd", id=arguments.String(required=True))

    facebook_ads_for_facebook_adset = fields.List(
        "FacebookAd",
        adset_id=arguments.String(required=True),
        page=arguments.Int(),
        include_insights=arguments.Boolean(),
        only_takumi=arguments.Boolean(),
    )

    @permissions.public.require()
    def resolve_facebook_ad(root, info, id):
        return FacebookService(current_user.facebook_account).get_ad(id)

    @permissions.public.require()
    def resolve_facebook_ads_for_facebook_adset(
        root, info, adset_id, page=0, include_insights=False, only_takumi=False
    ):
        return FacebookService(current_user.facebook_account).get_ads(
            adset_id, include_insights=include_insights, page=page, only_takumi=only_takumi
        )
