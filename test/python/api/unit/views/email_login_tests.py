# encoding=utf-8
from contextlib import contextmanager

import mock
import pytest
from flask import url_for
from freezegun import freeze_time
from mock import patch
from werkzeug.security import generate_password_hash

from takumi.constants import PASSWORD_HASH_METHOD
from takumi.ig.instascrape import InstascrapeError
from takumi.models import EmailLogin
from takumi.services.user import ExpiredLoginException, InvalidLoginException, verify_otp
from takumi.signers import url_signer
from takumi.utils.login import _upload_profile_picture


def test_verify_otp_invalid_salt(email_login):
    email_login.otp_salt = "bar"
    token = url_signer.dumps(email_login.email, salt="foo")
    with pytest.raises(InvalidLoginException):
        verify_otp(token, email_login)


def test_verify_otp_too_old(email_login):
    email_login.otp_salt = "foo"
    with freeze_time("2011-12-31"):
        token = url_signer.dumps(email_login.email, salt="foo")

    with freeze_time("2012-01-02"):
        with pytest.raises(ExpiredLoginException):
            verify_otp(token, email_login)


def email_login_request(client, **request_json):
    request_json.setdefault("email", "valtyr@example.com")
    request_json.setdefault("password", "password")
    return client.post(url_for("api.login"), data=request_json)


def test_login_user_doesnt_exist(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )
    monkeypatch.setattr("takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=None))

    # Act
    response = email_login_request(client)

    # Assert
    assert response.status_code == 403


def test_login_bad_password(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=EmailLogin())
    )
    monkeypatch.setattr(
        "takumi.models.email_login.check_password_hash", lambda password_hash, password: False
    )
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    # Act
    response = email_login_request(client)

    # Assert
    assert response.status_code == 403


def test_login_inactive_user(client, email_login, monkeypatch):
    # Arrange
    email_login.user.active = False
    email_login.password_hash = ""

    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )
    monkeypatch.setattr(
        "takumi.models.email_login.check_password_hash", lambda password_hash, password: True
    )
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    # Act
    response = email_login_request(client)

    # Assert
    assert response.status_code == 403


def test_login_successful(client, email_login, monkeypatch):
    # Arrange
    assert email_login.user.last_login is None
    email_login.password_hash = "password_hash"

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )
    monkeypatch.setattr(
        "takumi.models.email_login.check_password_hash", lambda password_hash, password: True
    )
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )
    _stub_advertiser_brand_profile(monkeypatch, None)

    # Act
    response = email_login_request(client)

    # Assert
    assert response.status_code == 200
    assert email_login.user.last_login


def test_login_with_brand_profile(client, email_login, monkeypatch, advertiser_brand_profile_user):
    # Arrange
    assert email_login.user.last_login is None
    email_login.password_hash = "password_hash"

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )
    monkeypatch.setattr(
        "takumi.models.email_login.check_password_hash", lambda password_hash, password: True
    )
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )
    _stub_advertiser_brand_profile(monkeypatch, advertiser_brand_profile_user)

    # Act
    response = email_login_request(client)

    # Assert
    assert response.status_code == 200
    assert email_login.user.last_login


@patch("takumi.views.email_login.PasswordRecoveryEmail")
def test_password_recovery_email_does_not_exist(mock_email, client, monkeypatch):
    # Arrange
    monkeypatch.setattr("takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=None))

    # Act
    response = client.post(
        url_for("api.password_recovery"), data={"email": "sometestemail@test.com"}
    )

    # Assert
    assert response.status_code == 200
    assert not mock_email.called


@patch("takumi.views.email_login.PasswordRecoveryEmail")
def test_password_recovery_email_not_verified(mock_email, client, email_login, monkeypatch):
    # Arrange
    email_login.verified = False
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )

    # Act
    response = client.post(url_for("api.password_recovery"), data={"email": email_login.email})

    # Assert
    assert response.status_code == 200
    assert not mock_email.called


@patch("takumi.views.email_login.PasswordRecoveryEmail")
def test_password_recovery_email_from_influencer(mock_email, client, email_login, monkeypatch):
    # Arrange
    email_login.user.role_name == "influencer"
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )

    # Act
    response = client.post(url_for("api.password_recovery"), data={"email": email_login.email})

    # Assert
    assert response.status_code == 200
    assert not mock_email.called


@patch("takumi.views.email_login.PasswordRecoveryEmail")
def test_password_recovery_successful(mock_email, email_login, client, monkeypatch):
    # Arrange
    email_login.verified = True
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )

    # Act
    response = client.post(url_for("api.password_recovery"), data={"email": email_login.email})

    # Assert
    assert response.status_code == 200
    assert mock_email.called


def test_password_recovery_change_with_invalid_token(client):
    response = client.put(
        url_for("api.password_recovery_change"), data={"password": "password", "token": "badtoken"}
    )
    assert response.status_code == 404


