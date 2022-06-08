from __future__ import division

import mock
import pytest

from takumi.services.exceptions import CampaignFullyReservedException
from takumi.services.offer import OfferService

MILLION = 1_000_000


def test_reach_budget_doesnt_reach_target_succeeds_campaign_not_reserved(
    db_session, db_reach_campaign, db_influencer_alice, db_influencer_bob, db_reach_post
):

    db_influencer_alice.instagram_account.followers = MILLION / 2
    db_influencer_bob.instagram_account.followers = (MILLION / 2) - 1
    db_reach_campaign.units = MILLION
    db_reach_campaign.state = "launched"
    db_reach_campaign.posts = [db_reach_post]

    alice_offer = OfferService.create(db_reach_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_reach_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_reach_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()

    db_session.add(alice_offer)
    db_session.commit()

    with OfferService(bob_offer) as actions:
        actions.reserve()

    db_session.add(bob_offer)
    db_session.commit()
    # No exception should be thrown. Reservations succeed

    assert not db_reach_campaign.is_fully_reserved()


def test_reach_budget_reaches_exact_target_succeeds_campaign_reserved(
    db_session, db_reach_campaign, db_influencer_alice, db_influencer_bob, db_reach_post
):

    db_influencer_alice.instagram_account.followers = MILLION / 2
    db_influencer_bob.instagram_account.followers = MILLION / 2
    db_reach_campaign.units = MILLION
    db_reach_campaign.state = "launched"
    db_reach_campaign.posts = [db_reach_post]

    alice_offer = OfferService.create(db_reach_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_reach_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_reach_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    with OfferService(bob_offer) as actions:
        actions.reserve()
    db_session.add(bob_offer)
    db_session.commit()

    # No exception should be thrown. Reservations succeed
    with mock.patch("takumi.funds.reach.ReachFund.minimum_reservations_met", return_value=True):
        assert db_reach_campaign.is_fully_reserved()


def test_reach_fund_reserve_filled_campaign_throws_exception(
    db_session, db_reach_campaign, db_influencer_alice, db_influencer_bob, db_reach_post
):

    db_influencer_alice.instagram_account.followers = MILLION
    db_influencer_bob.instagram_account.followers = MILLION / 2
    db_reach_campaign.units = MILLION
    db_reach_campaign.state = "launched"
    db_reach_campaign.posts = [db_reach_post]

    alice_offer = OfferService.create(db_reach_campaign.id, db_influencer_alice.id)
    bob_offer = OfferService.create(db_reach_campaign.id, db_influencer_bob.id)

    db_session.add(alice_offer)
    db_session.add(bob_offer)
    db_session.add(db_influencer_alice)
    db_session.add(db_influencer_bob)
    db_session.add(db_reach_campaign)
    db_session.commit()

    with OfferService(alice_offer) as actions:
        actions.reserve()
    db_session.add(alice_offer)
    db_session.commit()

    with mock.patch("takumi.funds.reach.ReachFund.minimum_reservations_met", return_value=True):
        assert db_reach_campaign.is_fully_reserved()

        # Exception should be thrown. This reservation should fail
        with pytest.raises(CampaignFullyReservedException):
            with OfferService(bob_offer) as actions:
                actions.reserve()
