import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.models.user import EMAIL_NOTIFICATION_PREFERENCES
from takumi.services import OfferService
from takumi.tasks.scheduled.insights import fetch_expiring_insights
from takumi.tasks.scheduled.payments import PAYMENT_REAP_DELAY, payment_reaper
from takumi.tasks.scheduled.reapers import _notify_clients_that_have_unseen_comments

_now = dt.datetime.now(dt.timezone.utc)


@freeze_time(_now)
def test_notify_clients_that_have_unseen_comments_does_not_send_emails_for_old_comments(
    db_offer, db_advertiser_user, user_factory
):
    # Arrange
    db_advertiser_user.email_login.email = "someone@advertiser.com"
    db_advertiser_user.email_notification_preference = EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)

    with OfferService(db_offer) as srv:
        srv.make_comment("123", user_factory())

    comment = db_offer.comments[0]
    comment.created = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)

    # Act
    with mock.patch("takumi.tasks.scheduled.reapers.NewCommentEmail") as mock_email:
        _notify_clients_that_have_unseen_comments(
            time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
        )

    # Assert
    assert not mock_email.called


@freeze_time(_now)
def test_notify_clients_that_have_unseen_comments_does_not_send_emails_for_seen_comments(
    db_offer, db_advertiser_user, user_factory
):
    # Arrange
    db_advertiser_user.email_login.email = "someone@advertiser.com"
    db_advertiser_user.email_notification_preference = EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)

    with OfferService(db_offer) as srv:
        srv.make_comment("123", user_factory())

    with OfferService(db_offer) as srv:
        srv.mark_comments_as_seen_by(db_advertiser_user)

    # Act
    with mock.patch("takumi.tasks.scheduled.reapers.NewCommentEmail") as mock_email:
        _notify_clients_that_have_unseen_comments(
            time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
        )

    # Assert
    assert not mock_email.called


@freeze_time(_now)
def test_notify_clients_that_have_unseen_comments_sends_emails_for_unseen_comments(
    db_advertiser_user, db_offer, user_factory
):
    # Arrange
    db_advertiser_user.email_login.email = "someone@advertiser.com"
    db_advertiser_user.email_notification_preference = EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)

    with OfferService(db_offer) as srv:
        srv.make_comment("123", user_factory())

    # Act
    with mock.patch("takumi.tasks.scheduled.reapers.NewCommentEmail") as mock_email:
        _notify_clients_that_have_unseen_comments(
            time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
        )

    # Assert
    assert mock_email.called


@pytest.mark.skip(reason="until facebook fixed")
@freeze_time(_now)
def test_expiring_frames_update_insights(db_session, story_frame_factory):
    expired_frames = [
        story_frame_factory(posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=100)),
        story_frame_factory(posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25)),
        story_frame_factory(
            posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24, minutes=30)
        ),
        story_frame_factory(
            posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24, minutes=16)
        ),
    ]
    expiring_frames = [
        story_frame_factory(
            posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24, minutes=14)
        ),
        story_frame_factory(posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)),
        story_frame_factory(
            posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=23, minutes=31)
        ),
    ]
    too_fresh_frames = [
        story_frame_factory(posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=23)),
        story_frame_factory(posted=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)),
    ]

    db_session.add_all(expired_frames)
    db_session.add_all(expiring_frames)
    db_session.add_all(too_fresh_frames)
    db_session.commit()

    with mock.patch("takumi.tasks.scheduled.insights.update_frame_insights") as mock_update:
        fetch_expiring_insights()

    expected_calls = [mock.call(frame.id) for frame in expiring_frames]
    assert mock_update.delay.call_args_list == expected_calls


@freeze_time(_now)
def test_payment_reaper_spreads_out_payments(db_session, payment_factory, monkeypatch):
    dwolla_payments = [
        payment_factory(state=PAYMENT_STATES.PENDING, type="dwolla"),
        payment_factory(state=PAYMENT_STATES.PENDING, type="dwolla"),
    ]

    revolut_payments = [
        payment_factory(state=PAYMENT_STATES.PENDING, type="revolut"),
        payment_factory(state=PAYMENT_STATES.PENDING, type="revolut"),
        payment_factory(state=PAYMENT_STATES.PENDING, type="revolut"),
    ]

    db_session.add_all(dwolla_payments + revolut_payments)
    db_session.commit()

    with mock.patch("takumi.tasks.scheduled.payments.tiger") as mock_tiger:
        payment_reaper()

    assert mock_tiger.tiger.delay.called
    calls = mock_tiger.tiger.delay.call_args_list

    assert len(calls) == 5

    # Assert payment ids
    called_payment_ids = {call[1]["args"][0] for call in calls}
    expected_payment_ids = {payment.id for payment in dwolla_payments + revolut_payments}

    assert called_payment_ids == expected_payment_ids

    # Assert delay
    called_whens = {call[1]["when"] for call in calls}
    expected_whens = {dt.timedelta(seconds=PAYMENT_REAP_DELAY * idx) for idx in range(5)}

    assert called_whens == expected_whens
