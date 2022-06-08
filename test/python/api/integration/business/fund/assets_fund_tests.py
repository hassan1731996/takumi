from __future__ import division

import pytest

from takumi.models.gig import STATES as GIG_STATES
from takumi.services.exceptions import CampaignFullyReservedException
from takumi.services.offer import OfferService

MILLION = 1_000_000


def test_assets_fund_budget_reserve_but_dont_reach_target_succeds_campaign_not_reserved(
    db_session, db_campaign, db_influencer_alice, db_influencer_bob, db_post
):

    db_campaign.units = 3
    db_campaign.state = "launched"
    db_campaign.posts = [db_post]

    alice_offer = OfferService.create(db_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    # No exception should be thrown. Reservations succeed
    with OfferService(bob_offer) as actions:
        actions.reserve()
    db_session.add(bob_offer)
    db_session.commit()

    assert not db_campaign.is_fully_reserved()


def test_assets_fund_budget_reaches_exact_target_succeeds(
    db_session, db_campaign, db_influencer_alice, db_influencer_bob, db_post
):

    db_campaign.units = 2
    db_campaign.state = "launched"
    db_campaign.posts = [db_post]

    alice_offer = OfferService.create(db_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    # No exception should be thrown. Reservation succeeds
    with OfferService(bob_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    assert db_campaign.is_fully_reserved()


def test_assets_fund_reserve_filled_campaign_fails(
    db_session, db_campaign, db_influencer_alice, db_influencer_bob, db_post
):

    db_campaign.units = 1
    db_campaign.state = "launched"
    db_campaign.posts = [db_post]

    alice_offer = OfferService.create(db_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    assert db_campaign.is_fully_reserved()

    # Exception should be thrown. This reservation should fail
    with OfferService(bob_offer) as actions:
        with pytest.raises(CampaignFullyReservedException):
            actions.reserve()


def test_get_progress_submitted_offer_get_filtered_out_if_not_reserved(
    db_session, db_post, db_influencer_bob, gig_factory
):
    campaign = db_post.campaign
    campaign.state = "launched"
    campaign.units = 10

    offer = OfferService.create(campaign.id, db_influencer_bob.id)

    gig = gig_factory(offer=offer, post=db_post)

    db_session.add(gig)
    db_session.add(offer)
    db_session.commit()
    assert campaign.fund.get_progress() == {"total": 10, "reserved": 0, "submitted": 0}


def test_get_progress_one_submitted_offer_and_one_new_offer(
    db_session, db_post, db_influencer_bob, db_influencer_alice, gig_factory, instagram_post_factory
):
    campaign = db_post.campaign
    campaign.state = "launched"
    campaign.units = 10

    offer = OfferService.create(campaign.id, db_influencer_bob.id)
    offer2 = OfferService.create(campaign.id, db_influencer_alice.id)

    with OfferService(offer) as actions:
        actions.reserve()

    gig = gig_factory(
        state=GIG_STATES.APPROVED,
        offer=offer,
        post=db_post,
        instagram_post=instagram_post_factory(),
        is_verified=True,
    )

    db_session.add(gig)
    db_session.add(offer)
    db_session.add(offer2)
    db_session.commit()
    assert campaign.fund.get_progress() == {"total": 10, "reserved": 1, "submitted": 1}


def test_get_progress_one_reserved_offer_one_submitted_offer(
    db_session, db_post, db_influencer_bob, db_influencer_alice, gig_factory, instagram_post_factory
):
    campaign = db_post.campaign
    campaign.state = "launched"
    campaign.units = 10

    offer = OfferService.create(campaign.id, db_influencer_bob.id)
    offer2 = OfferService.create(campaign.id, db_influencer_alice.id)

    with OfferService(offer) as actions:
        actions.reserve()
    with OfferService(offer2) as actions:
        actions.reserve()

    gig = gig_factory(
        state=GIG_STATES.APPROVED,
        offer=offer,
        post=db_post,
        instagram_post=instagram_post_factory(),
        is_verified=True,
    )

    db_session.add(gig)
    db_session.add(offer)
    db_session.add(offer2)
    db_session.commit()

    assert campaign.fund.get_progress() == {"total": 10, "reserved": 2, "submitted": 1}


def test_get_progress_one_submitted_offer(
    db_session, db_post, db_influencer_bob, gig_factory, instagram_post_factory
):
    campaign = db_post.campaign
    campaign.state = "launched"
    campaign.units = 10

    offer = OfferService.create(campaign.id, db_influencer_bob.id)

    with OfferService(offer) as actions:
        actions.reserve()

    gig = gig_factory(
        state=GIG_STATES.APPROVED,
        offer=offer,
        post=db_post,
        instagram_post=instagram_post_factory(),
        is_verified=True,
    )

    db_session.add(gig)
    db_session.add(offer)
    db_session.commit()

    assert campaign.fund.get_progress() == {"total": 10, "reserved": 1, "submitted": 1}


def test_get_progress_one_reserved_offer(db_session, db_post, db_influencer_bob):
    campaign = db_post.campaign
    campaign.state = "launched"
    campaign.units = 10

    offer = OfferService.create(campaign.id, db_influencer_bob.id)

    with OfferService(offer) as actions:
        actions.reserve()

    db_session.add(offer)
    db_session.commit()

    assert campaign.fund.get_progress() == {"total": 10, "reserved": 1, "submitted": 0}
