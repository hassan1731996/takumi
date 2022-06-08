# encoding=utf-8
import datetime as dt

import mock
from flask import url_for
from freezegun import freeze_time

from takumi.constants import EMAIL_CHANGE_SIGNER
from takumi.signers import url_signer


@freeze_time("2015-1-1")
def test_influencer_user_accepts_terms_updates_timestamp(influencer_client, db_influencer):
    assert "terms_accepted" not in db_influencer.info
    resp = influencer_client.post(url_for("api.accept_terms"))
    assert resp.status_code == 200
    assert db_influencer.info["terms_accepted"] == "2015-01-01T00:00:00"


@freeze_time("2015-1-1")
def test_influencer_user_accepts_privacy_updates_timestamp(influencer_client, db_influencer):
    assert "privacy_accepted" not in db_influencer.info
    resp = influencer_client.post(url_for("api.accept_privacy"))
    assert resp.status_code == 200
    assert db_influencer.info["privacy_accepted"] == "2015-01-01T00:00:00"


def test_set_influencer_address(influencer_client, db_influencer):
    resp = influencer_client.put(
        url_for("api.set_address"),
        data={
            "address1": "13 Keyworth Mews",
            "address2": "",
            "city": "Canterbury",
            "is_pobox": False,
            "postal_code": "CT1 1XQ",
            "phonenumber": "123",
        },
    )
    assert resp.status_code == 200


@freeze_time("2015-1-1")
def test_influencer_schedule_delete_schedules_account_deletion(
    influencer_client, db_influencer, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.tasks.influencer.schedule_deletion", lambda *args: None)
    assert db_influencer.deletion_date is None

    # Act
    response = influencer_client.put(url_for("api.influencer_schedule_delete"))

    # Assert
    assert response.status_code == 200
    assert db_influencer.deletion_date is not None


def test_influencer_schedule_delete_cant_schedule_an_already_scheduled_deletion(
    db_influencer, influencer_client
):
    db_influencer.deletion_date = dt.datetime(2050, 1, 1, tzinfo=dt.timezone.utc)

    response = influencer_client.put(url_for("api.influencer_schedule_delete"))

    assert response.status_code == 400
    assert response.json["error"]["message"] == "Influencer already scheduled for deletion"


def test_influencer_cancel_scheduled_deletion_fails_if_no_scheduled_deletion(
    db_influencer, influencer_client
):
    response = influencer_client.put(url_for("api.influencer_cancel_scheduled_deletion"))

    assert response.status_code == 400
    assert response.json["error"]["message"] == "Influencer has not been scheduled for deletion"


@freeze_time("2015-1-1")
def test_influencer_cancel_scheduled_deletion_cancels_the_deletion_date(
    influencer_client, db_influencer, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.tasks.influencer.schedule_deletion", lambda *args: None)
    monkeypatch.setattr("takumi.tasks.influencer.clear_deletion", lambda *args: None)

    influencer_client.put(url_for("api.influencer_schedule_delete"))
    assert db_influencer.deletion_date is not None

    # Act
    response = influencer_client.put(url_for("api.influencer_cancel_scheduled_deletion"))

    # Assert
    assert response.status_code == 200
    assert db_influencer.deletion_date is None


def test_influencer_settings_change_email(influencer_client, db_session, db_influencer):
    # Arrange
    assert db_influencer.events == []
    db_session.commit()

    # Act
    with mock.patch("takumi.services.influencer.VerificationEmail.send") as mock_verification_email:
        with mock.patch(
            "takumi.services.influencer.ChangeEmailNotificationEmail.send"
        ) as mock_notification_email:
            response = influencer_client.put(
                url_for("api.influencer_settings"), data={"email": "some@email.com"}
            )

    # Assert
    assert response.status_code == 200
    assert db_influencer.events != []
    assert mock_verification_email.called
    assert mock_notification_email.called


def test_verify_email_change(influencer_client, db_influencer):
    # Arrange
    token = url_signer.dumps(
        dict(email="new@email.com", influencer_id=db_influencer.id), salt=EMAIL_CHANGE_SIGNER
    )

    # Act
    response = influencer_client.get(url_for("api.verify_email_change", token=token))

    # Assert
    assert response.status_code == 200
    assert db_influencer.user.email_login.email == "new@email.com"
