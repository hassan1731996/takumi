from flask_login import current_user

from takumi.gql import fields
from takumi.roles import permissions
from takumi.services import FacebookService


class FacebookPagesQuery:
    facebook_pages = fields.List("FacebookPage")

    @permissions.public.require()
    def resolve_facebook_pages(root, info):
        return FacebookService(current_user.facebook_account).get_pages()
