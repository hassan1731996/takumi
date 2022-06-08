import datetime as dt

from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.gql.utils import get_gig_or_404, get_story_frame_or_404
from takumi.models import Influencer, StoryFrame
from takumi.roles import permissions
from takumi.services import InstagramStoryService


class StoryFrameQuery:
    story_frame = fields.Field("StoryFrame", id=arguments.UUID(required=True))
    story_frames_for_gig = fields.ConnectionField(
        "StoryFrameConnection",
        id=arguments.UUID(required=True, description="The gig ID"),
        date_from=arguments.DateTime(description="Datetime that filters out all older frames"),
        date_to=arguments.DateTime(description="Datetime that filters out all newer frames"),
    )

    story_frames_for_influencer = fields.ConnectionField(
        "StoryFrameConnection", username=arguments.String()
    )

    @permissions.manage_influencers.require()
    def resolve_story_frame(root, info, id):
        return get_story_frame_or_404(id)

    @permissions.public.require()
    def resolve_story_frames_for_influencer(root, info, username=None):
        if not permissions.manage_influencers.can() and (
            not current_user.influencer
            or (username != None and current_user.influencer.username != username)
        ):
            return []

        influencer = Influencer.by_username(username) if username else current_user.influencer

        if not influencer:
            raise QueryException("Influencer not found")

        return InstagramStoryService.download_story_frames(influencer.id, update_insights=False)

    @permissions.manage_influencers.require()
    def resolve_story_frames_for_gig(root, info, id, date_from=None, date_to=None):
        gig = get_gig_or_404(id)

        if date_from is None:
            date_from = gig.offer.accepted or gig.offer.created

        if date_to is None:
            date_to = dt.datetime.now(dt.timezone.utc)

        return StoryFrame.query.filter(
            StoryFrame.influencer_id == gig.offer.influencer_id,
            StoryFrame.created.between(date_from, date_to),
        ).order_by(StoryFrame.posted.desc(), StoryFrame.id)
