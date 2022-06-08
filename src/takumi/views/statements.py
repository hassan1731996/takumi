from flask import Response, abort, request
from flask_login import current_user
from itsdangerous import BadData, SignatureExpired
from marshmallow import Schema, fields
from sentry_sdk import capture_exception

from core.common.exceptions import APIError

from takumi.auth import influencer_required
from takumi.receipts import (
    MultipleCurrenciesException,
    NoReceiptsFoundException,
    ReceiptServiceException,
    get_influencer_receipt_pdf,
)
from takumi.services import InfluencerService
from takumi.signers import url_signer
from takumi.statements import get_statement_salt_for_influencer, get_statements
from takumi.views.blueprint import api


class MoneySchema(Schema):
    amount = fields.Integer()
    currency = fields.String()
    formatted_amount = fields.String()


class StatementSchema(Schema):
    label = fields.String(attribute="year")
    url = fields.String()
    balance = fields.Nested(MoneySchema())


class StatementResponseSchema(Schema):
    years = fields.List(fields.Nested(StatementSchema()))


@api.route("/self/statements")
@influencer_required
def get_influencer_statements():
    return StatementResponseSchema(), {"years": get_statements(current_user.influencer)}, 200


def get_pdf_content(influencer, year, currency=None):
    try:
        pdf_content = get_influencer_receipt_pdf(influencer, year, currency=currency)
    except ReceiptServiceException:
        capture_exception()
        abort(503, "Service Unavailable")
    except MultipleCurrenciesException:
        capture_exception()
        raise APIError("Unable to generate report for multiple currencies. Please contact support.")
    except NoReceiptsFoundException:
        raise APIError(f"No statement found for {year}")
    return pdf_content


@api.route("/self/statements/<int:year>.pdf")
@influencer_required
def get_statement(year):
    # Deprecated for clients 4.0.0+
    return Response(
        get_pdf_content(current_user.influencer, year),
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=receipt-{year}.pdf"},
    )


@api.route("/statements/<username>/<currency>/<int:year>.pdf")
def get_tokenised_statement(username, currency, year):
    influencer = InfluencerService.get_by_username(username)
    if influencer is None:
        raise APIError("Statement not found", 404)

    token = request.args.get("token")
    if token is None:
        raise APIError("Invalid token", 404)

    try:
        data = url_signer.loads(
            token, salt=get_statement_salt_for_influencer(influencer), max_age=86400
        )
    except SignatureExpired:
        raise APIError("Token has expired", 410)
    except BadData:
        raise APIError("Invalid token", 404)

    if data["currency"] != currency or data["year"] != year:
        raise APIError("Invalid token", 404)

    return Response(
        get_pdf_content(influencer, year, currency),
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=receipt-{year}.pdf"},
    )
