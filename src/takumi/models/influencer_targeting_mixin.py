import datetime as dt

import sqlalchemy
from flask import current_app
from sqlalchemy import and_, cast, extract, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased

from core.common.sqla import UUIDString

from takumi.constants import MIN_INSTAGRAM_POSTS
from takumi.extensions import db
from takumi.models.influencer_information import InfluencerInformation

from .helpers import (
    add_columns_as_attributes,
    hybrid_method_expression,
    hybrid_method_subquery,
    hybrid_property_subquery,
)
from .instagram_account import InstagramAccount


class InfluencerTargetingMixin:
    @hybrid_property
    def interest_ids(self):
        return [i.id for i in self.interests]

    @interest_ids.expression  # type: ignore
    def interest_ids(cls):
        from takumi.models.influencer import influencer_interests

        influencer_interests = add_columns_as_attributes(influencer_interests)

        return cast(
            func.array(
                select([influencer_interests.influencer_interests_interest_id])
                .select_from(influencer_interests)
                .where(influencer_interests.influencer_interests_influencer_id == cls.id)
                .label("interest_ids")
            ),
            ARRAY(sqlalchemy.Text),
        )

    @hybrid_property_subquery
    def is_eligible(cls):
        from takumi.models.influencer import STATES

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .join(InstagramAccount)
            .filter(
                AliasedInfluencer.id == cls.id,
                AliasedInfluencer.is_signed_up,
                AliasedInfluencer.state != STATES.DISABLED,
                InstagramAccount.followers >= current_app.config["MINIMUM_FOLLOWERS"],
                ~InstagramAccount.ig_is_private,
                InstagramAccount.media_count >= MIN_INSTAGRAM_POSTS,
            )
        )

    @hybrid_method_expression
    def matches_any_of_interest_ids(cls, interest_ids):
        return or_(interest_ids == [], interest_ids == None, cls.interest_ids.overlap(interest_ids))

    @hybrid_method_subquery
    def matches_any_of_ages(cls, ages):
        from takumi.models import User

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .join(User)
            .filter(User.age.in_(ages) if ages else True)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_gender(cls, gender):
        from takumi.models import User

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .join(User)
            .filter(User.gender == gender if gender else True)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_max_followers(cls, max_followers):
        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .filter(AliasedInfluencer.followers <= max_followers if max_followers else True)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_min_followers(cls, min_followers):
        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .filter(AliasedInfluencer.followers >= min_followers)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_any_of_regions(cls, regions):
        from takumi.models import Region

        AliasedInfluencer = aliased(cls)

        if not regions:
            regions = []

        region_ids = [region.id for region in regions]

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .join(Region, Region.id == AliasedInfluencer.target_region_id)
            .filter(AliasedInfluencer.id == cls.id)
            .filter(
                or_(
                    *[
                        or_(Region.path.overlap(region_ids), Region.id == region_id)
                        for region_id in region_ids
                    ]
                )
            )
        )

    @hybrid_method_expression
    def matches_targeting(cls, targeting):
        return and_(
            cls.matches_any_of_regions(targeting.regions),
            cls.matches_any_of_interest_ids(targeting.interest_ids),
            cls.matches_any_of_ages(targeting.ages),
            cls.matches_gender(targeting.gender),
            cls.matches_max_followers(targeting.max_followers),
            cls.matches_min_followers(targeting.min_followers or targeting.absolute_min_followers),
            cls.matches_any_of_hair_types(targeting.hair_types),
            cls.matches_any_of_hair_colours(targeting.hair_colours),
            cls.matches_any_of_eye_colours(targeting.hair_colours),
            cls.matches_glasses(targeting.has_glasses),
            cls.matches_any_of_languages(targeting.languages),
            cls.matches_self_tags(targeting.self_tags),
            cls.matches_children_targeting(targeting.children_targeting)
            if targeting.children_targeting
            else True,
        )

    @hybrid_method_subquery
    def has_active_offer_in(cls, campaign, state=None):
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        return db.session.query(func.count(Offer.id) > 0).filter(
            Offer.campaign_id == campaign.id,
            Offer.influencer_id == cls.id,
            Offer.state.in_(
                (
                    OFFER_STATES.ACCEPTED,
                    OFFER_STATES.INVITED,
                    OFFER_STATES.REQUESTED,
                    OFFER_STATES.CANDIDATE,
                    OFFER_STATES.APPROVED_BY_BRAND,
                )
            ),
            Offer.state == state if state else True,
        )

    @hybrid_method_subquery
    def has_offer_in(cls, campaign):
        from takumi.models.offer import Offer

        return db.session.query(func.count(Offer.id) > 0).filter(
            Offer.campaign_id == campaign.id, Offer.influencer_id == cls.id
        )

    @hybrid_method_subquery
    def is_on_cooldown_for_advertiser(cls, advertiser):
        from . import Advertiser, Campaign, Offer
        from .influencer import STATES as INFLUENCER_STATES
        from .offer import STATES as OFFER_STATES

        AliasedInfluencer = aliased(cls)

        days_since_offer_accepted = func.trunc(
            (extract("epoch", dt.datetime.now(dt.timezone.utc)) - extract("epoch", Offer.accepted))
            / 86400
        )
        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(Offer)
            .outerjoin(Campaign)
            .outerjoin(Advertiser)
            .filter(
                or_(
                    and_(
                        Advertiser.id == advertiser.id,
                        Offer.state == OFFER_STATES.ACCEPTED,
                        Advertiser.influencer_cooldown != None,
                        Advertiser.influencer_cooldown != 0,
                        days_since_offer_accepted <= Advertiser.influencer_cooldown,
                    ),
                    AliasedInfluencer.state == INFLUENCER_STATES.COOLDOWN,
                )
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_expression
    def matches_campaign(cls, campaign):
        from takumi.models.influencer import STATES as INFLUENCER_STATES

        return and_(
            cls.state.in_([INFLUENCER_STATES.VERIFIED, INFLUENCER_STATES.REVIEWED]),
            ~cls.is_on_cooldown_for_advertiser(campaign.advertiser),
            ~cls.has_offer_in(campaign),
            cls.matches_targeting(campaign.targeting),
        )

    @hybrid_method_subquery
    def matches_glasses(cls, glasses):
        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(or_(glasses == None, InfluencerInformation.glasses == glasses))
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_any_of_hair_types(cls, hair_types):
        hair_type_ids = [hair_type.id for hair_type in hair_types]

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(or_(hair_type_ids == [], InfluencerInformation.hair_type_id.in_(hair_type_ids)))
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_any_of_hair_colours(cls, hair_colours):
        hair_colour_ids = [hair_colour.id for hair_colour in hair_colours]

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(
                or_(
                    hair_colour_ids == [], InfluencerInformation.hair_colour_id.in_(hair_colour_ids)
                )
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_any_of_eye_colours(cls, eye_colours):
        eye_colour_ids = [eye_colour.id for eye_colour in eye_colours]

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(
                or_(eye_colour_ids == [], InfluencerInformation.eye_colour_id.in_(eye_colour_ids))
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_subquery
    def matches_any_of_languages(cls, languages):
        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(
                or_(
                    languages == None,
                    languages == [],
                    InfluencerInformation.languages.overlap(
                        cast(array(languages or []), ARRAY(db.String))
                    ),
                )
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_expression
    def matches_self_tags(cls, self_tags):
        self_tag_ids = [t.id for t in self_tags]

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .filter(
                or_(
                    self_tags == [],
                    cast(array(self_tag_ids), ARRAY(UUIDString)).contained_by(
                        InfluencerInformation.tag_ids
                    ),
                )
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_method_expression
    def matches_children_count(cls, min_children_count, max_children_count):
        return db.session.query(
            and_(
                InfluencerInformation.children_count >= func.coalesce(min_children_count, 0),
                (InfluencerInformation.children_count <= max_children_count)
                if max_children_count is not None
                else True,
            )
        ).filter(InfluencerInformation.influencer_id == cls.id)

    @hybrid_method_expression
    def matches_children_ages(cls, ages):
        from takumi.models.influencer_information import InfluencerChild

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .outerjoin(InfluencerChild)
            .filter(InfluencerChild.age.in_(ages) if ages else True)
            .filter(InfluencerInformation.influencer_id == cls.id)
        )

    @hybrid_method_expression
    def matches_child_gender(cls, gender):
        from takumi.models.influencer_information import InfluencerChild

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .outerjoin(InfluencerChild)
            .filter(InfluencerChild.gender == gender if gender else True)
            .filter(InfluencerInformation.influencer_id == cls.id)
        )

    @hybrid_method_expression
    def matches_unborn_child(cls, has_unborn_child):
        from takumi.models.influencer_information import InfluencerChild

        AliasedInfluencer = aliased(cls)

        query = (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .outerjoin(
                InfluencerChild,
                and_(
                    InfluencerChild.influencer_information_id == InfluencerInformation.id,
                    InfluencerChild.is_unborn,
                ),
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

        if has_unborn_child is not None:
            if has_unborn_child:
                return query.filter(InfluencerChild.id != None)
            else:
                return query.filter(InfluencerChild.id == None)

        return query

    @hybrid_method_expression
    def matches_born_child(cls, has_born_child):
        from takumi.models.influencer_information import InfluencerChild

        AliasedInfluencer = aliased(cls)

        query = (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .outerjoin(InfluencerInformation)
            .outerjoin(
                InfluencerChild,
                and_(
                    InfluencerChild.influencer_information_id == InfluencerInformation.id,
                    InfluencerChild.is_born,
                ),
            )
            .filter(AliasedInfluencer.id == cls.id)
        )

        if has_born_child is not None:
            if has_born_child:
                return query.filter(InfluencerChild.id != None)
            else:
                return query.filter(InfluencerChild.id == None)

        return query

    @hybrid_method_expression
    def matches_children_targeting(cls, children_targeting):
        min_children_count = children_targeting.min_children_count
        max_children_count = children_targeting.max_children_count
        children_ages = children_targeting.ages
        child_gender = children_targeting.child_gender
        has_unborn_child = children_targeting.has_unborn_child
        has_born_child = children_targeting.has_born_child

        return and_(
            cls.matches_children_count(min_children_count, max_children_count),
            cls.matches_children_ages(children_ages),
            cls.matches_child_gender(child_gender),
            cls.matches_unborn_child(has_unborn_child),
            cls.matches_born_child(has_born_child),
        )