def test_password_recovery_change_when_valid_email_login_doesnt_exist(client, monkeypatch):
    # Arrange
    monkeypatch.setattr("takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=None))

    # Act
    token = url_signer.dumps(dict(email="sometestemail@test.com"), salt="password-recovery-key")
    response = client.put(
        url_for("api.password_recovery_change"), data={"password": "password", "token": token}
    )

    # Assert
    assert response.status_code == 404


def test_password_recovery_change_successful(client, email_login, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    # Act
    token = url_signer.dumps(dict(email=email_login.email), salt="password-recovery-key")
    response = client.put(
        url_for("api.password_recovery_change"), data={"password": "password", "token": token}
    )

    # Assert
    assert email_login.check_password("password")
    assert response.status_code == 200


@contextmanager
def mock_rate_limit(*args, **kwargs):
    yield


def test_email_login_with_otp_includes_jwt_token(client, influencer_user, influencer, monkeypatch):
    # Arrange
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.refresh_on_interval", lambda _: None
    )
    monkeypatch.setattr("takumi.models.influencer.Influencer.total_rewards", lambda _: None)
    monkeypatch.setattr(
        "takumi.services.user.EmailLogin.get",
        mock.Mock(return_value=EmailLogin(user=influencer_user)),
    )
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    # Act
    token = url_signer.dumps({"email": "mockuser@mocktakumi.com"})
    with mock.patch(
        "takumi.models.influencer.Influencer.total_rewards",
        new_callable=mock.PropertyMock,
        return_value=0,
    ):
        response = client.post(url_for("api.login_otp", token=token))

    # Assert
    assert response.status_code == 200
    assert "token" in response.json


def test_app_login_without_custom_app_uri_expo(client):
    with mock.patch("takumi.views.email_login.get_ios_version_from_user_agent", return_value=None):
        response = client.get(url_for("api.app_login", token="tttoken"))  # noqa

    assert response.status_code == 302
    assert response.location == "takumi://login/tttoken"


def test_app_login_without_custom_app_uri_ios_10_redirects_to_login_portal_expo(client):
    with mock.patch(
        "takumi.views.email_login.get_ios_version_from_user_agent", return_value=[10, 2, 1]
    ):
        response = client.get(url_for("api.app_login", token="tttoken"))  # noqa

    assert response.status_code == 302
    assert response.location == "http://login.takumi.com/e/?token=tttoken"


def test_app_login_without_custom_app_uri_ios_11_doesnt_use_login_portal(client):
    with mock.patch(
        "takumi.views.email_login.get_ios_version_from_user_agent", return_value=[11, 0, 0]
    ):
        response = client.get(url_for("api.app_login", token="tttoken"))  # noqa

    assert response.status_code == 302
    assert response.location == "takumi://login/tttoken"


def test_upload_profile_picture_uses_scraped_profile_picture_when_available(
    influencer, monkeypatch
):
    monkeypatch.setattr(
        "takumi.utils.login.instascrape.get_user", lambda _: {"profile_picture": "fresh"}
    )

    with mock.patch("takumi.tasks.cdn.upload_profile_to_cdn") as mock_task:
        _upload_profile_picture(influencer.user)

    mock_task.delay.assert_called_with(user_id=influencer.user.id, image_url="fresh")


def test_upload_profile_picture_uses_default_profile_picture_when_new_cant_be_scraped(influencer):
    default_profile = influencer.instagram_account.profile_picture

    with mock.patch(
        "takumi.utils.login.instascrape.get_user", side_effect=InstascrapeError(500, "err")
    ):
        with mock.patch("takumi.tasks.cdn.upload_profile_to_cdn") as mock_task:
            _upload_profile_picture(influencer.user)

    mock_task.delay.assert_called_with(user_id=influencer.user.id, image_url=default_profile)


def test_login_updates_old_password_hash(
    client, email_login, monkeypatch, advertiser_brand_profile_user
):
    email_login.password_hash = generate_password_hash("s3cur3_pa55w0rd", method="pbkdf2:sha1:1000")
    assert PASSWORD_HASH_METHOD not in email_login.password_hash

    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.models.email_login.EmailLogin.get", mock.Mock(return_value=email_login)
    )
    monkeypatch.setattr(
        "takumi.models.email_login.check_password_hash", lambda password_hash, password: True
    )
    _stub_advertiser_brand_profile(monkeypatch, advertiser_brand_profile_user)

    response = email_login_request(client)

    assert response.status_code == 200
    assert PASSWORD_HASH_METHOD in email_login.password_hash


def _stub_advertiser_brand_profile(monkeypatch, value):
    return monkeypatch.setattr(
        "takumi.gql.utils.UserService.check_is_brand_archived_for_brand_profile",
        mock.Mock(return_value=value),
    )
