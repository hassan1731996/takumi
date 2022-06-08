import datetime as dt
import re

from flask_login import current_user
from graphene import Enum, ObjectType

from takumi import models
from takumi.gql import fields
from takumi.gql.db import filter_gigs
from takumi.gql.relay import Connection, Node
from takumi.gql.types.percent import Percent
from takumi.gql.utils import influencer_post_step
from takumi.models import Currency
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes
from takumi.reports import StandardPostReport, StoryPostReport, VideoPostReport
from takumi.roles import permissions
from takumi.roles.needs import influencer_role
from takumi.schedule import PostSchedule


class PostStates(Enum):
    draft = "draft"
    launched = "launched"
    completed = "completed"


class MediaRequirementType(Enum):
    image = "image"
    video = "video"
    any = "any"


class MediaRequirement(ObjectType):
    type = MediaRequirementType(
        description="The required type of the media to be submitted for review"
    )


class Post(ObjectType):
    class Meta:
        interfaces = (Node,)

    post_type = fields.String()
    opened = fields.DateTime()
    submission_deadline = fields.DateTime()
    deadline = fields.DateTime()
    instructions = fields.String()
    brief = fields.List("BriefSectionInterface")
    requires_review_before_posting = fields.Boolean(
        description="Whether the posts needs reviewing before being posted"
    )
    archived = fields.Boolean()
    price = fields.Field("Currency")

    gigs = fields.List("Gig")
    campaign = fields.Field("Campaign")

    mention = fields.String()
    hashtags = fields.List(fields.String)
    start_first_hashtag = fields.Boolean()
    location = fields.String()
    swipe_up_link = fields.String()

    timezone = fields.String(resolver=fields.deep_source_resolver("campaign.timezone"))
    gallery_photo_count = fields.Int()

    step = fields.AuthenticatedField(fields.String, needs=influencer_role)

    media_requirements = fields.List(
        MediaRequirement, description="List of required media types to be submitted for review"
    )
    allow_extra_media = fields.Boolean()

    reach = fields.Int(description="Total reach for the post")
    likes = fields.Int(description="Total likes for the post")
    comments = fields.Int(description="Total comments for the post")
    video_views = fields.Int(description="Total video views for the post")
    video_engagement = fields.Field(
        Percent, description="Average engagement rate based on video views"
    )
    engagements = fields.Int(description="Total number of engagements for the post")
    engagement = fields.Field(Percent, description="Average engagement for the post")

    schedule = fields.Field("Schedule", description="Dates that control the campaign process")
    supports_stats = fields.Boolean()

    report = fields.Field("PostReportInterface", description="The overall report of a the post")

    def resolve_price(post, info):
        if post.price:
            currency = post.campaign.market.currency
            return Currency(amount=post.price, currency=currency)

    def resolve_report(post, info):
        from takumi.models.post import PostTypes

        if not permissions.view_post_reports.can():
            # Temporarily require permission to see these new reports
            return None

        if post.campaign.state == CAMPAIGN_STATES.DRAFT:
            # No reports in draft campaigns
            return None

        if post.post_type == PostTypes.standard:
            return StandardPostReport(post)
        if post.post_type == PostTypes.video:
            return VideoPostReport(post)
        if post.post_type == PostTypes.story:
            if (
                not permissions.developer.can()
                and post.opened
                and post.opened < dt.datetime(2019, 1, 1, tzinfo=dt.timezone.utc)
            ):
                # Only return story post reports for recent posts
                return None
            return StoryPostReport(post)

    def resolve_gigs(post, info):
        gigs_q = models.Gig.query.filter(models.Gig.post_id == post.id)

        if "token" in info.context:
            gigs_q = gigs_q.join(models.Post, models.Campaign).filter(
                models.Gig.state == GIG_STATES.APPROVED,
                models.Campaign.report_token == info.context["token"],
            )
            if post.post_type == PostTypes.story:
                gigs_q = gigs_q.join(models.InstagramStory, models.StoryFrame).filter(
                    models.Gig.instagram_story != None
                )
                return sorted(gigs_q, key=lambda gig: gig.instagram_story.posted, reverse=True)
            else:
                gigs_q = gigs_q.filter(models.Gig.instagram_post != None)
                return sorted(gigs_q, key=lambda gig: gig.instagram_post.engagement, reverse=True)

        return filter_gigs(gigs_q)

    def resolve_mention(root, info):
        return next((c["value"] for c in root.conditions if c["type"] == "mention"), None)

    def resolve_hashtags(root, info):
        return [c["value"] for c in root.conditions if c["type"] == "hashtag"]

    def resolve_location(root, info):
        return next((c["value"] for c in root.conditions if c["type"] == "location"), None)

    def resolve_swipe_up_link(root, info):
        return next((c["value"] for c in root.conditions if c["type"] == "swipe_up_link"), None)

    def resolve_step(root, info):
        influencer = current_user.influencer
        if influencer:
            client_version = info.context.get("client_version")
            return influencer_post_step(
                post=root, influencer=influencer, client_version=client_version
            )

    def resolve_schedule(post, info):
        if not post.deadline:
            return None

        return PostSchedule(post)

    def resolve_brief(post, info):
        """Fallback to old instructions if brief is not set"""
        if post.brief:
            return post.brief

        pattern = re.compile(r"(\n\s*){2,}")

        brief = []
        if post.campaign.description:
            brief.append({"type": "heading", "value": "Brand Background"})
            brief += [
                {"type": "paragraph", "value": paragraph.replace("\n", "<br>")}
                for paragraph in pattern.sub("\n\n", post.campaign.description).split("\n\n")
                if len(paragraph.strip())
            ]
        if post.instructions:
            brief.append({"type": "heading", "value": "Instructions"})
            brief += [
                {"type": "paragraph", "value": paragraph.replace("\n", "<br>")}
                for paragraph in pattern.sub("\n\n", post.instructions).split("\n\n")
                if len(paragraph.strip())
            ]

        return brief


class PostHistory(ObjectType):
    class Meta:
        interfaces = (Node,)

    user = fields.Field("User")
    created = fields.String(source="_created")
    team_member = fields.Boolean(source="_team_member")
    type = fields.String(source="_type")

    event = fields.GenericScalar(description="Post history dictionary")

    def resolve_event(obj, info):
        return {k: v for k, v in obj.items() if not k.startswith("_")}

    def resolve_user(obj, info):
        user_id = obj.get("_user_id")
        if user_id is None:
            return None
        return models.User.query.get(user_id)


class PostHistoryConnection(Connection):
    class Meta:
        node = PostHistory


class PostConnection(Connection):
    class Meta:
        node = Post
