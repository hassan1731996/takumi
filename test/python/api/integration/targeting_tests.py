# encoding=utf-8
import datetime as dt

from takumi.models import Campaign, InfluencerInformation, Interest
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.children_targeting import ChildrenTargeting
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.influencer_information import (
    EyeColour,
    HairColour,
    HairType,
    InfluencerChild,
    Tag,
)
from takumi.models.offer import STATES as OFFER_STATES
from takumi.search.influencer import InfluencerSearch
from takumi.utils import uuid4_str


def test_target_influencer_query_reviewed_and_not_non_participating(
    es_influencer, db_campaign, db_session, update_influencer_es
):
    es_influencer.state = "disabled"
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0
    es_influencer.state = "new"
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0
    es_influencer.state = "reviewed"
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1
    db_campaign.targeting.interest_ids = [uuid4_str()]
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0


def test_target_influencer_query_verified(es_influencer, db_campaign, update_influencer_es):
    es_influencer.state = "verified"
    update_influencer_es(es_influencer.id)
    assert (
        InfluencerSearch().filter_campaign_eligibility(db_campaign).filter_verified().count() == 1
    )
    es_influencer.state = "new"
    update_influencer_es(es_influencer.id)
    assert (
        InfluencerSearch().filter_campaign_eligibility(db_campaign).filter_verified().count() == 0
    )


def test_target_influencer_query_non_participating_returns_influencer_with_no_gigc(
    es_influencer, db_campaign
):
    results = (
        InfluencerSearch()
        .filter_campaign_eligibility(db_campaign)
        .filter_campaign_non_participating(db_campaign)
    )
    assert [i.id for i in results.all()] == [es_influencer.id]


def test_target_influencer_query_non_participating_returns_no_influencer_with_gig(
    db_offer, db_campaign, update_influencer_es
):
    db_offer.state = OFFER_STATES.ACCEPTED
    update_influencer_es(db_offer.influencer.id)
    assert (
        InfluencerSearch()
        .filter_campaign_eligibility(db_campaign)
        .filter_campaign_non_participating(db_campaign)
        .count()
    ) == 0


def test_target_influencer_query_min_followers_instagram_account(
    es_influencer, db_campaign, update_influencer_es
):
    es_influencer.instagram_account.followers = 999
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0

    es_influencer.instagram_account.followers = 1000
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1


def test_target_influencer_query_follower_range(
    es_influencer, db_session, db_campaign, update_influencer_es
):
    es_influencer.instagram_account.followers = 5000
    update_influencer_es(es_influencer.id)
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.public = True

    db_campaign.targeting.min_followers = 4999
    db_campaign.targeting.max_followers = 5001
    db_session.commit()

    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == [db_campaign]

    db_campaign.targeting.min_followers = 5001
    db_campaign.targeting.max_followers = 5002
    db_session.commit()

    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == []

    db_campaign.targeting.min_followers = 4998
    db_campaign.targeting.max_followers = 4999
    db_session.commit()

    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == []

    db_campaign.targeting.min_followers = 4999
    db_campaign.targeting.max_followers = 5000
    db_session.commit()

    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == [db_campaign]

    db_campaign.targeting.min_followers = 5000
    db_campaign.targeting.max_followers = 5001
    db_session.commit()

    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == [db_campaign]


def test_filter_query_for_post_targeting(
    db_session, es_influencer, db_campaign, update_influencer_es
):
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 1
    es_influencer.target_region = es_influencer.target_region.__class__(
        id=uuid4_str(), name="foo", locale_code="bar"
    )
    db_session.add(es_influencer)
    update_influencer_es(es_influencer.id)
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).count() == 0


