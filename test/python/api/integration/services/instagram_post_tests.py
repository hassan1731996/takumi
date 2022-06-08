import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.models.media import TYPES as MEDIA_TYPES
from takumi.models.media import Video
from takumi.services import InstagramPostService, OfferService
from takumi.services.exceptions import (
    CreateInstagramPostException,
    GigNotFoundException,
    InvalidMediaException,
    MediaNotFoundException,
    UnlinkGigException,
    UpdateMediaThumbnailException,
    UpdateMediaUrlException,
)
from takumi.utils import uuid4_str
from takumi.validation.errors import ValidationError

_now = dt.datetime(2017, 1, 1, 0, tzinfo=dt.timezone.utc)


def test_get_by_id_returns_none_if_not_found(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act and Assert
    assert InstagramPostService.get_by_id(unknown_id) is None


def test_get_by_id_returns_instagram_post(db_instagram_post):
    # Act and Assert
    assert InstagramPostService.get_by_id(db_instagram_post.id) == db_instagram_post


def test_get_instagram_posts_from_post_returns_instagram_posts(db_instagram_post, db_post):
    # Act and Assert
    assert InstagramPostService.get_instagram_posts_from_post(db_post.id) == [db_instagram_post]


def test_create_raises_if_gig_not_found(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act
    with pytest.raises(GigNotFoundException) as exc:
        InstagramPostService.create(unknown_id, "shortcode")

    # Assert
    assert "Could not find gig with id {}".format(unknown_id) in exc.exconly()


def test_create_raises_if_validation_fails(db_gig, monkeypatch):
    # Arrange
    def raise_validation_error():
        raise ValidationError("error")

    monkeypatch.setattr(
        "takumi.validation.media.InstagramMediaValidator.validate",
        lambda *args, **kwargs: raise_validation_error(),
    )

    # Act
    with pytest.raises(CreateInstagramPostException) as exc:
        InstagramPostService.create(db_gig.id, "shortcode")

    # Assert
    assert "Unable to create instagram post" in exc.exconly()


@freeze_time(_now)
def test_create_successfully_creates_an_instagram_post_but_doesnt_call_claimable_nor_callback(
    db_gig, monkeypatch
):
    # Arrange
    db_gig.is_verified = False
    media = {"id": "some_unique_id"}
    monkeypatch.setattr(
        "takumi.models.gig.Gig.end_of_review_period",
        mock.PropertyMock(return_value=_now - dt.timedelta(days=1)),
    )
    monkeypatch.setattr(
        "takumi.models.offer.Offer.has_all_gigs_claimable", mock.Mock(return_value=False)
    )
    monkeypatch.setattr(
        "takumi.validation.media.InstagramMediaValidator.validate", mock.Mock(return_value=media)
    )
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService._assemble_media",
        mock.Mock(return_value=[]),
    )
    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_instagram_post_media_to_cdn_and_update_instagram_post", mock.Mock()
    )

    # Act
    with mock.patch.object(OfferService, "set_claimable") as mock_set_claimable:
        result = InstagramPostService.create(db_gig.id, "shortcode")

    # Assert
    assert not mock_set_claimable.called
    assert result.ig_post_id == media["id"]
    assert db_gig.is_verified is True


@freeze_time(_now)
def test_create_successfully_creates_an_instagram_post_and_sets_offer_as_claimable(
    db_gig, monkeypatch
):
    # Arrange
    media = {"id": "some_unique_id", "created": _now - dt.timedelta(days=30)}
    monkeypatch.setattr(
        "takumi.models.gig.Gig.claimable_time",
        mock.PropertyMock(return_value=_now - dt.timedelta(days=1)),
    )
    monkeypatch.setattr(
        "takumi.models.offer.Offer.has_all_gigs_claimable", mock.Mock(return_value=True)
    )
    monkeypatch.setattr(
        "takumi.validation.media.InstagramMediaValidator.validate", mock.Mock(return_value=media)
    )
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService._assemble_media",
        mock.Mock(return_value=[]),
    )
    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_instagram_post_media_to_cdn_and_update_instagram_post", mock.Mock()
    )

    # Act
    with mock.patch.object(OfferService, "set_claimable") as mock_set_claimable:
        result = InstagramPostService.create(db_gig.id, "shortcode")

    # Assert
    assert mock_set_claimable.called
    assert result.ig_post_id == media["id"]


