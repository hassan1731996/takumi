# encoding=utf-8

import datetime as dt

import pytest

from takumi.constants import MAX_FOLLOWERS_BEYOND_REWARD_POOL, MILLE
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services import OfferService
from takumi.services.exceptions import (
    OfferAlreadyExistsException,
    OfferNotRejectableException,
    OfferNotReservableException,
    ServiceException,
)


@pytest.fixture(autouse=True, scope="function")
def launch_db_campaign(db_campaign):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED


@pytest.fixture(scope="function")
def test_reach_campaign(db_session, db_reach_campaign, db_reach_post):
    db_reach_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_reach_campaign.units = 1_000_000
    db_session.commit()
    yield db_reach_campaign


@pytest.fixture(scope="function")
def test_accepted_offer(db_session, db_offer):
    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.accepted = dt.datetime.now(dt.timezone.utc)
    db_session.commit()
    yield db_offer


#############
# spec: 2.0 #
#############


def test_influencer_can_only_have_single_offer_for_campaign(db_influencer, db_campaign):
    """spec: 2.0.1

    "The influencer can only hold a single accepted offer for a particular campaign at one time"
    """
    OfferService.create(db_campaign.id, db_influencer.id)
    with pytest.raises(OfferAlreadyExistsException):
        OfferService.create(db_campaign.id, db_influencer.id)


def test_influencer_can_accept_or_decline_offer(db_influencer, db_campaign):
    """spec: 2.0.2

    "When an influencer receives an offer they can accept or decline the offer"
    """
    # accept
    offer1 = OfferService.create(db_campaign.id, db_influencer.id)
    with OfferService(offer1) as actions:
        actions.reserve()
    assert offer1.is_reserved

    with OfferService(offer1) as actions:
        actions.reject()
    assert not offer1.is_reserved


def test_influencer_can_no_longer_participate_in_a_campaign_after_declining_an_offer(
    db_session, db_offer, db_campaign
):
    """spec: 2.0.3

    "If they decline the offer, they can no longer participate in the campaign"
    """
    # Arrange
    db_offer.state = OFFER_STATES.REJECTED
    db_session.commit()
    assert not db_offer.is_reserved

    # Act
    with pytest.raises(OfferNotReservableException) as exc:
        OfferService(db_offer).reserve()

    # Assert
    assert "Cannot reserve rejected offer" in exc.exconly()


def test_influencer_can_reject_an_accepted_offer_within_1_hour(test_accepted_offer):
    """spec: 2.0.4

    "If the offer is accepted, the influencer can choose to cancel the offer until the time limit is up"
    """
    # Act
    with OfferService(test_accepted_offer) as actions:
        actions.reject()

    # Assert
    assert test_accepted_offer.state == OFFER_STATES.REJECTED


def test_influencer_can_not_reject_an_accepted_offer_after_1_hour(db_session, test_accepted_offer):
    """spec: 2.0.5

    "After that, their place in the campaign is locked in and they can no longer cancel"
    """
    # Arrange
    test_accepted_offer.accepted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    db_session.commit()

    # Act
    with pytest.raises(OfferNotRejectableException) as exc:
        OfferService(test_accepted_offer).reject()

    # Assert
    assert "This offer cannot be rejected" in exc.exconly()


def test_campaign_or_community_manager_can_revoke_a_non_claimable_offer(test_accepted_offer):
    """spec: 2.0.6

    "A campaign or community manager can revoke an offer at any time as long as the offer isn't claimable"
    """
    # Act
    with OfferService(test_accepted_offer) as actions:
        actions.revoke()

    # Assert
    assert test_accepted_offer.state == OFFER_STATES.REVOKED


def test_campaign_or_community_manager_can_not_revoke_a_claimable_offer(
    db_session, db_payable_offer
):
    """spec: 2.0.6

    "A campaign or community manager can revoke an offer at any time as long as the offer isn't claimable"
    """
    # Act
    with pytest.raises(ServiceException) as exc:
        OfferService(db_payable_offer).revoke()

    # Assert
    assert "Can't revoke a claimable offer" in exc.exconly()


# XXX: talk about how we should tackle 2.0.7


def test_a_revoked_offer_can_be_renewed_then_accepted(db_session, db_offer):
    """spec: 2.0.8

    "If an offer has been revoked by mistake, it can be either "renewed", causing it to go back to the "new"
    state where it can be accepted"
    """
    with OfferService(db_offer) as actions:
        actions.revoke()

    with OfferService(db_offer) as actions:
        actions.renew()
    assert db_offer.state == OFFER_STATES.INVITED

    with OfferService(db_offer) as actions:
        actions.reserve()
    assert db_offer.state == OFFER_STATES.ACCEPTED


def test_a_revoked_offer_can_be_force_reserved(db_session, db_offer):
    """spec: 2.0.9

    "it can be "force reserved" which makes it accepted"
    """
    with OfferService(db_offer) as actions:
        actions.revoke()

    with OfferService(db_offer) as actions:
        actions.force_reserve()

    assert db_offer.is_reserved is True


#############
# spec: 2.1 #
#############


def test_offer_has_fixed_reward_at_creation_time(db_campaign, db_influencer, db_post):
    """spec: 2.1.1

    "The offer has a fixed reward which is calculated at the time the offer is made"
    """
    # Arrange
    offer = OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert offer.reward is not None
    assert offer.reward != 0


def test_influencer_fixed_price_is_defined_by_the_campaign_pricing(
    db_session, db_influencer_bob, db_influencer_alice, db_campaign
):
    """spec: 2.1.2

    "The influencer is paid a fixed price defined by the campaign pricing"
    """
    # Arrange
    db_influencer_bob.instagram_account.followers = 10000
    db_influencer_alice.instagram_account.followers = 100_000_000
    db_session.commit()

    # Act
    offer_bob = OfferService.create(db_campaign.id, db_influencer_bob.id)
    offer_alice = OfferService.create(db_campaign.id, db_influencer_alice.id)

    # Assert
    assert offer_bob.reward is not None
    assert offer_bob.reward == offer_alice.reward


def test_number_of_followers_in_reach_reward_calculation_is_influencer_followers(
    db_session, db_influencer, test_reach_campaign
):
    """spec: 2.1.3

    "The number of followers used in the calculation is the minimum of the following:
        - The influencer's follower count
        - The remaining campaign reach + 25,000"
    """
    # Arrange
    db_influencer.instagram_account.followers = 20000
    test_reach_campaign.custom_reward_units = 550
    reward = 550 * 20000 / MILLE
    db_session.commit()

    # Act
    offer = OfferService.create(test_reach_campaign.id, db_influencer.id)

    # Assert
    assert offer.reward is not None
    assert offer.reward == reward


def test_number_of_followers_in_reach_reward_calculation_is_the_remaining_campaign_reach_plus_100k(
    db_session, db_influencer, test_reach_campaign
):
    """spec: 2.1.3

    "The number of followers used in the calculation is the minimum of the following:
        - The influencer's follower count
        - 200,000
        - The remaining campaign reach + 100,000"
    """
    # Arrange
    db_influencer.instagram_account.followers = 150_000
    test_reach_campaign.units = 5000
    test_reach_campaign.custom_reward_units = 550
    db_session.commit()

    reward = 550 * (test_reach_campaign.units + MAX_FOLLOWERS_BEYOND_REWARD_POOL) / MILLE
    # Reward is rounded down to nearest 100
    reward -= reward % 100

    # Act
    offer = OfferService.create(test_reach_campaign.id, db_influencer.id)

    # Assert
    assert offer.reward is not None
    assert offer.reward == reward
