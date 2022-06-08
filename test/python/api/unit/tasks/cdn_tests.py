# encoding=utf-8

import mock
import pytest

from takumi.constants import IMGIX_TAKUMI_URL
from takumi.models.media import Video
from takumi.services import InstagramPostService, InstagramStoryService
from takumi.tasks.cdn import (
    ANONYMOUS,
    ImageDownloadException,
    PathException,
    construct_s3_path,
    set_user_profile_picture,
    upload_instagram_post_media_to_cdn_and_update_instagram_post,
    upload_media_to_cdn,
    upload_profile_to_cdn,
    upload_story_media_to_cdn_and_update_story,
)


def test_construct_s3_path_raises_exception_for_invalid_image_url():
    # Arrange
    image_url = "something_invalid"

    # Act / Assert
    with pytest.raises(PathException):
        construct_s3_path(image_url, "id")


def test_construct_s3_path_returns_expected_path(monkeypatch):
    # Arrange
    image_url = "someurltophoto.jpg"

    monkeypatch.setattr("takumi.tasks.cdn.get_human_random_string", lambda *args: "random_hash")

    # Act
    res_path = construct_s3_path(image_url, "my_id")

    # Assert
    assert res_path == "m/y/my_id-random_hash.jpg"


def test_set_user_profile_picture_saves_original_profile_picture(influencer, monkeypatch):
    # Arrange
    user = influencer.user
    original_profile_picture = influencer.profile_picture

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: user)
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda *args: None)

    # Act
    set_user_profile_picture(user.id, "derp")

    # Assert
    assert (
        user.influencer.instagram_account.info["original_profile_picture"]
        == original_profile_picture
    )
    assert influencer.profile_picture == "derp"


def test_set_user_profile_picture_does_not_save_original_profile_picture_if_from_cdn(
    influencer, monkeypatch
):
    # Arrange
    user = influencer.user
    influencer.instagram_account.profile_picture = "https://lemonade.imgix.net"

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: user)
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda *args: None)

    # Act
    set_user_profile_picture(user.id, "derp")

    # Assert
    assert not user.influencer.instagram_account.info.get("original_profile_picture")
    assert influencer.instagram_account.profile_picture == "derp"


def test_upload_profile_to_cdn_sets_user_image_to_anonymous_if_image_not_found(
    influencer_user, influencer, monkeypatch
):
    # Arrange
    user = influencer_user
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: user)
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    assert influencer.instagram_account.profile_picture != ANONYMOUS

    # Act
    with mock.patch("takumi.tasks.cdn.requests.head") as mock_get:
        mock_get.return_value.status_code = 404
        upload_profile_to_cdn(image_url="https://example.com/image.jpg", user_id=user.id)

    # Assert
    assert influencer.instagram_account.profile_picture == ANONYMOUS


def test_upload_profile_to_cdn_updates_profile_to_our_cdn_url(
    influencer_user, influencer, monkeypatch
):
    # Arrange
    user = influencer_user
    external_url = "https://instagram-cdn.com/image.jpg"
    influencer.instagram_account.profile_picture = external_url
    imgix_url = "imgix_url"

    monkeypatch.setattr("takumi.tasks.cdn.upload_media_to_cdn", lambda *args: imgix_url)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: user)
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    with mock.patch("takumi.tasks.cdn.requests.head") as mock_get:
        mock_get.return_value.status_code = 200
        upload_profile_to_cdn(
            image_url=influencer.instagram_account.profile_picture, user_id=user.id
        )

    # Assert
    assert influencer.instagram_account.profile_picture == imgix_url


