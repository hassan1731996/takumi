from graphene import ObjectType

from takumi.gql import arguments, fields


class AudienceThematics(arguments.InputObjectType):
    name = arguments.String(required=True)
    min_val = arguments.Float()
    max_val = arguments.Float()


class LikersLanguages(arguments.InputObjectType):
    country_code = arguments.String(required=True)
    min_val = arguments.Float()
    max_val = arguments.Float()


class FollowersLanguages(LikersLanguages):
    pass


class FollowersGeography(arguments.InputObjectType):
    name = arguments.String(required=True)
    min_val = arguments.Float()
    max_val = arguments.Float()


class InfluencerAuditGraphQLMixin:
    AUDIT_RANGE_PARAMS = {
        "audience_quality_score": dict(type=arguments.Float()),
        "average_likes": dict(type=arguments.Float()),
        "average_comments": dict(type=arguments.Float()),
        "average_posts_per_week": dict(type=arguments.Float()),
        "average_ad_posts_per_week": dict(type=arguments.Float()),
        "likes_spread": dict(type=arguments.Float()),
        "likes_comments_ratio": dict(type=arguments.Float()),
        "followers_quality": dict(type=arguments.Float()),
        "followers_reachability": dict(type=arguments.Float()),
        "followers_count": dict(type=arguments.Float()),
        "followings_count": dict(type=arguments.Float()),
        "likers_quality": dict(type=arguments.Float()),
        "engagement_rate": dict(type=arguments.Float()),
        "ad_engagement_rate": dict(type=arguments.Float()),
        "followers_reach_real": dict(type=arguments.Float()),
        "followers_reach_mass_followers": dict(type=arguments.Float()),
        "followers_reach_suspicious_accounts": dict(type=arguments.Float()),
        "followers_reach_influencers": dict(type=arguments.Float()),
        "followers_demography_male": dict(type=arguments.Float()),
        "followers_demography_female": dict(type=arguments.Float()),
        "likers_reach_real": dict(type=arguments.Float()),
        "likers_reach_mass_followers": dict(type=arguments.Float()),
        "likers_reach_suspicious_accounts": dict(type=arguments.Float()),
        "likers_reach_influencers": dict(type=arguments.Float()),
    }
    AUDIT_NESTED_PARAMS = {
        "max_age": dict(type=arguments.Int()),
        "audience_thematics": dict(type=arguments.List(AudienceThematics)),
        "likers_languages": dict(type=arguments.List(LikersLanguages)),
        "followers_languages": dict(type=arguments.List(FollowersLanguages)),
        "followers_geography": dict(type=arguments.List(FollowersGeography)),
    }
    MIN_AUDIT_PARAMS = {"min_" + k: v for k, v in AUDIT_RANGE_PARAMS.items()}
    MAX_AUDIT_PARAMS = {"max_" + k: v for k, v in AUDIT_RANGE_PARAMS.items()}

    AUDIT_PARAMS = dict(dict(MAX_AUDIT_PARAMS, **MIN_AUDIT_PARAMS), **AUDIT_NESTED_PARAMS)

    AUDIT_RANGE_RESULTS = [
        param
        for param in AUDIT_RANGE_PARAMS
        if not any(
            [
                param.startswith(v)
                for v in [
                    "followers_geography_",
                    "followers_demography_",
                    "followers_reach_",
                    "likers_reach_",
                ]
            ]
        )
    ]

    def _filter_audit_age(self, gql_params):
        max_age = gql_params.get("max_age")
        if max_age is not None:
            return self.filter_audit_created(max_age)
        return self

    def _filter_audience_quality_score(self, gql_params):
        return self.filter_audit_audience_quality_score(
            gql_params["min_audience_quality_score"], gql_params["max_audience_quality_score"]
        )

    def _filter_average_likes(self, gql_params):
        return self.filter_audit_average_likes(
            gql_params["min_average_likes"], gql_params["max_average_likes"]
        )

    def _filter_average_comments(self, gql_params):
        return self.filter_audit_average_comments(
            gql_params["min_average_comments"], gql_params["max_average_comments"]
        )

    def _filter_average_posts_per_week(self, gql_params):
        return self.filter_audit_average_posts_per_week(
            gql_params["min_average_posts_per_week"], gql_params["max_average_posts_per_week"]
        )

    def _filter_average_ad_posts_per_week(self, gql_params):
        return self.filter_audit_average_ad_posts_per_week(
            gql_params["min_average_ad_posts_per_week"], gql_params["max_average_ad_posts_per_week"]
        )

    def _filter_likes_spread(self, gql_params):
        return self.filter_audit_likes_spread(
            gql_params["min_likes_spread"], gql_params["max_likes_spread"]
        )

    def _filter_likes_comments_ratio(self, gql_params):
        return self.filter_audit_likes_comments_ratio(
            gql_params["min_likes_spread"], gql_params["max_likes_spread"]
        )

    def _filter_followers_quality(self, gql_params):
        return self.filter_audit_followers_quality(
            gql_params["min_followers_quality"], gql_params["max_followers_quality"]
        )

    def _filter_followers_reachability(self, gql_params):
        return self.filter_audit_followers_reachability(
            gql_params["min_followers_reachability"], gql_params["max_followers_reachability"]
        )

    def _filter_followers_count(self, gql_params):
        return self.filter_audit_followers_count(
            gql_params["min_followers_count"], gql_params["max_followers_count"]
        )

    def _filter_followings_count(self, gql_params):
        return self.filter_audit_followings_count(
            gql_params["min_followings_count"], gql_params["max_followings_count"]
        )

    def _filter_likers_quality(self, gql_params):
        return self.filter_audit_likers_quality(
            gql_params["min_likers_quality"], gql_params["max_likers_quality"]
        )

    def _filter_engagement_rate(self, gql_params):
        return self.filter_audit_engagement_rate(
            gql_params["min_engagement_rate"], gql_params["max_engagement_rate"]
        )

    def _filter_ad_engagement_rate(self, gql_params):
        return self.filter_audit_ad_engagement_rate(
            gql_params["min_ad_engagement_rate"], gql_params["max_ad_engagement_rate"]
        )

    def _filter_followers_reach_real(self, gql_params):
        return self.filter_audit_followers_reach_real(
            gql_params["min_followers_reach_real"], gql_params["max_followers_reach_real"]
        )

    def _filter_followers_reach_mass_followers(self, gql_params):
        return self.filter_audit_followers_reach_mass_followers(
            gql_params["min_followers_reach_mass_followers"],
            gql_params["max_followers_reach_mass_followers"],
        )

    def _filter_followers_reach_suspicious_accounts(self, gql_params):
        return self.filter_audit_followers_reach_suspicious_accounts(
            gql_params["min_followers_reach_suspicious_accounts"],
            gql_params["max_followers_reach_suspicious_accounts"],
        )

    def _filter_followers_reach_influencers(self, gql_params):
        return self.filter_audit_followers_reach_influencers(
            gql_params["min_followers_reach_influencers"],
            gql_params["max_followers_reach_influencers"],
        )

    def _filter_followers_demography_male(self, gql_params):
        return self.filter_audit_followers_demography_male(
            gql_params["min_followers_demography_male"], gql_params["max_followers_demography_male"]
        )

    def _filter_followers_demography_female(self, gql_params):
        return self.filter_audit_followers_demography_female(
            gql_params["min_followers_demography_female"],
            gql_params["max_followers_demography_female"],
        )

    def _filter_likers_reach_real(self, gql_params):
        return self.filter_audit_likers_reach_real(
            gql_params["min_likers_reach_real"], gql_params["max_likers_reach_real"]
        )

    def _filter_likers_reach_mass_followers(self, gql_params):
        return self.filter_audit_likers_reach_mass_followers(
            gql_params["min_likers_reach_mass_followers"],
            gql_params["max_likers_reach_mass_followers"],
        )

    def _filter_likers_reach_suspicious_accounts(self, gql_params):
        return self.filter_audit_likers_reach_suspicious_accounts(
            gql_params["min_likers_reach_suspicious_accounts"],
            gql_params["max_likers_reach_suspicious_accounts"],
        )

    def _filter_likers_reach_influencers(self, gql_params):
        return self.filter_audit_likers_reach_influencers(
            gql_params["min_likers_reach_influencers"], gql_params["max_likers_reach_influencers"]
        )

    def _filter_audience_schematics(self, gql_params):
        audience_thematics = gql_params["audience_thematics"]
        query = self
        if audience_thematics:
            for filtering in audience_thematics:
                name = filtering.get("name")
                min_val = filtering.get("min_val")
                max_val = filtering.get("max_val")
                query = query.filter_audit_audience_thematics(name, min_val, max_val)
        return query

    def _filter_audience_likers_languages(self, gql_params):
        likers_languages = gql_params["likers_languages"]
        query = self
        if likers_languages:
            for filtering in likers_languages:
                country_code = filtering.get("country_code")
                min_val = filtering.get("min_val")
                max_val = filtering.get("max_val")
                query = query.filter_audit_likers_languages(country_code, min_val, max_val)
        return query

    def _filter_audience_followers_languages(self, gql_params):
        followers_languages = gql_params["followers_languages"]
        query = self
        if followers_languages:
            for filtering in followers_languages:
                country_code = filtering.get("country_code")
                min_val = filtering.get("min_val")
                max_val = filtering.get("max_val")
                query = query.filter_audit_followers_languages(country_code, min_val, max_val)
        return query

    def _filter_audience_followers_geography(self, gql_params):
        followers_geography = gql_params["followers_geography"]
        query = self
        if followers_geography:
            for filtering in followers_geography:
                name = filtering.get("name")
                min_val = filtering.get("min_val")
                max_val = filtering.get("max_val")
                query = query.filter_audit_followers_geography(name, min_val, max_val)
        return query

    def _filter_audit(self, gql_params):
        default_values = {k: v.get("default") for k, v in self.AUDIT_PARAMS.items()}
        gql_params = dict(default_values, **gql_params)
        return (
            self._filter_audience_quality_score(gql_params)
            ._filter_average_likes(gql_params)
            ._filter_average_comments(gql_params)
            ._filter_average_posts_per_week(gql_params)
            ._filter_average_ad_posts_per_week(gql_params)
            ._filter_likes_spread(gql_params)
            ._filter_likes_comments_ratio(gql_params)
            ._filter_followers_quality(gql_params)
            ._filter_followers_reachability(gql_params)
            ._filter_followers_count(gql_params)
            ._filter_followings_count(gql_params)
            ._filter_likers_quality(gql_params)
            ._filter_engagement_rate(gql_params)
            ._filter_ad_engagement_rate(gql_params)
            ._filter_followers_reach_real(gql_params)
            ._filter_followers_reach_mass_followers(gql_params)
            ._filter_followers_reach_suspicious_accounts(gql_params)
            ._filter_followers_reach_influencers(gql_params)
            ._filter_followers_demography_male(gql_params)
            ._filter_followers_demography_female(gql_params)
            ._filter_likers_reach_real(gql_params)
            ._filter_likers_reach_mass_followers(gql_params)
            ._filter_likers_reach_suspicious_accounts(gql_params)
            ._filter_likers_reach_influencers(gql_params)
            ._filter_audience_schematics(gql_params)
            ._filter_audience_likers_languages(gql_params)
            ._filter_audience_followers_languages(gql_params)
            ._filter_audience_followers_geography(gql_params)
            ._filter_audit_age(gql_params)
        )

    def _sort_audit(self, gql_params):
        sort_by = gql_params["sort_by"].replace("__", ".")
        desc = gql_params["sort_order"] == "desc"

        def default_sorting(desc):
            return self.sort_by(
                sort_by.replace("audit_", "audit.", 1), desc=desc, nested_path="audit"
            )

        try:
            sorting_function = getattr(self, "sort_by_" + sort_by)
        except AttributeError:
            sorting_function = default_sorting

        return sorting_function(desc)

    @classmethod
    def _transform_agg_results(self, results, field):
        aggregations = results.aggregations()
        return [
            dict(
                name=c["key"],
                followers=dict(
                    c.get("stats_" + field + "_followers", {}),
                    median=(
                        c.get("stats_median_" + field + "_followers", {})
                        .get("values", {})
                        .get("50.0")
                    ),
                ),
                value=dict(
                    c["stats_" + field + "_value"],
                    median=c["stats_median_" + field + "_value"]["values"]["50.0"],
                ),
            )
            for c in aggregations["audit_" + field]["group_by_" + field]["buckets"]
        ]

    @classmethod
    def _extract_audit_aggs(cls, results):
        aggregations = results.aggregations()
        audit_results = aggregations["audit"]

        grouped_follower_results = {
            field: cls._transform_agg_results(results, field)
            for field in [
                "followers_languages",
                "likers_languages",
                "followers_reach",
                "likers_reach",
                "followers_demography",
                "audience_thematics",
            ]
        }

        grouped_follower_results["followers_geography"] = {
            unit: cls._transform_agg_results(results, "follower_" + unit)
            for unit in ["countries", "cities", "states"]
        }

        range_values = {
            field: dict(
                audit_results["stats_audit_" + field],
                median=audit_results["stats_audit_median_" + field]["values"]["50.0"],
            )
            for field in cls.AUDIT_RANGE_RESULTS
        }

        range_values["audience_quality_score_histogram"] = [
            dict(range=b["key"], count=b["doc_count"])
            for b in aggregations["audit"]["audience_quality_score_histogram"]["buckets"]
        ]

        return dict(range_values, **grouped_follower_results)


