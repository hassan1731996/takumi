from typing import Dict

from graphene import ObjectType

from takumi.constants import ALL_REGIONS, ALL_SUPPORTED_REGIONS
from takumi.gql import arguments, fields
from takumi.gql.db import filter_campaigns
from takumi.gql.query.targeting import GenderType
from takumi.models import Campaign, Region
from takumi.search.influencer import InfluencerSearch
from takumi.search.influencer.audit.search import AuditSearchMixin

from .audit import AuditParams, InfluencerAuditGraphQLMixin, InfluencerAuditStatsResults
from .information import InfluencerInformationGraphQLMixin, InformationParams

InfluencerSortValues = type(
    "InfluencerSortValues",
    (arguments.Enum,),
    {
        param: param
        for param in [
            "user_created",
            "engagements",
            "followers",
            "participating_campaign_count",
            "followers_history_anomalies",
        ]
        + [
            "audit_" + AuditSearchMixin.AUDIT_FIELD_MAPPINGS.get(k, k)
            for k in InfluencerAuditGraphQLMixin.AUDIT_RANGE_PARAMS.keys()
        ]
    },
)


class FollowersRegion(arguments.InputObjectType):
    region_id = arguments.UUID(required=True)
    min_val = arguments.Float()
    max_val = arguments.Float()


