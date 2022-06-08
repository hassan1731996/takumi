import datetime as dt

import mock
import pytest

from takumi.ig.instascrape import NotFound
from takumi.models import StoryFrame, Video
from takumi.models.media import TYPES as MEDIA_TYPES
from takumi.models.post import PostTypes
from takumi.services import InstagramStoryService
from takumi.services.exceptions import NotAStoryPostException
from takumi.services.instagram_story import InvalidMediaException, StoryFrameNotFoundException
from takumi.utils import uuid4_str


def test_get_by_id_returns_none_if_not_found(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act & Assert
    assert InstagramStoryService.get_by_id(unknown_id) is None


def test_get_by_id_returns_instagram_story(db_instagram_story):
    # Act & Assert
    assert InstagramStoryService.get_by_id(db_instagram_story.id) == db_instagram_story


def _scraped_story():
    return {
        "data": {
            "items": [
                {
                    "display_url": "display_url1",
                    "is_video": False,
                    "id": "storyframe1",
                    "swipe_up_url": "swipe_up_url1",
                    "tappable_objects": [
                        {"id": "1", "short_name": "location1", "type": "location"},
                        {"name": "MENTION1", "username": "mention1", "type": "mention"},
                        {"id": "11", "name": "#hashtag1", "type": "hashtag"},
                    ],
                    "taken_at_timestamp": "2018-08-20T22:10:01+00:00",
                },
                {
                    "display_url": "display_url2",
                    "is_video": True,
                    "id": "storyframe2",
                    "swipe_up_url": "swipe_up_url2",
                    "tappable_objects": [
                        {"id": "2", "short_name": "location2", "type": "location"},
                        {"name": "MENTION2", "username": "mention2", "type": "mention"},
                        {"id": "22", "name": "#hashtag2", "type": "hashtag"},
                    ],
                    "video_url": "video_url",
                    "taken_at_timestamp": "2018-08-20T22:10:01+00:00",
                },
            ]
        }
    }


def test_create_story_success(db_gig, monkeypatch):
    # Arrange
    assert db_gig.instagram_story is None
    monkeypatch.setattr(
        "takumi.models.gig.Gig.end_of_review_period",
        mock.PropertyMock(return_value=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)),
    )
    monkeypatch.setattr(
        "takumi.models.offer.Offer.has_all_gigs_claimable", mock.Mock(return_value=False)
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.story_downloader.download_influencer_story_frames", mock.Mock()
    )
    monkeypatch.setattr(
        "takumi.services.instagram_story.instascrape.get_user_story",
        lambda *args, **kwargs: _scraped_story(),
    )
    # Act
    InstagramStoryService.create(db_gig.id)

    # Assert
    assert db_gig.instagram_story is not None
    # assert len(db_gig.instagram_story.story_frames) == 2
    # story_frame1 = db_gig.instagram_story.story_frames[0]
    # story_frame2 = db_gig.instagram_story.story_frames[1]
    #
    # assert story_frame1.mentions == [{"name": "MENTION1", "username": "mention1"}]
    # assert story_frame1.locations == [{"id": "1", "name": "location1"}]
    # assert story_frame1.hashtags == [{"id": "11", "name": "#hashtag1"}]
    # assert story_frame1.media.type == MEDIA_TYPES.IMAGE
    # assert story_frame1.media.url == "display_url1"
    # assert story_frame1.swipe_up_link == "swipe_up_url1"
    #
    # assert story_frame2.mentions == [{"name": "MENTION2", "username": "mention2"}]
    # assert story_frame2.locations == [{"id": "2", "name": "location2"}]
    # assert story_frame2.hashtags == [{"id": "22", "name": "#hashtag2"}]
    # assert story_frame2.media.type == MEDIA_TYPES.VIDEO
    # assert story_frame2.media.url == "video_url"
    # assert story_frame2.media.thumbnail == "display_url2"
    # assert story_frame2.swipe_up_link == "swipe_up_url2"


def test_get_story_frame_fails_if_story_frame_does_not_exist(db_instagram_story):
    # Arrange
    unknown_id = uuid4_str()

    # Act & Assert
    with pytest.raises(StoryFrameNotFoundException):
        InstagramStoryService(db_instagram_story)._get_story_frame(unknown_id)


