import datetime as dt

from takumi.schedule import PostSchedule

start = dt.datetime(2018, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
deadline = dt.datetime(2018, 2, 1, 0, 0, tzinfo=dt.timezone.utc)


def test_post_schedule_gives_minimum_four_days_to_submit_by_default(post):
    post.campaign.started = start
    schedule = PostSchedule(post)

    assert schedule.suggested_earliest_submission_deadline == dt.datetime(
        2018, 1, 5, 0, 0, tzinfo=dt.timezone.utc
    )


def test_post_schedule_uses_supplied_submission_deadline(post):
    submission_deadline = dt.datetime(2018, 1, 12, 0, 0, tzinfo=dt.timezone.utc)

    post.submission_deadline = submission_deadline
    schedule = PostSchedule(post)

    assert schedule.submission_deadline == submission_deadline


def test_post_schedule_generates_submission_deadline_if_none_supplied(post):
    post.submission_deadline = None

    schedule = PostSchedule(post)

    assert schedule.submission_deadline is not None


def test_post_schedule_periods_with_deadline_are_well_ordered(post):
    for day in range(1, 31):
        post.campaign.brand_safety = True
        post.deadline = dt.datetime(2018, 1, day, 23, 59, tzinfo=dt.timezone.utc)
        schedule = PostSchedule(post)

        assert (
            schedule.submission_deadline
            < schedule.internal_review_deadline
            < schedule.external_review_deadline
            < schedule.post_deadline
        )


def test_post_schedule_periods_with_deadline_are_long_enough(post):
    for day in range(1, 31):
        post.campaign.brand_safety = True
        post.deadline = dt.datetime(2018, 1, day, 23, 59, tzinfo=dt.timezone.utc)

        schedule = PostSchedule(post)

        assert (schedule.internal_review_deadline - schedule.submission_deadline) >= dt.timedelta(
            hours=24
        )
        assert (
            schedule.external_review_deadline - schedule.internal_review_deadline
            >= dt.timedelta(hours=48)
        )
        assert schedule.post_deadline - schedule.external_review_deadline >= dt.timedelta(hours=48)


def test_post_schedule_periods_without_deadline_are_long_enough(post):
    for day in range(1, 31):
        post.campaign.brand_safety = True
        schedule = PostSchedule(post)

        assert (schedule.internal_review_deadline - schedule.submission_deadline) >= dt.timedelta(
            hours=24
        )
        assert (
            schedule.external_review_deadline - schedule.internal_review_deadline
            >= dt.timedelta(hours=48)
        )
        assert schedule.post_deadline - schedule.external_review_deadline >= dt.timedelta(hours=48)


def test_post_schedule_adding_brand_safety_makes_the_submission_deadline_earlier(post):
    post.submission_deadline = None
    post.campaign.started = start
    post.campaign.brand_safety = False
    post.deadline = dt.datetime(2018, 1, 21, 0, 0, tzinfo=dt.timezone.utc)

    schedule = PostSchedule(post)

    assert schedule.submission_deadline == dt.datetime(2018, 1, 18, 0, 0, tzinfo=dt.timezone.utc)

    post.campaign.brand_safety = True
    schedule_with_brand_safety = PostSchedule(post)

    assert schedule_with_brand_safety.submission_deadline == dt.datetime(
        2018, 1, 16, 0, 0, tzinfo=dt.timezone.utc
    )


def test_post_schedule_no_brand_safety_external_review_period_is_zero(post):
    post.campaign.brand_safety = False
    post.submission_deadline = None
    post.deadline = deadline
    schedule = PostSchedule(post)

    # Without brand safety, schedule shouldn't allow any time for external review
    assert schedule.external_review_deadline - schedule.internal_review_deadline == dt.timedelta(
        hours=0
    )


def test_post_schedule_with_brand_safety_external_review_period_is_at_least_48_hours(post):
    post.campaign.brand_safety = True
    schedule = PostSchedule(post)

    assert schedule.external_review_deadline - schedule.internal_review_deadline >= dt.timedelta(
        hours=48
    )


def test_post_schedule_with_extended_review_external_review_period_is_at_least_120_hours(post):
    post.campaign.brand_safety = True
    post.campaign.extended_review = True
    schedule = PostSchedule(post)

    assert schedule.external_review_deadline - schedule.internal_review_deadline >= dt.timedelta(
        hours=120
    )


def test_post_schedule_skip_review_period_can_submit_until_the_deadline(post):
    post.requires_review_before_posting = False
    post.submission_deadline = None
    post.deadline = deadline
    schedule = PostSchedule(post)

    assert schedule.suggested_latest_submission_deadline == deadline
    assert schedule.submission_deadline == deadline


def test_post_schedule_get_schedule_for_post(post):
    post.submission_deadline = dt.datetime(2018, 1, 5, tzinfo=dt.timezone.utc)
    schedule = PostSchedule(post)

    assert schedule.post_deadline == post.deadline
    assert schedule.submission_deadline == post.submission_deadline


def test_post_schedule_get_schedule_for_post_no_brand_safety(post):
    post.campaign.brand_safety = False
    post.deadline = deadline
    post.submission_deadline = None

    schedule = PostSchedule(post)

    assert schedule.external_review_deadline == schedule.internal_review_deadline
