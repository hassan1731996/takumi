from dataclasses import dataclass
from typing import Dict, List, Union

from graphene import ObjectType

from takumi.gql import fields
from takumi.roles import permissions


@dataclass
class SupportedCountry:
    country_code: str
    label: str
    uses_iban: bool

    # Default to details input
    edit_using_details: bool = False

    def as_dict(self) -> Dict[str, Union[str, bool]]:
        return {
            "country_code": self.country_code,
            "label": self.label,
            "edit_using_details": self.edit_using_details,
            "uses_iban": self.uses_iban,
            "phone_number_mask": "",  # XXX: Deprecated
        }


SUPPORTED_COUNTRIES: List[SupportedCountry] = [
    SupportedCountry(country_code="AT", label="Austria", uses_iban=True),
    SupportedCountry(country_code="BE", label="Belgium", uses_iban=True),
    SupportedCountry(country_code="CH", label="Switzerland", uses_iban=True),
    SupportedCountry(country_code="DE", label="Germany", uses_iban=True),
    SupportedCountry(country_code="DK", label="Denmark", uses_iban=True),
    SupportedCountry(country_code="ES", label="Spain", uses_iban=True),
    SupportedCountry(country_code="FR", label="France", uses_iban=True),
    SupportedCountry(country_code="IE", label="Ireland", uses_iban=True),
    SupportedCountry(country_code="IT", label="Italy", uses_iban=True),
    SupportedCountry(country_code="NL", label="Netherlands", uses_iban=True),
    SupportedCountry(country_code="PL", label="Poland", uses_iban=True),
    SupportedCountry(country_code="PT", label="Portugal", uses_iban=True),
    # Non IBAN countries (XXX: GB moving from IBAN input)
    SupportedCountry(
        country_code="GB", label="United Kingdom", uses_iban=False, edit_using_details=True
    ),
    SupportedCountry(
        country_code="US", label="United States", uses_iban=False, edit_using_details=True
    ),
    SupportedCountry(
        country_code="ZA", label="South Africa", uses_iban=False, edit_using_details=True
    ),
]


class Country(ObjectType):
    country_code = fields.String()
    label = fields.String()
    details = fields.Boolean()  # support country-specific bank details
    edit_using_details = fields.Boolean()  # use country-specific detailed bank form by default
    uses_iban = fields.Boolean()  # does this country use IBAN


class CountryQuery:
    supported_countries = fields.List(Country)

    @permissions.public.require()
    def resolve_supported_countries(root, info, **args):
        return [country.as_dict() for country in SUPPORTED_COUNTRIES]