def test_get_story_frame_success(db_instagram_story):
    # Arrange
    story_frame = db_instagram_story.story_frames[0]

    # Act & Assert
    assert InstagramStoryService(db_instagram_story)._get_story_frame(story_frame.id) == story_frame


def test_update_media_url(db_instagram_story):
    # Arrange
    new_url = "new url"
    story_frame = db_instagram_story.story_frames[0]
    assert story_frame.media.url != new_url

    # Act
    InstagramStoryService(db_instagram_story).update_media_url(story_frame.id, new_url)

    # Assert
    assert story_frame.media.url == new_url


def test_update_media_thumbnail_fails_for_none_video(db_instagram_story):
    # Arrange
    story_frame = db_instagram_story.story_frames[0]
    assert story_frame.media.type == MEDIA_TYPES.IMAGE

    # Act & Assert
    with pytest.raises(InvalidMediaException):
        InstagramStoryService(db_instagram_story).update_media_thumbnail(story_frame.id, "Fail")


def test_update_media_thumbnail_success(db_session, db_gig, instagram_story_factory):
    # Arrange
    new_thumbnail = "new thumbnail"
    video_story_frame = StoryFrame(
        id=uuid4_str(), ig_story_id="123randomstory", influencer=db_gig.offer.influencer
    )
    video_story_frame.media = Video(
        url="url",
        thumbnail="old_thumbnail",
        owner_id=video_story_frame.id,
        owner_type="story_frame",
    )
    instagram_story = instagram_story_factory(gig=db_gig, story_frames=[video_story_frame])
    db_session.add(instagram_story)
    db_session.commit()

    # Act
    InstagramStoryService(instagram_story).update_media_thumbnail(
        video_story_frame.id, new_thumbnail
    )

    # Assert
    assert video_story_frame.media.thumbnail == new_thumbnail


def test_unlink_gig(db_instagram_story):
    assert db_instagram_story.gig is not None

    InstagramStoryService(db_instagram_story).unlink_gig()

    assert db_instagram_story.gig is None


def test_copy_submission_to_story_fails_for_non_story_posts(db_gig):
    assert db_gig.post.post_type != PostTypes.story

    with pytest.raises(NotAStoryPostException):
        InstagramStoryService.copy_submission_to_story(db_gig.id)


def test_copy_submission_to_story_when_instagram_story_does_not_exist(db_submission):
    db_submission.gig.post.post_type = PostTypes.story
    assert db_submission.gig.instagram_story is None

    instagram_story = InstagramStoryService.copy_submission_to_story(db_submission.gig.id)

    assert db_submission.media[0].url == instagram_story.story_frames[0].media.url
    assert instagram_story.has_marked_frames is True


def test_copy_submission_to_story_when_instagram_story_exists(db_instagram_story, db_submission):
    db_instagram_story.gig.post.post_type = PostTypes.story
    db_instagram_story.story_frames = []
    assert db_instagram_story.has_marked_frames is False

    instagram_story = InstagramStoryService.copy_submission_to_story(db_instagram_story.gig.id)

    assert (
        db_instagram_story.gig.submission.media[0].url == instagram_story.story_frames[0].media.url
    )

    assert instagram_story.has_marked_frames is True


def test_link_story_frame_sucess(db_instagram_story, db_story_frame):
    assert db_story_frame.instagram_story_id is None
    assert db_instagram_story.gig.is_verified is False

    InstagramStoryService(db_instagram_story).link_story_frame(db_story_frame.id)

    assert db_story_frame.instagram_story_id == db_instagram_story.id
    assert db_instagram_story.gig.is_verified is True


def test_instagram_story_download_story_frames_returns_empty_when_no_story_found(
    db_instagram_story, monkeypatch
):
    monkeypatch.setattr(
        "takumi.services.instagram_story.instascrape.get_user_story",
        mock.Mock(side_effect=[NotFound]),
    )

    story_frames = InstagramStoryService.download_story_frames(
        db_instagram_story.gig.offer.influencer_id
    )
    assert story_frames == []
