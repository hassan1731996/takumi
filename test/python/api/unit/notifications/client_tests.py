import datetime as dt

import mock
from freezegun import freeze_time

from takumi.notifications import NotificationClient
from takumi.notifications.client import STAGGER_MINUTES, TYPES, _send_message

NOW = dt.datetime(2018, 1, 1, 10, 0, tzinfo=dt.timezone.utc)


def test_notification_client_send_rejection(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_rejection("Rejection", campaign)

    assert mock_send.called
    mock_send.assert_called_with(
        "Rejection", {"type": TYPES.REJECTION, "payload": {"campaign_id": campaign.id}}
    )


def test_notification_client_send_payable(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_payable("Payable", campaign)

    assert mock_send.called
    mock_send.assert_called_with(
        "Payable", {"type": TYPES.PAYABLE, "payload": {"campaign_id": campaign.id}}
    )


def test_notification_client_send_payout_failed(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_payout_failed("Payout Failed", campaign)

    assert mock_send.called
    mock_send.assert_called_with(
        "Payout Failed", {"type": TYPES.PAYOUT_FAILED, "payload": {"campaign_id": campaign.id}}
    )


def test_notification_client_send_reservation_reminder(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_reservation_reminder("Reservation Reminder", campaign)

    assert mock_send.called
    mock_send.assert_called_with(
        "Reservation Reminder",
        {"type": TYPES.RESERVATION_REMINDER, "payload": {"campaign_id": campaign.id}},
    )


def test_notification_client_send_offer(influencer, campaign, offer, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_offer(offer, "New Offer")

    assert mock_send.called
    mock_send.assert_called_with(
        "New Offer", {"type": TYPES.NEW_CAMPAIGN, "payload": {"campaign_id": offer.campaign.id}}
    )


def test_notification_client_send_campaign(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_campaign("Campaign", campaign)

    assert mock_send.called
    mock_send.assert_called_with(
        "Campaign",
        {"type": TYPES.NEW_CAMPAIGN, "payload": {"campaign_id": campaign.id, "token": None}},
    )


def test_notification_client_send_campaign_with_token(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_campaign("Campaign", campaign, token="tttoken")

    assert mock_send.called
    mock_send.assert_called_with(
        "Campaign",
        {"type": TYPES.NEW_CAMPAIGN, "payload": {"campaign_id": campaign.id, "token": "tttoken"}},
    )


def test_notification_client_send_settings(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_settings("Settings")

    assert mock_send.called
    mock_send.assert_called_with("Settings", {"type": TYPES.SETTINGS})


def test_notification_client_instagram_view_profile(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_instagram_view_profile("Username", "Text")

    assert mock_send.called
    mock_send.assert_called_with(
        "Open to view Username's profile",
        {"type": TYPES.RECRUIT, "payload": {"username": "Username", "text": "Text"}},
    )


def test_notification_client_instagram_direct_message(influencer, campaign, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.first", lambda *args: None)
    client = NotificationClient(influencer)

    with mock.patch.object(NotificationClient, "send_message") as mock_send:
        client.send_instagram_direct_message("Username", "Text")

    assert mock_send.called
    mock_send.assert_called_with(
        "Open to send DM to Username",
        {"type": TYPES.RECRUIT, "payload": {"username": "Username", "text": "Text"}},
    )


@freeze_time(NOW)
def test_send_message_staggers_notifications_every_ten_minutes(app):
    devices = [mock.Mock() for _ in range(201)]
    client = NotificationClient(devices)

    with mock.patch("takumi.notifications.client.tiger") as mock_tiger:
        client.send_message("body", "data")

    assert mock_tiger.tiger.delay.called
    assert mock_tiger.tiger.delay.call_count == 3

    calls = mock_tiger.tiger.delay.call_args_list

    # First batch
    assert calls[0][1]["args"][0] == [d.device_token for d in devices[0:100]]
    assert calls[0][1]["when"] == NOW

    # Second batch
    assert calls[1][1]["args"][0] == [d.device_token for d in devices[100:200]]
    assert calls[1][1]["when"] == NOW + dt.timedelta(minutes=STAGGER_MINUTES)

    # Third batch
    assert calls[2][1]["args"][0] == [devices[200].device_token]
    assert calls[2][1]["when"] == NOW + dt.timedelta(minutes=2 * STAGGER_MINUTES)


def test__send_message_with_removed_or_empty(app):
    tokens = ["Expo[1]", "Expo[2]", None, "Expo[3]", "Expo[4]-removed", "expo[5]", "removed_token"]
    expected_tokens = ["Expo[1]", "Expo[2]", "Expo[3]", "expo[5]"]

    mock_client = mock.MagicMock()

    with mock.patch("takumi.notifications.client.PushClient.__new__", return_value=mock_client):
        _send_message(tokens, {}, {})

    actual_tokens = [msg.to for msg in mock_client.publish_multiple.call_args_list[0][0][0]]

    assert actual_tokens == expected_tokens
