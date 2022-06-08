from elasticsearch_dsl import Q


class AuditSearchMixin:

    AUDIT_FIELD_MAPPINGS = {
        "average_likes": "average_likes",
        "average_comments": "average_comments",
        "average_posts_per_week": "average_posts_per_week",
        "average_ad_posts_per_week": "average_ad_posts_per_week",
        "likes_spread": "likes_spread",
        "likes_comments_ratio": "likes_comments_ratio",
        "followers_quality": "followers_quality",
        "followers_reachability": "followers_reachability",
        "followers_count": "followers_count",
        "followings_count": "followings_count",
        "likers_quality": "likers_quality",
        "engagement_rate": "engagement_rate__value",
        "ad_engagement_rate": "ad_engagement_rate__value",
        "audience_quality_score": "audience_quality_score",
    }

    def get_mapping(self, field):
        return "audit__" + self.AUDIT_FIELD_MAPPINGS.get(field, field)

    def filter_audit_field_by_range(self, field, min_val, max_val):
        if min_val is None and max_val is None:
            return self
        range_filter = {}
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val
        return self.filter(
            "nested", path="audit", query=Q("range", **{self.get_mapping(field): range_filter})
        )

    def filter_audit_created(self, max_days_ago):
        return self.filter_audit_field_by_range("created", f"now-{max_days_ago}d/d", None)

    def filter_audit_audience_quality_score(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("audience_quality_score", min_val, max_val)

    def filter_audit_average_likes(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("average_likes", min_val, max_val)

    def filter_audit_average_comments(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("average_comments", min_val, max_val)

    def filter_audit_average_posts_per_week(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("average_posts_per_week", min_val, max_val)

    def filter_audit_average_ad_posts_per_week(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("average_ad_posts_per_week", min_val, max_val)

    def filter_audit_likes_spread(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("likes_spread", min_val, max_val)

    def filter_audit_likes_comments_ratio(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("likes_comments_ratio", min_val, max_val)

    def filter_audit_followers_quality(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("followers_quality", min_val, max_val)

    def filter_audit_followers_reachability(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("followers_reachability", min_val, max_val)

    def filter_audit_followers_count(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("followers_count", min_val, max_val)

    def filter_audit_followings_count(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("followings_count", min_val, max_val)

    def filter_audit_likers_quality(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("likers_quality", min_val, max_val)

    def filter_audit_engagement_rate(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("engagement_rate", min_val, max_val)

    def filter_audit_ad_engagement_rate(self, min_val=None, max_val=None):
        return self.filter_audit_field_by_range("ad_engagement_rate", min_val, max_val)

    def _filter_breakdownfield_by_name(self, path, name, min_val, max_val):
        range_filter = {}
        if min_val is None and max_val is None:
            return self
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        matches_name = Q("term", **{"audit__" + path + "__name": name})
        matches_value = Q("range", **{"audit__" + path + "__value__value": range_filter})

        return self.filter(
            "nested",
            path="audit",
            query=Q("nested", path="audit." + path, query=matches_name & matches_value),
        )

    def filter_audit_followers_reach_real(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name("followers_reach", "real", min_val, max_val)

    def filter_audit_followers_reach_mass_followers(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "followers_reach", "mass_followers", min_val, max_val
        )

    def filter_audit_followers_reach_suspicious_accounts(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "followers_reach", "suspicious_accounts", min_val, max_val
        )

    def filter_audit_followers_reach_influencers(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "followers_reach", "influencers", min_val, max_val
        )

    def filter_audit_followers_demography_male(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name("followers_demography", "male", min_val, max_val)

    def filter_audit_followers_demography_female(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "followers_demography", "female", min_val, max_val
        )

    def filter_audit_likers_reach_real(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name("likers_reach", "real", min_val, max_val)

    def filter_audit_likers_reach_mass_followers(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "likers_reach", "mass_followers", min_val, max_val
        )

    def filter_audit_likers_reach_suspicious_accounts(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name(
            "likers_reach", "suspicious_accounts", min_val, max_val
        )

    def filter_audit_likers_reach_influencers(self, min_val=None, max_val=None):
        return self._filter_breakdownfield_by_name("likers_reach", "influencers", min_val, max_val)

    def filter_audit_audience_thematics(self, name, min_val=None, max_val=None):
        range_filter = {}
        if min_val is None and max_val is None:
            return self
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        matches_name = Q("term", audit__audience_thematics__name=name)
        matches_value = Q("range", audit__audience_thematics__value__value=range_filter)

        return self.filter(
            "nested",
            path="audit",
            query=Q("nested", path="audit.audience_thematics", query=matches_name & matches_value),
        )

    def filter_audit_likers_languages(self, country_code, min_val=None, max_val=None):
        range_filter = {}
        if min_val is None and max_val is None:
            return self
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        matches_name = Q("term", audit__likers_languages__country_code=country_code)
        matches_value = Q("range", audit__likers_languages__value__value=range_filter)

        return self.filter(
            "nested",
            path="audit",
            query=Q("nested", path="audit.likers_languages", query=matches_name & matches_value),
        )

    def filter_audit_followers_languages(self, country_code, min_val=None, max_val=None):
        range_filter = {}
        if min_val is None and max_val is None:
            return self
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        matches_name = Q("term", audit__followers_languages__country_code=country_code)
        matches_value = Q("range", audit__followers_languages__value__value=range_filter)

        return self.filter(
            "nested",
            path="audit",
            query=Q("nested", path="audit.followers_languages", query=matches_name & matches_value),
        )

    def filter_audit_followers_geography(self, name, min_val=None, max_val=None):
        range_filter = {}
        if min_val is None and max_val is None:
            return self
        if min_val:
            range_filter["gte"] = min_val
        if max_val:
            range_filter["lte"] = max_val

        city_matches_name = Q("term", audit__followers_geography__cities__name=name)
        city_matches_value = Q(
            "range", audit__followers_geography__cities__value__value=range_filter
        )

        country_matches_name = Q("term", audit__followers_geography__countries__name=name)
        country_matches_value = Q(
            "range", audit__followers_geography__countries__value__value=range_filter
        )

        state_matches_name = Q("term", audit__followers_geography__states__name=name)
        state_matches_value = Q(
            "range", audit__followers_geography__states__value__value=range_filter
        )

        return self.filter(
            "nested",
            path="audit",
            query=Q(
                "nested",
                path="audit.followers_geography",
                query=(
                    Q(
                        "nested",
                        path="audit.followers_geography.cities",
                        query=city_matches_name & city_matches_value,
                    )
                    | Q(
                        "nested",
                        path="audit.followers_geography.countries",
                        query=country_matches_name & country_matches_value,
                    )
                    | Q(
                        "nested",
                        path="audit.followers_geography.states",
                        query=state_matches_name & state_matches_value,
                    )
                ),
            ),
        )

    def _add_followers_stats_aggregation(
        self, field, group_by_field="name", include_followers=True
    ):
        bucket = self.aggs.bucket("audit_" + field, "nested", path="audit." + field).bucket(
            "group_by_" + field, "terms", field="audit." + field + "." + group_by_field
        )
        bucket.bucket(
            "stats_" + field + "_value", "extended_stats", field="audit." + field + ".value.value"
        )
        bucket.bucket(
            "stats_median_" + field + "_value",
            "percentiles",
            field="audit." + field + ".value.value",
            percents=[50],
        )
        if include_followers:
            bucket.bucket(
                "stats_" + field + "_followers",
                "extended_stats",
                field="audit." + field + ".followers",
            )
            bucket.bucket(
                "stats_median_" + field + "_followers",
                "percentiles",
                field="audit." + field + ".followers",
                percents=[50],
            )

    def _add_followers_geography_aggregation(self):
        for unit in ["countries", "cities", "states"]:
            bucket = self.aggs.bucket(
                "audit_follower_" + unit, "nested", path="audit.followers_geography." + unit
            ).bucket(
                "group_by_follower_" + unit,
                "terms",
                field="audit.followers_geography." + unit + ".name",
            )
            bucket.bucket(
                "stats_follower_" + unit + "_followers",
                "extended_stats",
                field="audit.followers_geography." + unit + ".followers",
            )
            bucket.bucket(
                "stats_follower_" + unit + "_value",
                "extended_stats",
                field="audit.followers_geography." + unit + ".value.value",
            )

            bucket.bucket(
                "stats_median_follower_" + unit + "_followers",
                "percentiles",
                field="audit.followers_geography." + unit + ".followers",
                percents=[50],
            )
            bucket.bucket(
                "stats_median_follower_" + unit + "_value",
                "percentiles",
                field="audit.followers_geography." + unit + ".value.value",
                percents=[50],
            )

    def add_audit_statistics_aggregations(self):
        audit_bucket = self.aggs.bucket("audit", "nested", path="audit")

        audit_bucket.bucket(
            "audience_quality_score_histogram",
            "histogram",
            interval=10,
            field="audit.audience_quality_score",
        )

        for field, field_mapping in self.AUDIT_FIELD_MAPPINGS.items():
            field_mapping = field_mapping.replace("__", ".")
            audit_bucket.bucket(
                "stats_audit_" + field, "extended_stats", field="audit." + field_mapping
            )
            audit_bucket.bucket(
                "stats_audit_median_" + field,
                "percentiles",
                field="audit." + field_mapping,
                percents=[50],
            )

        self._add_followers_geography_aggregation()

        self._add_followers_stats_aggregation("followers_reach")
        self._add_followers_stats_aggregation("followers_languages", group_by_field="country_code")
        self._add_followers_stats_aggregation("followers_demography")
        self._add_followers_stats_aggregation("audience_thematics")
        self._add_followers_stats_aggregation(
            "likers_languages", group_by_field="country_code", include_followers=False
        )
        self._add_followers_stats_aggregation("likers_reach", include_followers=False)

    def _sort_by_breakdownfield_by_name(self, field, value, desc=False):
        return self.sort(
            {
                "audit."
                + field
                + ".value.value": dict(
                    order="desc" if desc else "asc",
                    nested_path="audit." + field,
                    nested_filter=Q("term", **{"audit__" + field + "__name": value}).to_dict(),
                )
            }
        )

    def sort_by_audit_followers_demography_male(self, desc=False):
        return self._sort_by_breakdownfield_by_name("followers_demography", "male", desc=desc)

    def sort_by_audit_followers_demography_female(self, desc=False):
        return self._sort_by_breakdownfield_by_name("followers_demography", "female", desc=desc)

    def sort_by_audit_followers_reach_real(self, desc=False):
        return self._sort_by_breakdownfield_by_name("followers_reach", "real", desc=desc)

    def sort_by_audit_followers_reach_mass_followers(self, desc=False):
        return self._sort_by_breakdownfield_by_name("followers_reach", "mass_followers", desc=desc)

    def sort_by_audit_followers_reach_suspicious_accounts(self, desc=False):
        return self._sort_by_breakdownfield_by_name(
            "followers_reach", "suspicious_accounts", desc=desc
        )

    def sort_by_audit_followers_reach_influencers(self, desc=False):
        return self._sort_by_breakdownfield_by_name("followers_reach", "influencers", desc=desc)

    def sort_by_audit_likers_reach_real(self, desc=False):
        return self._sort_by_breakdownfield_by_name("likers_reach", "real", desc=desc)

    def sort_by_audit_likers_reach_mass_followers(self, desc=False):
        return self._sort_by_breakdownfield_by_name("likers_reach", "mass_followers", desc=desc)

    def sort_by_audit_likers_reach_suspicious_accounts(self, desc=False):
        return self._sort_by_breakdownfield_by_name(
            "likers_reach", "suspicious_accounts", desc=desc
        )

    def sort_by_audit_likers_reach_influencers(self, desc=False):
        return self._sort_by_breakdownfield_by_name("likers_reach", "influencers", desc=desc)
