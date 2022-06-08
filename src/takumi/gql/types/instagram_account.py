import statistics
from typing import List, Optional

from graphene import ObjectType

from takumi.gql import fields


class Stat(ObjectType):
    mean = fields.Int()
    median = fields.Int()
    count = fields.Int()

    def resolve_mean(numbers, info):
        if numbers:
            return statistics.mean(numbers)

    def resolve_median(numbers, info):
        if numbers:
            return statistics.median(numbers)

    def resolve_count(numbers, info):
        return len(numbers)


class StatSection(ObjectType):
    image = fields.Field(Stat)
    video = fields.Field(Stat)
    gallery = fields.Field(Stat)
    story = fields.Field(Stat)

    def resolve_image(insights, info):
        return [i["insight"] for i in insights if i["type"] == "IMAGE"]

    def resolve_video(insights, info):
        return [i["insight"] for i in insights if i["type"] == "VIDEO"]

    def resolve_gallery(insights, info):
        return [i["insight"] for i in insights if i["type"] == "CAROUSEL_ALBUM"]

    def resolve_story(insights, info):
        # TODO: Later slice
        return []


def _insight_by_type(medias: List, key: str, sub_key: Optional[str] = None) -> Optional[List]:
    getter = lambda x: x[key][sub_key] if sub_key else x[key]

    data = [
        {"insight": getter(media), "type": media["media_type"]}
        for media in medias
        if "insights" in media
    ]
    if data:
        return data
    return None


class RecentPostsStats(ObjectType):
    impressions = fields.Field(StatSection)
    engagements = fields.Field(StatSection)
    likes = fields.Field(StatSection)
    comments = fields.Field(StatSection)

    def resolve_impressions(medias, info):
        return _insight_by_type(medias, key="insights", sub_key="impressions")

    def resolve_engagements(medias, info):
        return _insight_by_type(medias, key="insights", sub_key="engagement")

    def resolve_likes(medias, info):
        return _insight_by_type(medias, key="like_count")

    def resolve_comments(medias, info):
        return _insight_by_type(medias, key="comments_count")


class FollowersHistory(ObjectType):
    followers = fields.Int()
    prev_followers = fields.Int()
    followers_diff = fields.Int()
    avg_followers_diff = fields.Int()
    perc = fields.Float()
    date = fields.String()
    short_date = fields.String()


class FollowersHistoryAnomaly(ObjectType):
    follower_increase = fields.Int()
    date = fields.String()
    ignore = fields.Boolean()
    anomaly_factor = fields.Float()


class InstagramAccount(ObjectType):
    id = fields.String(description="The ID of the account")
    active = fields.Boolean()
    username = fields.String(source="ig_username", description="The name of the account")
    followers = fields.Int()
    biography = fields.String(source="ig_biography", description="Biography of the account")
    profile_picture = fields.String(description="Profile picture of the account")
    is_private = fields.Boolean(source="ig_is_private")
    media_count = fields.Int()
    estimated_engagements_per_post = fields.Int()
    facebook_page = fields.Field("FacebookPage")
    followers_history_anomalies = fields.ViewInfluencerInfoField(
        fields.List(FollowersHistoryAnomaly)
    )
    is_business_account = fields.ViewInfluencerInfoField(
        fields.Boolean, source="ig_is_business_account"
    )
    is_verified = fields.ViewInfluencerInfoField(fields.Boolean, source="ig_is_verified")
    boosted = fields.ManageInfluencersField(
        fields.Boolean,
        resolver=fields.deep_source_resolver("instagram_account.boosted"),
        description="Whether the account has had follower numbers boosted for demo/development purposes",
    )
    audience_insight = fields.ViewInfluencerInfoField(
        "InstagramAudienceInsight", allow_self=True, source="instagram_audience_insight"
    )
    followers_history = fields.ViewInfluencerInfoField(fields.List(FollowersHistory))
    estimated_impressions = fields.ViewInfluencerInfoField(fields.Int)
    impressions_ratio = fields.ViewInfluencerInfoField("Percent")
    engagement = fields.Field("Percent")
    follows = fields.Int()
    recent_posts_stats = fields.ViewInfluencerInfoField(RecentPostsStats)
    recent_posts_updated = fields.ViewInfluencerInfoField(
        fields.DateTime, source="recent_media_updated"
    )

    def resolve_recent_posts_stats(root, info):
        if isinstance(root, dict):
            return root.get("recent_media")
        if hasattr(root, "recent_media"):
            return root.recent_media
        return None

    def resolve_estimated_impressions(root, info):
        if root.influencer:
            return root.influencer.estimated_impressions
        return None

    def resolve_impressions_ratio(root, info):
        if root.influencer:
            return root.influencer.impressions_ratio
        return None
