from flask import jsonify, request
from itsdangerous import BadData, SignatureExpired
from marshmallow import Schema, fields

from core.common.exceptions import APIError

from takumi.constants import EMAIL_ENROLLMENT_SIGNER_NAMESPACE, EMAIL_VERIFICATION_MAX_AGE_SECONDS
from takumi.extensions import db
from takumi.models import EmailLogin
from takumi.signers import url_signer
from takumi.tokens import get_token_for_user
from takumi.utils.json import get_valid_json
from takumi.views.blueprint import api


class EnrollVerifySchema(Schema):
    token = fields.String(required=True)


@api.route("/users/enroll/verify", methods=["POST"])
def advertiser_enroll_verify():
    form = get_valid_json(EnrollVerifySchema(), request)
    token = form["token"]
    try:
        data = url_signer.loads(
            token,
            salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE,
            max_age=EMAIL_VERIFICATION_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        raise APIError("Link has expired. Please request a new invite.", 410)
    except BadData:
        raise APIError("Not Found.", 404)

    email_login = EmailLogin.get(data["email"])
    if not email_login.verified:
        email_login.verified = True
        db.session.add(email_login)
        db.session.commit()

    token = get_token_for_user(email_login.user)
    return jsonify(dict(token=token)), 200
