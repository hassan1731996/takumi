from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_gig_or_404, get_story_frame_or_404
from takumi.models import StoryFrame
from takumi.roles import permissions
from takumi.services import GigService, InstagramStoryService


class LinkStoryFramesToGig(Mutation):
    """Link story frames to a gig"""

    class Arguments:
        frame_ids = arguments.List(
            arguments.UUID, required=True, description="The ids of the story frames being marked"
        )
        gig_id = arguments.UUID(required=True, description="The id of the story frame being marked")
        overwrite = arguments.Boolean(default_value=False)

    story_frames = fields.List("StoryFrame")

    @permissions.review_gig.require()
    def mutate(root, info, frame_ids, gig_id, overwrite):
        gig = get_gig_or_404(gig_id)
        influencer_id = gig.offer.influencer_id

        if not permissions.review_gig.can():
            if influencer_id != current_user.influencer.id:
                raise MutationException(f"Gig ({gig_id}) not found")
            if gig.is_verified:
                raise MutationException("Story frames already verified")
            if gig.instagram_story and not gig.instagram_story.marked_posted_within_last_24_hours:
                raise MutationException(
                    "Cannot select story frames when 24 hours have passed since posting"
                )

        story_frames = StoryFrame.query.filter(
            StoryFrame.influencer_id == influencer_id, StoryFrame.id.in_(frame_ids)
        ).all()

        if gig.instagram_story is None:
            InstagramStoryService.create(gig_id)

        with InstagramStoryService(gig.instagram_story) as service:
            if overwrite:
                for story_frame in gig.instagram_story.story_frames:
                    if story_frame not in story_frames:
                        service.unlink_story_frame(story_frame.id)

            for story_frame in story_frames:
                service.link_story_frame(story_frame.id, verify=False)

        return LinkStoryFramesToGig(story_frames=story_frames, ok=True)


class LinkStoryFrameToGig(Mutation):
    """Link a story frame to a gig"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the story frame being marked")
        gig_id = arguments.UUID(required=True, description="The id of the story frame being marked")

    story_frame = fields.Field("StoryFrame")

    @permissions.review_gig.require()
    def mutate(root, info, id, gig_id):
        story_frames = LinkStoryFramesToGig().mutate(info, [id], gig_id, False).story_frames
        return LinkStoryFrameToGig(story_frame=next((f for f in story_frames), None), ok=True)


class UnlinkStoryFrameFromGig(Mutation):
    """Unlink a story frames from a gig"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the story frame being unlinked")

    story_frame = fields.Field("StoryFrame")

    @permissions.review_gig.require()
    def mutate(root, info, id):
        story_frame = get_story_frame_or_404(id)
        instagram_story = story_frame.instagram_story

        if instagram_story is None:
            raise MutationException("Story frame doesn't belong to story")

        with InstagramStoryService(instagram_story) as service:
            service.unlink_story_frame(story_frame.id)

        if not instagram_story.has_marked_frames:
            with GigService(instagram_story.gig) as service:
                service.mark_as_verified(False)

        return UnlinkStoryFrameFromGig(story_frame=story_frame, ok=True)


class CreateInstagramStoryFromSubmission(Mutation):
    """
    Takes a submission from a gig and creates an Instagram Story Post
    with story frames for each media of the submission marked as part of the campaign
    """

    class Arguments:
        id = arguments.UUID(
            required=True, description="The id of the gig to copy the submission from"
        )

    instagram_story = fields.Field("InstagramStory")

    @permissions.review_gig.require()
    def mutate(root, info, id):
        gig = get_gig_or_404(id)
        instagram_story = InstagramStoryService.copy_submission_to_story(gig.id)

        from takumi.services.gig import GigService

        with GigService(instagram_story.gig) as service:
            service.mark_as_verified(True)

        return CreateInstagramStoryFromSubmission(instagram_story=instagram_story, ok=True)


class InstagramStoryMutation:
    link_story_frame_to_gig = LinkStoryFrameToGig.Field()
    link_story_frames_to_gig = LinkStoryFramesToGig.Field()
    unlink_story_frame_from_gig = UnlinkStoryFrameFromGig.Field()
    create_instagram_story_from_submission = CreateInstagramStoryFromSubmission.Field()
