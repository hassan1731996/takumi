from flask_login import current_user
from graphene import ObjectType

from takumi.gql import fields


class FacebookAccount(ObjectType):
    id = fields.String(description="The ID of the account")
    name = fields.String(description="The name of the account")
    facebook_page = fields.Field("FacebookPage")
    facebook_pages = fields.List("FacebookPage")

    def resolve_name(root, info):
        return root.facebook_name

    def resolve_facebook_page(root, info):
        if not current_user.influencer:
            return None
        if not current_user.influencer.instagram_account:
            return None
        facebook_page = current_user.influencer.instagram_account.facebook_page
        if not facebook_page and current_user.influencer.username == "joemoidustein":
            return dict(id="123", name="Joe's Page")
        if facebook_page and not facebook_page.active:
            return None
        return facebook_page
