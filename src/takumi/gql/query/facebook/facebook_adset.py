from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookAdSetQuery:
    facebook_adset = fields.Field("FacebookAdSet", id=arguments.String(required=True))

    facebook_adsets_for_facebook_campaign = fields.List(
        "FacebookAdSet",
        campaign_id=arguments.String(required=True),
        page=arguments.Int(),
        include_insights=arguments.Boolean(),
        only_takumi=arguments.Boolean(),
    )

    @permissions.public.require()
    def resolve_facebook_adset(root, info, id):
        return FacebookService(current_user.facebook_account).get_adset(id)

    @permissions.public.require()
    def resolve_facebook_adsets_for_facebook_campaign(
        root, info, campaign_id, page=0, include_insights=False, only_takumi=False
    ):
        return FacebookService(current_user.facebook_account).get_adsets(
            campaign_id, include_insights=include_insights, page=page, only_takumi=only_takumi
        )
