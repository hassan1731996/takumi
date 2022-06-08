from typing import TYPE_CHECKING

from flask import current_app
from sqlalchemy import and_, case, cast, func, or_
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, array
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString

from takumi.constants import MIN_INSTAGRAM_FOLLOWERS_REACH
from takumi.extensions import db
from takumi.models.influencer_information import EyeColour, HairColour, HairType, Tag
from takumi.models.many_to_many import targeting_region_table
from takumi.utils import uuid4_str

from .helpers import hybrid_method_expression, hybrid_method_subquery, hybrid_property_expression

if TYPE_CHECKING:
    from takumi.models import Campaign, ChildrenTargeting, Region, User  # noqa


def get_influencer_information_attr(influencer, attr):
    if not influencer.information:
        return None
    return getattr(influencer.information, attr)


def get_influencer_targeting_filters(targeting, influencer):
    filters = {
        "Regions": targeting.targets_region(influencer.target_region),
        "Interests": targeting.targets_any_of_interests(influencer.interests),
        "Age": targeting.targets_age(influencer.user.age),
        "Gender": targeting.targets_gender(influencer.user.gender),
        "Maximum followers": targeting.targets_max_followers(influencer.followers),
        "Minimum followers": targeting.targets_min_followers(influencer.followers),
        "Glasses": targeting.targets_glasses(
            get_influencer_information_attr(influencer, "glasses")
        ),
        "Hair Type": targeting.targets_hair_type(
            get_influencer_information_attr(influencer, "hair_type")
        ),
        "Hair Colour": targeting.targets_hair_colour(
            get_influencer_information_attr(influencer, "hair_colour")
        ),
        "Eye Colour": targeting.targets_eye_colour(
            get_influencer_information_attr(influencer, "eye_colour")
        ),
        "Languages": targeting.targets_any_of_languages(
            get_influencer_information_attr(influencer, "languages")
        ),
        "Self Tags": targeting.targets_self_tags(
            get_influencer_information_attr(influencer, "tags")
        ),
        "Children": targeting.targets_children(
            get_influencer_information_attr(influencer, "children")
        ),
    }
    if targeting.verified_only:
        filters["Is verified"] = targeting.targets_is_verified(influencer.state)

    return filters


