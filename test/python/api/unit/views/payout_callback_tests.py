import mock
from flask import g, url_for

from takumi.extensions import db
from takumi.models import ApiTask
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.utils import uuid4_str


def test_dwolla_payout_callback_posts_to_slack_and_returns_if_unknown_topic(client):
    # Arrange
    task = ApiTask(allowed_views=["tasks.dwolla_payout_callback"])
    setattr(g, "task", task)

    # Act
    with mock.patch("takumi.views.task.WebhookEvent"):
        with mock.patch("takumi.views.task.is_event_supported") as mock_check:
            with mock.patch("takumi.views.task.slack.dwolla_hook") as mock_slack:
                mock_check.return_value = False
                client.post(url_for("tasks.dwolla_payout_callback", task_id=uuid4_str()), data={})
    # Assert
    assert mock_slack.called


@mock.patch("takumi.views.task.WebhookEvent")
def test_dwolla_payout_callback_posts_to_slack_and_returns_if_offer_id_not_in_metadata(whe, client):
    # Arrange
    task = ApiTask(allowed_views=["tasks.dwolla_payout_callback"])
    setattr(g, "task", task)

    class FakeTransfer:
        metadata = {}

    # Act
    with mock.patch("takumi.views.task.dwolla") as mock_dwolla:
        with mock.patch("takumi.views.task.is_event_supported") as mock_check:
            mock_check.return_value = True
            mock_dwolla.get_transfer.return_value = FakeTransfer()
            with mock.patch("takumi.views.task.slack.dwolla_hook") as mock_slack:
                client.post(url_for("tasks.dwolla_payout_callback", task_id=uuid4_str()), data={})

    # Assert
    assert mock_slack.called


@mock.patch("takumi.views.task.WebhookEvent")
@mock.patch("takumi.views.task.dwolla")
@mock.patch("takumi.views.task.is_event_supported")
@mock.patch("sqlalchemy.orm.query.Query.get")
@mock.patch("takumi.views.task.capture_message")
def test_dwolla_payout_callback_alerts_if_transfer_id_reference_mismatch(
    mock_capture_message, mock_get, mock_check, mock_dwolla, whe, client, payment
):
    # Arrange
    task = ApiTask(allowed_views=["tasks.dwolla_payout_callback"])
    setattr(g, "task", task)

    class FakeTransfer:
        id = "transfer-123"
        metadata = {"payment_id": "1234"}

    mock_check.return_value = True
    mock_dwolla.get_transfer.return_value = FakeTransfer()
    mock_get.return_value = payment

    # Act
    with mock.patch("takumi.views.task.slack.dwolla_hook") as mock_slack:
        client.post(url_for("tasks.dwolla_payout_callback", task_id=uuid4_str()), data={})

    # Assert
    assert mock_slack.called
    assert mock_capture_message.called
    assert (
        mock_capture_message.call_args[0][0] == "Payout callback from Dwolla ID reference mismatch!"
    )


@mock.patch("takumi.views.task.WebhookEvent")
@mock.patch("takumi.views.task.dwolla")
@mock.patch("takumi.views.task.is_success_event")
@mock.patch("sqlalchemy.orm.query.Query.get")
def test_dwolla_payout_callback_adds_succeed_event_if_event_topic_is_success(
    mock_get, mock_check, mock_dwolla, whe, client, monkeypatch, payment, slack_post
):
    # Arrange
    monkeypatch.setattr(db.session, "commit", lambda: None)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.one_or_none", lambda *args: [None])
    task = ApiTask(allowed_views=["tasks.dwolla_payout_callback"])
    setattr(g, "task", task)
    payment.state = PAYMENT_STATES.REQUESTED

    class FakeTransfer:
        id = "transfer-123"
        metadata = {"payment_id": "123"}

    payment.reference = FakeTransfer.id

    mock_check.return_value = True
    mock_dwolla.get_transfer.return_value = FakeTransfer()
    mock_get.return_value = payment

    # Act
    resp = client.post(url_for("tasks.dwolla_payout_callback", task_id=uuid4_str()), data={})

    # Assert
    assert resp.status_code == 200
    assert payment.events[-1]["_type"] == "succeed"


@mock.patch("takumi.views.task.WebhookEvent")
@mock.patch("takumi.views.task.slack.payout_failure_dwolla")
@mock.patch("takumi.views.task.send_failed_payout_push_notification")
def test_dwolla_payout_callback_adds_fail_event_if_event_topic_is_failure(
    whe, pf, ppn, client, monkeypatch, payment
):
    # Arrange
    payment.successful = True
    payment.state = PAYMENT_STATES.REQUESTED
    monkeypatch.setattr(db.session, "commit", lambda: None)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.one_or_none", lambda *args: [None])
    task = ApiTask(allowed_views=["tasks.dwolla_payout_callback"])
    setattr(g, "task", task)

    class FakeTransfer:
        id = "transfer-123"
        metadata = {"payment_id": "123"}

    payment.reference = FakeTransfer.id

    # Act
    with mock.patch("takumi.views.task.dwolla") as mock_dwolla:
        with mock.patch("takumi.views.task.is_failure_event") as mock_check:
            mock_check.return_value = True
            mock_dwolla.get_transfer.return_value = FakeTransfer()
            with mock.patch("sqlalchemy.orm.query.Query.get") as m_get:
                m_get.return_value = payment
                client.post(url_for("tasks.dwolla_payout_callback", task_id=uuid4_str()), data={})

    # Assert
    assert payment.events[-1]["_type"] == "fail"
    assert payment.successful == False
