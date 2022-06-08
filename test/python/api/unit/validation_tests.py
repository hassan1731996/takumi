import datetime as dt

import mock
import pytest

from takumi.constants import MAX_CAPTION_LENGTH
from takumi.validation.errors import (
    CaptionTooLongError,
    HashtagNotAtStartError,
    InvalidGalleryCountError,
    MissingHashtagError,
    MissingMentionError,
    MultipleErrorsError,
    TooEarlyError,
    ValidationError,
)
from takumi.validation.media import (
    CaptionLengthValidator,
    CaptionStartsWithHashtagValidator,
    ComposedValidator,
    ConditionsValidator,
    GalleryCountValidator,
    HashtagValidator,
    MentionValidator,
)
from takumi.validation.offer import OfferValidator
from takumi.validation.post import PostTimeValidator


def test_composed_validator_runs_all_validators():
    validators = [HashtagValidator("hash"), HashtagValidator("tag")]
    composed_validator = ComposedValidator(validators)

    with pytest.raises(MultipleErrorsError, match="Multiple errors: 2"):
        composed_validator.validate("no hashtags")

    assert "Missing hashtag: #hash" in [str(error) for error in composed_validator.errors]
    assert "Missing hashtag: #tag" in [str(error) for error in composed_validator.errors]


def test_running_composed_validator_twice_doesnt_duplicate_errors():
    validators = [HashtagValidator("hash")]
    composed_validator = ComposedValidator(validators)

    with pytest.raises(MultipleErrorsError, match="Multiple errors: 1"):
        composed_validator.validate("no hashtags")

    with pytest.raises(MultipleErrorsError, match="Multiple errors: 1"):
        composed_validator.validate("no hashtags")

    assert len(composed_validator.errors) == 1


def test_hashtag_validator_doesnt_raise_if_caption_has_hashtag():
    caption = "Hello, this is an #ad"
    hashtag = "ad"

    HashtagValidator(hashtag).validate(caption)


def test_hashtag_validator_is_case_insensitive():
    caption = "#foo #Bar #BAZ"

    HashtagValidator("foo").validate(caption)
    HashtagValidator("bar").validate(caption)
    HashtagValidator("baz").validate(caption)


def test_hashtag_validator_reports_the_missing_hashtag():
    caption = "This is not an ad"
    hashtag = "ad"

    with pytest.raises(MissingHashtagError, match="Missing hashtag: #ad"):
        HashtagValidator(hashtag).validate(caption)


def test_mention_validator_doesnt_raise_if_caption_has_mention():
    caption = "Hello, this is @brand"
    mention = "brand"

    MentionValidator(mention).validate(caption)


def test_mention_validator_is_case_insensitive():
    caption = "@foo @Bar @BAZ"

    MentionValidator("foo").validate(caption)
    MentionValidator("bar").validate(caption)
    MentionValidator("baz").validate(caption)


def test_mention_validator_raises_on_missing_mention():
    caption = "@takumihq"
    mention = "brand"

    with pytest.raises(MissingMentionError, match="Missing mention: @brand"):
        MentionValidator(mention).validate(caption)


def test_gallery_validator_raises_on_amount_of_gallery_photos():
    gallery = [
        {"code": "a", "url": "http://"},
        {"code": "b", "url": "http://"},
        {"code": "c", "url": "http://"},
    ]

    with pytest.raises(InvalidGalleryCountError, match="Expected 4 gallery photos, got 3"):
        GalleryCountValidator(required_gallery_count=4).validate(gallery)


def test_post_time_validator_raises_if_created_is_before_opened_using_datetime():
    opened = dt.datetime(2018, 1, 1, 10, tzinfo=dt.timezone.utc)
    created = dt.datetime(2018, 1, 1, 9, tzinfo=dt.timezone.utc)

    with pytest.raises(TooEarlyError, match="Posts created before .* are not valid"):
        PostTimeValidator(opened).validate(created)


def test_post_time_validator_raises_if_created_is_before_opened_using_timestamp():
    opened = dt.datetime(2018, 1, 1, 10, tzinfo=dt.timezone.utc)
    created = (dt.datetime(2018, 1, 1, 9) - dt.datetime(1970, 1, 1)).total_seconds()

    with pytest.raises(TooEarlyError, match="Posts created before .* are not valid"):
        PostTimeValidator(opened).validate(created)


def test_post_time_validator_raises_if_created_is_before_opened_using_isoformat():
    opened = dt.datetime(2018, 1, 1, 10, tzinfo=dt.timezone.utc)
    created = dt.datetime(2018, 1, 1, 9, tzinfo=dt.timezone.utc).isoformat()

    with pytest.raises(TooEarlyError, match="Posts created before .* are not valid"):
        PostTimeValidator(opened).validate(created)


