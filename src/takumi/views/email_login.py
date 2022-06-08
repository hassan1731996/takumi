from typing import Tuple

from flask import abort, jsonify, redirect, request
from flask_login import current_user
from itsdangerous import BadData, SignatureExpired
from marshmallow import Schema, fields

from core.common.exceptions import APIError

from takumi import slack
from takumi.auth import min_version_required
from takumi.constants import CLIENT_URI
from takumi.emails import PasswordRecoveryEmail
from takumi.extensions import db
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.public.authentication import Login, OTPLogin
from takumi.models import EmailLogin
from takumi.roles.roles import InfluencerRole
from takumi.schemas import SelfInfluencerSchema, SelfUserSchema
from takumi.security import check_if_password_leaked
from takumi.services import ServiceException
from takumi.signers import url_signer
from takumi.utils.json import get_valid_json
from takumi.utils.user_agent import get_ios_version_from_user_agent

from .blueprint import api


class PasswordRecoverySchema(Schema):
    email = fields.Email(required=True)


@api.route("/password-recovery", methods=["POST"])
def password_recovery():
    """This view should not indicate e-mail lookup errors or matches so
    attackers cannot harvest email addresses from our database.

    """
    form = get_valid_json(PasswordRecoverySchema(), request)
    email = form["email"]

    reset_message = (
        "We've emailed you instructions for setting your "
        + "password, if an account exists with the email you "
        + "entered. You should receive them shortly."
    )
    response = jsonify(message=reset_message)

    email_login = EmailLogin.get(email)
    if (
        email_login is None
        or not email_login.verified
        or email_login.user.role_name == InfluencerRole.name
    ):
        return response

    PasswordRecoveryEmail(
        {
            "recipient": email,
            "token": url_signer.dumps(dict(email=email), salt="password-recovery-key"),
        }
    ).send(email)

    return response


class PasswordRecoveryChangeSchema(Schema):
    password = fields.String(required=True)
    token = fields.String(required=True)


@api.route("/self/password", methods=["PUT"])
@api.route("/users/self/password", methods=["PUT"])  # legacy
def password_recovery_change():
    form = get_valid_json(PasswordRecoveryChangeSchema(), request)

    try:
        data = url_signer.loads(form["token"], salt="password-recovery-key", max_age=86400)
    except SignatureExpired:
        abort(410)
    except BadData:
        abort(404)

    email = data["email"]

    email_login = EmailLogin.get(email)
    if email_login is None:
        abort(404)

    email_login.set_password(form["password"])
    db.session.add(email_login)
    db.session.commit()

    return jsonify(message="Password reset complete")


@api.route("/login/app/<token>")
@min_version_required
def app_login(token):
    """A HTTP redirect to deep link into the app

    Many email clients (for example gmail) don't linkify links to unknown
    schemes, such as exp://. Instead of sending the exp:// link directly in
    emails, we send a http link to the server, to this view, which takes care
    of redirecting the user to a relevant deeplink for the app.

    If app_uri is in the url parameters, we use that, if not, we use the
    default base uri.
    """
    user_agent = request.headers.get("User-Agent")
    ios_version = get_ios_version_from_user_agent(user_agent)
    if ios_version is not None and ios_version < [11, 0, 0]:
        # A bug in versions prior to 11 prevent redirecting to deeplink directly,
        # Use the old login.takumi.com portal
        return redirect(f"http://login.takumi.com/e/?token={token}")

    app_uri = request.args.get("app_uri")

    return redirect(f"{app_uri or CLIENT_URI}login/{token}")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


@api.route("/login", methods=["POST"])
def login() -> Tuple[str, int]:
    form = get_valid_json(LoginSchema(), request)
    email: str = form["email"]
    password: str = form["password"]

    try:
        login = Login().mutate("info", email, password)
        user = login.user
        token = login.token
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 403)

    if email.lower().endswith("@takumi.com") and check_if_password_leaked(password):
        slack.report_leaked_password(user)

    return jsonify(user=SelfUserSchema().dump(user).data, token=token), 200


@api.route("/login/otp/<token>", methods=["POST"])
@min_version_required
def login_otp(token):
    try:
        login = OTPLogin().mutate("info", token)
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 403)

    return (
        jsonify(
            user=SelfInfluencerSchema(context={"user": login.user}).dump(current_user).data,
            token=login.token,
        ),
        200,
    )
