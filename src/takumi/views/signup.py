import random

from flask import jsonify, request
from marshmallow import Schema, fields
from sentry_sdk import capture_exception
from sqlalchemy import func

from core.common.crypto import get_human_random_string
from core.common.exceptions import APIError

from takumi.error_codes import (
    ALREADY_VERIFIED_ERROR_CODE,
    MEDIA_NO_CODE_FOUND_ERROR_CODE,
    MEDIA_NOT_FOUND_ERROR_CODE,
    MEDIA_OWNER_MISMATCH_ERROR_CODE,
    MEDIA_VERIFICATION_ID_MISMATCH,
    UNABLE_TO_FIND_SIGNUP_FOR_INSTAGRAM_USERNAME,
)
from takumi.events.instagram_account import InstagramAccountLog
from takumi.extensions import db, instascrape
from takumi.ig.instascrape import InstascrapeUnavailable, NotFound
from takumi.models import EmailLogin, InstagramAccount
from takumi.tasks import instagram_account as instagram_account_tasks
from takumi.tokens import encode_token
from takumi.utils import is_emaily, uuid4_str
from takumi.utils.json import get_valid_json

from .blueprint import api


def get_scraped_ig_info(username):
    """Scrape instagram by the username

    If the username is also found on our system, verify that the ig user ids match.
    If they do not match, there has been a username change, which we handle
    """
    stripped_username = username.strip(" @")

    try:
        profile = instascrape.get_user(stripped_username, nocache=True)
    except NotFound:
        raise APIError("Could not find Instagram profile", 404)
    except InstascrapeUnavailable:
        raise APIError("Unable to connect to Instagram. Please try again later", 503)

    account = InstagramAccount.query.filter(
        func.lower(InstagramAccount.ig_username) == func.lower(stripped_username)
    ).first()

    if account is not None and profile["id"] != account.ig_user_id:
        # Free up the username, since it's a different account
        log = InstagramAccountLog(account)
        temp_username = "{}-invalid-{}".format(stripped_username, get_human_random_string(length=6))
        log.add_event("username-change", {"username": temp_username})
        db.session.commit()

        # If user didn't finish signup, then they won't have an influencer object.
        # Only schedule a tracked username update on signed up users
        if account.influencer is not None:
            instagram_account_tasks.instagram_account_new_username.delay(account.id)

    return profile


@api.route("/users/accounts/<username>", methods=["GET"])
def get_instagram_user(username):
    if is_emaily(username):
        email_login = EmailLogin.get(username)
        if email_login:
            instagram_account = (
                email_login.user.influencer.instagram_account if email_login else None
            )
            if instagram_account:
                username = instagram_account.ig_username
            else:
                return jsonify(
                    {
                        "followers": 1000,
                        "full_name": email_login.user.full_name,
                        "id": email_login.user.id,
                        "is_private": False,
                        "media_count": 50,
                        "profile_picture": email_login.user.influencer.profile_picture,
                        "username": username,
                        "verified": email_login.verified,
                        "influencer": {"is_signed_up": True},
                    }
                )
        else:
            return jsonify(
                {
                    "followers": 1000,
                    "full_name": "",
                    "id": None,
                    "is_private": False,
                    "media_count": 50,
                    "profile_picture": None,
                    "username": username,
                    "verified": False,
                    "influencer": {"is_signed_up": True},
                }
            )

    profile = get_scraped_ig_info(username)

    account = InstagramAccount.query.filter(InstagramAccount.ig_user_id == profile["id"]).first()
    if account is None or account.influencer is None:
        return jsonify(
            {
                "followers": profile["followers"],
                "full_name": profile["full_name"],
                "id": profile["id"],
                "is_private": profile["is_private"],
                "media_count": profile["media_count"],
                "profile_picture": profile["profile_picture"],
                "username": profile["username"],
                "verified": False,
                "influencer": {"is_signed_up": False},
            }
        )

    if account.ig_username != profile["username"]:
        log = InstagramAccountLog(account.influencer.instagram_account)
        log.add_event("username-change", {"username": profile["username"]})
        db.session.add(account.influencer)
        db.session.commit()

    return jsonify(
        {
            "followers": account.followers,
            "full_name": account.influencer.user.full_name,
            "id": account.ig_user_id,
            "is_private": account.ig_is_private,
            "media_count": account.media_count,
            "profile_picture": account.influencer.profile_picture,
            "username": account.ig_username,
            "verified": account.influencer.is_signed_up,  # Legacy
            "influencer": {"is_signed_up": account.influencer.is_signed_up},
        }
    )


class StartVerificationSchema(Schema):
    username = fields.String(required=True)