@freeze_time(_now)
def test_create_successfully_creates_an_instagram_post_and_schedules_is_claimable(
    db_gig, monkeypatch
):
    # Arrange
    media = {"id": "some_unique_id", "created": _now - dt.timedelta(days=30)}
    monkeypatch.setattr(
        "takumi.models.gig.Gig.claimable_time", mock.PropertyMock(return_value=_now)
    )
    monkeypatch.setattr(
        "takumi.validation.media.InstagramMediaValidator.validate", mock.Mock(return_value=media)
    )
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService._assemble_media",
        mock.Mock(return_value=[]),
    )
    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_instagram_post_media_to_cdn_and_update_instagram_post", mock.Mock()
    )

    # Act
    with mock.patch.object(OfferService, "set_claimable") as mock_set_claimable:
        result = InstagramPostService.create(db_gig.id, "shortcode")

    # Assert
    assert not mock_set_claimable.called
    assert result.ig_post_id == media["id"]


def test_update_media_url_raises_if_media_not_found(db_instagram_post):
    # Arrange
    unknown_id = uuid4_str()

    # Act
    with pytest.raises(MediaNotFoundException) as exc:
        InstagramPostService(db_instagram_post).update_media_url(unknown_id, "url")

    # Assert
    assert 'Media not found for id "{}"'.format(unknown_id) in exc.exconly()


def test_update_media_url_raises_if_media_is_not_on_the_instagram_post(
    db_instagram_post, instagram_post_factory, gig_factory, db_session
):
    # Arrange
    another_instagram_post = instagram_post_factory(gig=gig_factory())
    media = another_instagram_post.media[0]
    db_session.add(another_instagram_post)
    db_session.commit()

    # Act
    with pytest.raises(UpdateMediaUrlException) as exc:
        InstagramPostService(db_instagram_post).update_media_url(media.id, "url")

    # Assert
    assert (
        "<InstagramPost: {}> does not contain <Media: {}>".format(db_instagram_post.id, media.id)
        in exc.exconly()
    )


def test_update_media_thumbnail_updates_media_thumbnail(db_instagram_post, db_session):
    # Arrange
    new_thumbnail = "i am a new url"
    media = Video(
        url="url", thumbnail="thumbnail", owner_id=db_instagram_post.id, owner_type="instagram_post"
    )
    db_session.add(media)
    db_session.commit()

    # Act
    InstagramPostService(db_instagram_post).update_media_thumbnail(media.id, new_thumbnail)

    # Assert
    assert media.thumbnail == new_thumbnail


def test_update_media_thumbnail_raises_if_media_is_not_video(db_instagram_post):
    # Arrange
    media = db_instagram_post.media[0]
    assert media.type != MEDIA_TYPES.VIDEO

    # Act
    with pytest.raises(InvalidMediaException) as exc:
        InstagramPostService(db_instagram_post).update_media_thumbnail(media.id, "url")

    # Assert
    assert "Only video media has a thumbnail" in exc.exconly()


def test_update_media_thumbnail_raises_if_media_not_found(db_instagram_post):
    # Arrange
    unknown_id = uuid4_str()

    # Act
    with pytest.raises(MediaNotFoundException) as exc:
        InstagramPostService(db_instagram_post).update_media_thumbnail(unknown_id, "url")

    # Assert
    assert 'Media not found for id "{}"'.format(unknown_id) in exc.exconly()


def test_update_media_thumbnail_raises_if_media_is_not_on_the_instagram_post(
    db_instagram_post, instagram_post_factory, gig_factory, db_session
):
    # Arrange
    another_instagram_post = instagram_post_factory(gig=gig_factory())
    media = another_instagram_post.media[0]
    db_session.add(another_instagram_post)
    db_session.commit()

    # Act
    with pytest.raises(UpdateMediaThumbnailException) as exc:
        InstagramPostService(db_instagram_post).update_media_thumbnail(media.id, "url")

    # Assert
    assert (
        "<InstagramPost: {}> does not contain <Media: {}>".format(db_instagram_post.id, media.id)
        in exc.exconly()
    )


def test_update_media_url_updates_media_url(db_instagram_post):
    # Arrange
    new_url = "i am a new url"

    # Act
    InstagramPostService(db_instagram_post).update_media_url(db_instagram_post.media[0].id, new_url)

    # Assert
    assert db_instagram_post.media[0].url == new_url


def test_update_comments_updates_comments(db_instagram_post):
    # Arrange
    comments = 1337

    # Act
    InstagramPostService(db_instagram_post).update_comments(comments)

    # Assert
    assert db_instagram_post.comments == comments


def test_update_likes_updates_likes(db_instagram_post):
    # Arrange
    likes = 1337

    # Act
    InstagramPostService(db_instagram_post).update_likes(likes)

    # Assert
    assert db_instagram_post.likes == likes


