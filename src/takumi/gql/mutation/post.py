from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_post_or_404
from takumi.models.post import PostTypes
from takumi.roles import permissions
from takumi.services import PostService


class PostType(arguments.Enum):
    standard = PostTypes.standard
    video = PostTypes.video
    story = PostTypes.story
    reel = PostTypes.reel
    tiktok = PostTypes.tiktok
    youtube = PostTypes.youtube


class BriefSectionType(arguments.Enum):
    heading = "heading"
    subHeading = "sub_heading"
    paragraph = "paragraph"
    important = "important"
    divider = "divider"
    dosAndDonts = "dos_and_donts"
    orderedList = "ordered_list"
    unorderedList = "unordered_list"


class BriefSection(arguments.InputObjectType):
    type = BriefSectionType(required=True)
    value = arguments.String()
    items = arguments.List(arguments.String, description="Used in ordered/unordered lists")
    dos = arguments.List(arguments.String, description="Used in Do's and Don'ts")
    donts = arguments.List(arguments.String, description="Used in Do's and Don'ts")


class CreatePost(Mutation):
    """Create post"""

    class Arguments:
        campaign_id = arguments.UUID(
            required=True, description="Id of the campaign, which the post belongs to"
        )

    post = fields.Field("Post")

    @permissions.manage_posts.require()
    def mutate(root, info, campaign_id):
        post = PostService.create_post(campaign_id)
        return CreatePost(post=post, ok=True)


class UpdatePost(Mutation):
    """Update a post"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the post being updated")
        mention = arguments.String(description="Mention needed per post", strip=True)
        hashtags = arguments.List(arguments.String, description="Hashtags needed per post")
        start_first_hashtag = arguments.Boolean(
            description="Whether the require the first hashtag to be at the start of the caption",
            default_value=False,
        )
        location = arguments.String()
        swipe_up_link = arguments.String(description="Swipe up link for story posts")
        opened = arguments.DateTime(description="Datetime of when the post will be opened")
        submission_deadline = arguments.DateTime(
            description="Deadline for submitting content for review"
        )
        deadline = arguments.DateTime(
            description="Datetime representing the post's deadline"
        )  # allow_none
        instructions = arguments.String(description="The instructions for a post")
        gallery_photo_count = arguments.Int(
            description="The count of media in a gallery, defaults to 0", default_value=0
        )
        post_type = PostType(
            description="The type of the post. Must be one of `standard`, `video`, `story`, `reel`, `tiktok`, `youtube`"
        )
        requires_review_before_posting = arguments.Boolean(
            description="Dictates whether a review of the submission is needed before influencer can post"
        )
        price = arguments.Int(description="The price of the post, used in reports only")
        brief = arguments.List(BriefSection, description="The brief sections of the post")

    post = fields.Field("Post")

    @permissions.manage_posts.require()  # noqa: C901
    def mutate(
        root,
        info,
        id,
        post_type=None,
        mention=None,
        hashtags=None,
        start_first_hashtag=False,
        location=None,
        swipe_up_link=None,
        opened=None,
        submission_deadline=None,
        deadline=None,
        instructions=None,
        gallery_photo_count=None,
        requires_review_before_posting=None,
        price=None,
        brief=None,
    ):
        post = get_post_or_404(id)

        with PostService(post) as service:
            if post_type is not None:
                if post.post_type != post_type:
                    service.update_post_type(post_type)

            service.update_conditions(mention, hashtags, swipe_up_link, start_first_hashtag)

            if opened is not None or submission_deadline is not None or deadline is not None:
                service.update_schedule(
                    opened=opened, deadline=deadline, submission_deadline=submission_deadline
                )

            if instructions is not None:
                service.update_instructions(instructions)

            if gallery_photo_count is not None:
                if post.gallery_photo_count != gallery_photo_count:
                    service.update_gallery_photo_count(gallery_photo_count)

            if requires_review_before_posting is not None:
                if requires_review_before_posting != post.requires_review_before_posting:
                    service.update_requires_review_before_posting(requires_review_before_posting)
            if price is not None:
                service.update_price(price * 100)
            if brief is not None:
                service.update_brief(brief)

        return UpdatePost(post=post, ok=True)


class ArchivePost(Mutation):
    """Archive a post.
    The post will be flagged as `archived` and it'll be shown as archived in the web tool.
    Two days later, the post will be deleted if the flag won't be reverted."""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the post being archived")

    post = fields.Field("Post")

    @permissions.manage_posts.require()
    def mutate(root, info, id):
        post = get_post_or_404(id)

        with PostService(post) as service:
            service.archive()

        return ArchivePost(post=post, ok=True)


class PostMutation:
    create_post = CreatePost.Field()
    update_post = UpdatePost.Field()
    archive_post = ArchivePost.Field()
