from graphene.types.objecttype import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection, Node
from takumi.gql.types.instagram_content import InstagramContentInterface
from takumi.roles import permissions


class StoryFrame(ObjectType):
    class Meta:
        interfaces = (Node,)

    created = fields.DateTime()
    modified = fields.DateTime()
    posted = fields.DateTime()
    instagram_story_id = fields.UUID()

    swipe_up_link = fields.String()
    locations = fields.List(fields.GenericScalar)
    mentions = fields.List(fields.GenericScalar)
    hashtags = fields.List(fields.GenericScalar)

    instagram_story_frame_insight = fields.Field(
        "InstagramStoryFrameInsight", fetch_if_not_available=fields.Boolean()
    )

    media = fields.Field("MediaResult")

    def resolve_instagram_story_frame_insight(root, info, fetch_if_not_available=False):
        if not permissions.team_member.can():
            return None
        if not root.instagram_story_frame_insight and fetch_if_not_available:
            root.update_instagram_insights()
        return root.instagram_story_frame_insight


class StoryFrameConnection(Connection):
    class Meta:
        node = StoryFrame


class InstagramStory(ObjectType):
    class Meta:
        interfaces = (InstagramContentInterface,)

    story_frames = fields.List(StoryFrame)

    marked_posted_within_last_24_hours = fields.Boolean()

    @classmethod
    def resolve_media(cls, story, info):
        media = story.media
        if len(media) > 1:
            return media
        if len(media) == 1:
            return media[0]
        return None

    @classmethod
    def resolve_story_frames(cls, story, info):
        return sorted(story.story_frames, key=lambda frame: frame.created, reverse=True)

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.instagram_story import InstagramStory

        return isinstance(root, InstagramStory)