@pytest.mark.skip(reason="Indico is having issues for now")
def test_update_caption_updates_sentiment_if_none_and_caption_is_none(
    db_instagram_post, db_session
):
    # Arrange
    db_instagram_post.sentiment = None
    db_instagram_post.caption = None
    caption = None
    db_session.commit()

    # Act
    with mock.patch.object(InstagramPostService, "update_sentiment") as mock_update_sentiment:
        with mock.patch(
            "takumi.services.instagram_post.instagram_post_tasks.update_caption_sentiment.delay"
        ) as mock_schedule_update_sentiment:
            InstagramPostService(db_instagram_post).update_caption(caption)

    # Assert
    mock_update_sentiment.assert_called_once_with(None)
    assert db_instagram_post.caption == caption
    assert not mock_schedule_update_sentiment.called


@pytest.mark.skip(reason="Indico is having issues for now")
def test_update_caption_updates_sentiment_from_task_if_caption_changes(
    db_instagram_post, db_session
):
    # Arrange
    db_instagram_post.sentiment = 42
    caption = "new caption"
    db_session.commit()

    # Act
    with mock.patch.object(InstagramPostService, "update_sentiment") as mock_update_sentiment:
        with mock.patch(
            "takumi.services.instagram_post.instagram_post_tasks.update_caption_sentiment.delay"
        ) as mock_schedule_update_sentiment:
            InstagramPostService(db_instagram_post).update_caption(caption)

    # Assert
    mock_schedule_update_sentiment.assert_called_once_with(db_instagram_post.id, caption)
    assert db_instagram_post.caption == caption
    assert not mock_update_sentiment.called


def test_update_caption_updates_caption_but_not_sentiment(db_instagram_post, db_session):
    # Arrange
    db_instagram_post.sentiment = 42
    caption = db_instagram_post.caption
    db_session.commit()

    # Act
    with mock.patch.object(InstagramPostService, "update_sentiment") as mock_update_sentiment:
        with mock.patch(
            "takumi.services.instagram_post.instagram_post_tasks.update_caption_sentiment.delay"
        ) as mock_schedule_update_sentiment:
            InstagramPostService(db_instagram_post).update_caption(caption)

    # Assert
    assert not mock_update_sentiment.called
    assert not mock_schedule_update_sentiment.called


def test_update_sentiment_updates_sentiment(db_instagram_post):
    # Arrange
    sentiment = 1337.42

    # Act
    InstagramPostService(db_instagram_post).update_sentiment(sentiment)

    # Assert
    assert db_instagram_post.sentiment == sentiment


def test_update_media_deleted_updates_deleted(db_instagram_post, db_session):
    # Arrange
    db_instagram_post.deleted = False
    db_session.commit()

    # Act
    InstagramPostService(db_instagram_post).update_media_deleted(True)

    # Assert
    assert db_instagram_post.deleted is True


def test_update_followers_updates_followers(db_instagram_post):
    # Arrange
    followers = 1337

    # Act
    InstagramPostService(db_instagram_post).update_followers(followers)

    # Assert
    assert db_instagram_post.followers == followers


def test_update_scraped_updates_scraped(db_instagram_post):
    # Arrange
    scraped = _now

    # Act
    InstagramPostService(db_instagram_post).update_scraped(scraped)

    # Assert
    assert db_instagram_post.scraped == scraped


def test_update_video_views_updates_video_views(db_instagram_post):
    # Arrange
    video_views = 1337

    # Act
    InstagramPostService(db_instagram_post).update_video_views(video_views)

    # Assert
    assert db_instagram_post.video_views == video_views


def test_unlink_gig_raises_if_already_unlinked(db_instagram_post, db_session):
    # Arrange
    db_instagram_post.gig = None
    db_session.commit()

    # Act
    with pytest.raises(UnlinkGigException) as exc:
        InstagramPostService(db_instagram_post).unlink_gig()

    # Assert
    assert (
        "<InstagramPost: {}> has already been unlinked".format(db_instagram_post.id)
        in exc.exconly()
    )


def test_unlink_gig_unlinks_gig(db_instagram_post, db_session):
    # Arrange
    gig = db_instagram_post.gig
    assert db_instagram_post.gig is not None

    # Act
    with InstagramPostService(db_instagram_post) as service:
        service.unlink_gig()

    # Assert
    assert db_instagram_post.gig is None
    assert gig.instagram_post is None
    assert db_instagram_post.events[0].type == "unlink_gig"
    assert gig.events[0].type == "unlink_instagram_post"
