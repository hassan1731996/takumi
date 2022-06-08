import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.tokens import (
    TOKEN_VALID_FOR_DAYS,
    InvalidToken,
    InvalidTokenHeader,
    TokenExpired,
    decode_token,
    encode_token,
    get_jwt_session,
)


def test_token_payload():
    payload = dict(user_id="123")

    token = encode_token(payload)
    assert decode_token(token) == payload


def test_token_is_invalid_if_empty():
    with pytest.raises(InvalidToken):
        decode_token("")


def test_token_is_invalid_if_incorrectly_formatted():
    with pytest.raises(InvalidToken):
        decode_token("not a token")


def test_token_is_expired_if_too_old():
    """Create a token in the past and check it's expired"""
    with freeze_time(dt.datetime.utcnow() - dt.timedelta(days=TOKEN_VALID_FOR_DAYS + 1)):
        token = encode_token({})

    with pytest.raises(TokenExpired):
        decode_token(token)


def test_token_is_not_expired_if_not_too_old():
    payload = dict(user_id="123")
    with freeze_time(dt.datetime.utcnow() - dt.timedelta(days=TOKEN_VALID_FOR_DAYS - 1)):
        token = encode_token(payload)

    assert decode_token(token) == payload


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def test_get_jwt_session_uses_current_request_if_none_supplied():
    with pytest.raises(RuntimeError, match="outside of request context"):
        get_jwt_session()


@mock.patch("takumi.tokens.decode_token")
def test_get_jwt_session_returns_none_if_no_use_token_auth_header(mock_decode_token):
    assert get_jwt_session(FakeRequest(headers={})) is None
    assert not mock_decode_token.called


@mock.patch("takumi.tokens.decode_token")
def test_get_jwt_session_returns_none_if_no_token_in_auth_bearer_header(mock_decode_token):
    assert get_jwt_session(FakeRequest(headers={"Authorization": ""})) is None
    assert not mock_decode_token.called


def test_get_jwt_session_raises_invalid_token_header_on_any_exception_in_header_parsing():
    mock_headers = mock.Mock()
    mock_headers.get = mock.Mock(
        side_effect=[1, Exception]
    )  # the second headers.get call should raise
    with pytest.raises(InvalidTokenHeader):
        get_jwt_session(FakeRequest(headers=mock_headers))


@mock.patch("takumi.tokens.decode_token")
def test_get_jwt_session_returns_decode_token_if_token_found(mock_decode_token):
    session = get_jwt_session(FakeRequest(headers={"Authorization": "Bearer abcde"}))
    assert mock_decode_token.call_args[0][0] == "abcde"
    assert session == mock_decode_token("abcde")
