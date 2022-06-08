from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookAdAccountQuery:
    facebook_ad_account = fields.Field("FacebookAdAccount", id=arguments.String(required=True))
    facebook_ad_accounts = fields.List("FacebookAdAccount")

    @permissions.public.require()
    def resolve_facebook_ad_account(root, info, id):
        return FacebookService(current_user.facebook_account).get_ad_account(id)

    @permissions.public.require()
    def resolve_facebook_ad_accounts(root, info):
        return FacebookService(current_user.facebook_account).get_ad_accounts()
