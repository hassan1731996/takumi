# encoding=utf-8

import mock
import pytest

from takumi.events import EventApplicationException, InvalidStartStateException
from takumi.events.offer import OfferLog
from takumi.models import Offer
from takumi.models.offer import STATES as OFFER_STATES


def test_create_offer_invite_event(campaign, influencer):
    # Arrange
    offer = Offer()
    log = OfferLog(offer)

    # Act
    log.add_event(
        "create_invite",
        dict(
            campaign_id=campaign.id,
            influencer_id=influencer.id,
            vat_percentage=0.19,
            reward=100 * 100,
            followers_per_post=25 * 1000,
            engagements_per_post=200,
        ),
    )

    # Assert
    assert offer.state == OFFER_STATES.INVITED


def test_create_new_pending_event(campaign, influencer):
    # Arrange
    offer = Offer()
    log = OfferLog(offer)

    # Act
    log.add_event(
        "create",
        dict(
            campaign_id=campaign.id,
            influencer_id=influencer.id,
            vat_percentage=0.19,
            reward=100 * 100,
            followers_per_post=25 * 1000,
            engagements_per_post=200,
        ),
    )

    # Assert
    assert offer.state == OFFER_STATES.PENDING


def test_request_participation_requests_an_offer_for_participation(offer):
    # Arrange
    offer.state = OFFER_STATES.PENDING
    log = OfferLog(offer)

    # Act
    log.add_event("request_participation")

    # Assert
    assert offer.state == OFFER_STATES.REQUESTED


def test_set_as_candidate_sets_offer_as_candidate(offer):
    # Arrange
    offer.state = OFFER_STATES.REQUESTED
    log = OfferLog(offer)

    # Act
    log.add_event("set_as_candidate")

    # Assert
    assert offer.state == OFFER_STATES.CANDIDATE


def test_approve_candidate_approved_offer_as_brand(offer):
    # Arrange
    offer.state = OFFER_STATES.CANDIDATE
    log = OfferLog(offer)

    # Act
    log.add_event("approve_candidate")

    # Assert
    assert offer.state == OFFER_STATES.APPROVED_BY_BRAND


def test_reject_candidate_approved_offer_as_brand(offer):
    # Arrange
    offer.state = OFFER_STATES.CANDIDATE
    log = OfferLog(offer)

    # Act
    log.add_event("reject_candidate", {"reason": "reason"})

    # Assert
    assert offer.state == OFFER_STATES.REJECTED_BY_BRAND


def test_accept_requested_participation_accepts_an_offer(offer):
    # Arrange
    offer.state = OFFER_STATES.REQUESTED
    log = OfferLog(offer)

    # Act
    log.add_event("accept_requested_participation")

    # Assert
    assert offer.state == OFFER_STATES.ACCEPTED


def test_accept_brand_approved_requested_participation_accepts_an_offer(offer):
    # Arrange
    offer.state = OFFER_STATES.APPROVED_BY_BRAND
    log = OfferLog(offer)

    # Act
    log.add_event("accept_requested_participation")

    # Assert
    assert offer.state == OFFER_STATES.ACCEPTED


def test_reject_request_participation_rejects_an_offer(offer):
    # Arrange
    offer.state = OFFER_STATES.REQUESTED
    log = OfferLog(offer)

    # Act
    log.add_event("reject")

    # Assert
    assert offer.state == OFFER_STATES.REJECTED


def test_reserve_offer_reserves_an_offer(offer):
    # Arrange
    offer.state = OFFER_STATES.INVITED
    log = OfferLog(offer)

    # Act
    log.add_event("reserve")

    # Assert
    assert offer.state == OFFER_STATES.ACCEPTED


def test_reserves_offer_raises_exception_because_of_invalid_start_state(offer):
    # Arrange
    offer.state = OFFER_STATES.REVOKED
    log = OfferLog(offer)

    # Act
    with pytest.raises(EventApplicationException):
        log.add_event("reserve")

    # Assert
    assert offer.state == OFFER_STATES.REVOKED


def test_revoke_offer_revokes_offer_for_valid_start_states(app):
    # Arrange
    offer1 = Offer(state=OFFER_STATES.INVITED)
    offer2 = Offer(state=OFFER_STATES.ACCEPTED)
    log1 = OfferLog(offer1)
    log2 = OfferLog(offer2)

    # Act
    log1.add_event("revoke")
    log2.add_event("revoke")

    # Assert
    assert offer1.state == OFFER_STATES.REVOKED
    assert offer2.state == OFFER_STATES.REVOKED


def test_renew_offer_renews_revoked_offers_but_not_rejected(app):
    # Arrange
    offer1 = Offer(state=OFFER_STATES.REVOKED)
    offer2 = Offer(state=OFFER_STATES.REJECTED)
    log1 = OfferLog(offer1)
    log2 = OfferLog(offer2)

    # Act
    log1.add_event("renew")
    with pytest.raises(InvalidStartStateException):
        log2.add_event("renew")

    # Assert
    assert offer1.state == OFFER_STATES.INVITED
    assert offer2.state == OFFER_STATES.REJECTED


def test_set_offer_in_transit_sets_in_transit(offer):
    # Arrange
    offer.state = OFFER_STATES.ACCEPTED
    log = OfferLog(offer)

    # Act
    log.add_event("mark_dispatched")

    # Assert
    assert offer.in_transit


def test_set_offer_in_transit_sets_tracking_code(offer):
    # Arrange
    tracking_code = "offer tracking code"
    offer.state = OFFER_STATES.ACCEPTED
    log = OfferLog(offer)

    # Act
    log.add_event("mark_dispatched", {"tracking_code": tracking_code})

    # Assert
    assert offer.tracking_code == tracking_code


def test_set_offer_in_transit_raises_exception_because_of_invalid_start_state(offer):
    # Arrange
    offer.state = OFFER_STATES.INVITED
    log = OfferLog(offer)

    # Act
    with pytest.raises(EventApplicationException):
        log.add_event("mark_dispatched")

    # Assert
    assert offer.state == OFFER_STATES.INVITED


def test_set_offer_claimable(offer):
    assert offer.is_claimable is not True

    log = OfferLog(offer)
    log.add_event("set_claimable")

    assert offer.is_claimable is True


def test_send_push_notification_calls_send_offer_push_notification(offer, monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.has_device", mock.PropertyMock(return_value=True)
    )
    # Arrange
    log = OfferLog(offer)

    # Act
    with mock.patch("takumi.events.offer.NotificationClient.from_influencer") as mock_client:
        log.add_event("send_push_notification", {"message": 1337})

    # Assert
    mock_client.assert_called_with(offer.influencer)
    mock_client.return_value.send_offer.assert_called_with(offer, message=1337)


def test_offer_update_engagement_event(offer):
    log = OfferLog(offer)

    log.add_event("update_engagement", {"engagements_per_post": 12_345_123})
    assert offer.engagements_per_post == 12_345_123
