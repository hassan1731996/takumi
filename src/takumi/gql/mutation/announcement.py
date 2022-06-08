from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import GraphQLException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_announcement_or_404
from takumi.roles import permissions


class SeeAnnouncement(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    announcement = fields.Field("Announcement")

    @permissions.influencer.require()
    def mutate(root, info, id):
        influencer = current_user.influencer
        if not influencer:
            raise GraphQLException("User is not an Influencer!")
        announcement = get_announcement_or_404(id)
        announcement.see_announcement(influencer)
        return SeeAnnouncement(ok=True, announcement=announcement)


class AnnouncementMutation:
    see_announcement = SeeAnnouncement.Field()