class InfluencerGraphQLSearchFactory(
    InfluencerSearch, InfluencerAuditGraphQLMixin, InfluencerInformationGraphQLMixin
):
    PARAMS: Dict[str, Dict] = {
        "region_id": dict(default=ALL_REGIONS, type=arguments.UUID()),
        "state": dict(type=arguments.List(arguments.String)),
        "eligible": dict(default=False, type=arguments.Boolean()),
        "has_no_offer_in_campaign_id": dict(type=arguments.UUID()),
        "has_interests": dict(default=None, type=arguments.Boolean()),
        "has_facebook_page": dict(default=None, type=arguments.Boolean()),
        "has_tiktok_account": dict(default=None, type=arguments.Boolean()),
        "has_youtube_channel": dict(default=None, type=arguments.Boolean()),
        "search": dict(type=arguments.String()),
        "eligible_for_campaign_id": dict(type=arguments.UUID()),
        "min_followers": dict(type=arguments.Int()),
        "max_followers": dict(type=arguments.Int()),
        "interest_ids": dict(type=arguments.List(arguments.UUID)),
        "gender": dict(type=GenderType()),
        "min_age": dict(type=arguments.Int()),
        "audit": dict(type=AuditParams(), default={}),
        "information": dict(type=InformationParams(), default={}),
        "max_age": dict(type=arguments.Int()),
        "min_engagements": dict(type=arguments.Int()),
        "max_engagements": dict(type=arguments.Int()),
        "min_engagement": dict(type=arguments.Float()),
        "max_engagement": dict(type=arguments.Float()),
        "min_participating_campaign_count": dict(type=arguments.Int()),
        "max_participating_campaign_count": dict(type=arguments.Int()),
        "min_followers_history_anomaly_factor": dict(type=arguments.Float()),
        "max_followers_history_anomaly_factor": dict(type=arguments.Float()),
        "followers_region": dict(type=arguments.List(FollowersRegion)),
    }
    SORT_PARAMS = {
        "sort_by": dict(
            type=InfluencerSortValues(), default=InfluencerSortValues.user_created.value  # type: ignore
        ),
        "sort_order": dict(type=arguments.SortOrder(), default=arguments.SortOrder.desc.value),  # type: ignore
    }
    ARGUMENTS = {k: v["type"] for k, v in PARAMS.items()}
    ARGUMENTS_WITH_SORT = {k: v["type"] for k, v in dict(PARAMS, **SORT_PARAMS).items()}
    DEFAULT_VALUES = {k: v.get("default") for k, v in dict(PARAMS, **SORT_PARAMS).items()}

    def _filter_search(self, gql_params):
        search_param = gql_params["search"]
        if search_param is not None:
            return self.search(search_param)
        return self

    def _filter_eligible(self, gql_params):
        if gql_params["eligible"]:
            return self.filter_eligible()
        return self

    def _filter_campaign_eligibility(self, gql_params):
        eligible_for_campaign_id = gql_params["eligible_for_campaign_id"]
        if eligible_for_campaign_id:
            campaign = (
                filter_campaigns().filter(Campaign.id == eligible_for_campaign_id).one_or_none()
            )
            if campaign is not None:
                return self.filter_campaign_eligibility(campaign)
        return self

    def _filter_has_no_offer_in_campaign_id(self, gql_params):
        campaign_id = gql_params["has_no_offer_in_campaign_id"]
        if campaign_id:
            campaign = filter_campaigns().filter(Campaign.id == campaign_id).one_or_none()
            if campaign is not None:
                return self.filter_doesnt_have_offer_in_campaign(campaign)
        return self

    def _filter_has_interests(self, gql_params):
        has_interests = gql_params["has_interests"]
        if has_interests is True:
            return self.filter_has_interests()
        if has_interests is False:
            return self.filter_has_no_interests()
        return self

    def _filter_state(self, gql_params):
        state = gql_params["state"]
        if state:
            return self.filter("terms", state=state)
        return self

    def _filter_has_facebook_page(self, gql_params):
        has_facebook_page = gql_params["has_facebook_page"]
        if has_facebook_page is True:
            return self.filter_has_facebook_page()
        if has_facebook_page is False:
            return self.filter_has_no_facebook_page()
        return self

    def _filter_has_tiktok_account(self, gql_params):
        has_tiktok_account = gql_params["has_tiktok_account"]
        if has_tiktok_account is True:
            return self.filter_has_tiktok_account()
        if has_tiktok_account is False:
            return self.filter_has_no_tiktok_account()
        return self

    def _filter_has_youtube_channel(self, gql_params):
        has_youtube_channel = gql_params["has_youtube_channel"]
        if has_youtube_channel is True:
            return self.filter_has_youtube_channel()
        if has_youtube_channel is False:
            return self.filter_has_no_youtube_channel()
        return self

    def _filter_gender(self, gql_params):
        gender = gql_params["gender"]
        if gender:
            return self.filter_gender(gender)
        return self

    def _filter_region_id(self, gql_params):
        region_id = gql_params["region_id"]
        if region_id == ALL_SUPPORTED_REGIONS:
            return self.filter_supported_regions()
        elif region_id not in (None, ALL_REGIONS):
            region = Region.query.get(region_id)
            return self.filter_region(region)
        return self

    def _filter_interest_ids(self, gql_params):
        interest_ids = gql_params["interest_ids"]
        if interest_ids:
            return self.filter_interests(interest_ids)
        return self

    def _filter_age(self, gql_params):
        min_age = gql_params["min_age"]
        max_age = gql_params["max_age"]
        if min_age or max_age:
            return self.filter_age(min_age=min_age or 0, max_age=max_age or 100)
        return self

    def _filter_participating_campaign_count(self, gql_params):
        min_campaign_count = gql_params["min_participating_campaign_count"]
        max_campaign_count = gql_params["max_participating_campaign_count"]
        if min_campaign_count or max_campaign_count:
            return self.filter_participating_campaign_count(min_campaign_count, max_campaign_count)
        return self

    def _filter_engagements(self, gql_params):
        return self.filter_estimated_engagements_per_post(
            min_engagements=gql_params["min_engagements"],
            max_engagements=gql_params["max_engagements"],
        )

    def _filter_engagement(self, gql_params):
        return self.filter_engagement(
            min_engagement=gql_params["min_engagement"],
            max_engagement=gql_params["max_engagement"],
        )

    def _filter_followers_history_anomaly_factor(self, gql_params):
        return self.filter_followers_history_anomalies(
            min_val=gql_params["min_followers_history_anomaly_factor"],
            max_val=gql_params["max_followers_history_anomaly_factor"],
        )

    def _filter_followers(self, gql_params):
        min_followers = gql_params["min_followers"]
        max_followers = gql_params["max_followers"]
        if min_followers or max_followers:
            return self.filter_followers(min_followers=min_followers, max_followers=max_followers)
        return self

    def _filter_followers_region(self, gql_params):
        followers_region = gql_params["followers_region"]
        query = self
        if followers_region:
            for filtering in followers_region:
                region_id = filtering.get("region_id")
                min_val = filtering.get("min_val")
                max_val = filtering.get("max_val")
                query = query.filter_follower_percentage_in_region(
                    region_id, min_val=min_val, max_val=max_val
                )
        return query

    def _gql_sort(self, gql_params):
        sort_by = gql_params["sort_by"].replace("__", ".")
        if sort_by.startswith("audit_"):
            return self._sort_audit(gql_params)
        if sort_by == "participating_campaign_count":
            return self.sort_by_participating_campaign_count(
                desc=gql_params["sort_order"] == "desc"
            )
        if sort_by == "followers_history_anomalies":
            return self.sort_by_followers_history_anomalies(desc=gql_params["sort_order"] == "desc")
        return self.sort_by(sort_by, desc=gql_params["sort_order"] == "desc")

    def _add_count_by_aggregation(self, gql_params):
        count_by = gql_params.get("count_by")
        if count_by:
            for field in count_by:
                try:
                    getattr(self, "add_count_by_" + field)()
                except AttributeError:
                    self.add_count_by_aggregation(field)
        return self

    @classmethod
    def from_params(cls, gql_params):
        gql_params = dict(cls.DEFAULT_VALUES, **gql_params)
        return (
            cls()
            ._filter_search(gql_params)
            ._filter_eligible(gql_params)
            ._filter_has_facebook_page(gql_params)
            ._filter_has_tiktok_account(gql_params)
            ._filter_has_youtube_channel(gql_params)
            ._filter_campaign_eligibility(gql_params)
            ._filter_has_no_offer_in_campaign_id(gql_params)
            ._filter_has_interests(gql_params)
            ._filter_state(gql_params)
            ._filter_gender(gql_params)
            ._filter_region_id(gql_params)
            ._filter_interest_ids(gql_params)
            ._filter_participating_campaign_count(gql_params)
            ._filter_age(gql_params)
            ._filter_engagement(gql_params)
            ._filter_engagements(gql_params)
            ._filter_followers(gql_params)
            ._filter_audit(gql_params["audit"])
            ._filter_information(gql_params["information"])
            ._filter_followers_history_anomaly_factor(gql_params)
            ._filter_followers_region(gql_params)
            ._add_count_by_aggregation(gql_params)
            ._gql_sort(gql_params)
        )


class HistogramStats(ObjectType):
    range = fields.Float()
    count = fields.Int()


class InfluencerGraphQLSearch:
    ARGUMENTS = InfluencerGraphQLSearchFactory.ARGUMENTS
    ARGUMENTS_WITH_SORT = InfluencerGraphQLSearchFactory.ARGUMENTS_WITH_SORT

    @classmethod
    def extract_aggs(cls, results):
        aggs = results.aggregations()
        campaign_count_histogram = [
            dict(range=b["key"], count=b["doc_count"])
            for b in aggs["participating_campaign_count_histogram"]["buckets"]
        ]
        return dict(
            count=results.count(),
            campaign_count_histogram=campaign_count_histogram,
            audit=InfluencerGraphQLSearchFactory._extract_audit_aggs(results),
        )

    def __new__(cls, gql_params):
        return InfluencerGraphQLSearchFactory().from_params(gql_params)


class InfluencerStatsResults(ObjectType):
    count = fields.Int()
    audit = fields.Field(InfluencerAuditStatsResults)
    campaign_count_histogram = fields.List(HistogramStats)