class AuditParams(arguments.InputObjectType):
    for k, v in InfluencerAuditGraphQLMixin.AUDIT_PARAMS.items():
        locals()[k] = v["type"]


class ElasticSearchExtendedStatsStdBounds(ObjectType):
    upper = fields.Float()
    lower = fields.Float()


class ElasticSearchExtendedStats(ObjectType):
    count = fields.Int()
    min = fields.Float()
    max = fields.Float()
    avg = fields.Float()
    sum = fields.Float()
    sum_of_squares = fields.Float()
    variance = fields.Float()
    std_deviation = fields.Float()
    std_deviation_bounds = fields.Field(ElasticSearchExtendedStatsStdBounds)
    upper = fields.Float()
    lower = fields.Float()
    median = fields.Float()


class HistogramAuditStats(ObjectType):
    range = fields.Float()
    count = fields.Int()


class AuditListUnit(ObjectType):
    name = fields.String()
    value = fields.Field(ElasticSearchExtendedStats)


class AuditListUnitWithFollowers(AuditListUnit):
    followers = fields.Field(ElasticSearchExtendedStats)


class AuditFollowersGeography(ObjectType):
    countries = fields.List(AuditListUnitWithFollowers)
    cities = fields.List(AuditListUnitWithFollowers)
    states = fields.List(AuditListUnitWithFollowers)


class InfluencerAuditStatsResults(ObjectType):
    for field in InfluencerAuditGraphQLMixin.AUDIT_RANGE_RESULTS:
        locals()[field] = fields.Field(ElasticSearchExtendedStats)
    followers_geography = fields.Field(AuditFollowersGeography)
    followers_languages = fields.List(AuditListUnitWithFollowers)
    likers_languages = fields.List(AuditListUnit)
    likers_reach = fields.List(AuditListUnit)
    followers_reach = fields.List(AuditListUnitWithFollowers)
    followers_demography = fields.List(AuditListUnitWithFollowers)
    audience_thematics = fields.List(AuditListUnitWithFollowers)
    audience_quality_score_histogram = fields.List(HistogramAuditStats)