def test_post_time_validator_raises_if_created_is_invalid():
    opened = dt.datetime(2018, 1, 1, 10, tzinfo=dt.timezone.utc)

    with pytest.raises(ValidationError, match="Invalid timestamp: foobar"):
        PostTimeValidator(opened).validate("foobar")


def test_caption_hashtag_start_validator_reports_if_caption_doesnt_start_with_the_hashtag():
    caption = "This is an #ad"
    hashtag = "ad"

    with pytest.raises(HashtagNotAtStartError, match="Caption must start with #ad"):
        CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_accepts():
    caption = "#ad well well well"
    hashtag = "ad"

    CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_accepts_case_insensitive():
    caption = "#AD well well well"
    hashtag = "ad"

    CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_accepts_ignoring_whitespace():
    caption = "   #ad well well well"
    hashtag = "ad"

    CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_accepts_if_new_line():
    caption = "\n#ad well well well"
    hashtag = "ad"

    CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_reports_if_emoji_before_tag():
    caption = "💚#ad 💚"
    hashtag = "ad"

    with pytest.raises(HashtagNotAtStartError, match="Caption must start with #ad"):
        CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_hashtag_start_validator_accepts_if_invisible_characters_before_tag():
    caption = "\u2063#ad 💚 foo 💚 \u2063\n\u2063\nbar"
    hashtag = "ad"

    CaptionStartsWithHashtagValidator(hashtag).validate(caption)


def test_caption_length_validator_raises_if_too_long():
    caption = "x" * (MAX_CAPTION_LENGTH + 1)

    with pytest.raises(CaptionTooLongError, match=r"Caption has to be below \d+ characters"):
        CaptionLengthValidator().validate(caption)


def test_caption_length_validator_accepts_max_length():
    caption = "x" * MAX_CAPTION_LENGTH

    CaptionLengthValidator().validate(caption)


def test_conditions_validator_with_multiple_conditions():
    caption = "#ad Hello, this is @brand #sp"
    conditions = [
        {"type": "mention", "value": "brand"},
        {"type": "hashtag", "value": "ad"},
        {"type": "hashtag", "value": "sp"},
    ]

    ConditionsValidator(conditions, start_first_hashtag=True).validate(caption)


def test_conditions_validator_reports_the_missing_conditions():
    caption = "Where are the conditions?"
    conditions = [{"type": "mention", "value": "brand"}, {"type": "hashtag", "value": "ad"}]

    validator = ConditionsValidator(conditions, start_first_hashtag=False)
    with pytest.raises(MultipleErrorsError, match="Multiple errors: 2"):
        validator.validate(caption)

    assert len(validator.errors) == 2
    assert "Missing hashtag: #ad" in [str(error) for error in validator.errors]
    assert "Missing mention: @brand" in [str(error) for error in validator.errors]


def test_offer_validator_reports_on_missing_gigs(post):
    mock_offer = mock.Mock()
    mock_offer.iter_post_gigs.return_value = [(post, None)]

    validator = OfferValidator(mock_offer)
    with pytest.raises(MultipleErrorsError, match="Multiple errors: 1"):
        validator.validate()

    assert len(validator.errors) == 1
    assert "Gig missing from post" in str(validator.errors[0])


def test_offer_validator_reports_on_missing_gig_media(post, gig):
    mock_offer = mock.Mock()
    mock_offer.iter_post_gigs.return_value = [(post, gig)]

    validator = OfferValidator(mock_offer)
    with pytest.raises(MultipleErrorsError, match="Multiple errors: 1"):
        validator.validate()

    assert len(validator.errors) == 1
    assert "Gig missing media" in str(validator.errors[0])


def test_offer_validator_reports_on_any_gig_errors(
    post_factory, gig_factory, instagram_post_factory
):
    mock_offer = mock.Mock()

    post1 = post_factory()
    post2 = post_factory()

    gig1 = gig_factory(post=post1, instagram_post=instagram_post_factory())
    gig2 = gig_factory(post=post2, instagram_post=instagram_post_factory())

    mock_offer.iter_post_gigs.return_value = [(post1, gig1), (post2, gig2)]

    with mock.patch("takumi.validation.offer.InstagramMediaValidator.from_gig") as mock_validator:
        mock_valid = mock.Mock()
        mock_invalid = mock.Mock()
        mock_invalid.validate.side_effect = [ValidationError("error")]
        mock_invalid.errors = ["error"]
        mock_validator.side_effect = [mock_valid, mock_invalid]

        validator = OfferValidator(mock_offer)
        with pytest.raises(MultipleErrorsError, match="Multiple errors: 1"):
            validator.validate()

    assert len(validator.errors) == 1
    assert validator.errors == ["error"]
