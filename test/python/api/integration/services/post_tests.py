# encoding=utf-8
import datetime as dt

import mock
import pytest

from takumi.models import InstagramPostComment
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes
from takumi.services import PostService
from takumi.services.exceptions import (
    ArchivePostException,
    CampaignNotFound,
    CreatePostException,
    InvalidConditionsException,
    UpdatePostScheduleException,
)
from takumi.utils import uuid4_str


def test_post_service_get_by_id(db_post):
    post = PostService.get_by_id(db_post.id)
    assert post == db_post


def test_post_service_create_post(db_campaign, monkeypatch):
    monkeypatch.setattr(
        "takumi.services.post.CampaignService.get_by_id", mock.Mock(return_value=db_campaign)
    )
    post = PostService.create_post(db_campaign.id, PostTypes.standard)

    assert post.campaign_id == db_campaign.id
    assert post.post_type == PostTypes.standard
    assert post.conditions == [{"type": "hashtag", "value": "ad"}]


def test_post_service_create_post_raises_exception_if_campaign_not_found(monkeypatch):
    # Arrange
    some_id = uuid4_str()
    monkeypatch.setattr(
        "takumi.services.post.CampaignService.get_by_id", mock.Mock(return_value=None)
    )

    # Act
    with pytest.raises(CampaignNotFound) as exc:
        PostService.create_post(some_id)

    # Assert
    assert "<Campaign {}> not found".format(some_id) in exc.exconly()


def test_post_service_create_post_raises_exception_if_campaign_is_not_in_draft_state(
    monkeypatch, campaign
):
    # Arrange
    campaign.state = CAMPAIGN_STATES.LAUNCHED
    monkeypatch.setattr(
        "takumi.services.post.CampaignService.get_by_id", mock.Mock(return_value=campaign)
    )

    # Act
    with pytest.raises(CreatePostException) as exc:
        PostService.create_post(campaign.id)

    # Assert
    assert "Campaign needs to be in draft state in order to add posts to it" in exc.exconly()


def test_post_service_update_conditions(db_post):
    # Arrange
    expected_condition = [
        {"type": "mention", "value": "takumi"},
        {"type": "hashtag", "value": "dont_need_the_actual_hashtag"},
        {"type": "hashtag", "value": "1337"},
        {"type": "swipe_up_link", "value": "https://getyourhotdogs.com"},
    ]
    assert db_post.conditions != expected_condition

    # Act
    with PostService(db_post) as service:
        service.update_conditions(
            "@takumi",
            ["dont_need_the_actual_hashtag", "#1337"],
            "https://getyourhotdogs.com",
            start_first_hashtag=False,
        )

    # Assert
    assert db_post.conditions == expected_condition


def test_post_service_update_conditions_removes_empty_hashtags(db_post):
    # Arrange
    expected_hashtags = {"foo", "bar"}
    hashtags = {con["value"] for con in db_post.conditions if con["type"] == "hashtag"}
    assert hashtags != expected_hashtags

    # Act
    with PostService(db_post) as service:
        service.update_conditions(
            "@takumi", ["foo", "", "bar"], "https://getyourhotdogs.com", start_first_hashtag=False
        )

    # Assert
    hashtags = {con["value"] for con in db_post.conditions if con["type"] == "hashtag"}
    assert hashtags == expected_hashtags


def test_post_service_update_conditions_raises_on_invalid_hashtags(db_post):
    with pytest.raises(InvalidConditionsException, match="Invalid hashtags"):
        PostService(db_post).update_conditions(
            "@takumi",
            ["#derp", "#1337", "no-dashes-alllowed"],
            "https://getyourhotdogs.com",
            start_first_hashtag=False,
        )


def test_post_service_update_conditions_raises_on_invalid_mention(db_post):
    with pytest.raises(InvalidConditionsException, match="Invalid mentions"):
        PostService(db_post).update_conditions(
            "@takumi-with-dashes",
            ["#derp", "#1337"],
            "https://getyourhotdogs.com",
            start_first_hashtag=False,
        )


