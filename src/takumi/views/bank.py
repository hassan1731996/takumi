from typing import Dict, Tuple

from flask import request
from flask_login import login_required
from marshmallow import Schema, fields

from core.common.exceptions import APIError

from takumi.auth import influencer_required
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.bank import (
    RegisterGbAccount,
    RegisterIban,
    RegisterUsAccount,
    RegisterZaAccount,
)
from takumi.schemas import TransferDestination

from .blueprint import api

ResponseTuple = Tuple[Schema, Dict, int]

REQUIRES_ADDRESS = ["CH"]


@api.route("/iban/calculate", methods=["POST"])
@login_required
def calculate_iban() -> ResponseTuple:
    raise APIError("Invalid payment details. Please update the Takumi app", 422)


class TransferDestinationResponse(Schema):
    valid = fields.Boolean(required=True)
    destination = fields.Nested(TransferDestination(), required=False)


def validate_bank_register(form: Dict) -> None:
    if len(form.get("full_name", "").split()) < 2:
        raise APIError("Full name is required", 422)
    if "bank_name" not in form:
        raise APIError("Bank name is required", 422)
    if "country_code" not in form:
        raise APIError("Country code is required", 422)

    # Validate IBAN country
    if "iban" in form and len(form["iban"]) > 2:
        iban_country_code = form["iban"][0:2].upper()

        if iban_country_code == "GB":
            raise APIError("IBAN not supported for UK", 422)
        elif iban_country_code != form["country_code"].upper():
            raise APIError("Country code does not match iban country code", 422)


@api.route("/bank/register", methods=["POST"])
@influencer_required
def register_bank_details() -> ResponseTuple:
    form = request.get_json()
    validate_bank_register(form)

    country_code = form["country_code"].upper()

    try:
        if "iban" in form:
            response = RegisterIban().mutate(
                "info",
                full_name=form["full_name"],
                country_code=form["country_code"],
                iban=form["iban"],
                bic=form["bic"],
            )
            return (
                TransferDestinationResponse(),
                {
                    "valid": True,
                    "destination": {
                        "type": response.destination_type,
                        "value": response.destination_value,
                    },
                },
                200,
            )
        elif country_code == "GB":
            if "account_number" not in form or "sort_code" not in form:
                raise APIError("Account number and sort code is required", 422)
            response = RegisterGbAccount().mutate(
                "info",
                full_name=form["full_name"],
                account_number=form["account_number"],
                sort_code=form["sort_code"],
            )
            return (
                TransferDestinationResponse(),
                {
                    "valid": True,
                    "destination": {
                        "type": response.destination_type,
                        "value": response.destination_value,
                    },
                },
                200,
            )
        elif country_code == "US":
            if "account_number" not in form or "routing_number" not in form:
                raise APIError("Account number and routing number is required", 422)
            response = RegisterUsAccount().mutate(
                "info",
                full_name=form["full_name"],
                bank_name=form["bank_name"],
                account_number=form["account_number"],
                routing_number=form["routing_number"],
                account_type=form["account_type"],
            )
            return (
                TransferDestinationResponse(),
                {
                    "valid": True,
                    "destination": {
                        "type": response.destination_type,
                        "value": response.destination_value,
                    },
                },
                200,
            )
        elif country_code == "ZA":
            response = RegisterZaAccount().mutate(
                "info",
                full_name=form["full_name"],
                account_number=form["account_number"],
                bic=form["bic"],
            )
            return (
                TransferDestinationResponse(),
                {
                    "valid": True,
                    "destination": {
                        "type": response.destination_type,
                        "value": response.destination_value,
                    },
                },
                200,
            )
        else:
            raise APIError("Missing valid payment details", 422)
    except MutationException as e:
        raise APIError(str(e), 400)
