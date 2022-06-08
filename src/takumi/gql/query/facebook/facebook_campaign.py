from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookCampaignQuery:
    facebook_campaign = fields.Field("FacebookCampaign", id=arguments.String(required=True))

    facebook_campaigns_for_ad_account = fields.List(
        "FacebookCampaign",
        account_id=arguments.String(required=True),
        page=arguments.Int(),
        include_insights=arguments.Boolean(),
        only_takumi=arguments.Boolean(),
    )

    @permissions.public.require()
    def resolve_facebook_campaign(root, info, id):
        return FacebookService(current_user.facebook_account).get_campaign(id)

    @permissions.public.require()
    def resolve_facebook_campaigns_for_ad_account(
        root, info, account_id, page=0, include_insights=False, only_takumi=False
    ):
        return FacebookService(current_user.facebook_account).get_campaigns(
            account_id, include_insights=include_insights, page=page, only_takumi=only_takumi
        )
