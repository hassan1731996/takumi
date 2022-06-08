import datetime as dt

import mock
from flask import url_for
from freezegun import freeze_time

from takumi.constants import EMAIL_ENROLLMENT_SIGNER_NAMESPACE, EMAIL_VERIFICATION_MAX_AGE_SECONDS
from takumi.signers import url_signer


def test_advertiser_enroll_verify_success(client, email_login, monkeypatch):
    # Arrange
    assert not email_login.verified

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.views.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )

    # Act
    token = url_signer.dumps(dict(email=email_login.email), salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE)
    response = client.post(url_for("api.advertiser_enroll_verify"), data={"token": token})

    # Assert
    assert response.status_code == 200
    assert email_login.verified


def test_advertiser_enroll_verify_expired_link(client, email_login, monkeypatch):
    # Arrange
    assert not email_login.verified
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.views.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )

    # Act
    token = url_signer.dumps(dict(email=email_login.email), salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE)
    with freeze_time(
        dt.datetime.now(dt.timezone.utc)
        + dt.timedelta(seconds=EMAIL_VERIFICATION_MAX_AGE_SECONDS + 1)
    ):
        response = client.post(url_for("api.advertiser_enroll_verify"), data={"token": token})

    # Assert
    assert response.status_code == 410
    assert not email_login.verified
