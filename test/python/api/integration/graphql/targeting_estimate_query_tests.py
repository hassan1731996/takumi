import mock

from core.targeting.targeting import age

from takumi.gql.query.targeting import TargetingEstimateQuery

influencer_estimate = mock.Mock(field_name="influencerEstimate")
follower_estimate = mock.Mock(field_name="followerEstimate")


def test_resolve_estimates_no_regions_no_ages_no_gender(db_campaign, es_influencer):
    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[]
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 1
    assert estimate["verified"] == 1

    estimate = TargetingEstimateQuery.resolve_follower_estimate(
        None, follower_estimate, db_campaign.id, regions=[]
    )
    assert estimate["total"] == es_influencer.followers
    assert estimate["eligible"] == es_influencer.followers
    assert estimate["verified"] == es_influencer.followers


def test_resolve_influencer_estimate_with_regions(
    db_session, db_campaign, db_region, es_influencer, region_factory
):
    new_region = region_factory(market_slug=db_campaign.market_slug)
    db_session.add(new_region)
    db_session.commit()
    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[new_region.id]
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 0

    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[db_region.id]
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 1


def test_resolve_influencer_estimate_with_age(db_session, db_campaign, es_influencer):
    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[], ages=[99, 100]
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 0

    infl_age = age(es_influencer.user.birthday)
    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[], ages=[infl_age]
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 1


def test_resolve_influencer_estimate_with_gender(
    db_session, db_campaign, es_influencer, update_influencer_es
):
    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[], gender="male"
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 0
    es_influencer.user.gender = "female"
    update_influencer_es(es_influencer.id)

    estimate = TargetingEstimateQuery.resolve_influencer_estimate(
        None, influencer_estimate, db_campaign.id, regions=[], gender="female"
    )
    assert estimate["total"] == 1
    assert estimate["eligible"] == 1
