from dataclasses import dataclass
from typing import List, Optional, Set

import pytz


class Margins:
    asset = None
    reach = None

    def __init__(self, asset=0.5, reach=0.45):
        self.asset = asset
        self.reach = reach

    def __repr__(self):
        return f"<Margins: asset {self.asset}, reach {self.reach}>"


class Market:
    margins = Margins()
    supported = True
    shipping_cost = 2000
    default_locale = ""

    slug: str
    currency: str
    name: str
    country_codes: List[str]
    default_timezone: str
    sentiment_supported: bool

    @staticmethod
    def get_all_markets() -> List["Market"]:
        return MARKETS

    @staticmethod
    def get_all_slugs() -> List[str]:
        return [market.slug for market in Market.get_all_markets()]

    @staticmethod
    def get_market(market_slug: str) -> Optional["Market"]:
        markets = {market.slug: market for market in Market.get_all_markets()}
        return markets.get(market_slug, None)

    @staticmethod
    def get_all_supported_markets() -> List["Market"]:
        return [market for market in Market.get_all_markets() if market.supported]

    @property
    def timezone_choices(self) -> Set[str]:
        return {tz for cc in self.country_codes for tz in pytz.country_timezones[cc]}

    def __eq__(self, other):
        return self.slug == other.slug

    def __repr__(self):
        return f"<Market: {self.name}>"


@dataclass(frozen=True)
class _EuMarket(Market):
    slug = "eu"
    currency = "EUR"
    name = "Europe (EU)"
    country_codes = [
        "AT",
        "CH",
        "DE",
        "DK",
        "ES",
        "FR",
        "IE",
        "IT",
        "NL",
        "PL",
    ]
    default_timezone = "Europe/Berlin"
    default_locale = "de_DE"
    sentiment_supported = True


@dataclass(frozen=True)
class _UkMarket(Market):
    slug = "uk"
    currency = "GBP"
    name = "United Kingdom"
    country_codes = ["GB"]
    default_timezone = "Europe/London"
    default_locale = "en_GB"
    sentiment_supported = True


@dataclass(frozen=True)
class _IsMarket(Market):
    slug = "is"
    currency = "EUR"
    name = "Iceland"
    country_codes = ["IS"]
    default_timezone = "Atlantic/Reykjavik"
    default_locale = "is_IS"
    sentiment_supported = False
    supported = False


@dataclass(frozen=True)
class _ZaMarket(Market):
    slug = "za"
    currency = "ZAR"
    name = "South Africa"
    country_codes = ["ZA"]
    default_timezone = "Africa/Johannesburg"
    default_locale = "en_ZA"
    sentiment_supported = True


@dataclass(frozen=True)
class _UsMarket(Market):
    slug = "us"
    currency = "USD"
    name = "United States"
    country_codes = ["US"]
    default_timezone = "America/New_York"
    default_locale = "en_US"
    sentiment_supported = True
    margins = Margins(asset=2 / 3.0)  # Overwriting asset margins


@dataclass(frozen=True)
class _TestMarket(Market):
    slug = "test"
    currency = "GBP"
    name = "Test Market"
    country_codes = ["GB"]
    default_timezone = "Europe/London"
    default_locale = "en_GB"
    sentiment_supported = False


eu_market = _EuMarket()
uk_market = _UkMarket()
is_market = _IsMarket()
us_market = _UsMarket()
za_market = _ZaMarket()
test_market = _TestMarket()

MARKETS = [eu_market, uk_market, is_market, us_market, za_market, test_market]
