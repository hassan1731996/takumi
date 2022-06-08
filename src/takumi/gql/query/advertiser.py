from takumi.gql import arguments, fields
from takumi.gql.db import filter_advertisers
from takumi.models import Advertiser
from takumi.roles import permissions
from takumi.search import search_advertisers_query


class AdvertiserQuery:
    advertiser = fields.Field("Advertiser", domain=arguments.String(required=True))
    advertisers = fields.ConnectionField(
        "AdvertiserConnection", archived=arguments.Boolean(), search=arguments.String()
    )

    @permissions.public.require()
    def resolve_advertiser(root, info, domain):
        query = filter_advertisers()
        return query.filter(Advertiser.domain == domain).one_or_none()

    @permissions.public.require()
    def resolve_advertisers(root, info, archived=False, search=None):
        query = filter_advertisers()

        if not permissions.archive_brand.can():
            # Force filter out archived brands if user cannot archive brands
            archived = False

        query = query.filter(Advertiser.archived == archived)

        if search is not None:
            query = search_advertisers_query(query, search)

        return query.order_by(Advertiser.name)
