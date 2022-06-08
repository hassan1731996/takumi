from typing import Any, Dict, Iterable

from marshmallow import Schema, fields

from takumi.gql.query.country import CountryQuery

from .blueprint import api


class CountrySettingsSchema(Schema):
    country_code = fields.String()
    label = fields.String()
    details = fields.Boolean()  # support country-specific bank details
    edit_using_details = fields.Boolean()  # use country-specific detailed bank form by default
    uses_iban = fields.Boolean()  # does this country use IBAN
    phone_number_mask = fields.String()


class SupportedCountrySchema(Schema):
    countries = fields.List(fields.Nested(CountrySettingsSchema()))


@api.route("/_countries", methods=["GET"])
def supported_countries() -> Any:
    """Return supported countries and their specifics"""

    countries = CountryQuery().resolve_supported_countries("info")

    payload: Dict[str, Iterable[Dict]] = dict(
        countries=sorted(countries, key=lambda country: country["label"])
    )

    return (
        SupportedCountrySchema(),
        payload,
        200,
    )
