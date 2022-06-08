import datetime as dt

import mock
from freezegun import freeze_time

from takumi.models import Config
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.models.post import PostTypes
from takumi.services.exceptions import PaymentRequestFailedException
from takumi.tasks.scheduled.payments import payment_reaper, reap_payment
from takumi.tasks.scheduled.story_downloader import DAYS_PAST_DEADLINE, download_story_frames


@freeze_time(dt.datetime(2018, 1, 10, tzinfo=dt.timezone.utc))
def test_download_story_frames_goes_over_deadline(
    db_session, db_gig_story, db_submission, db_post_story
):
    db_gig_story.instagram_story = None
    db_post_story.post_type = PostTypes.story
    Config.get("SCRAPE_STORIES").value = True
    db_session.commit()

    # Deadline 1 hour less than the DAYS_PAST_DEADLINE
    db_post_story.deadline = (
        dt.datetime.now(dt.timezone.utc)
        - dt.timedelta(days=DAYS_PAST_DEADLINE)
        + dt.timedelta(hours=1)
    )
    with mock.patch("takumi.tasks.scheduled.story_downloader.tiger") as mock_tiger:
        download_story_frames()

    assert mock_tiger.tiger.delay.called

    # Deadline 1 hour more ago than the DAYS_PAST_DEADLINE
    db_post_story.deadline = dt.datetime(2018, 1, 7, 23, tzinfo=dt.timezone.utc)
    db_post_story.deadline = (
        dt.datetime.now(dt.timezone.utc)
        - dt.timedelta(days=DAYS_PAST_DEADLINE)
        - dt.timedelta(hours=1)
    )
    with mock.patch("takumi.tasks.scheduled.story_downloader.tiger") as mock_tiger:
        download_story_frames()

    assert not mock_tiger.tiger.delay.called


def test_payment_reaper_respectes_config(db_session, payment_factory, monkeypatch):
    Config.get("PROCESS_REVOLUT_PAYMENTS").value = False
    Config.get("PROCESS_DWOLLA_PAYMENTS").value = False

    revolut = payment_factory(state=PAYMENT_STATES.PENDING, type="revolut")
    dwolla = payment_factory(state=PAYMENT_STATES.PENDING, type="dwolla")

    db_session.add_all([revolut, dwolla])
    db_session.commit()

    no_call_mock = mock.Mock()
    monkeypatch.setattr("takumi.tasks.scheduled.payments.tiger", no_call_mock)

    # No calls should be made
    payment_reaper()

    no_call_mock.tiger.delay.assert_not_called()

    # Only revolut
    Config.get("PROCESS_REVOLUT_PAYMENTS").value = True
    only_revolut_mock = mock.Mock()
    monkeypatch.setattr("takumi.tasks.scheduled.payments.tiger", only_revolut_mock)
    db_session.commit()

    payment_reaper()

    only_revolut_mock.tiger.delay.assert_called_once_with(
        reap_payment, args=[revolut.id], retry=False, unique=True, when=dt.timedelta(seconds=0)
    )

    # Only dwolla
    Config.get("PROCESS_DWOLLA_PAYMENTS").value = True
    Config.get("PROCESS_REVOLUT_PAYMENTS").value = False
    only_dwolla_mock = mock.Mock()
    monkeypatch.setattr("takumi.tasks.scheduled.payments.tiger", only_dwolla_mock)
    db_session.commit()

    payment_reaper()

    only_dwolla_mock.tiger.delay.assert_called_once_with(
        reap_payment, args=[dwolla.id], retry=False, unique=True, when=dt.timedelta(seconds=0)
    )

    # Both
    Config.get("PROCESS_DWOLLA_PAYMENTS").value = True
    Config.get("PROCESS_REVOLUT_PAYMENTS").value = True
    both_mock = mock.Mock()
    monkeypatch.setattr("takumi.tasks.scheduled.payments.tiger", both_mock)
    db_session.commit()

    payment_reaper()

    both_mock.tiger.delay.assert_has_calls(
        [
            mock.call(
                reap_payment,
                args=[dwolla.id],
                retry=False,
                unique=True,
                when=dt.timedelta(seconds=0),
            ),
            mock.call(
                reap_payment,
                args=[revolut.id],
                retry=False,
                unique=True,
                when=dt.timedelta(seconds=5),
            ),
        ]
    )
    assert both_mock.tiger.delay.call_count == 2


def test_payment_reaper_handles_failed_payments(db_session, payment_factory):
    revolut = payment_factory(
        state=PAYMENT_STATES.PENDING, type="revolut", details={"destination": "black hole"}
    )
    dwolla = payment_factory(
        state=PAYMENT_STATES.PENDING, type="dwolla", details={"destination": "bank account"}
    )

    db_session.add_all([revolut, dwolla])
    db_session.commit()

    with mock.patch("takumi.tasks.scheduled.payments.PaymentService") as mock_service:
        with mock.patch(
            "takumi.tasks.scheduled.payments.send_failed_payout_push_notification"
        ) as mock_notify:
            service_ctx = mock_service.return_value.__enter__.return_value
            # Make request raise a payment faileda for the first payment
            service_ctx.request.side_effect = [
                PaymentRequestFailedException("Black hole not found!"),
                None,
            ]

            reap_payment(revolut.id)
            reap_payment(dwolla.id)

    service_ctx.request.assert_has_calls(
        [
            mock.call(revolut.details),
            mock.call(dwolla.details),
        ]
    )
    service_ctx.request_failed.assert_called_once_with("Black hole not found!")
    mock_notify.assert_called_once_with(revolut.offer)
