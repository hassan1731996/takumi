import datetime as dt

import mock
from freezegun import freeze_time

from takumi.tasks.posts.reminders import get_reminder_task, schedule_post_reminders

_now = dt.datetime(2017, 1, 1, 0, tzinfo=dt.timezone.utc)


def _get_reminder_labels(post):
    return [
        reminder.label
        for reminder in post.get_reminder_schedule
        if get_reminder_task(post=post, reminder=reminder) is not None
    ]


@freeze_time(_now)
def test_get_reminder_schedule_returns_sorted_reminders(post, client, developer_user):
    # Arrange
    post.submission_deadline = _now + dt.timedelta(days=2)
    post.opened = _now + dt.timedelta(days=3)
    post.deadline = _now + dt.timedelta(days=4)

    # Act
    with mock.patch("takumi.tasks.posts.reminders.tiger"):
        schedule_post_reminders(post)

    # Assert
    assert _get_reminder_labels(post) == [
        "SUBMISSION_REMINDER_48",
        "SUBMISSION_REMINDER_24",
        "SUBMISSION_REMINDER_6",
        "SUBMISSION_REMINDER_1",
        "POST_OPENS_REMINDER",
        "POST_TO_INSTAGRAM_REMINDER_24",
        "POST_TO_INSTAGRAM_REMINDER_6",
        "POST_TO_INSTAGRAM_REMINDER_1",
        "POST_TO_INSTAGRAM_DEADLINE",
    ]


@freeze_time(_now)
def test_schedule_without_opened_doesnt_yield_opened(post):
    # Arrange
    post.opened = None
    post.deadline = _now + dt.timedelta(days=2)

    # Act
    with mock.patch("takumi.tasks.posts.reminders.tiger"):
        schedule_post_reminders(post)

    # Assert
    assert _get_reminder_labels(post) == [
        "POST_TO_INSTAGRAM_REMINDER_24",
        "POST_TO_INSTAGRAM_REMINDER_6",
        "POST_TO_INSTAGRAM_REMINDER_1",
        "POST_TO_INSTAGRAM_DEADLINE",
    ]


@freeze_time(_now)
def test_schedule_with_not_opened_doesnt_yield_passed_opened(post):
    # Arrange
    post.opened = _now - dt.timedelta(days=1)

    # Act
    with mock.patch("takumi.tasks.posts.reminders.tiger"):
        schedule_post_reminders(post)

    # Assert
    assert _get_reminder_labels(post) == [
        "SUBMISSION_REMINDER_48",
        "SUBMISSION_REMINDER_24",
        "SUBMISSION_REMINDER_6",
        "SUBMISSION_REMINDER_1",
        "POST_TO_INSTAGRAM_REMINDER_24",
        "POST_TO_INSTAGRAM_REMINDER_6",
        "POST_TO_INSTAGRAM_REMINDER_1",
        "POST_TO_INSTAGRAM_DEADLINE",
    ]


@freeze_time(_now)
def test_cancels_old_reminders_before_scheduling_new_ones(post):
    post.submission_deadline = _now + dt.timedelta(days=2)
    post.opened = _now + dt.timedelta(days=3)
    post.deadline = _now + dt.timedelta(days=4)
    with mock.patch("takumi.tasks.posts.reminders.tiger") as mock_tiger:
        schedule_post_reminders(post)

    # Test cancelling old tasks
    assert len(mock_tiger.get_unique_task().cancel.call_args_list) == 9
    assert mock_tiger.get_unique_task().cancel.called

    # Test creating unique task
    assert len(mock_tiger.get_unique_task.call_args_list) == 20
    assert mock_tiger.get_unique_task.called

    # Test scheduling task
    assert len(mock_tiger.get_unique_task().delay.call_args_list) == 9
    assert mock_tiger.get_unique_task().delay.called
