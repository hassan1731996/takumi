from collections import Counter

from graphene import ObjectType
from sqlalchemy import func

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.models.instagram_audience_insight import RegionInsightValue as RegionInsightValueModel
from takumi.utils import uuid4_str


class RegionInsightValue(ObjectType):
    id = fields.UUID()
    follower_count = fields.Int()
    follower_percentage = fields.Field("Percent")
    region = fields.Field("Region")


class GenderAgeInsightsValue(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    gender = fields.String()
    follower_count = fields.Int()
    age_from = fields.Int()
    age_to = fields.Int()
    follower_percentage = fields.Field("Percent")


class SplitValue(ObjectType):
    id = fields.UUID()
    name = fields.String()
    follower_count = fields.Int()
    follower_percentage = fields.Field("Percent")


class InstagramAudienceInsight(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    region_insights = fields.List(RegionInsightValue, max_results=arguments.Int(default_value=-1))
    total_region_followers = fields.Int()
    gender_age_insights = fields.List(GenderAgeInsightsValue)
    gender_split = fields.List(SplitValue)
    age_split = fields.List(SplitValue)

    def resolve_region_insights(insight, info, max_results):
        query = RegionInsightValueModel.query.filter(
            RegionInsightValueModel.instagram_audience_insight == insight
        ).order_by(RegionInsightValueModel.follower_count.desc())

        if max_results > 0:
            return query.limit(max_results)

        return query

    def resolve_total_region_followers(insight, info):
        return (
            db.session.query(func.sum(RegionInsightValueModel.follower_count)).filter(
                RegionInsightValueModel.instagram_audience_insight == insight
            )
        ).scalar()

    def resolve_gender_split(insight, info):
        counter = Counter({"female": 0, "male": 0, "unknown": 0})
        for ins in insight.gender_age_insights:
            counter.update({ins.gender: ins.follower_count})
        total = sum(counter.values())
        return [
            {
                "id": uuid4_str(),
                "name": key.title(),
                "follower_count": value,
                "follower_percentage": value / total if total > 0 else 0,
            }
            for key, value in counter.items()
        ]

    def resolve_age_split(insight, info):
        counter = Counter(
            {"13-17": 0, "18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55-64": 0, "65+": 0}
        )
        for ins in insight.gender_age_insights:
            if not ins.age_to:
                key = f"{ins.age_from}+"
            else:
                key = f"{ins.age_from}-{ins.age_to}"
            counter.update({key: ins.follower_count})
        total = sum(counter.values())
        return [
            {
                "id": uuid4_str(),
                "name": key,
                "follower_count": value,
                "follower_percentage": value / total if total > 0 else 0,
            }
            for key, value in counter.items()
        ]
