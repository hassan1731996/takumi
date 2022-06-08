from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookTakumiAdQuery:
    facebook_takumi_ad = fields.Field("FacebookTakumiAd", id=arguments.UUID(required=True))

    @permissions.public.require()
    def resolve_facebook_takumi_ad(root, info, id):
        return FacebookService(current_user.facebook_account).get_takumi_ad_by_id(id)
