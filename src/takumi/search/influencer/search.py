import datetime as dt
import inspect
import operator
from functools import partial, reduce

from elasticsearch_dsl import Q, Search
from flask import current_app

from core.elasticsearch import ResultSet
from core.targeting.targeting import age_es_query_filters

from takumi.extensions import elasticsearch
from takumi.utils import is_emaily, is_uuid

from .audit.search import AuditSearchMixin
from .indexing import InfluencerInfo
from .information.search import InformationSearchMixin


class InfluencerSearch(Search, AuditSearchMixin, InformationSearchMixin):
    def __init__(self, *args, **kwargs):
        using = kwargs.pop("using", elasticsearch)
        return super().__init__(*args, using=using, **kwargs)

    def filter_field_by_range(self, field, min_val, max_val):
        if min_val is None and max_val is None:
            return self
        range_filter = {}
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val
        return self.filter("range", **{field: range_filter})

    def filter_participating_campaign_count(self, min_count=None, max_count=None):
        participating_campaign_id_size = 'doc["participating_campaign_ids"].size()'
        _self = self
        if min_count:
            _self = _self.filter(
                {"script": {"script": f"{participating_campaign_id_size} >= {min_count}"}}
            )
        if max_count:
            _self = _self.filter(
                {"script": {"script": f"{participating_campaign_id_size} <= {max_count}"}}
            )
        return _self

    def filter_followers_history_anomalies(self, min_val=None, max_val=None):
        if min_val is None and max_val is None:
            return self
        range_filter = {}
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val
        return self.filter(
            "nested",
            path="followers_history_anomalies",
            query=Q("range", **{"followers_history_anomalies__anomaly_factor": range_filter})
            & Q("term", followers_history_anomalies__ignore=False),
        )

    def filter_disabled(self):
        return self.filter(Q("term", state="disabled"))

    def filter_not_disabled(self):
        return self.filter(~Q("term", state="disabled"))

    def filter_has_tiktok_account(self):
        return self.filter(Q("term", has_tiktok_account=True))

    def filter_has_no_tiktok_account(self):
        return self.filter(Q("term", has_tiktok_account=False))

    def filter_has_youtube_channel(self):
        return self.filter(Q("term", has_youtube_channel=True))

    def filter_has_no_youtube_channel(self):
        return self.filter(Q("term", has_youtube_channel=False))

    def filter_has_interests(self):
        return self.filter(Q("term", has_interests=True))

    def filter_has_no_interests(self):
        return self.filter(Q("term", has_interests=False))

    def filter_engagement(self, min_engagement=None, max_engagement=None):
        return self.filter_field_by_range("engagement.value", min_engagement, max_engagement)

    def filter_follower_percentage_in_region(self, region_id, min_val=None, max_val=None):
        range_filter = {}
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        region_matches_id = Q(
            "term", instagram_audience_insight__region_insights__region__id=region_id
        )
        region_matches_value = Q(
            "range",
            instagram_audience_insight__region_insights__follower_percentage__value=range_filter,
        )
        return self.filter(
            "nested",
            path="instagram_audience_insight",
            query=Q(
                "nested",
                path="instagram_audience_insight.region_insights",
                query=Q(
                    "nested",
                    path="instagram_audience_insight.region_insights.region",
                    query=region_matches_id,
                )
                & region_matches_value,
            ),
        )

    def filter_estimated_engagements_per_post(self, min_engagements=None, max_engagements=None):
        return self.filter_field_by_range(
            "estimated_engagements_per_post", min_engagements, max_engagements
        )

    def filter_followers(self, min_followers=None, max_followers=None):
        return self.filter_field_by_range("followers", min_followers, max_followers)

    def filter_min_platform_followers(self):
        return self.filter_followers(min_followers=current_app.config["MINIMUM_FOLLOWERS"])

    def filter_not_private(self):
        return self.filter("term", is_private=False)

    def filter_min_media_count(self):
        return self.filter("range", media_count={"gte": 50})

    def filter_signed_up(self):
        return self.filter("term", is_signed_up=True)

    def filter_has_facebook_page(self):
        return self.filter("term", has_facebook_page=True)

    def filter_has_no_facebook_page(self):
        return self.filter("term", has_facebook_page=False)

    def filter_verified(self):
        return self.filter("term", state="verified")

    def filter_verified_or_reviewed(self):
        return self.filter("terms", state=["verified", "reviewed"])

    def filter_eligible(self):
        return (
            self.filter_not_disabled()
            .filter_min_platform_followers()
            .filter_not_private()
            .filter_min_media_count()
            .filter_signed_up()
        )

    def filter_by_user_created(self, from_date=None, to_date=None):
        return self.filter_field_by_range(
            "user_created",
            from_date.isoformat() if from_date else None,
            to_date.isoformat() if to_date else None,
        )

    def filter_untagged_signups(self):
        return (
            self.filter_eligible()
            .filter_supported_regions()
            .filter(
                ~Q("exists", field="interests")
                & Q("term", state="new")
                & Q("term", is_signed_up=True)
                & Q(  # Only show signups that have been active in the past 30 days
                    "range",
                    user_created={
                        "gt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
                    },
                )
            )
        )

    def filter_regions(self, regions):
        return self.query(
            "nested",
            path="target_region",
            query=reduce(
                operator.or_,
                (
                    Q("term", target_region__id=region.id)
                    | Q("term", target_region__path=region.id)
                    for region in regions
                ),
            ),
        )

    def filter_region(self, region):
        return self.filter_regions([region])

    def filter_supported_regions(self):
        return self.query(
            "nested", path="target_region", query=Q("term", target_region__targetable=True)
        )

    def filter_region_or_all_supported(self, region):
        if not region:
            return self.filter_supported_regions()
        return self.filter_region(region)

    def filter_target_regions(self, targeting):
        if not targeting.regions:
            return self
        return self.filter_regions(targeting.regions)

    def filter_gender(self, gender):
        return self.filter("term", gender=gender)

    def filter_age(self, min_age=0, max_age=100):
        return self.filter(age_es_query_filters(range(min_age, max_age + 1), "birthday"))

    def filter_target_ages(self, targeting):
        return self.filter(age_es_query_filters(targeting.ages, "birthday"))

    def filter_interests(self, interest_ids):
        return self.query("nested", path="interests", query=Q("terms", interests__id=interest_ids))

    def filter_targeting(self, targeting):  # noqa
        query = self.filter_eligible().filter_target_regions(targeting)

        if targeting.verified_only:
            query = query.filter_verified()
        else:
            query = query.filter_verified_or_reviewed()

        if targeting.gender:
            query = query.filter_gender(targeting.gender)
        if targeting.ages:
            query = query.filter_target_ages(targeting)
        if targeting.interest_ids:
            query = query.filter_interests(targeting.interest_ids)
        if targeting.max_followers:
            query = query.filter_followers(max_followers=targeting.max_followers)
        if targeting.min_followers:
            query = query.filter_followers(min_followers=targeting.min_followers)

        if targeting.hair_type_ids:
            query = query.filter_information_hair_type(targeting.hair_type_ids)
        if targeting.hair_colour_categories:
            query = query.filter_information_hair_colour_category(targeting.hair_colour_categories)
        if targeting.eye_colour_ids:
            query = query.filter_information_eye_colour(targeting.eye_colour_ids)
        if targeting.has_glasses is not None:
            if targeting.has_glasses:
                query = query.filter_information_has_glasses()
            else:
                query = query.filter_information_has_no_glasses()
        if targeting.languages:
            query = query.filter_information_languages(targeting.languages)
        if targeting.self_tag_ids:
            query = query.filter_information_tags(targeting.self_tag_ids)

        children_targeting = targeting.children_targeting
        if children_targeting:
            query = query.filter_information_child_count(
                children_targeting.min_children_count, children_targeting.max_children_count
            )
            if children_targeting.ages:
                query = query.filter_information_child_age(children_targeting.ages)
            if children_targeting.child_gender:
                query = query.filter_information_child_gender(children_targeting.child_gender)
            if children_targeting.has_born_child:
                query = query.filter_information_has_born_child()
            if children_targeting.has_unborn_child:
                query = query.filter_information_has_unborn_child()

        return query

    def filter_campaign_non_participating(self, campaign):
        return self.filter(~Q("term", participating_campaign_ids=campaign.id))

    def filter_campaign_non_invited(self, campaign):
        return self.filter(~Q("term", invited_campaign_ids=campaign.id))

    def filter_campaign_market(self, campaign):
        return self.query(
            "nested",
            path="target_region",
            query=Q("term", target_region__market_slug=campaign.market_slug),
        )

    def filter_doesnt_have_offer_in_campaign(self, campaign):
        return self.filter_campaign_non_participating(campaign).filter_campaign_non_invited(
            campaign
        )

    def filter_campaign_eligibility(self, campaign, targeting=None):
        if not targeting:
            targeting = campaign.targeting
        result = self.filter_targeting(targeting)
        return result

    def search(self, search_string):
        search_string = search_string.strip()
        if is_emaily(search_string):
            return self.filter("term", email=search_string)
        if is_uuid(search_string):
            return self.filter("term", id=search_string)
        if not search_string.endswith("*"):
            search_string = f"{search_string}*"
        return self.query(
            "simple_query_string",
            query=search_string,
            fields=["full_name", "username", "biography", "email", "tiktok_username"],
        )

    def sort_by_participating_campaign_count(self, desc=False):
        return self.sort(
            {
                "_script": dict(
                    type="number",
                    script=dict(lang="painless", source='doc["participating_campaign_ids"].size()'),
                    order="desc" if desc else "asc",
                )
            }
        )

    def sort_by_followers_history_anomalies(self, desc=False):
        return self.sort(
            {
                "followers_history_anomalies.anomaly_factor": dict(
                    order="desc" if desc else "asc",
                    nested_path="followers_history_anomalies",
                    nested_filter={"term": {"followers_history_anomalies.ignore": False}},
                )
            }
        )

    def sort_by(self, field, desc=False, nested_path=None):
        return self.sort(
            {
                field: dict(
                    order="desc" if desc else "asc",
                    **dict(nested_path=nested_path) if nested_path else {},
                )
            }
        )

    def _add_participating_campaign_count_histogram(self):
        self.aggs.bucket(
            "participating_campaign_count_histogram",
            "histogram",
            interval=10,
            script=dict(lang="painless", source='doc["participating_campaign_ids"].size()'),
        )

    def add_statistics_aggregations(self):
        self._add_participating_campaign_count_histogram()
        self.add_audit_statistics_aggregations()

    def add_count_by_aggregation(self, field):
        self.aggs.bucket("count_by_" + field, "terms", field=field, size=1000).bucket(
            "sum_followers", "sum", field="followers"
        )
        return self

    def add_count_by_interests(self):
        interests_bucket = self.aggs.bucket("count_by_interests", "nested", path="interests")
        interests_bucket.bucket("sub_bucket", "terms", field="interests.name", size=1000).bucket(
            "sub_bucket", "reverse_nested"
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def add_count_by_region(self):
        region_bucket = self.aggs.bucket("count_by_target_region", "nested", path="target_region")
        region_bucket.bucket("sub_bucket", "terms", field="target_region.id", size=1000).bucket(
            "sub_bucket", "reverse_nested"
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def add_count_by_device_model(self):
        device_bucket = self.aggs.bucket("count_by_device_model", "nested", path="device")
        device_bucket.bucket("sub_bucket", "terms", field="device.device_model", size=1000).bucket(
            "sub_bucket", "reverse_nested"
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def _add_count_by_ranges(self, field, ranges, field_val=None, date=False):
        self.aggs.bucket(
            "count_by_" + field,
            "date_range" if date else "range",
            field=field_val or field,
            ranges=ranges,
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def add_count_by_followers(self):
        return self._add_count_by_ranges(
            "followers",
            [
                {"to": 1000},
                {"from": 1000, "to": 2000},
                {"from": 2000, "to": 3000},
                {"from": 3000, "to": 4000},
                {"from": 4000, "to": 5000},
                {"from": 5000, "to": 10_000},
                {"from": 10_000, "to": 20_000},
                {"from": 20_000, "to": 40_000},
                {"from": 40_000, "to": 100_000},
                {"from": 100_000, "to": 200_000},
                {"from": 200_000, "to": 500_000},
                {"from": 500_000, "to": 1_000_000},
                {"from": 1_000_000},
            ],
        )

    def add_count_by_media_count(self):
        return self._add_count_by_ranges(
            "media_count",
            [
                {"to": 100},
                {"from": 100, "to": 200},
                {"from": 200, "to": 500},
                {"from": 500, "to": 1000},
                {"from": 1000, "to": 2000},
                {"from": 2000, "to": 4000},
                {"from": 4000},
            ],
        )

    def add_count_by_following(self):
        return self._add_count_by_ranges(
            "following",
            [
                {"to": 100},
                {"from": 100, "to": 200},
                {"from": 200, "to": 300},
                {"from": 300, "to": 600},
                {"from": 600, "to": 1200},
                {"from": 1200, "to": 2400},
                {"from": 2400, "to": 4800},
                {"from": 4800, "to": 9600},
                {"from": 9600},
            ],
        )

    def add_count_by_estimated_engagements_per_post(self):
        return self._add_count_by_ranges(
            "estimated_engagements_per_post",
            [
                {"from": 1, "to": 50},
                {"from": 50, "to": 100},
                {"from": 100, "to": 150},
                {"from": 150, "to": 300},
                {"from": 300, "to": 600},
                {"from": 600, "to": 1200},
                {"from": 1200, "to": 2400},
                {"from": 2400, "to": 4800},
                {"from": 4800, "to": 9600},
                {"from": 9600, "to": 19200},
                {"from": 19200},
            ],
        )

    def add_count_by_total_rewards(self):
        return self._add_count_by_ranges(
            "total_rewards",
            [
                {"to": 80},
                {"from": 80, "to": 160},
                {"from": 160, "to": 320},
                {"from": 320, "to": 640},
                {"from": 640, "to": 1280},
                {"from": 1280, "to": 2560},
                {"from": 2560, "to": 5120},
                {"from": 5120, "to": 10240},
                {"from": 10240, "to": 20480},
                {"from": 20480},
            ],
            field_val="total_rewards.value",
        )

    def add_count_by_user_created(self):
        now = dt.datetime.now()
        months = (now.year - 2015) * 12 + now.month - 12
        return self._add_count_by_ranges(
            "user_created",
            ranges=[
                {
                    "from": "now-" + str(months - nm + 1) + "M/M",
                    "to": "now-" + str(months - nm) + "M/M",
                }
                for nm in range(0, months + 1)
            ]
            + [{"from": "now-0M/M"}],
            date=True,
        )

    def add_count_by_last_login(self):
        now = dt.datetime.now()
        months = (now.year - 2017) * 12 + now.month - 8
        return self._add_count_by_ranges(
            "last_login",
            ranges=[
                {
                    "from": "now-" + str(months - nm + 1) + "M/M",
                    "to": "now-" + str(months - nm) + "M/M",
                }
                for nm in range(0, months + 1)
            ]
            + [{"from": "now-0M/M"}],
            date=True,
        )

    def add_count_by_age(self):
        current_year = dt.datetime.now().year
        self.aggs.bucket(
            "count_by_age",
            "range",
            script=str(current_year) + "-doc['birthday'].date.year",
            ranges=[
                {"from": 0, "to": 20},
                {"from": 20, "to": 25},
                {"from": 25, "to": 30},
                {"from": 30, "to": 35},
                {"from": 35, "to": 40},
                {"from": 40, "to": 50},
                {"from": 50, "to": 60},
                {"from": 60},
            ],
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def add_count_by_participating_campaign_count(self):
        self.aggs.bucket(
            "count_by_participating_campaign_count",
            "range",
            script='doc["participating_campaign_ids"].size()',
            ranges=[
                {"from": 1, "to": 2},
                {"from": 2, "to": 5},
                {"from": 5, "to": 10},
                {"from": 10, "to": 20},
                {"from": 20, "to": 30},
                {"from": 30, "to": 40},
                {"from": 40, "to": 50},
                {"from": 50, "to": 60},
                {"from": 60, "to": 70},
                {"from": 70, "to": 80},
                {"from": 80, "to": 90},
                {"from": 90, "to": 100},
                {"from": 100},
            ],
        ).bucket("sum_followers", "sum", field="followers")
        return self

    def get(self, id):
        return self.filter("term", id=id).first()

    def execute(self):
        return ResultSet(self, elasticsearch, result_cls=InfluencerInfo)

    def count(self):
        return self.execute().count()

    def first(self):
        return self.execute().first()

    def ids(self, limit=10000):
        resultset = self.source(["id"]).execute()
        resultset.fetch(0, limit)
        return [r.id for r in resultset.all()]

    def all(self):
        return self.execute().all()

    def sum(self, field, name=None):
        if name is None:
            name = f"sum_{field}"
        self.aggs.bucket(name, "sum", field=field)
        return self

    def aggregations(self):
        return self.execute().aggregations()


class TracedInfluencerSearch(InfluencerSearch):
    def __init__(self, *args, **kwargs):
        self.tracing = []
        return super(InfluencerSearch, self).__init__(*args, **kwargs)

    def __getattribute__(self, attr):
        attribute = object.__getattribute__(self, attr)

        def wrapped(*args, **kwargs):
            name, method = kwargs.pop("_original_method")
            filter_results = method(*args, **kwargs)
            filter_results.tracing = self.tracing
            self.tracing.append((name, filter_results.count()))
            return filter_results

        traceable = inspect.ismethod(attribute) and attribute.__name__.startswith("filter_")

        if traceable:
            name = attribute.__name__
            return partial(wrapped, _original_method=(name, attribute))

        return attribute
