# encoding=utf-8

import mock
import pytest

from takumi.services import InstagramPostCommentService, InstagramPostService, OfferService
from takumi.tasks import TaskException
from takumi.tasks.instagram_post import (
    scrape_and_update_instagram_post_media,
    update_caption_sentiment,
    update_instagram_post_comments,
)
from takumi.utils import uuid4_str


def test_scrape_and_update_instagram_post_media_raises_if_instagram_post_not_found(
    app, monkeypatch
):
    # Arrange
    instagram_post_id = "some_id"
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: None)

    # Act
    with pytest.raises(TaskException) as exc:
        scrape_and_update_instagram_post_media(instagram_post_id)

    # Assert
    assert 'InstagramPost with id "{}" not found'.format(instagram_post_id) in exc.exconly()


def test_scrape_and_update_instagram_post_media_doesnt_scrape_unlinked_instagram_post(
    instagram_post, monkeypatch
):
    # Arrange
    instagram_post.gig = None
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)

    # Act
    with mock.patch("takumi.extensions.instascrape.get_media") as mock_scrape:
        scrape_and_update_instagram_post_media(instagram_post.id)

    # Assert
    assert not mock_scrape.called


def test_scrape_and_update_instagram_post_media_updates_media_deleted_comments_likes_and_caption(
    instagram_post, monkeypatch
):
    # Arrange
    media_data = {
        "comments": {"count": 1337, "nodes": []},
        "likes": {"count": 1337},
        "caption": "Some caption",
        "owner": {"username": "someusername"},
        "video_view_count": 1337,
    }
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr(
        "takumi.extensions.instascrape.get_media", lambda *args, **kwargs: media_data
    )
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    # Act
    with mock.patch.object(
        InstagramPostService, "update_media_deleted"
    ) as mock_update_media_deleted:
        with mock.patch.object(InstagramPostService, "update_comments") as mock_update_comments:
            with mock.patch.object(InstagramPostService, "update_likes") as mock_update_likes:
                with mock.patch.object(
                    InstagramPostService, "update_video_views"
                ) as mock_update_video_views:
                    with mock.patch.object(
                        InstagramPostService, "update_caption"
                    ) as mock_update_caption:
                        with mock.patch(
                            "takumi.tasks.instagram_post.update_instagram_post_comments.delay"
                        ) as mock_update_instagram_post_comments:
                            scrape_and_update_instagram_post_media(instagram_post.id)

    # Assert
    mock_update_media_deleted.assert_called_once_with(False)
    mock_update_instagram_post_comments.assert_called_once_with(instagram_post.id, [])
    mock_update_comments.assert_called_once_with(1337)
    mock_update_video_views.assert_called_once_with(1337)
    mock_update_likes.assert_called_once_with(1337)
    mock_update_caption.assert_called_once_with("Some caption")


def test_scrape_and_update_instagram_post_media_calls_offer_update_engagements_per_post_if_engagement_changed(
    instagram_post, offer, monkeypatch
):
    # Arrange
    media_data = {
        "comments": {"count": 1, "nodes": []},
        "likes": {"count": 1},
        "caption": "Some caption",
        "owner": {"username": "someusername"},
        "video_view_count": 1337,
    }

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr(
        "takumi.extensions.instascrape.get_media", lambda *args, **kwargs: media_data
    )
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    assert (
        instagram_post.engagements != media_data["comments"]["count"] + media_data["likes"]["count"]
    )

    with mock.patch.object(
        OfferService, "update_engagements_per_post"
    ) as mock_update_offer_engagements:
        scrape_and_update_instagram_post_media(instagram_post.id)
    assert mock_update_offer_engagements.called


def test_scrape_and_update_instagram_post_media_sets_followers_if_not_set(
    instagram_post, monkeypatch
):
    # Arrange
    instagram_post.followers = 0

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.extensions.instascrape.get_user", lambda *args: {"followers": 1234})

    # Act
    with mock.patch.object(OfferService, "update_engagements_per_post"):
        with mock.patch.object(InstagramPostService, "update_followers") as mock_set_followers:
            scrape_and_update_instagram_post_media(instagram_post.id)

    # Assert
    mock_set_followers.assert_called_with(1234)


