from flask_login import current_user
from graphene import ObjectType

from takumi.extensions import get_locale
from takumi.gql import fields
from takumi.gql.relay import Connection, Node


class Announcement(ObjectType):
    class Meta:
        interfaces = (Node,)

    id = fields.ID(required=True)
    created = fields.DateTime()
    title = fields.String(description="Announcement title")
    message = fields.String(description="Announcement message")
    type = fields.String(description="Announcement type")
    seen = fields.Boolean()
    button_action = fields.String()
    button_action_props = fields.GenericScalar()

    def resolve_title(root, info):
        locale = get_locale()
        return root.translations.get(locale, {}).get("title", root.title)

    def resolve_message(root, info):
        locale = get_locale()
        return root.translations.get(locale, {}).get("message", root.message)

    def resolve_seen(root, info):
        influencer = current_user.influencer
        if not influencer:
            return False
        return root.seen_by_influencer(influencer)


class AnnouncementConnection(Connection):
    class Meta:
        node = Announcement
