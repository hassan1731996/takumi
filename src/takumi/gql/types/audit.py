from graphene import ObjectType

from takumi.gql import fields


class Language(ObjectType):
    country_code = fields.String(description="The country code in ISO 639-1: Two letters")
    value = fields.Field("Percent", description="How many users speak the language")
    followers = fields.Int(description="The total amount of followers that speak the language")


class Thematic(ObjectType):
    name = fields.String(description="Interest name")
    value = fields.Field("Percent", description="How many users share this interest")
    followers = fields.Int(description="The total amount of followers that share this interest")


class UserBreakdown(ObjectType):
    name = fields.String(description="User type")
    value = fields.Field("Percent", description="How many users are of this type")
    followers = fields.Int(description="The total number of users in this type")


class GeographyItem(ObjectType):
    name = fields.String(description="Location name")
    value = fields.Field("Percent", description="How many users are in the location")
    followers = fields.Int(description="The total amount of followers that speak the language")


def _percentage_to_float(percentage):
    if isinstance(percentage, dict):
        return percentage["value"]
    return percentage


class Geography(ObjectType):
    cities = fields.SortedList(
        GeographyItem,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="Breakdown of followers by cities",
    )
    countries = fields.SortedList(
        GeographyItem,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="Breakdown of followers by countries",
    )
    states = fields.SortedList(
        GeographyItem,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="Breakdown of followers by US states",
    )


class Demography(ObjectType):
    name = fields.String(description="Demography name")
    value = fields.Field("Percent", description="How many users are of this demography")
    followers = fields.Int(description="The total amount of followers of this demography")


class Audit(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()
    pdf = fields.String()

    audience_quality_score = fields.Float(
        description=(
            "AQS is a 1 to 100 metric which combines followers quality (not number), "
            "engagement rate and it's authenticity into one metric"
        )
    )

    # Engagement rates
    engagement_rate = fields.Field(
        "Percent",
        description=(
            "Percent of the audience who like or comment on all "
            "the posts (engage with the content)"
        ),
    )
    ad_engagement_rate = fields.Field(
        "Percent",
        description=(
            "Percent of the audience who like or comment on "
            "only the ad posts (engage with the content)"
        ),
    )

    # User
    average_likes = fields.Float(description="Average number of likes per post")
    average_comments = fields.Float(description="Average number of comments per post")
    average_posts_per_week = fields.Float(
        description="Average number of posts per week, including ad posts"
    )
    average_ad_posts_per_week = fields.Float(description="Average number of ad posts per week")

    likes_spread = fields.Float()  # TODO: Unsure what this number means..
    likes_comments_ratio = fields.Float(
        description=(
            "Likes-Comments Ratio shows if the blogger gets more likes or more comments. "
            "Significant difference from similar accounts might mean that either comments "
            "or likes number was increased artificially. The number is how many likes per comment"
        )
    )

    # Followers
    followers_languages = fields.SortedList(
        Language,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="Breakdown of the languages the followers speak",
    )
    followers_quality = fields.Float(
        description=(
            "Followers who don't look suspicious are considered quality. "
            "This is the sum of real and influencers in followers reach"
        )
    )
    followers_reach = fields.List(UserBreakdown, description="Breakdown of followers by type")
    followers_reachability = fields.Float(
        description=(
            "Followers who follow less than 1,500 accounts are considered "
            "reachable. They probably see most of the influencer's posts"
        )
    )
    followers_geography = fields.Field(
        Geography, description="Breakdown of followers by different regions"
    )
    followers_demography = fields.List(Demography, description="Breakdown of followers by gender")

    # Likers
    likers_languages = fields.SortedList(
        Language,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="Breakdown of the languages the likers speak",
    )
    likers_quality = fields.Float(
        description=(
            "Likers who don't look suspicious are considered quality. "
            "This is the sum of real and influencers in likers reach"
        )
    )
    likers_reach = fields.List(UserBreakdown, description="Breakdown of likers by type")

    # Other
    audience_thematics = fields.SortedList(
        Thematic,
        key=lambda x: _percentage_to_float(x["value"]),
        reverse=True,
        description="The audience interests",
    )
    followers_count = fields.Int(
        description="The amount of followers the user has at the time of the audit"
    )
    followings_count = fields.Int(
        description="The amount of users the user followers at the time of the audit"
    )

    def resolve_id(root, info):
        # Cause ES gives us a unicode instance
        return str(root.id)