def test_post_service_update_requires_review_before_posting_success(db_post):
    # Arrange
    assert db_post.requires_review_before_posting is True

    # Act
    with PostService(db_post) as service:
        service.update_requires_review_before_posting(False)

    # Assert
    assert db_post.requires_review_before_posting is False


def test_post_service_update_schedule_sets_schedule(db_post):
    # Arrange
    opened = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)
    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=4)
    assert db_post.opened != opened
    assert db_post.deadline != deadline

    # Act
    with PostService(db_post) as service:
        with mock.patch("takumi.tasks.posts.reminders.tiger"):
            service.update_schedule(opened, deadline)

    # Assert
    assert db_post.opened == opened
    assert db_post.deadline == deadline


def test_post_service_update_schedule_sets_schedule_for_none_values(db_post, db_session):
    # Arrange
    opened = None
    deadline = None
    db_post.opened = None
    db_post.deadline = None
    db_session.commit()

    # Act
    with PostService(db_post) as service:
        with mock.patch("takumi.tasks.posts.reminders.tiger"):
            service.update_schedule(opened, deadline)

    # Assert
    assert db_post.opened is None
    assert db_post.deadline is None


def test_post_service_update_schedule_sets_schedule_when_opened_is_none_and_deadline_has_value(
    db_post, db_session
):
    # Arrange
    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=4)
    db_post.opened = None
    assert db_post.deadline != deadline
    db_session.commit()

    # Act
    with PostService(db_post) as service:
        with mock.patch("takumi.tasks.posts.reminders.tiger"):
            service.update_schedule(None, deadline)

    # Assert
    assert db_post.opened is None
    assert db_post.deadline == deadline


def test_post_service_update_schedule_sets_schedule_when_deadline_is_none_and_opened_has_value(
    db_post, db_session
):
    # Arrange
    opened = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)
    assert db_post.opened != opened
    db_post.deadline = None
    db_session.commit()

    # Act
    with PostService(db_post) as service:
        service.update_schedule(opened, None)

    # Assert
    assert db_post.opened == opened
    assert db_post.deadline is None


def test_post_service_update_schedule_raises_if_deadline_is_before_opened(db_post):
    # Arrange
    opened = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=4)
    deadline = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)

    # Act
    with pytest.raises(UpdatePostScheduleException) as exc:
        PostService(db_post).update_schedule(opened, deadline)

    # Assert
    assert "The post deadline must be after post to Instagram opens" in exc.exconly()


def test_post_service_update_schedule_raises_if_submission_deadline_is_after_deadline(db_post):
    # Arrange
    submission_deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    deadline = dt.datetime.now(dt.timezone.utc)

    # Act
    with pytest.raises(UpdatePostScheduleException) as exc:
        PostService(db_post).update_schedule(
            submission_deadline=submission_deadline, deadline=deadline
        )

    # Assert
    assert "The submission deadline must be before the deadline" in exc.exconly()


def test_post_service_update_schedule_raises_if_deadline_is_before_opened_after_falling_back_to_posts_attributes(
    db_post, db_session
):
    # Arrange
    db_post.opened = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=4)
    db_post.deadline = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)
    db_session.commit()

    # Act
    with pytest.raises(UpdatePostScheduleException) as exc:
        PostService(db_post).update_schedule(None, None)

    # Assert
    assert "The post deadline must be after post to Instagram opens" in exc.exconly()


def test_post_service_update_instructions(db_post):
    # Arrange
    instructions = "some instructions"
    assert db_post.instructions != instructions

    # Act
    with PostService(db_post) as service:
        service.update_instructions(instructions)

    # Assert
    assert db_post.instructions == instructions


def test_post_service_update_post_type(db_post):
    # Arrange
    post_type = PostTypes.video
    assert db_post.post_type != post_type

    # Act
    with PostService(db_post) as service:
        service.update_post_type(post_type)

    # Assert
    assert db_post.post_type == post_type


