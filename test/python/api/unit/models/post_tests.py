# encoding=utf-8

import datetime as dt
from unittest import TestCase

import mock
from freezegun import freeze_time

from takumi.models import Gig, InstagramPost, Post
from takumi.models.gig import STATES as GIG_STATES

frozen_now = dt.datetime(2010, 1, 1, 0, 0, tzinfo=dt.timezone.utc)


@freeze_time(frozen_now)
def test_post_is_open_boolean_false_state():
    later = frozen_now + dt.timedelta(seconds=1)
    assert Post(opened=later).is_open == False


@freeze_time(frozen_now)
def test_post_is_open_boolean_true_state():
    assert Post(opened=frozen_now).is_open == True


class PostGigStatAccumulatorTests(TestCase):
    def setUp(self):
        post1 = InstagramPost(likes=100, comments=10, followers=1000, video_views=200)
        post2 = InstagramPost(likes=100, comments=10, followers=1000, video_views=300)

        gig1 = Gig(state=GIG_STATES.APPROVED, instagram_post=post1, is_verified=True)
        gig2 = Gig(state=GIG_STATES.REJECTED, instagram_post=post2, is_verified=True)
        self.post = Post(gigs=[gig1, gig2])

    def test_post_model_likes(self):
        assert self.post.likes == 100

    def test_post_model_comments(self):
        assert self.post.comments == 10

    def test_post_model_reach(self):
        assert self.post.reach == 1000

    def test_post_model_engagement(self):
        assert self.post.engagement == 0.11

    def test_post_model_engagements(self):
        assert self.post.engagements == 110

    def test_post_model_video_views(self):
        assert self.post.video_views == 200

    def test_post_model_video_engagement(self):
        assert self.post.video_engagement == 0.2


def test_post_recent_gig_posted_is_true_if_there_are_recent_gigs(app, post):
    with mock.patch("sqlalchemy.orm.query.Query.count") as sql_count:
        sql_count.return_value = 1

        assert post.recent_gig_posted() is True


def test_post_recent_gig_posted_is_false_if_there_are_no_recent_gigs(app, post):
    with mock.patch("sqlalchemy.orm.query.Query.count") as sql_count:
        sql_count.return_value = 0

        assert post.recent_gig_posted() is False


def test_post_emoji_count_returns_a_count_if_items(monkeypatch):
    # This is how the list of lists are returned from the database
    db_return_set = [
        (["emoji1"], ["hash1", "hash2"]),
        (["emoji2"], []),
        ([], ["hash1"]),
        (["emoji1", "emoji2", "emoji4"], []),
        (["emoji1", "emoji3"], ["hash2", "hash3"]),
    ]

    monkeypatch.setattr(
        "takumi.services.post.PostService.get_comment_stats", mock.Mock(return_value=db_return_set)
    )

    post = Post()

    count = post.comment_stat_count()
    emoji_count = count["emojis"]
    hashtag_count = count["hashtags"]

    assert emoji_count.get("emoji1") == 3
    assert emoji_count.get("emoji2") == 2
    assert emoji_count.get("emoji3") == 1
    assert emoji_count.get("emoji4") == 1

    assert hashtag_count.get("hash1") == 2
    assert hashtag_count.get("hash2") == 2
    assert hashtag_count.get("hash3") == 1


def test_post_emoji_count_returns_none_count_if_no_results(monkeypatch):
    monkeypatch.setattr(
        "takumi.services.post.PostService.get_comment_stats", mock.Mock(return_value=[])
    )

    post = Post()

    count = post.comment_stat_count()
    assert len(count["emojis"]) == 0
    assert len(count["hashtags"]) == 0


def test_post_media_requirements_with_no_gallery(post):
    assert post.gallery_photo_count == 0
    assert post.media_requirements == [{"type": "any"}]


def test_post_media_requirements_with_with_gallery(post):
    post.gallery_photo_count = 2

    assert post.media_requirements == [{"type": "any"}, {"type": "any"}, {"type": "any"}]
