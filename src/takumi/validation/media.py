import datetime as dt
from string import printable
from unicodedata import normalize

import dateutil.parser
from itp import itp
from sentry_sdk import capture_exception

from core.facebook import InstagramMediaNotFound
from core.facebook.instagram import InstagramError

from takumi.constants import MAX_CAPTION_LENGTH
from takumi.extensions import instascrape
from takumi.ig.instascrape import NotFound
from takumi.roles import permissions
from takumi.validation import ComposedValidator, Validator
from takumi.validation.errors import (
    CaptionTooLongError,
    HashtagNotAtStartError,
    InvalidGalleryCountError,
    MediaNotFoundError,
    MissingHashtagError,
    MissingMentionError,
    MissingSwipeUpLinkError,
    MultipleErrorsError,
    ValidationError,
)
from takumi.validation.post import PostTimeValidator


class HashtagValidator(Validator):
    def __init__(self, hashtag):
        self.hashtag = hashtag.lower()

    def validate(self, caption):
        caption = normalize("NFC", caption)
        parsed = itp.Parser().parse(caption)

        hashtags = [tag.lower() for tag in parsed.tags]
        if self.hashtag not in hashtags:
            raise MissingHashtagError(self.hashtag)


class MentionValidator(Validator):
    def __init__(self, mention):
        self.mention = mention.lower()

    def validate(self, caption):
        caption = normalize("NFC", caption)
        parsed = itp.Parser().parse(caption)

        mentions = [user.lower() for user in parsed.users]
        if self.mention not in mentions:
            raise MissingMentionError(self.mention)


class CaptionStartsWithHashtagValidator(Validator):
    def __init__(self, hashtag):
        self.hashtag = hashtag.lower()

    def validate(self, caption):
        stripped = "".join(
            char for char in caption.lower().strip() if char in printable or char.isprintable()
        )
        if not stripped.startswith(f"#{self.hashtag}"):
            raise HashtagNotAtStartError(self.hashtag)


class CaptionLengthValidator(Validator):
    def validate(self, caption):
        if len(caption) > MAX_CAPTION_LENGTH:
            raise CaptionTooLongError(len(caption))


class GalleryCountValidator(Validator):
    def __init__(self, required_gallery_count):
        self.required_gallery_count = required_gallery_count

    def validate(self, gallery):
        if len(gallery) != self.required_gallery_count:
            raise InvalidGalleryCountError(
                expected_count=self.required_gallery_count, actual_count=len(gallery)
            )


class ConditionsValidator(ComposedValidator):
    def __init__(self, conditions, start_first_hashtag):
        self.conditions = conditions
        validators = []

        for condition in self.conditions:
            if condition["type"] == "hashtag":
                validators.append(HashtagValidator(condition["value"]))
            elif condition["type"] == "mention":
                validators.append(MentionValidator(condition["value"]))

        if start_first_hashtag:
            first_hashtag = next((c["value"] for c in conditions if c["type"] == "hashtag"), None)
            if first_hashtag:
                validators.append(CaptionStartsWithHashtagValidator(first_hashtag))

        validators.append(CaptionLengthValidator())

        super().__init__(validators)