def test_upload_media_to_cdn_raises_exception_on_failed_image_download():
    with pytest.raises(ImageDownloadException):
        with mock.patch("takumi.tasks.cdn.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            upload_media_to_cdn("image_url", "gig_id")


def test_upload_instagram_post_media_and_update_instagram_post_replaces_media_urls_with_cdn_url(
    instagram_post, monkeypatch
):
    # Arrange
    imgix_url = "imgix_url"
    monkeypatch.setattr("takumi.tasks.cdn.upload_media_to_cdn", lambda *args: imgix_url)
    monkeypatch.setattr(
        "takumi.tasks.cdn.InstagramPostService.get_by_id", mock.Mock(return_value=instagram_post)
    )
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    with mock.patch.object(InstagramPostService, "update_media_url") as mock_update_media_url:
        upload_instagram_post_media_to_cdn_and_update_instagram_post(instagram_post.id)

    # Assert
    mock_update_media_url.assert_called_once_with(instagram_post.ig_post_id, imgix_url)


def test_upload_instagram_post_media_and_update_instagram_post_replaced_thumbnails_on_videos(
    instagram_post, monkeypatch
):
    # Arrange
    image_url = "http://image.jpg"
    video_url = "http://video.mp4"

    instagram_post.media = [Video(url=video_url, thumbnail=image_url)]

    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_media_to_cdn", mock.Mock(side_effect=[video_url, image_url])
    )
    monkeypatch.setattr(
        "takumi.tasks.cdn.InstagramPostService.get_by_id", mock.Mock(return_value=instagram_post)
    )
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    with mock.patch.object(InstagramPostService, "update_media_url") as mock_url:
        with mock.patch.object(InstagramPostService, "update_media_thumbnail") as mock_thumb:
            upload_instagram_post_media_to_cdn_and_update_instagram_post(instagram_post.id)

    # Assert
    mock_url.assert_called_once_with(instagram_post.ig_post_id, video_url)
    mock_thumb.assert_called_once_with(instagram_post.ig_post_id, image_url)


def test_upload_instagram_post_media_and_update_instagram_post_replaces_media_urls_with_cdn_url_for_gallery_media(
    instagram_post_gallery, monkeypatch
):
    # Arrange
    imgix_url = "imgix_url"
    mock_upload_media = mock.Mock(return_value=imgix_url)
    monkeypatch.setattr("takumi.tasks.cdn.upload_media_to_cdn", mock_upload_media)
    monkeypatch.setattr(
        "takumi.tasks.cdn.InstagramPostService.get_by_id",
        mock.Mock(return_value=instagram_post_gallery),
    )
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    with mock.patch.object(InstagramPostService, "update_media_url") as mock_update_media_url:
        with mock.patch.object(InstagramPostService, "update_media_thumbnail") as mock_thumb:
            upload_instagram_post_media_to_cdn_and_update_instagram_post(instagram_post_gallery.id)

    # Assert
    assert mock_update_media_url.call_count == 3
    assert mock_upload_media.call_count == 4
    assert mock_thumb.call_count == 1


def test_upload_instagram_story_media_and_update_instagram_story_replaces_media_urls_with_cdn_url(
    instagram_story, monkeypatch
):
    # Arrange
    image_url = "http://image.jpg"
    video_url = "http://video.mp4"

    story_frame = instagram_story.story_frames[0]
    story_frame.media = Video(url=video_url, thumbnail=image_url)

    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_media_to_cdn", mock.Mock(side_effect=[video_url, image_url])
    )
    monkeypatch.setattr(
        "takumi.tasks.cdn.InstagramStoryService.get_story_frame_by_id",
        mock.Mock(return_value=story_frame),
    )
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    with mock.patch.object(InstagramStoryService, "update_media_url") as mock_url:
        with mock.patch.object(InstagramStoryService, "update_media_thumbnail") as mock_thumb:
            upload_story_media_to_cdn_and_update_story(story_frame.id)

    # Assert
    mock_url.assert_called_once_with(story_frame.id, video_url)
    mock_thumb.assert_called_once_with(story_frame.id, image_url)


def test_upload_instagram_story_media_and_update_instagram_story_does_not_replace_already_uploaded_urls(
    instagram_story, monkeypatch
):
    # Arrange
    image_url = IMGIX_TAKUMI_URL + "image.jpg"
    video_url = IMGIX_TAKUMI_URL + "video.mp4"

    story_frame = instagram_story.story_frames[0]
    story_frame.media = Video(url=video_url, thumbnail=image_url)

    monkeypatch.setattr(
        "takumi.tasks.cdn.InstagramStoryService.get_story_frame_by_id",
        mock.Mock(return_value=story_frame),
    )

    # Act
    with mock.patch.object(InstagramStoryService, "update_media_url") as mock_url:
        with mock.patch.object(InstagramStoryService, "update_media_thumbnail") as mock_thumb:
            upload_story_media_to_cdn_and_update_story(instagram_story.id)

    # Assert
    assert not mock_url.called
    assert not mock_thumb.called
