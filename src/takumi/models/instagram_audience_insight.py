from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString, deprecated_column

from takumi.extensions import db
from takumi.utils import uuid4_str

from .region import Region

if TYPE_CHECKING:
    from takumi.models import Influencer, InstagramAccount  # noqa


class GENDER_TYPES:
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"

    @staticmethod
    def values():
        return [GENDER_TYPES.MALE, GENDER_TYPES.FEMALE, GENDER_TYPES.UNKNOWN]


class InstagramAudienceInsight(db.Model):
    __tablename__ = "instagram_audience_insight"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=True)
    modified = db.Column(UtcDateTime, onupdate=func.now())

    influencer_id = deprecated_column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"), nullable=True
    )

    instagram_account_id = db.Column(
        UUIDString, db.ForeignKey("instagram_account.id", ondelete="restrict")
    )
    instagram_account = relationship("InstagramAccount")

    city_followers = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    locale_followers = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    raw_value = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    def __repr__(self):
        return f"<InstagramAudienceInsight: {self.id})>"

    @staticmethod  # noqa
    def from_raw_value(raw_value):

        instagram_audience_insight = InstagramAudienceInsight()
        instagram_audience_insight.raw_value = raw_value

        instagram_audience_insight.city_followers = raw_value.get("audience_city")
        instagram_audience_insight.locale_followers = raw_value.get("audience_locale")

        territories = raw_value.get("audience_country", {}).keys()
        regions = Region.get_by_territory_list(territories)

        for key, follower_count in raw_value.get("audience_country", {}).items():
            try:
                country = next(
                    region for region in regions if region.locale_code.endswith(f"_{key}")
                )
            except StopIteration:
                from takumi import slack

                slack.notify_debug(
                    f"Unable to find the {key} territory", username="Audience insights"
                )
                continue
            instagram_audience_insight.region_insights.append(
                RegionInsightValue(region=country, follower_count=follower_count)
            )

        for key, follower_count in raw_value.get("audience_gender_age", {}).items():
            gender_raw_val = key[0]
            age_range_raw_val = key[2:]

            age_to = None

            if "+" in age_range_raw_val:
                age_from = age_range_raw_val.split("+")[0]
            else:
                age_from, age_to = age_range_raw_val.split("-")

            gender = GENDER_TYPES.UNKNOWN

            if gender_raw_val == "M":
                gender = GENDER_TYPES.MALE
            elif gender_raw_val == "F":
                gender = GENDER_TYPES.FEMALE

            instagram_audience_insight.gender_age_insights.append(
                GenderAgeInsightsValue(
                    age_from=age_from, age_to=age_to, gender=gender, follower_count=follower_count
                )
            )

        return instagram_audience_insight


class GenderAgeInsightsValue(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)

    age_from = db.Column(db.Integer, nullable=False)
    age_to = db.Column(db.Integer, nullable=True)

    gender = db.Column(SoftEnum(*GENDER_TYPES.values()), nullable=False)

    follower_count = db.Column(db.Integer, nullable=False)

    instagram_audience_insight_id = db.Column(
        UUIDString, db.ForeignKey(InstagramAudienceInsight.id, ondelete="restrict"), nullable=False
    )
    instagram_audience_insight = relationship(
        "InstagramAudienceInsight",
        backref=backref(
            "gender_age_insights",
            uselist=True,
            order_by="func.concat(GenderAgeInsightsValue.gender, '-', GenderAgeInsightsValue.age_from)",
        ),
    )

    @property
    def follower_percentage(self):
        total_followers_gender = sum(
            [i.follower_count for i in self.instagram_audience_insight.gender_age_insights]
        )
        return self.follower_count / total_followers_gender

    def __repr__(self):
        return "<GenderAgeInsightsValue: ({}, {}-{}, {}))>".format(
            self.gender, self.age_from, self.age_to, self.follower_count
        )


class RegionInsightValue(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    follower_count = db.Column(db.Integer, nullable=False)

    region_id = db.Column(UUIDString, db.ForeignKey(Region.id), nullable=False, index=True)
    region = relationship(Region)

    instagram_audience_insight_id = db.Column(
        UUIDString,
        db.ForeignKey(InstagramAudienceInsight.id, ondelete="restrict"),
        nullable=False,
        index=True,
    )
    instagram_audience_insight = relationship(
        "InstagramAudienceInsight",
        backref=backref(
            "region_insights",
            uselist=True,
            order_by="desc(RegionInsightValue.follower_count)",
        ),
    )

    @property
    def follower_percentage(self):
        total_followers_region = sum(
            [i.follower_count for i in self.instagram_audience_insight.region_insights]
        )
        return self.follower_count / total_followers_region

    def __repr__(self):
        return f"<RegionInsightValue: ({self.region.name}, {self.follower_count}))>"
