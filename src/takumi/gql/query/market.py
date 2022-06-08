from sqlalchemy import func

from takumi.gql import fields
from takumi.models import Region
from takumi.models.market import Market
from takumi.roles import permissions


def market_regions():
    for market in Market.get_all_supported_markets():
        if not market.country_codes:
            regions = None
        else:
            regions = Region.query.filter(
                Region.path == None,  # noqa: E711
                func.substring(Region.locale_code, 4, 2).in_(market.country_codes),
            ).all()
        yield market, regions


class MarketQuery:
    markets = fields.List("Market")

    @permissions.developer.require()
    def resolve_markets(root, info):
        markets = []
        for market, regions in market_regions():
            market.regions = regions
            markets.append(market)
        return markets
