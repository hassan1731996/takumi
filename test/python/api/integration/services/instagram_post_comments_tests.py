import pytest

from takumi.sentiment import Sentiment
from takumi.services import InstagramPostCommentService
from takumi.services.exceptions import InstagramPostNotFoundException
from takumi.utils import uuid4_str


def test_get_by_id_returns_none_if_not_found(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act and Assert
    assert InstagramPostCommentService.get_by_id(unknown_id) is None


def test_get_by_id_returns_instagram_post_comment(db_instagram_post_comment):
    # Act and Assert
    assert (
        InstagramPostCommentService.get_by_id(db_instagram_post_comment.id)
        == db_instagram_post_comment
    )


def test_create_raises_if_instagram_post_not_found(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act
    with pytest.raises(InstagramPostNotFoundException) as exc:
        InstagramPostCommentService.create("some_id", "username", "text", unknown_id, [], [], None)

    # Assert
    assert "InstagramPost with id {} not found".format(unknown_id) in exc.exconly()


def test_create_creates_instagram_post_comment(db_instagram_post):
    # Arrange
    ig_comment_id = "some_id"

    # Act
    InstagramPostCommentService.create(
        ig_comment_id, "username", "text", db_instagram_post.id, [], [], None
    )

    # Assert
    assert db_instagram_post.ig_comments[0].ig_comment_id == ig_comment_id


def test_update_sentiment_updates_sentiment(db_instagram_post_comment):
    # Arrange
    sentiment = Sentiment(
        text="Hello",
        language_code="en",
        sentiment="POSITIVE",
        positive_score=0.9,
        neutral_score=0.01,
        negative_score=0.05,
        mixed_score=0.04,
    )

    # Act
    InstagramPostCommentService(db_instagram_post_comment).update_sentiment(sentiment)

    # Assert
    assert db_instagram_post_comment.sentiment_type == "POSITIVE"
    assert db_instagram_post_comment.sentiment_positive_score == 0.9
