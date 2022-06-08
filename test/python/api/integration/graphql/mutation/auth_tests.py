import datetime as dt
from contextlib import contextmanager

import mock
import pytest

from takumi.gql.mutation.public.authentication import CreateOTP


@contextmanager
def mock_rate_limit(*args, **kwargs):
    yield


@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def test_create_otp_signup_new_user(app, db_session, monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    with mock.patch("takumi.services.user.send_otp") as mock_send_otp:
        CreateOTP().mutate(
            "info",
            email="new_user_signup@takumi.com",
            app_uri="http://example.com",
            timestamp=dt.datetime(2020, 1, 1),
            new_signup=True,
        )

    assert mock_send_otp.called
    args = mock_send_otp.call_args.args
    kwargs = mock_send_otp.call_args.kwargs

    assert args[0].email == "new_user_signup@takumi.com"
    assert kwargs["app_uri"] == "http://example.com"
    assert kwargs["timestamp"] == dt.datetime(2020, 1, 1)
    assert kwargs["new_signup"] == True


def test_create_otp_login_with_new_user_does_nothing(app, db_session, monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    with mock.patch("takumi.services.user.send_otp") as mock_send_otp:
        CreateOTP().mutate(
            "info",
            email="new_user_login@takumi.com",
            app_uri="http://example.com",
            timestamp=dt.datetime(2020, 1, 1),
            new_signup=False,
        )

    assert not mock_send_otp.called


def test_create_otp_signup_with_existing_user_just_sends_login(app, db_influencer, monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    with mock.patch("takumi.services.user.send_otp") as mock_send_otp:
        CreateOTP().mutate(
            "info",
            email=db_influencer.user.email,
            app_uri="http://example.com",
            timestamp=dt.datetime(2020, 1, 1),
            new_signup=True,
        )

    assert mock_send_otp.called
    args = mock_send_otp.call_args.args
    kwargs = mock_send_otp.call_args.kwargs

    assert args[0].email == db_influencer.user.email
    assert kwargs["app_uri"] == "http://example.com"
    assert kwargs["timestamp"] == dt.datetime(2020, 1, 1)
    assert kwargs["new_signup"] == False


def test_create_otp_login_with_existing_user_sends_login(app, db_influencer, monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )

    with mock.patch("takumi.services.user.send_otp") as mock_send_otp:
        CreateOTP().mutate(
            "info",
            email=db_influencer.user.email,
            app_uri="http://example.com",
            timestamp=dt.datetime(2020, 1, 1),
            new_signup=False,
        )

    assert mock_send_otp.called
    args = mock_send_otp.call_args.args
    kwargs = mock_send_otp.call_args.kwargs

    assert args[0].email == db_influencer.user.email
    assert kwargs["app_uri"] == "http://example.com"
    assert kwargs["timestamp"] == dt.datetime(2020, 1, 1)
    assert kwargs["new_signup"] == False
