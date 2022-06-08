import datetime as dt

from elasticsearch_dsl import Q
from graphene import ObjectType

from takumi.constants import ALL_SUPPORTED_REGIONS
from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.models import Region
from takumi.roles import permissions
from takumi.search.influencer import InfluencerSearch
from takumi.utils import construct_cursor_from_items


class Interval(arguments.Enum):
    """Time period to aggregate data over"""

    year = "year"
    month = "month"
    week = "week"


class KeyCount(ObjectType):
    key = fields.String()
    count = fields.Int(source="doc_count")


class StatsResult(ObjectType):
    date = fields.String()
    count = fields.Int()
    by_state = fields.List(KeyCount)


class StatsResults(ObjectType):
    results = fields.List(StatsResult)
    count = fields.Int()


def get_region_by_id(region_id):
    region = None

    if region_id and region_id != ALL_SUPPORTED_REGIONS:
        region = Region.query.get(region_id)
        if region is None:
            raise QueryException(f'No region with id "{region_id}" found')

    return region


class SignupsQuery:
    influencer_signups = fields.Field("NextSignup", id=arguments.UUID(), region_id=arguments.UUID())

    influencer_signups_stats = fields.Field(
        StatsResults,
        interval=Interval(required=True, description="Time period to aggregate data over"),
        region_id=arguments.UUID(
            description="Filter by region. If missing will use all supported regions"
        ),
    )

    @permissions.access_all_influencers.require()
    def resolve_influencer_signups(root, info, id=None, region_id=None):
        """Returns signups that have been active in the past 30 days"""
        region = get_region_by_id(region_id)

        signup_query = Q("term", state="new") & Q(
            "range",
            last_login={
                "gt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
            },
        )

        search = (
            InfluencerSearch()
            .filter_eligible()
            .filter_region_or_all_supported(region)
            .filter(signup_query)
            .sort({"user_created": {"order": "desc"}})
        )

        ids = [i.id for i in search.execute()]
        result = construct_cursor_from_items(ids, target_item=id)
        result["count"] = search.count()

        return result

    @permissions.access_all_influencers.require()
    def resolve_influencer_signups_stats(root, info, interval, region_id=None):
        region = get_region_by_id(region_id)

        search = (
            InfluencerSearch()
            .filter_signed_up()
            .filter_min_platform_followers()
            .filter_min_media_count()
            .filter_not_private()
            .filter_region_or_all_supported(region)
        )

        search.aggs.bucket(
            "by_created",
            "date_histogram",
            field="user_created",
            interval=interval,
            format="yyyy-MM-dd",
            order={"_key": "desc"},
        ).bucket("by_state", "terms", field="state")

        stats_results = search.execute()

        results = [
            StatsResult(
                date=r["key_as_string"], count=r["doc_count"], by_state=r["by_state"]["buckets"]
            )
            for r in stats_results.aggregations()["by_created"]["buckets"]
        ]

        return StatsResults(count=stats_results.count(), results=results)