class InstagramMediaValidator:
    def __init__(self, conditions, opened, start_first_hashtag, influencer=None):
        self.conditions = conditions
        self.opened = opened
        self.start_first_hashtag = start_first_hashtag

        self.influencer = influencer

        self.errors = []

    @classmethod
    def from_post(cls, post):
        return cls(
            conditions=post.conditions,
            opened=post.opened,
            start_first_hashtag=post.start_first_hashtag,
        )

    @classmethod
    def from_gig(cls, gig):
        post = gig.post
        influencer = gig.offer.influencer
        return cls(
            conditions=post.conditions,
            opened=post.opened,
            start_first_hashtag=post.start_first_hashtag,
            influencer=influencer,
        )

    def validate(self, media_id: str, force: bool = False):  # noqa: C901
        """Validate scraped instagram media for post conditions

        Verify that the instagram post is live, hasn't been posted too early and
        follows campaign post conditions

        Returns the media if everything is valid

        XXX: Unfortunately the valdiation does a lot of logic, so force is a
        parameter that bypasses all the validation (which is the only thing
        this function should be doing!!), to still do the scraping
        """
        from takumi.models.influencer import FacebookPageDeactivated, MissingFacebookPage

        try:
            media = self.influencer.instagram_api.get_media_by_ig_id(media_id)
            media["created"] = media["timestamp"]
            media["url"] = media["media_url"]

            if media["media_type"] == "IMAGE":
                media["type"] = "image"
                media["owner"] = self.influencer.instagram_api.get_profile()
            elif media["media_type"] == "VIDEO":
                insights = self.influencer.instagram_api.get_media_insights(
                    media["id"], nocache=True
                )
                media["type"] = "video"
                media["video_views"] = insights.get("video_views")
            elif media["media_type"] == "CAROUSEL_ALBUM":
                media["type"] = "gallery"
                media["gallery"] = self.influencer.instagram_api.get_media_children(media["id"])
                for child in media["gallery"]:
                    child["url"] = child["media_url"]
                    child["type"] = child["media_type"].lower()
                    child["thumbnail"] = child.get("thumbnail_url")
            try:
                scraped_media = instascrape.get_media(media_id)
                media["sponsors"] = scraped_media.get("sponsors", [])
            except Exception:
                pass  # XXX: Revisit if we look at sponsors, which should be done through official means

            ConditionsValidator(self.conditions, self.start_first_hashtag).validate(
                media.get("caption", "")
            )
        except (
            FacebookPageDeactivated,
            MissingFacebookPage,
            InstagramError,
            InstagramMediaNotFound,
            ValidationError,
            KeyError,
        ) as e:
            if isinstance(e, InstagramError):
                capture_exception()
            if e.__class__ == ValidationError:
                capture_exception()
            if e.__class__ == KeyError:
                capture_exception()
            try:
                media = instascrape.get_media(media_id)
            except NotFound:
                self.errors.append(MediaNotFoundError(media_id))
                raise MultipleErrorsError(self.errors)

        post_time_validator = PostTimeValidator(self.opened)
        try:
            post_time_validator.validate(media["created"])
        except ValidationError as error:
            self.errors.append(error)

        conditions_validator = ConditionsValidator(self.conditions, self.start_first_hashtag)
        try:
            conditions_validator.validate(media.get("caption", ""))
        except ValidationError:
            self.errors += conditions_validator.errors

        if len(self.errors):
            if not permissions.developer.can() and not force:
                raise MultipleErrorsError(self.errors)

        if "created" in media and isinstance(media["created"], str):
            # Convert to datetime
            media["created"] = dateutil.parser.parse(media["created"]).replace(
                tzinfo=dt.timezone.utc
            )

        return media


class StoryHashtagValidator(Validator):
    def __init__(self, hashtag):
        self.hashtag = hashtag.lower()

    def validate(self, story_frame):
        hashtags = [hashtag["name"].lower() for hashtag in story_frame.hashtags]
        if self.hashtag not in hashtags:
            raise MissingHashtagError(self.hashtag)


class StoryMentionValidator(Validator):
    def __init__(self, mention):
        self.mention = mention.lower()

    def validate(self, story_frame):
        mentions = [mention["username"].lower() for mention in story_frame.mentions]
        if self.mention not in mentions:
            raise MissingMentionError(self.mention)


class StorySwipeUpLinkValidator(Validator):
    def __init__(self, swipe_up_link):
        self.swipe_up_link = swipe_up_link.lower()

    def validate(self, story_frame):
        if self.swipe_up_link != story_frame.swipe_up_link:
            raise MissingSwipeUpLinkError(self.swipe_up_link)


class StoryConditionsValidator(ComposedValidator):
    def __init__(self, conditions):
        self.conditions = conditions
        validators = []

        for condition in self.conditions:
            if condition["type"] == "hashtag":
                validators.append(StoryHashtagValidator(condition["value"]))
            elif condition["type"] == "mention":
                validators.append(StoryMentionValidator(condition["value"]))
            elif condition["type"] == "swipe_up_link":
                validators.append(StorySwipeUpLinkValidator(condition["value"]))

        super().__init__(validators)


class StoryFrameValidator:
    def __init__(self, conditions, opened):
        self.conditions = conditions
        self.opened = opened

        self.errors = []

    @classmethod
    def from_post(cls, post):
        return cls(conditions=post.conditions, opened=post.opened)

    def validate(self, story_frame):
        validator = PostTimeValidator(self.opened)
        try:
            validator.validate(story_frame.posted)
        except ValidationError as error:
            self.errors.append(error)

        validator = StoryConditionsValidator(self.conditions)
        try:
            validator.validate(story_frame)
        except ValidationError:
            self.errors += validator.errors

        if len(self.errors):
            if not permissions.developer.can():
                raise MultipleErrorsError(self.errors)

        return story_frame


# TODO: This and all related story validations are not being used anywhere. Leaving this to be used at a later date
# Or for others to decide whether to remove or not.
class InstagramStoryValidator:
    def __init__(self, conditions, opened):
        self.conditions = conditions
        self.opened = opened

        self.errors = []

    @classmethod
    def from_post(cls, post):
        return cls(conditions=post.conditions, opened=post.opened)

    def validate(self, instagram_story):
        valid_frames = []
        for story_frame in instagram_story.story_frames:
            validator = StoryFrameValidator(self.conditions, self.opened)

            try:
                validator.validate(story_frame)
                valid_frames.append(story_frame)
            except MultipleErrorsError:
                pass

        if len(valid_frames) == 0:
            raise ValidationError("No valid frames")

        return valid_frames