def test_scrape_and_update_instagram_post_media_doesnt_set_followers_if_already_set(
    instagram_post, monkeypatch
):
    # Arrange
    instagram_post.followers = 1234

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr(
        "takumi.tasks.instagram_post.instascrape.get_user", lambda *args: {"followers": 1234}
    )
    monkeypatch.setattr(
        "takumi.tasks.instagram_post.instascrape.get_media",
        lambda *args, **kwargs: {
            "comments": {"count": 1234, "nodes": []},
            "likes": {"count": 1234},
            "caption": "foo",
            "owner": {"username": "foo"},
        },
    )

    # Act
    with mock.patch.object(OfferService, "update_engagements_per_post"):
        with mock.patch.object(InstagramPostService, "update_followers") as mock_set_followers:
            scrape_and_update_instagram_post_media(instagram_post.id)

    # Assert
    mock_set_followers.assert_not_called()


@pytest.mark.skip(reason="Indico is having issues for now")
def test_update_caption_sentiment_raises_if_instagram_post_not_found(app, monkeypatch):
    # Arrange
    unknown_id = uuid4_str()
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: None)

    # Act
    with pytest.raises(TaskException) as exc:
        update_caption_sentiment(unknown_id, "caption")

    # Assert
    assert 'InstagramPost with id "{}" not found'.format(unknown_id) in exc.exconly()


def test_update_caption_sentiment_returns_if_the_caption_isnt_analyzable(
    instagram_post, monkeypatch
):
    # Arrange
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr("takumi.tasks.instagram_post.has_analyzable_text", lambda *args: False)

    # Act
    with mock.patch.object(InstagramPostService, "update_sentiment") as mock_update_sentiment:
        update_caption_sentiment(instagram_post.id, "caption")

    # Assert
    mock_update_sentiment.assert_not_called()


@pytest.mark.skip(reason="Indico is having issues for now")
def test_update_caption_sentiment_updates_sentiment(instagram_post, monkeypatch):
    # Arrange
    result = 1337
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: instagram_post)
    monkeypatch.setattr("takumi.tasks.instagram_post.has_analyzable_text", lambda *args: True)
    monkeypatch.setattr("takumi.tasks.instagram_post.analyze_text_sentiment", lambda *args: result)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    # Act
    with mock.patch.object(InstagramPostService, "update_sentiment") as mock_update_sentiment:
        update_caption_sentiment(instagram_post.id, "caption")

    # Assert
    mock_update_sentiment.assert_called_once_with(result)


def _create_comments(count=1, hashtags=False, emojis=False):
    text = "This is comment number {}"
    if hashtags:
        text += " #l4l #yolo #yolo #yolo"
    if emojis:
        text += (
            " \U0001F525\U0001F525\U0001F525\U0001F525\u2764\ufe0f"  # Four fires and big red heart
        )

    return [
        {"id": "comment{}".format(x), "username": "test_user{}".format(x), "text": text.format(x)}
        for x in range(count)
    ]


def test_update_instagram_post_comments_saves_comments_to_db(instagram_post, monkeypatch):
    # Arrange
    comment_data = _create_comments(1)
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService.get_by_id",
        mock.Mock(return_value=instagram_post),
    )
    monkeypatch.setattr(
        "takumi.services.instagram_post_comment.InstagramPostCommentService.get_by_ig_comment_id",
        mock.Mock(return_value=None),
    )
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    # Act
    with mock.patch.object(InstagramPostCommentService, "create") as mock_create:
        update_instagram_post_comments(instagram_post, comment_data)

    # Assert
    mock_create.assert_called_once()


def test_update_instagram_post_comments_saves_only_new_commits_to_db(instagram_post, monkeypatch):
    comment_data = _create_comments(2)
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService.get_by_id",
        mock.Mock(return_value=instagram_post),
    )
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    with mock.patch("takumi.services.InstagramPostCommentService") as mock_service:
        mock_service.get_by_ig_comment_id.side_effect = [mock.Mock(), None]

        update_instagram_post_comments(instagram_post, comment_data)

    mock_service.create.assert_called_once()
