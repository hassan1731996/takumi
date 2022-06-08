AUDIT_MAPPING = {
    "type": "nested",
    "properties": {
        "id": {"type": "keyword"},
        "created": {"type": "date", "format": "date_time"},
        "modified": {"type": "date", "format": "date_time"},
        "audience_quality_score": {"type": "float"},
        "average_likes": {"type": "float"},
        "average_comments": {"type": "float"},
        "average_posts_per_week": {"type": "float"},
        "average_ad_posts_per_week": {"type": "float"},
        "likes_spread": {"type": "float"},
        "likes_comments_ratio": {"type": "float"},
        "followers_quality": {"type": "float"},
        "followers_reachability": {"type": "float"},
        "followers_count": {"type": "integer"},
        "followings_count": {"type": "integer"},
        "likers_quality": {"type": "float"},
        "engagement_rate.value": {"type": "float"},
        "ad_engagement_rate.value": {"type": "float"},
        "likers_reach": {
            "type": "nested",
            "properties": {
                "name": {"type": "keyword"},
                "followers": {"type": "integer"},
                "value.value": {"type": "float"},
            },
        },
        "followers_demography": {
            "type": "nested",
            "properties": {
                "name": {"type": "keyword"},
                "followers": {"type": "integer"},
                "value.value": {"type": "float"},
            },
        },
        "followers_reach": {
            "type": "nested",
            "properties": {
                "name": {"type": "keyword"},
                "followers": {"type": "integer"},
                "value.value": {"type": "float"},
            },
        },
        "audience_thematics": {
            "type": "nested",
            "properties": {"name": {"type": "keyword"}, "value.value": {"type": "float"}},
        },
        "followers_languages": {
            "type": "nested",
            "properties": {
                "country_code": {"type": "keyword"},
                "followers": {"type": "integer"},
                "value.value": {"type": "float"},
            },
        },
        "likers_languages": {
            "type": "nested",
            "properties": {
                "country_code": {"type": "keyword"},
                "followers": {"type": "integer"},
                "value.value": {"type": "float"},
            },
        },
        "followers_geography": {
            "type": "nested",
            "properties": {
                "cities": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "followers": {"type": "integer"},
                        "value.value": {"type": "float"},
                    },
                },
                "countries": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "followers": {"type": "integer"},
                        "value.value": {"type": "float"},
                    },
                },
                "states": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "followers": {"type": "integer"},
                        "value.value": {"type": "float"},
                    },
                },
            },
        },
    },
}
