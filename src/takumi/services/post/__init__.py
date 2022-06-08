from typing import Dict, List
from unicodedata import normalize

from itp import itp
from sqlalchemy import or_

from takumi.events.post import PostLog
from takumi.extensions import db
from takumi.models import Gig, InstagramPost, InstagramPostComment, Post
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes
from takumi.services import CampaignService, Service
from takumi.services.exceptions import (
    ArchivePostException,
    CampaignNotFound,
    CreatePostException,
    InvalidConditionsException,
    ServiceException,
    UpdatePostScheduleException,
)
from takumi.services.validation import Validate, ValidationSchema, validators
from takumi.tasks.instagram_metadata import refresh_mention_ig_metadata
from takumi.tasks.posts.reminders import schedule_post_reminders

from .utils import BRIEF_TYPES


class PostService(Service):
    """
    Represents the business model for Post. This is the bridge between
    the database and the application.
    """

    SUBJECT = Post
    LOG = PostLog

    @property
    def post(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(post_id):
        return Post.query.get(post_id)

    @staticmethod
    def get_comment_stats(id):
        """
        Returns a query with all 'list of emojis' and 'list of hashtags' from
        the comments, for every gig in the post
        """
        return (
            Post.query.join(Gig, Gig.post_id == Post.id)
            .join(InstagramPost, InstagramPost.gig_id == Gig.id)
            .join(InstagramPostComment, InstagramPostComment.instagram_post_id == InstagramPost.id)
            .filter(
                Post.id == id,
                Gig.state != GIG_STATES.REJECTED,
                or_(InstagramPostComment.emojis != [], InstagramPostComment.hashtags != []),
            )
            .with_entities(InstagramPostComment.emojis, InstagramPostComment.hashtags)
            .all()
        )

    # POST
    @staticmethod
    def create_post(campaign_id, post_type=PostTypes.standard):
        campaign = CampaignService.get_by_id(campaign_id)
        if campaign is None:
            raise CampaignNotFound(f"<Campaign {campaign_id}> not found")
        if campaign.state != CAMPAIGN_STATES.DRAFT:
            raise CreatePostException(
                "Campaign needs to be in draft state in order to add posts to it"
            )

        post = Post()
        log = PostLog(post)
        log.add_event(
            "create", {"campaign_id": campaign_id, "post_type": post_type, "conditions": []}
        )
        db.session.add(post)

        # Set initial conditions in English markets
        if campaign.market_slug in ["uk", "us"]:
            log.add_event("set_conditions", {"hashtags": ["ad"], "start_first_hashtag": True})

        db.session.commit()

        return post

    # PUT
    def archive(self):
        class ArchiveSchema(ValidationSchema):
            archived = validators.Equals(False), "Can't archive an already archived post"
            gigs = (
                validators.Length(0),
                "Post can only be archived if no gigs have been submitted for that post",
            )
            campaign__posts = validators.Length(2, None), "Campaigns must have at least one post"

        errors = Validate(self.post, ArchiveSchema)
        if errors:
            raise ArchivePostException(errors)

        self.log.add_event("set_archived", {"archived": not self.post.archived})

    def update_conditions(self, mention, hashtags, swipe_up_url, start_first_hashtag):
        if hashtags is not None:
            # Remove empty tags
            hashtags = [normalize("NFC", h) for h in hashtags if h]
            if len(hashtags):
                hashtags = [tag.replace("#", "").strip() for tag in hashtags]
            if mention:
                mention = mention.replace("@", "").strip()
                mention = normalize("NFC", mention)

            # Validate the hashtags
            if len(hashtags):
                caption = " ".join([f"#{tag.strip()}" for tag in hashtags])
                caption = normalize("NFC", caption)
                parsed_tags = itp.Parser().parse(caption).tags
                if set(parsed_tags) != set(hashtags):
                    raise InvalidConditionsException("Invalid hashtags")

        # Validate the mention
        if mention:
            parsed_mentions = itp.Parser().parse(f"@{mention.strip()}").users
            if set(parsed_mentions) != {mention}:
                raise InvalidConditionsException("Invalid mentions")

        swipe_up_url = swipe_up_url and swipe_up_url.strip()

        # Verify there are changes
        hashtags_changed = [
            c["value"] for c in self.post.conditions if c["type"] == "hashtag"
        ] != hashtags

        mention_changed = (
            next((c["value"] for c in self.post.conditions if c["type"] == "mention"), None)
        ) != mention

        swipe_up_changed = (
            next((c["value"] for c in self.post.conditions if c["type"] == "mention"), None)
            != swipe_up_url
        )

        first_hashtag_flag_changed = self.post.start_first_hashtag != start_first_hashtag

        if any([hashtags_changed, mention_changed, swipe_up_changed, first_hashtag_flag_changed]):
            self.log.add_event(
                "set_conditions",
                {
                    "mention": mention,
                    "hashtags": hashtags,
                    "swipe_up_link": swipe_up_url,
                    "start_first_hashtag": start_first_hashtag,
                },
            )

        if mention_changed and self.post.mention is not None:
            refresh_mention_ig_metadata.delay(self.post.mention)

    def update_requires_review_before_posting(self, requires_review_before_posting):
        self.log.add_event(
            "set_requires_review_before_posting",
            {"requires_review_before_posting": requires_review_before_posting},
        )

    def update_schedule(self, opened=None, deadline=None, submission_deadline=None):
        if opened is None:
            opened = self.post.opened
        if deadline is None:
            deadline = self.post.deadline
        if submission_deadline is None:
            submission_deadline = self.post.submission_deadline

        if opened is not None and deadline is not None and opened >= deadline:
            raise UpdatePostScheduleException(
                "The post deadline must be after post to Instagram opens"
            )

        if (
            submission_deadline is not None
            and deadline is not None
            and submission_deadline > deadline
        ):
            raise UpdatePostScheduleException("The submission deadline must be before the deadline")

        self.log.add_event(
            "set_schedule",
            {"opened": opened, "submission_deadline": submission_deadline, "deadline": deadline},
        )
        schedule_post_reminders(self.post)

    def update_instructions(self, instructions):
        self.log.add_event("set_instructions", {"instructions": instructions})

    def update_brief(self, brief: List[Dict]):
        brief_sections = []
        for section in brief:
            # Validate type
            type_ = section.get("type")
            if type_ not in BRIEF_TYPES:
                raise ServiceException(f"Invalid brief section type: {type_}")

            # Validate values for the type
            validator = BRIEF_TYPES[type_]
            values = validator(section)

            brief_sections.append({"type": type_, **values})

        self.log.add_event("set_brief", {"brief": brief_sections})

    def update_post_type(self, post_type):
        self.log.add_event("set_post_type", {"post_type": post_type})

    def update_gallery_photo_count(self, gallery_photo_count):
        self.log.add_event("set_gallery_photo_count", {"gallery_photo_count": gallery_photo_count})

    def update_price(self, price):
        self.log.add_event("set_price", {"price": price})
