from takumi.gql import arguments, fields
from takumi.models import Region
from takumi.roles import permissions


class RegionQuery:
    _filters = {"include_unsupported": arguments.Boolean(), "market": arguments.String()}
    regions = fields.List("Region", **_filters)
    countries = fields.List("Region", **_filters)

    @staticmethod
    def _regions(include_unsupported=False, market=None):
        query = Region.query.filter(Region.hidden == False)

        if not include_unsupported:
            query = query.filter(Region.supported == True)

        if market:
            query = query.filter(Region.market_slug == market)

        return query

    @permissions.list_regions.require()
    def resolve_regions(root, info, include_unsupported=False, market=None):
        query = RegionQuery._regions(include_unsupported, market)
        return query

    @permissions.list_regions.require()
    def resolve_countries(root, info, include_unsupported=False, market=None):
        query = RegionQuery._regions(include_unsupported, market)
        query = query.filter(Region.path == None).order_by(Region.name)  # noqa: E711
        return query