def test_influencer_targeted_campaigns(
    db_session, es_influencer, db_campaign, update_influencer_es, db_post
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.public = True
    db_session.commit()

    # Assert
    assert InfluencerSearch().filter_campaign_eligibility(db_campaign).ids() == [es_influencer.id]
    assert es_influencer.targeted_campaigns.with_entities(Campaign).all() == [db_campaign]

    # Test non expression part of targeting hybrid methods
    assert db_campaign.targeting.targets_influencer(es_influencer) == True
    assert db_campaign.targeting.targets_region(es_influencer.target_region) == True
    assert db_campaign.targeting.targets_any_of_interests(es_influencer.interests) == True
    assert db_campaign.targeting.targets_gender(es_influencer.user.gender) == True


def test_non_eligible_influencer_doesnt_get_targeted_campaigns(
    db_session, es_influencer, db_campaign
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Act

    # Make him disabled so won't get targeted
    es_influencer.state = INFLUENCER_STATES.DISABLED

    # Assert
    assert es_influencer.targeted_campaigns.all() == []


def test_targeting_hybrid_method_targets_region(
    db_session, db_campaign, db_influencer, region_factory
):
    # when region is targeted
    assert db_campaign.targeting.targets_region(db_influencer.target_region)

    # when region is not targeted
    not_targeted_region = region_factory(
        name="Not the same as advertiser region", locale_code="not_ad", market_slug="outside"
    )
    assert not db_campaign.targeting.targets_region(not_targeted_region)


def test_targeting_hybrid_method_targets_region_if_region_is_subregion_of_targeting(
    db_session, db_campaign, db_influencer, region_factory
):
    # when region is targeted
    assert db_campaign.targeting.targets_region(db_influencer.target_region)

    # when region is not targeted
    subregion = region_factory(
        name="Not the same as advertiser region",
        locale_code="not_ad",
        market_slug="outside",
        path=[db_campaign.targeting.regions[0].id],
    )
    db_influencer.target_region = subregion
    assert db_campaign.targeting.targets_region(subregion)
    assert db_influencer.matches_any_of_regions(db_campaign.targeting.regions)


def test_targeting_hybrid_method_targets_interests(
    db_session, db_campaign, db_influencer, region_factory
):

    # when interest is targeted
    assert db_campaign.targeting.targets_any_of_interests([db_influencer.interests[0]])

    # when interest is not targeted
    non_targeted_interest = Interest(id=uuid4_str(), name="non targeted interest")
    assert not db_campaign.targeting.targets_any_of_interests([non_targeted_interest])

    # no interests set
    db_campaign.targeting.interest_ids = []
    assert db_campaign.targeting.targets_any_of_interests([non_targeted_interest])
    db_campaign.targeting.interest_ids = None
    assert db_campaign.targeting.targets_any_of_interests([non_targeted_interest])


def test_targeting_hybrid_method_targets_age(
    db_session, db_campaign, db_influencer, region_factory
):
    db_campaign.targeting.ages = []
    assert db_campaign.targeting.targets_age(100)
    db_campaign.targeting.ages = None
    assert db_campaign.targeting.targets_age(100)

    db_campaign.targeting.ages = [25]

    # when age is targeted
    assert db_campaign.targeting.targets_age(db_campaign.targeting.ages[0])

    # when age is not targeted
    assert not db_campaign.targeting.targets_age(100)


def test_targeting_hybrid_method_targets_gender(db_session, db_campaign):
    db_campaign.targeting.gender = None
    assert db_campaign.targeting.targets_gender("male")

    db_campaign.targeting.gender = "male"

    # when gender is targeted
    assert db_campaign.targeting.targets_gender(db_campaign.targeting.gender)

    # when gender is not targeted
    assert not db_campaign.targeting.targets_gender("female")


def test_targeting_hybrid_method_targets_max_followers(db_session, db_campaign):
    # None should not filter on any number
    db_campaign.targeting.max_followers = None

    assert db_campaign.targeting.targets_max_followers(100_000_000)

    db_campaign.targeting.max_followers = 40000

    assert db_campaign.targeting.targets_max_followers(40000)
    assert not db_campaign.targeting.targets_max_followers(40001)


def test_targeting_hybrid_method_targets_min_followers(db_session, db_campaign):
    # None should filter by campaign min
    db_campaign.targeting.min_followers = None

    absolute_min = db_campaign.targeting.absolute_min_followers

    assert db_campaign.targeting.targets_min_followers(absolute_min)
    assert not db_campaign.targeting.targets_min_followers(absolute_min - 1)

    db_campaign.targeting.min_followers = 10_000

    assert db_campaign.targeting.targets_min_followers(10_000)
    assert not db_campaign.targeting.targets_min_followers(9_999)


def test_targeting_child_region_doesnt_target_parent_region(
    db_session, db_campaign, db_influencer, region_factory
):
    parent_region = region_factory(name="parent", locale_code="pr_PR", market_slug="parent")

    child_region = region_factory(name="child", locale_code="ch_CH", market_slug="child")
    child_region.path = [parent_region.id]

    db_campaign.targeting.regions = [child_region]
    db_influencer.target_region = parent_region

    assert db_campaign.targeting.targets_region(child_region)
    assert not db_campaign.targeting.targets_region(parent_region)

    assert db_influencer.matches_any_of_regions([parent_region])
    assert not db_influencer.matches_any_of_regions([child_region])


def test_targeting_parent_region_targets_both_parent_and_child(
    db_session, db_campaign, db_influencer, region_factory
):
    parent_region = region_factory(name="parent", locale_code="pr_PR", market_slug="parent")

    child_region = region_factory(name="child", locale_code="ch_CH", market_slug="child")
    child_region.path = [parent_region.id]

    db_campaign.targeting.regions = [parent_region]
    db_influencer.target_region = child_region

    assert db_campaign.targeting.targets_region(parent_region)
    assert db_campaign.targeting.targets_region(child_region)

    assert db_influencer.matches_any_of_regions([parent_region])
    assert db_influencer.matches_any_of_regions([child_region])


def test_targeting_hybrid_method_targets_has_glasses(db_session, db_campaign, db_influencer):
    # Targeting -> Influencer
    db_campaign.targeting.has_glasses = None

    assert db_campaign.targeting.targets_glasses(True)
    assert db_campaign.targeting.targets_glasses(False)
    assert db_campaign.targeting.targets_glasses(None)

    db_campaign.targeting.has_glasses = True

    assert db_campaign.targeting.targets_glasses(True)
    assert not db_campaign.targeting.targets_glasses(False)
    assert not db_campaign.targeting.targets_glasses(None)

    db_campaign.targeting.has_glasses = False
    assert not db_campaign.targeting.targets_glasses(True)
    assert db_campaign.targeting.targets_glasses(False)
    assert not db_campaign.targeting.targets_glasses(None)

    # Influencer -> Targeting
    db_influencer.information = None

    assert not db_influencer.matches_glasses(True)
    assert not db_influencer.matches_glasses(False)
    assert db_influencer.matches_glasses(None)

    db_influencer.information = InfluencerInformation()
    db_influencer.information.glasses = True

    assert db_influencer.matches_glasses(True)
    assert not db_influencer.matches_glasses(False)
    assert db_influencer.matches_glasses(None)

    db_influencer.information.glasses = False

    assert not db_influencer.matches_glasses(True)
    assert db_influencer.matches_glasses(False)
    assert db_influencer.matches_glasses(None)


def test_targeting_eyes_and_hair(db_session, db_campaign, db_influencer):
    curly_hair = HairType.get("ea769c27-a210-4fb3-8341-a0c3174b2124")
    straight_hair = HairType.get("0e7fb575-4184-48b9-b3b7-8e054c6f1e9a")

    midnight_black_hair = HairColour.get("058f2c4b-c0fe-4da7-ad85-19d476ba1e6f")
    darkest_brown_hair = HairColour.get("466f1955-3b84-41dd-b78b-a55bd67e65d6")

    blue_eyes = EyeColour.get("f34984ae-2157-4c63-ad36-bb1c535ab9bd")
    green_eyes = EyeColour.get("2734a7b4-4866-4df6-8cd6-3a7a4568ec38")

    # Targeting -> Influencer
    db_campaign.targeting.hair_type_ids = None
    assert db_campaign.targeting.targets_hair_type(None)
    assert db_campaign.targeting.targets_hair_type(curly_hair)
    assert db_campaign.targeting.targets_hair_type(straight_hair)

    db_campaign.targeting.hair_type_ids = [curly_hair.id]
    assert not db_campaign.targeting.targets_hair_type(None)
    assert db_campaign.targeting.targets_hair_type(curly_hair)
    assert not db_campaign.targeting.targets_hair_type(straight_hair)

    db_campaign.targeting.hair_colour_categories = None
    assert db_campaign.targeting.targets_hair_colour(None)
    assert db_campaign.targeting.targets_hair_colour(midnight_black_hair)
    assert db_campaign.targeting.targets_hair_colour(darkest_brown_hair)

    db_campaign.targeting.hair_colour_categories = [midnight_black_hair.category]
    assert not db_campaign.targeting.targets_hair_colour(None)
    assert db_campaign.targeting.targets_hair_colour(midnight_black_hair)
    assert not db_campaign.targeting.targets_hair_colour(darkest_brown_hair)

    db_campaign.targeting.eye_colour_ids = None
    assert db_campaign.targeting.targets_eye_colour(None)
    assert db_campaign.targeting.targets_eye_colour(blue_eyes)
    assert db_campaign.targeting.targets_eye_colour(green_eyes)

    db_campaign.targeting.eye_colour_ids = [blue_eyes.id]
    assert not db_campaign.targeting.targets_eye_colour(None)
    assert db_campaign.targeting.targets_eye_colour(blue_eyes)
    assert not db_campaign.targeting.targets_eye_colour(green_eyes)

    # Influencer -> Targeting
    db_influencer.information = None
    assert db_influencer.matches_any_of_hair_types([])
    assert not db_influencer.matches_any_of_hair_types([curly_hair])

    assert db_influencer.matches_any_of_hair_colours([])
    assert not db_influencer.matches_any_of_hair_colours([midnight_black_hair])

    assert db_influencer.matches_any_of_eye_colours([])
    assert not db_influencer.matches_any_of_eye_colours([blue_eyes])

    db_influencer.information = InfluencerInformation()
    db_influencer.information.hair_type_id = curly_hair.id
    assert db_influencer.matches_any_of_hair_types([])
    assert db_influencer.matches_any_of_hair_types([curly_hair])
    assert not db_influencer.matches_any_of_hair_types([straight_hair])

    db_influencer.information.hair_colour_id = midnight_black_hair.id
    assert db_influencer.matches_any_of_hair_colours([])
    assert not db_influencer.matches_any_of_hair_colours([darkest_brown_hair])
    assert db_influencer.matches_any_of_hair_colours([midnight_black_hair])

    db_influencer.information.eye_colour_id = blue_eyes.id
    assert db_influencer.matches_any_of_eye_colours([])
    assert db_influencer.matches_any_of_eye_colours([blue_eyes])
    assert not db_influencer.matches_any_of_eye_colours([green_eyes])


def test_targeting_languages(db_session, db_campaign, db_influencer):
    # Targeting -> Influencer
    db_campaign.targeting.languages = []
    assert db_campaign.targeting.targets_any_of_languages(["en"])
    assert db_campaign.targeting.targets_any_of_languages([])
    assert db_campaign.targeting.targets_any_of_languages(None)

    db_campaign.targeting.languages = ["en", "is"]

    assert db_campaign.targeting.targets_any_of_languages(["en"])
    assert db_campaign.targeting.targets_any_of_languages(["is"])
    assert db_campaign.targeting.targets_any_of_languages(["en", "is", "es"])
    assert not db_campaign.targeting.targets_any_of_languages(["es"])
    assert not db_campaign.targeting.targets_any_of_languages([])
    assert not db_campaign.targeting.targets_any_of_languages(None)

    # Influencer -> Targeting
    db_influencer.information = InfluencerInformation()
    db_influencer.information.languages = None
    assert db_influencer.matches_any_of_languages(None)
    assert db_influencer.matches_any_of_languages([])
    assert not db_influencer.matches_any_of_languages(["is"])

    db_influencer.information.languages = ["en", "is"]
    assert db_influencer.matches_any_of_languages(None)
    assert db_influencer.matches_any_of_languages([])
    assert db_influencer.matches_any_of_languages(["is"])
    assert db_influencer.matches_any_of_languages(["en", "is"])


def test_targeting_self_tags(db_session, db_campaign, db_influencer):
    # Targeting -> Influencer
    plus_size = Tag.get("e9944093-9acb-4d04-bd19-0b660576683b")
    sensitive_skin = Tag.get("8edc75dc-2ff7-40a3-a084-80fd73afac39")
    vegan = Tag.get("3fc0b9a5-ebf7-465f-b7b5-4ec376ade729")

    db_campaign.targeting.self_tag_ids = []
    assert db_campaign.targeting.targets_self_tags([])
    assert db_campaign.targeting.targets_self_tags([plus_size, vegan, sensitive_skin])

    db_campaign.targeting.self_tag_ids = [plus_size.id, sensitive_skin.id, vegan.id]
    assert not db_campaign.targeting.targets_self_tags([])
    assert not db_campaign.targeting.targets_self_tags([plus_size])
    assert not db_campaign.targeting.targets_self_tags([plus_size, sensitive_skin])
    assert db_campaign.targeting.targets_self_tags([plus_size, sensitive_skin, vegan])
    assert not db_campaign.targeting.targets_self_tags([vegan])

    # Influencer -> Targeting
    db_influencer.information = InfluencerInformation()
    db_influencer.information.tag_ids = None
    assert db_influencer.matches_self_tags([])
    assert not db_influencer.matches_self_tags([plus_size])

    db_influencer.information.tag_ids = [plus_size.id, sensitive_skin.id]
    assert db_influencer.matches_self_tags([sensitive_skin, plus_size])
    assert db_influencer.matches_self_tags([sensitive_skin])
    assert db_influencer.matches_self_tags([plus_size])
    assert not db_influencer.matches_self_tags([vegan])
    assert not db_influencer.matches_self_tags([sensitive_skin, plus_size, vegan])


def test_targeting_children(db_session, db_campaign, db_influencer):
    # It's difficult to freeze the time when depending on the database, so use
    # the current time for this test
    now = dt.datetime.now(dt.timezone.utc)

    # Targeting -> Influencer
    db_campaign.targeting.children_targeting = ChildrenTargeting()
    db_session.add(db_campaign.targeting)
    db_session.commit()

    children_targeting = db_campaign.targeting.children_targeting

    children_targeting.min_children_count = None
    children_targeting.max_children_count = 2
    assert children_targeting.targets_children_count(0)
    assert children_targeting.targets_children_count(1)
    assert children_targeting.targets_children_count(2)
    assert not children_targeting.targets_children_count(3)

    children_targeting.min_children_count = 2
    children_targeting.max_children_count = None
    assert not children_targeting.targets_children_count(0)
    assert not children_targeting.targets_children_count(1)
    assert children_targeting.targets_children_count(2)

    children_targeting.min_children_count = 2
    children_targeting.max_children_count = 4
    assert not children_targeting.targets_children_count(1)
    assert children_targeting.targets_children_count(2)
    assert children_targeting.targets_children_count(3)
    assert children_targeting.targets_children_count(4)
    assert not children_targeting.targets_children_count(5)

    children_targeting.ages = None
    assert children_targeting.targets_any_of_children_ages([1, 2, 3])
    assert children_targeting.targets_any_of_children_ages([None, 1])

    children_targeting.ages = [1, 2, 3]
    assert children_targeting.targets_any_of_children_ages([1, 2, 3])
    assert children_targeting.targets_any_of_children_ages([3])
    assert not children_targeting.targets_any_of_children_ages([4, 5, 6])
    assert not children_targeting.targets_any_of_children_ages([4])

    children_targeting.child_gender = None
    assert children_targeting.targets_any_of_children_genders(["male"])
    assert children_targeting.targets_any_of_children_genders(["female"])
    assert children_targeting.targets_any_of_children_genders([None])

    children_targeting.child_gender = "male"
    assert children_targeting.targets_any_of_children_genders(["male", "female"])
    assert children_targeting.targets_any_of_children_genders(["male"])
    assert not children_targeting.targets_any_of_children_genders(["female"])
    assert not children_targeting.targets_any_of_children_genders([None])

    children_targeting.has_unborn_child = None
    assert children_targeting.targets_unborn_child(True)
    assert children_targeting.targets_unborn_child(None)
    assert children_targeting.targets_unborn_child(False)

    children_targeting.has_unborn_child = True
    assert children_targeting.targets_unborn_child(True)
    assert not children_targeting.targets_unborn_child(None)
    assert not children_targeting.targets_unborn_child(False)

    children_targeting.has_unborn_child = False
    assert not children_targeting.targets_unborn_child(True)
    assert not children_targeting.targets_unborn_child(None)
    assert children_targeting.targets_unborn_child(False)

    children_targeting.has_born_child = None
    assert children_targeting.targets_born_child(True)
    assert children_targeting.targets_born_child(None)
    assert children_targeting.targets_born_child(False)

    children_targeting.has_born_child = True
    assert children_targeting.targets_born_child(True)
    assert not children_targeting.targets_born_child(None)
    assert not children_targeting.targets_born_child(False)

    children_targeting.has_born_child = False
    assert not children_targeting.targets_born_child(True)
    assert not children_targeting.targets_born_child(None)
    assert children_targeting.targets_born_child(False)

    # Influencer -> Targeting
    db_influencer.information = InfluencerInformation()
    db_influencer.information.children = []

    assert db_influencer.matches_children_count(None, None)
    assert db_influencer.matches_children_count(None, 5)
    assert db_influencer.matches_children_count(0, 5)
    assert not db_influencer.matches_children_count(1, None)
    assert not db_influencer.matches_children_count(1, 5)

    assert db_influencer.matches_children_ages([])
    assert db_influencer.matches_children_ages(None)

    assert not db_influencer.matches_child_gender("male")
    assert not db_influencer.matches_child_gender("female")
    assert db_influencer.matches_child_gender(None)

    assert db_influencer.matches_born_child(None)
    assert db_influencer.matches_born_child(False)
    assert not db_influencer.matches_born_child(True)

    assert db_influencer.matches_unborn_child(None)
    assert db_influencer.matches_unborn_child(False)
    assert not db_influencer.matches_unborn_child(True)

    db_influencer.information.children = [
        # Just over 2 years old
        InfluencerChild(gender="male", birthday=now - dt.timedelta(days=370 * 2))
    ]

    assert db_influencer.matches_born_child(None)
    assert not db_influencer.matches_born_child(False)
    assert db_influencer.matches_born_child(True)

    assert db_influencer.matches_unborn_child(None)
    assert db_influencer.matches_unborn_child(False)
    assert not db_influencer.matches_unborn_child(True)

    assert db_influencer.matches_children_count(None, None)
    assert db_influencer.matches_children_count(None, 5)
    assert db_influencer.matches_children_count(0, 5)
    assert db_influencer.matches_children_count(1, None)
    assert db_influencer.matches_children_count(1, 5)
    assert not db_influencer.matches_children_count(2, None)
    assert not db_influencer.matches_children_count(2, 5)

    assert db_influencer.matches_children_ages([2])
    assert db_influencer.matches_children_ages([1, 2, 3])
    assert not db_influencer.matches_children_ages([4, 5])
    assert not db_influencer.matches_children_ages([3])
    assert db_influencer.matches_children_ages([])

    assert db_influencer.matches_child_gender("male")
    assert not db_influencer.matches_child_gender("female")
    assert db_influencer.matches_child_gender(None)

    db_influencer.information.children = db_influencer.information.children + [
        # Just over 3 years old
        InfluencerChild(gender="female", birthday=now - dt.timedelta(days=370 * 3))
    ]

    assert db_influencer.matches_born_child(None)
    assert not db_influencer.matches_born_child(False)
    assert db_influencer.matches_born_child(True)

    assert db_influencer.matches_unborn_child(None)
    assert db_influencer.matches_unborn_child(False)
    assert not db_influencer.matches_unborn_child(True)

    assert db_influencer.matches_children_count(2, None)
    assert db_influencer.matches_children_count(2, 5)

    assert db_influencer.matches_children_ages([3])
    assert db_influencer.matches_children_ages([1, 2, 3])
    assert db_influencer.matches_children_ages([1, 3])
    assert not db_influencer.matches_children_ages([4, 5])
    assert db_influencer.matches_children_ages([])

    assert db_influencer.matches_child_gender("male")
    assert db_influencer.matches_child_gender("female")
    assert db_influencer.matches_child_gender(None)

    db_influencer.information.children = db_influencer.information.children + [
        # Expecting 100 days from now
        InfluencerChild(gender="female", birthday=now + dt.timedelta(days=100))
    ]

    assert db_influencer.matches_born_child(None)
    assert not db_influencer.matches_born_child(False)
    assert db_influencer.matches_born_child(True)

    assert db_influencer.matches_unborn_child(None)
    assert not db_influencer.matches_unborn_child(False)
    assert db_influencer.matches_unborn_child(True)
