import datetime as dt

import pytest

from takumi.events.instagram_post import InstagramPostLog
from takumi.models import Image, Video


@pytest.fixture(scope="function")
def log(instagram_post):
    # Arrange
    yield InstagramPostLog(instagram_post)


def test_create_instagram_post(log, instagram_post):
    # Act
    log.add_event(
        "create",
        {
            "gig_id": "some_id",
            "media": [],
            "post": {"instructions": "some_instruction", "conditions": "some_conditions"},
            "caption": "some_caption",
            "shortcode": "some_shortcode",
            "ig_post_id": "some_ig_post_id",
            "link": "some_link",
            "deleted": False,
            "sponsors": [],
            "likes": 1337,
            "comments": 42,
            "posted": None,
            "followers": 13,
            "video_views": 0,
            "scraped": None,
        },
    )

    # Assert
    assert instagram_post.link == "some_link"
    assert instagram_post.likes == 1337
    assert instagram_post.comments == 42
    assert instagram_post.followers == 13


def test_set_caption(log, instagram_post):
    # Act
    log.add_event("set_caption", {"caption": "some_caption"})

    # Assert
    assert instagram_post.caption == "some_caption"


def test_set_comments(log, instagram_post):
    # Act
    log.add_event("set_comments", {"comments": 1337})

    # Assert
    assert instagram_post.comments == 1337


def test_set_followers(log, instagram_post):
    # Act
    log.add_event("set_followers", {"followers": 1337})

    # Assert
    assert instagram_post.followers == 1337


def test_set_is_deleted(log, instagram_post):
    # Act
    log.add_event("set_is_deleted", {"deleted": True})

    # Assert
    assert instagram_post.deleted is True


def test_set_likes(log, instagram_post):
    # Act
    log.add_event("set_likes", {"likes": 1337})

    # Assert
    assert instagram_post.likes == 1337


def test_set_media_url(log, instagram_post):
    # Arrange
    media_id = "some_id"
    media_url = "some_url"
    instagram_post.media = [
        Image(
            id="some_id",
            url="not_the_same_url",
            owner_id=instagram_post.id,
            owner_type="instagram_post",
        )
    ]

    # Act
    log.add_event("set_media_url", {"media_id": media_id, "url": media_url})

    # Assert
    assert instagram_post.media[0].url == media_url


def test_set_media_thumbnail(log, instagram_post):
    # Arrange
    media_id = "some_id"
    new_thumbnail = "new_thumb"
    instagram_post.media = [
        Video(
            id="some_id",
            url="video_url",
            thumbnail="thumbnail",
            owner_id=instagram_post.id,
            owner_type="instagram_post",
        )
    ]

    # Act
    log.add_event("set_media_thumbnail", {"media_id": media_id, "thumbnail": new_thumbnail})

    # Assert
    assert instagram_post.media[0].thumbnail == new_thumbnail


def test_set_scraped(log, instagram_post):
    # Arrange
    scraped = dt.datetime.now(dt.timezone.utc)

    # Act
    log.add_event("set_scraped", {"scraped": scraped})

    # Assert
    assert instagram_post.scraped == scraped


def test_set_sentiment(log, instagram_post):
    # Act
    log.add_event("set_sentiment", {"sentiment": 1337.42})

    # Assert
    assert instagram_post.sentiment == 1337.42


def test_set_video_views(log, instagram_post):
    # Act
    log.add_event("set_video_views", {"video_views": 1337})

    # Assert
    assert instagram_post.video_views == 1337
