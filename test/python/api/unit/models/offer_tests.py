# encoding=utf-8

import datetime as dt

import mock
import pytest

from takumi.models import Gig
from takumi.models.offer import STATES


@pytest.fixture(scope="function")
def new_offer(offer):
    offer.state = STATES.INVITED
    yield offer


@pytest.fixture(scope="function")
def accepted_offer(offer):
    offer.state = STATES.ACCEPTED
    offer.accepted = dt.datetime.now(dt.timezone.utc)
    yield offer


def test_new_offer_can_reject(new_offer):
    assert new_offer.can_reject() is True


def test_accepted_offer_can_not_reject_with_gigs(accepted_offer, gig):
    accepted_offer.gigs = [gig]
    assert accepted_offer.can_reject() is False


def test_accepted_offer_can_not_reject_without_gigs_but_in_transit(accepted_offer):
    accepted_offer.in_transit = True
    assert accepted_offer.can_reject() is False


def test_accepted_offer_can_not_reject_if_1h_has_passed_since_accepting(accepted_offer):
    accepted_offer.in_transit = False
    accepted_offer.gigs = []
    accepted_offer.accepted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1, minutes=1)
    assert accepted_offer.can_reject() is False


def test_accepted_offer_can_reject_if_less_than_1h_has_passed_since_accepting(accepted_offer):
    assert (dt.datetime.now(dt.timezone.utc) - accepted_offer.accepted) < dt.timedelta(hours=1)
    assert accepted_offer.can_reject() is True


def test_accepted_offer_can_not_reject_if_less_than_1h_has_passed_since_accepting_in_apply_first(
    accepted_offer,
):
    accepted_offer.campaign.apply_first = True
    assert (dt.datetime.now(dt.timezone.utc) - accepted_offer.accepted) < dt.timedelta(hours=1)
    assert accepted_offer.can_reject() is False


def test_offer_is_paid_no_payment_is_false(accepted_offer):
    # Offer.payment == None                        = False (no payment has ever been attempted)
    assert accepted_offer.payment is None
    assert accepted_offer.is_paid is False


def test_offer_is_paid_payment_is_not_successful_is_false(accepted_offer, payment):
    # Offer.payment && payment.successful == False = False (has a failed payment)
    payment.successful = False
    assert accepted_offer.is_paid is False


def test_offer_is_paid_payment_is_pending_is_true(accepted_offer, payment):
    # Offer.payment && payment.successful == None  = True (payment is pending)
    payment.successful = None
    assert accepted_offer.payment == payment
    assert accepted_offer.is_paid is True


def test_offer_is_paid_payment_is_successful_is_true(accepted_offer, payment):
    # Offer.payment && payment.successful == True  = True (payment has been sucessfully made)
    payment.successful = True
    assert accepted_offer.is_paid is True


def test_offer_calculate_engagements_per_post_with_no_live_gigs_uses_influencer_estimate(
    accepted_offer, post, influencer
):
    with mock.patch(
        "takumi.models.Influencer.estimated_engagements_per_post",
        new_callable=mock.PropertyMock,
        return_value=100,
    ):  # noqa: E501
        assert (
            accepted_offer.calculate_engagements_per_post()
            == influencer.estimated_engagements_per_post
        )


def test_offer_calculate_engagements_per_post_with_live_gig_uses_instagram_post_engagement(
    accepted_offer, influencer, instagram_post
):
    with mock.patch(
        "takumi.models.Influencer.estimated_engagements_per_post",
        new_callable=mock.PropertyMock,
        return_value=100,
    ):  # noqa: E501
        assert accepted_offer.calculate_engagements_per_post() == instagram_post.engagements


def test_offer_calculate_engagements_per_post_with_unposted_but_also_live_gigs_uses_estimates_and_real_engagements(
    monkeypatch, accepted_offer, influencer, instagram_post
):

    # Arrange
    n_posts = 2
    instagram_post.comments = 50
    instagram_post.likes = 50
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=n_posts)
    )
    expected_engagements_per_post = (100 + instagram_post.engagements) / n_posts
    non_live_gig = Gig(offer_id=accepted_offer.id)
    accepted_offer.gigs.append(non_live_gig)

    with mock.patch(
        "takumi.models.Influencer.estimated_engagements_per_post",
        new_callable=mock.PropertyMock,
        return_value=100,
    ):  # noqa: E501
        assert accepted_offer.calculate_engagements_per_post() == expected_engagements_per_post