def test_archive_raises_an_exception_if_post_has_gigs(db_post, db_gig, db_session):
    # Arrange
    db_post.gigs = [db_gig]
    db_session.commit()

    # Act
    with pytest.raises(ArchivePostException) as exc:
        PostService(db_post).archive()

    # Assert
    assert "Post can only be archived if no gigs have been submitted for that post" in exc.exconly()


def test_archive_raises_an_exception_if_already_archived(db_post, db_gig, db_session):
    # Arrange
    db_post.archived = True
    db_session.commit()

    # Act
    with pytest.raises(ArchivePostException) as exc:
        PostService(db_post).archive()

    # Assert
    assert "Can't archive an already archived post" in exc.exconly()


def test_archive_raises_an_exception_if_only_one_campaign_post(db_post, db_campaign, db_session):
    # Arrange
    db_campaign.posts = [db_post]
    db_session.commit()

    # Act
    with pytest.raises(ArchivePostException) as exc:
        PostService(db_post).archive()

    # Assert
    assert "Campaigns must have at least one post" in exc.exconly()


def test_archive_sets_archived_to_true(db_post, db_campaign, post_factory, db_session):
    # Arrange
    db_post.archived = False
    db_campaign.posts = [post_factory(campaign=db_campaign), db_post]
    db_session.commit()

    # Act
    with PostService(db_post) as service:
        service.archive()

    # Assert
    assert db_post.archived is True


def test_get_comment_stats_returns_empty_list_for_unknown_id(db_session):
    # Arrange
    unknown_id = uuid4_str()

    # Act & Assert
    assert PostService.get_comment_stats(unknown_id) == []


def test_get_comment_stats_returns_emojis_and_hashtags_stats(
    db_session, db_post, post_factory, gig_factory, instagram_post_factory
):
    # Arrange
    ig_post1 = instagram_post_factory(
        gig=gig_factory(state=GIG_STATES.REJECTED),
        ig_comments=[
            InstagramPostComment(
                ig_comment_id=uuid4_str(),
                username="username",
                text="text",
                emojis=[1],
                hashtags=[1],
            )
        ],
    )
    ig_post2 = instagram_post_factory(
        ig_comments=[
            InstagramPostComment(
                ig_comment_id=uuid4_str(),
                username="username",
                text="text",
                emojis=[2],
                hashtags=[2],
            ),
            InstagramPostComment(
                ig_comment_id=uuid4_str(), username="username", text="text", hashtags=[3]
            ),
            InstagramPostComment(
                ig_comment_id=uuid4_str(), username="username", text="text", emojis=[4, 5]
            ),
            InstagramPostComment(ig_comment_id=uuid4_str(), username="username", text="text"),
        ]
    )
    ig_post3 = instagram_post_factory(
        ig_comments=[
            InstagramPostComment(
                ig_comment_id=uuid4_str(),
                username="username",
                text="text",
                emojis=[6],
                hashtags=[6],
            )
        ]
    )
    ig_post4 = instagram_post_factory(
        ig_comments=[
            InstagramPostComment(
                ig_comment_id=uuid4_str(),
                username="username",
                text="text",
                emojis=[7],
                hashtags=[7],
            )
        ]
    )
    db_post.gigs = [ig_post1.gig, ig_post2.gig, ig_post3.gig]
    another_post = post_factory()
    another_post.gigs = [ig_post4.gig]
    db_session.add_all([ig_post1, ig_post2, ig_post3, ig_post4, another_post])

    # Act
    result = PostService.get_comment_stats(db_post.id)

    # Assert
    assert len(result) == 4
    assert (["2"], ["2"]) in result
    assert ([], ["3"]) in result
    assert (["4", "5"], []) in result
    assert (["6"], ["6"]) in result


def test_post_service_update_gallery_photo_count(db_post):
    assert db_post.gallery_photo_count != 1337

    with PostService(db_post) as service:
        service.update_gallery_photo_count(1337)

    assert db_post.gallery_photo_count == 1337
