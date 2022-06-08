from flask_login import current_user

from takumi.gql import fields
from takumi.models import Announcement
from takumi.roles import permissions


class AnnouncementQuery:
    announcements = fields.ConnectionField("AnnouncementConnection")

    @permissions.public.require()
    def resolve_announcements(root, info, **params):
        announcements = Announcement.query
        influencer = current_user.influencer
        if influencer:
            announcements = announcements.filter(
                ~Announcement.seen_by_influencer(influencer), Announcement.active
            )
        return announcements.order_by(Announcement.created)