class Targeting(db.Model):
    """A database entry representing the campaign's targeting, a 1:1 map to a campaign"""

    __tablename__ = "targeting"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="cascade"), nullable=False, unique=True
    )
    campaign = relationship("Campaign", back_populates="targeting")
    reward_model = association_proxy("campaign", "reward_model")

    regions = relationship("Region", secondary="targeting_region")

    interest_ids = db.Column(MutableList.as_mutable(ARRAY(UUIDString)))

    ages = db.Column(MutableList.as_mutable(ARRAY(db.Integer)))

    gender = db.Column(db.Enum("female", "male", name="gender"))

    max_followers = db.Column(db.Integer)
    min_followers = db.Column(db.Integer)

    verified_only = db.Column(db.Boolean, server_default="f")

    hair_type_ids = db.Column(MutableList.as_mutable(ARRAY(UUIDString)))
    hair_colour_categories = db.Column(MutableList.as_mutable(ARRAY(db.String)))
    eye_colour_ids = db.Column(MutableList.as_mutable(ARRAY(UUIDString)))

    has_glasses = db.Column(db.Boolean, nullable=True)

    languages = db.Column(MutableList.as_mutable(ARRAY(db.String)))

    self_tag_ids = db.Column(MutableList.as_mutable(ARRAY(UUIDString)))

    children_targeting_id = db.Column(UUIDString, db.ForeignKey("children_targeting.id"))
    children_targeting = relationship("ChildrenTargeting", lazy="joined")

    def __repr__(self):
        return f"<Targeting: {self.id}>"

    @property
    def interests(self):
        if self.interest_ids:
            return [{"id": id} for id in self.interest_ids]

    @property
    def self_tags(self):
        return Tag.get_from_ids(self.self_tag_ids or [])

    @property
    def hair_types(self):
        hair_type_ids = self.hair_type_ids or []
        return list(filter(None, [HairType.get(hair_type_id) for hair_type_id in hair_type_ids]))

    @property
    def hair_colours(self):
        hair_colour_categories = self.hair_colour_categories or []
        return list(
            filter(None, [hc for hc in HairColour.all() if hc.category in hair_colour_categories])
        )

    @property
    def eye_colours(self):
        eye_colour_ids = self.eye_colour_ids or []
        return list(
            filter(None, [EyeColour.get(eye_colour_id) for eye_colour_id in eye_colour_ids])
        )

    @hybrid_property_expression
    def absolute_min_followers(cls):
        from takumi.models.campaign import RewardModels

        return case(
            [((cls.reward_model == RewardModels.assets), current_app.config["MINIMUM_FOLLOWERS"])],
            else_=MIN_INSTAGRAM_FOLLOWERS_REACH,
        )

    @hybrid_method_subquery
    def is_under_region(cls, region):
        from takumi.models import Region  # noqa

        subregion_ids = [
            r_id[0]
            for r_id in db.session.query(Region.id)
            .filter(Region.path.contains("{" + region.id + "}"))
            .all()
        ]
        region_ids = [region.id] + (region.path if region.path else []) + subregion_ids
        return (
            db.session.query(func.count(Region.id) > 0)
            .join(targeting_region_table)
            .filter(targeting_region_table.c.targeting_id == cls.id)
            .filter(or_(*[Region.id == region_id for region_id in region_ids]))
        )

    @hybrid_method_subquery
    def targets_region(cls, region):
        from takumi.models import Region  # noqa

        region_ids = ([region.id] + (region.path if region.path else [])) if region else []

        return (
            db.session.query(func.count(Region.id) > 0)
            .join(targeting_region_table)
            .filter(targeting_region_table.c.targeting_id == cls.id)
            .filter(or_(*[Region.id == region_id for region_id in region_ids]))
        )

    @hybrid_method_expression
    def targets_any_of_interests(self, interests):
        interest_ids = [i.id for i in interests]
        return or_(
            self.interest_ids == [],
            self.interest_ids == None,
            self.interest_ids.overlap(interest_ids),
        )

    @hybrid_method_expression
    def targets_self_tags(self, self_tags):
        self_tag_ids = [i.id for i in (self_tags or [])]
        return or_(
            self.self_tag_ids == [],
            self.self_tag_ids == None,
            self.self_tag_ids.contained_by(self_tag_ids),
        )

    @hybrid_method_expression
    def targets_age(self, age):
        if age:
            query = or_(
                self.ages == [], self.ages == None, self.ages.contains("{" + str(age) + "}")
            )
        else:
            query = or_(self.ages == [], self.ages == None)
        return query

    @hybrid_method_expression
    def targets_gender(self, gender):
        return or_(self.gender == None, self.gender == gender)

    @hybrid_method_expression
    def targets_max_followers(self, followers):
        if not followers:
            followers = 0
        return or_(self.max_followers == None, self.max_followers >= followers)

    @hybrid_method_expression
    def targets_min_followers(self, followers):
        if not followers:
            followers = 0
        return or_(
            and_(self.min_followers == None, self.absolute_min_followers <= followers),
            self.min_followers <= followers,
        )

    @hybrid_method_expression
    def targets_is_verified(self, state):
        from takumi.models.influencer import STATES as INFLUENCER_STATES

        return or_(
            ~self.verified_only, and_(self.verified_only, state == INFLUENCER_STATES.VERIFIED)
        )

    @hybrid_method_expression
    def targets_influencer(self, influencer):
        filters = get_influencer_targeting_filters(self, influencer)
        return and_(*filters.values())

    @hybrid_method_expression
    def targets_glasses(self, has_glasses):
        return or_(self.has_glasses == None, self.has_glasses == has_glasses)

    @hybrid_method_expression
    def targets_hair_colour(self, hair_colour):
        hair_colour_category = hair_colour.category if hair_colour else None
        return or_(
            self.hair_colour_categories == None,
            self.hair_colour_categories == [],
            self.hair_colour_categories.contains(
                ("{" + hair_colour_category + "}") if hair_colour_category else None
            ),
        )

    @hybrid_method_expression
    def targets_eye_colour(self, eye_colour):
        eye_colour_id = eye_colour.id if eye_colour else None
        return or_(
            self.eye_colour_ids == None,
            self.eye_colour_ids == [],
            self.eye_colour_ids.contains([eye_colour_id]),
        )

    @hybrid_method_expression
    def targets_hair_type(self, hair_type):
        hair_type_id = hair_type.id if hair_type else None
        return or_(
            self.hair_type_ids == None,
            self.hair_type_ids == [],
            self.hair_type_ids.contains([hair_type_id]),
        )

    @hybrid_method_expression
    def targets_any_of_languages(self, languages):
        return or_(
            self.languages == None,
            self.languages == [],
            self.languages.overlap(cast(array(languages or []), ARRAY(db.String))),
        )

    @hybrid_method_expression
    def targets_children(cls, children):
        from takumi.models.children_targeting import ChildrenTargeting  # noqa

        child_count = len(children or [])
        children_ages = [child.age for child in children or []]
        children_genders = [child.gender for child in children or []]
        has_unborn_child = any([child.is_unborn for child in children or []])
        has_born_child = any([child.is_born for child in children or []])

        AliasedTargeting = aliased(cls)

        return (
            db.session.query(func.count(AliasedTargeting.id) > 0)
            .outerjoin(ChildrenTargeting)
            .filter(AliasedTargeting.id == cls.id)
            .filter(
                or_(
                    ChildrenTargeting.id == None,
                    and_(
                        ChildrenTargeting.targets_children_count(child_count),
                        ChildrenTargeting.targets_any_of_children_ages(children_ages),
                        ChildrenTargeting.targets_any_of_children_genders(children_genders),
                        ChildrenTargeting.targets_unborn_child(has_unborn_child),
                        ChildrenTargeting.targets_born_child(has_born_child),
                    ),
                )
            )
        )


class TargetingEvent(db.Model):
    __tablename__ = "targeting_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"))
    creator_user = relationship("User", lazy="joined")

    targeting_id = db.Column(
        UUIDString, db.ForeignKey("targeting.id", ondelete="restrict"), nullable=False
    )
    targeting = relationship(
        "Targeting",
        backref=backref("events", uselist=True, order_by="TargetingEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    def __repr__(self):
        return "<TargetingEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "TargetingEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
