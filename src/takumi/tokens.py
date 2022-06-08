import datetime as dt
import os
import time
from typing import Dict

from flask import request as current_request
from jwt import ExpiredSignatureError, InvalidTokenError, decode, encode

from takumi.signers import url_signer

secret = os.environ["SECRET_KEY"]
TOKEN_VALID_FOR_DAYS = 30
LOGIN_CODE_LENGTH = 12


class TokenExpired(Exception):
    """Raised if the authorization token has expired"""


class InvalidToken(Exception):
    """Raise if the authorization token was invalid"""


class InvalidTokenHeader(Exception):
    """Raise if unable to extrac the token from the Authorization header"""


def encode_token(payload: Dict) -> bytes:
    payload["exp"] = dt.datetime.utcnow() + dt.timedelta(days=TOKEN_VALID_FOR_DAYS)
    return encode(payload, secret, algorithm="HS256")


def decode_token(token: bytes) -> Dict:
    try:
        return decode(token, secret, algorithm="HS256")
    except ExpiredSignatureError:
        raise TokenExpired
    except InvalidTokenError:
        raise InvalidToken


def get_jwt_session(request=None):
    if request is None:
        request = current_request

    if not request.headers.get("Authorization"):
        return None
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return None  # Need to return None if no token so we can log in.
    except Exception:
        raise InvalidTokenHeader("Malformed Authorization header")

    return decode_token(token)


def get_token_for_user(user, is_developer=False):
    return encode_token({"user_id": user.id, "developer": is_developer}).decode()


def create_otp_token(email_login, is_developer=False):
    # Store current time in the login token for debugging
    payload = dict(email=email_login.email, time=int(time.time()), is_developer=is_developer)
    return url_signer.dumps(payload, salt=email_login.otp_salt)