@api.route("/users/instagram/start-verification", methods=["POST"])
@api.route("/users/instagram/start_verification", methods=["POST"])  # Legacy
def start_verification():
    """Endpoint to verify access/ownership of an instagram account.
    Chooses a random instagram post and returns a token which the user should
    post as a comment on the provided post
    """

    form = get_valid_json(StartVerificationSchema(), request)
    username = form["username"]
    if is_emaily(username):
        return jsonify({"token": "No Instagram Verification"}), 201

    profile = get_scraped_ig_info(username)
    account = InstagramAccount.query.filter(InstagramAccount.ig_user_id == profile["id"]).first()

    exists = account is not None

    if exists and account.influencer is not None and account.influencer.is_signed_up:
        raise APIError("This account has already been verified", 403, ALREADY_VERIFIED_ERROR_CODE)

    try:
        recent_media = instascrape.get_user_media(username, nocache=True)["data"]
    except NotFound:
        raise APIError("Failed to get images from Instagram", 403)

    if not recent_media:
        raise APIError("No images found for account", 403)

    media = random.choice(recent_media)

    ig_media_id = media["id"]
    ig_username = profile["username"]
    ig_user_id = profile["id"]

    owner = instascrape.get_user(ig_username, nocache=True)

    token = get_human_random_string(length=6)
    if not exists:
        account = InstagramAccount(
            id=uuid4_str(),
            ig_user_id=ig_user_id,
            ig_username=ig_username,
            ig_is_private=owner["is_private"],
            ig_biography=owner["biography"],
            followers=owner["followers"],
            follows=owner["following"],
            media_count=owner["media_count"],
            verified=False,
        )
    account.token = token
    account.ig_media_id = ig_media_id
    db.session.add(account)
    db.session.commit()

    post = {"id": ig_media_id, "image_url": media["url"], "link": media["link"]}

    return jsonify({"post": post, "token": token}), exists and 200 or 201


def find_token_comment_for_media(media, account):
    if media["comments"]:
        for comment in media["comments"]["nodes"]:
            if not comment["user_id"] == account.ig_user_id:
                continue
            if account.token == comment["text"].upper().strip():
                return True
    # If no comment include the token, check the caption. If a user comments the
    # first comment on his own instagram post with no caption, the comment is
    # turned into a caption
    return account.token == media["caption"].upper().strip()


def verify_media_for_account(media, account):
    if not media:
        raise APIError("Media not found", 404, MEDIA_NOT_FOUND_ERROR_CODE)
    if media["owner"]["id"] != account.ig_user_id:
        raise APIError("Media belongs to a different user!", 403, MEDIA_OWNER_MISMATCH_ERROR_CODE)
    if not find_token_comment_for_media(media, account):
        raise APIError(
            "Couldn’t find a comment containing the code. The comment must posted by {username}.".format(
                username=account.ig_username
            ),
            403,
            MEDIA_NO_CODE_FOUND_ERROR_CODE,
        )


class VerifyInstagramAccountSchema(Schema):
    ig_user_id = fields.String()
    ig_media_id = fields.String()
    username = fields.String()


@api.route("/users/instagram/verify", methods=["POST"])
def verify_instagram_account():
    account = None
    form = get_valid_json(VerifyInstagramAccountSchema(), request)

    if is_emaily(form.get("username", "")):
        token = encode_token({"account_id": form["username"]})
        return jsonify({"token": token.decode("utf-8"), "verified": True}), 201

    if not ("ig_media_id" in form or "username" in form):
        raise APIError("ig_media_id or username required", 422)

    if "ig_media_id" in form:
        ig_media_id = form["ig_media_id"]
        account = InstagramAccount.query.filter(
            InstagramAccount.ig_user_id == form["ig_user_id"]
        ).first()

        if account is None:
            raise APIError(
                "User account not found", 404, UNABLE_TO_FIND_SIGNUP_FOR_INSTAGRAM_USERNAME
            )

        if account.ig_media_id != ig_media_id:
            raise APIError(
                "This user has not requested token verification for this media",
                404,
                MEDIA_VERIFICATION_ID_MISMATCH,
            )

    if "username" in form:
        profile = get_scraped_ig_info(form["username"])
        account = InstagramAccount.query.filter(
            InstagramAccount.ig_user_id == profile["id"]
        ).first()

        if account is None:
            raise APIError(
                "User account not found", 404, UNABLE_TO_FIND_SIGNUP_FOR_INSTAGRAM_USERNAME
            )

        ig_media_id = account.ig_media_id

    try:
        media = instascrape.get_media(ig_media_id)
    except NotFound:
        # XXX: Temporary just allow signing up without validating the token,
        # the user will have to link up the facebook page that will verify
        # access to the actual account in the end.
        log = InstagramAccountLog(account)
        log.add_event("verify-media-for-account", {"bypassed-login": True})
        db.session.commit()

        account.verified = True
        token = encode_token({"account_id": account.id})

        db.session.add(account)
        db.session.commit()

        return jsonify({"verified": account.verified, "form": form, "token": token.decode("utf-8")})

    try:
        log = InstagramAccountLog(account)
        log.add_event("verify-media-for-account", media)
        db.session.commit()
    except Exception:
        capture_exception()

    verify_media_for_account(media, account)

    account.verified = True
    token = encode_token({"account_id": account.id})

    db.session.add(account)
    db.session.commit()

    return jsonify({"verified": account.verified, "form": form, "token": token.decode("utf-8")})
