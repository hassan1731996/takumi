from dataclasses import dataclass
from typing import Optional

from babel import Locale

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.models import Region
from takumi.roles import permissions
from takumi.utils import uuid4_str


@dataclass
class Country:
    name: str
    locale: str


TERRS = Locale("en").territories


def get_country(code: str, locale_code: Optional[str] = None) -> Country:
    name = TERRS[code]
    try:
        locale = Locale.parse(f"und_{code}")
        locale_code = f"{locale.language}_{locale.territory}"
    except Exception as e:
        if locale_code is None:
            raise MutationException(
                "Unable to get country from code, you might need to provide locale code"
            ) from e

    return Country(name=name, locale=locale_code)


class AddRegionByCountryCode(Mutation):
    """Add region by a Country Code"""

    class Arguments:
        country_code = arguments.String(
            required=True,
            description="The country code. Example 'TJ'",
        )
        locale_code = arguments.String(
            description="Optional, might be required if the mutation fails without it. Example 'tg_TJ'",
        )

    region = fields.Field("Region")

    @permissions.developer.require()
    def mutate(
        root, info, country_code: str, locale_code: Optional[str] = None
    ) -> "AddRegionByCountryCode":
        country = get_country(country_code, locale_code)

        if exists := Region.query.filter(Region.name == country.name).first():
            raise MutationException(f"Country already exists by name: {exists}")
        if exists := Region.query.filter(Region.locale == country.locale).first():
            raise MutationException(f"Country already exists by locale: {exists}")

        region = Region(
            id=uuid4_str(), name=country.name, locale_code=country.locale, supported=False
        )
        db.session.add(region)
        db.session.commit()

        return AddRegionByCountryCode(ok=True, region=region)
