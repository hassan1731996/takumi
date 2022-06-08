from takumi.constants import MAX_CAPTION_LENGTH
from takumi.i18n import gettext as _


class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class MultipleErrorsError(ValidationError):  # Name not finalised
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Multiple errors: {}".format(len(self.errors)))


class HashtagNotAtStartError(ValidationError):
    def __init__(self, hashtag):
        self.type = "caption_start_hashtag"
        self.value = hashtag

        message = _("Caption must start with #%(hashtag)s", hashtag=hashtag)
        super().__init__(message)


class CaptionTooLongError(ValidationError):
    def __init__(self, length):
        self.type = "caption_too_long"

        message = _("Caption has to be below %(length)s characters", length=MAX_CAPTION_LENGTH)
        super().__init__(message)


class MissingHashtagError(ValidationError):
    def __init__(self, hashtag):
        self.type = "hashtag"
        self.value = hashtag

        message = _("Missing hashtag: #%(hashtag)s", hashtag=hashtag)
        super().__init__(message)


class MissingMentionError(ValidationError):
    def __init__(self, mention):
        self.type = "mention"
        self.value = mention

        message = _("Missing mention: @%(mention)s", mention=mention)
        super().__init__(message)


class MissingSwipeUpLinkError(ValidationError):
    def __init__(self, swipe_up_link):
        self.type = "swipe_up_link"
        self.value = swipe_up_link

        message = _("Missing swipe up link: %(link)s", link=swipe_up_link)
        super().__init__(message)


class InvalidGalleryCountError(ValidationError):
    def __init__(self, expected_count, actual_count):
        message = _(
            "Expected %(expected)s gallery photos, got %(actual)s",
            expected=expected_count,
            actual=actual_count,
        )
        super().__init__(message)


class TooEarlyError(ValidationError):
    def __init__(self, opened):
        formatted = opened.strftime("%Y-%m-%d %H:%M:%S%z")
        message = _("Posts created before %(date)s are not valid", date=formatted)
        super().__init__(message)


class MediaMissingError(ValidationError):
    def __init__(self, gig):
        super().__init__(f"Gig missing media ({gig.id})")


class GigMissingError(ValidationError):
    def __init__(self, post):
        super().__init__(f"Gig missing from post ({post.id})")


class MediaNotFoundError(ValidationError):
    def __init__(self, shortcode):
        super().__init__(f"Post not found on instagram ({shortcode})")
