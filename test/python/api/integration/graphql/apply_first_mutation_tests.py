import pytest

from takumi.gql.mutation.apply_first import (
    PromoteSelectedToAccepted,
    RejectCandidate,
    SetApplyFirstOfferPosition,
)
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services.exceptions import CampaignPromotionException


def test_set_apply_first_offer_position_moves_influencers(
    client,
    developer_user,
    db_session,
    db_region,
    db_campaign,
    offer_factory,
    influencer_factory,
    user_factory,
):
    offers = [
        offer_factory(
            state=OFFER_STATES.CANDIDATE,
            influencer=influencer_factory(
                state=INFLUENCER_STATES.REVIEWED, target_region=db_region, user=user_factory()
            ),
            campaign=db_campaign,
        )
        for i in range(20)
    ]
    db_session.add_all(offers)
    db_session.commit()

    entry = db_campaign.ordered_candidates_q.first()

    with client.user_request_context(developer_user):
        SetApplyFirstOfferPosition.mutate(
            "root", "info", db_campaign.id, 0, 1, db_campaign.candidates_hash
        )

    assert db_campaign.ordered_candidates_q.all()[1] == entry

    with client.user_request_context(developer_user):
        SetApplyFirstOfferPosition.mutate(
            "root", "info", db_campaign.id, 1, 10, db_campaign.candidates_hash
        )

    assert db_campaign.ordered_candidates_q.all()[10] == entry


@pytest.fixture
def promotion_offers(
    offer_factory,
    influencer_factory,
    user_factory,
    instagram_account_factory,
    db_session,
    db_region,
    db_reach_campaign,
):
    offers = [
        offer_factory(
            state=OFFER_STATES.APPROVED_BY_BRAND,
            influencer=influencer_factory(
                state=INFLUENCER_STATES.REVIEWED,
                target_region=db_region,
                user=user_factory(),
                instagram_account=instagram_account_factory(followers=100_000),
            ),
            campaign=db_reach_campaign,
            is_selected=True,
            followers_per_post=100_000,
        )
        for i in range(20)
    ]
    db_session.add_all(offers)

    db_reach_campaign.apply_first = True
    db_reach_campaign.brand_match = True
    db_reach_campaign.state = "launched"
    db_reach_campaign.units = 1_000_000

    db_session.commit()

    return offers


def test_promote_selected_to_accepted_raises_if_promoting_too_many_without_promoting_any(
    client, developer_user, db_reach_campaign, promotion_offers
):

    with pytest.raises(CampaignPromotionException, match="Trying to promote too many influencers"):
        with client.user_request_context(developer_user):
            PromoteSelectedToAccepted.mutate("root", "info", db_reach_campaign.id, force=False)

    for offer in promotion_offers:
        assert offer.state == OFFER_STATES.APPROVED_BY_BRAND


def test_promote_selected_to_accepted_promotes_without_force_if_not_overflowing(
    client, developer_user, db_session, db_reach_campaign, promotion_offers
):
    db_reach_campaign.units = sum(
        db_reach_campaign.fund.get_offer_units(offer) for offer in promotion_offers
    )
    db_session.commit()

    with client.user_request_context(developer_user):
        PromoteSelectedToAccepted.mutate("root", "info", db_reach_campaign.id, force=False)

    for offer in promotion_offers:
        assert offer.state == OFFER_STATES.ACCEPTED


def test_promote_selected_to_accepted_promotes_if_forced(
    client, developer_user, db_reach_campaign, promotion_offers
):

    with client.user_request_context(developer_user):
        PromoteSelectedToAccepted.mutate("root", "info", db_reach_campaign.id, force=True)

    for offer in promotion_offers:
        assert offer.state == OFFER_STATES.ACCEPTED


def test_reject_candidate_twice_doesnt_crash(
    client,
    developer_user,
    db_session,
    db_region,
    db_campaign,
    offer_factory,
    influencer_factory,
    user_factory,
):
    db_campaign.apply_first = True
    db_campaign.brand_match = True
    offer = offer_factory(
        state=OFFER_STATES.CANDIDATE,
        influencer=influencer_factory(
            state=INFLUENCER_STATES.REVIEWED, target_region=db_region, user=user_factory()
        ),
        campaign=db_campaign,
    )
    db_session.add(offer)
    db_session.commit()

    assert offer.state != OFFER_STATES.REJECTED_BY_BRAND

    with client.user_request_context(developer_user):
        RejectCandidate().mutate("info", offer.id, reason="Testing")

    assert offer.state == OFFER_STATES.REJECTED_BY_BRAND

    with client.user_request_context(developer_user):
        RejectCandidate().mutate("info", offer.id, reason="Testing")

    assert offer.state == OFFER_STATES.REJECTED_BY_BRAND
