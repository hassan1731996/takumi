import datetime as dt

import mock
import pytest

from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES
from takumi.services.exceptions import (
    CampaignFullyReservedException,
    CampaignNotLaunchedException,
    OfferNotClaimableException,
    OfferNotDispatchableException,
    OfferNotReservableException,
    OfferPushNotificationException,
)
from takumi.services.offer import OfferService


def test_offer_service_force_reserve_fails_if_offer_not_in_correct_state(offer):
    # Arrange
    offer.state = STATES.ACCEPTED

    # Act & Assert
    service = OfferService(offer)
    with pytest.raises(OfferNotReservableException):
        service.force_reserve()


def test_offer_service_force_reserve_fails_if_campaign_not_reservable(monkeypatch, offer):
    # Arrange
    monkeypatch.setattr("takumi.funds.assets.AssetsFund.is_reservable", lambda *args: False)
    offer.state = STATES.REJECTED

    # Act & Assert
    service = OfferService(offer)
    with pytest.raises(CampaignFullyReservedException):
        service.force_reserve()


def test_offer_service_force_reserve_fails_if_campaign_not_launched(monkeypatch, offer):
    # Arrange
    monkeypatch.setattr("takumi.funds.assets.AssetsFund.is_reservable", lambda *args: True)
    offer.state = STATES.REJECTED
    offer.campaign.state = CAMPAIGN_STATES.DRAFT

    # Act & Assert
    service = OfferService(offer)
    with pytest.raises(CampaignNotLaunchedException):
        service.force_reserve()


def test_offer_service_force_reserve_fails_if_deadline_passed(monkeypatch, offer, post):
    # Arrange
    monkeypatch.setattr("takumi.funds.assets.AssetsFund.is_reservable", lambda *args: True)
    offer.state = STATES.REJECTED
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    post.deadline = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)

    # Act
    service = OfferService(offer)
    with pytest.raises(OfferNotReservableException) as exc:
        service.force_reserve()

    # Assert
    assert "Deadline has already passed in this campaign" in exc.exconly()


def test_offer_service_force_reserve_success(monkeypatch, offer, post):
    # Arrange
    monkeypatch.setattr("takumi.funds.assets.AssetsFund.is_reservable", lambda *args: True)
    offer.state = STATES.REJECTED
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    post.deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)

    # Act
    service = OfferService(offer)
    service.force_reserve()

    # Assert
    assert offer.state == STATES.ACCEPTED


def test_offer_service_set_claimable_raises_if_state_not_accepted(offer):
    offer.state = STATES.INVITED

    service = OfferService(offer)
    with pytest.raises(OfferNotClaimableException):
        service.set_claimable()


def test_offer_service_set_claimable_raises_if_not_enough_gigs_claimable(
    offer, campaign, monkeypatch
):
    offer.state = STATES.ACCEPTED
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=2)
    )
    monkeypatch.setattr(
        "takumi.models.offer.Offer.gigs",
        [mock.Mock(is_claimable=True), mock.Mock(is_claimable=False)],
    )

    service = OfferService(offer)

    with pytest.raises(OfferNotClaimableException) as exc:
        service.set_claimable()

    assert "All gigs need to have passed the review" in exc.exconly()


def test_offer_service_set_claimable_sets_claimable(offer, campaign, monkeypatch):
    offer.is_claimable = False
    offer.state = STATES.ACCEPTED
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=2)
    )
    monkeypatch.setattr(
        "takumi.models.offer.Offer.gigs",
        [mock.Mock(is_passed_review_period=True), mock.Mock(is_passed_review_period=True)],
    )

    service = OfferService(offer)
    service.set_claimable()

    assert offer.is_claimable is True


def test_offer_service_mark_dispatched_sets_in_transit(offer):
    offer.state = STATES.ACCEPTED
    offer.campaign.shipping_required = True
    tracking_code = "offer tracking code"

    service = OfferService(offer)
    service.mark_dispatched(tracking_code)

    assert offer.tracking_code == tracking_code
    assert offer.in_transit


def test_offer_service_mark_dispatched_fails_for_non_shipping_campaign(offer):
    offer.state = STATES.ACCEPTED
    offer.campaign.shipping_required = False

    service = OfferService(offer)

    with pytest.raises(OfferNotDispatchableException):
        service.mark_dispatched()


def test_offer_service_mark_dispatched_fails_for_not_accepted_offer(offer):
    offer.state = STATES.INVITED
    offer.campaign.shipping_required = True

    service = OfferService(offer)

    with pytest.raises(OfferNotDispatchableException):
        service.mark_dispatched()


def test_offer_service_revoke_offer(offer):
    offer.state = STATES.ACCEPTED

    service = OfferService(offer)
    service.revoke()

    assert offer.state == STATES.REVOKED


def test_offer_service_last_gig_submitted_sets_payable_to_expected_timestamp(offer, posted_gig):
    assert offer.payable is None
    service = OfferService(offer)
    service.last_gig_submitted()
    assert offer.payable is not None
    assert offer.payable == posted_gig.claimable_time


def test_offer_send_push_notification_raises_exception_if_states_are_invalid(monkeypatch, offer):
    # Arrange
    monkeypatch.setattr("takumi.models.Influencer.device", True)
    offer.state = STATES.REVOKED
    service = OfferService(offer)

    # Act
    with pytest.raises(OfferPushNotificationException) as exc:
        service.send_push_notification()

    # Assert
    assert "Cannot send a push notification for offer in revoked state" in exc.exconly()


def test_offer_send_push_notification_raises_exception_if_campaign_is_not_launched(
    monkeypatch, offer, post
):
    # Arrange
    monkeypatch.setattr("takumi.models.Influencer.has_device", True)
    offer.campaign.state = CAMPAIGN_STATES.DRAFT
    service = OfferService(offer)

    # Act
    with pytest.raises(OfferPushNotificationException) as exc:
        service.send_push_notification()

    # Assert
    assert (
        "Can't send a push notification for a campaign in draft state. Campaign needs to be launched"
        in exc.exconly()
    )


def test_offer_send_push_notification_raises_exception_if_all_gigs_are_submitted(
    offer, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.models.Influencer.has_device", True)
    monkeypatch.setattr("takumi.models.offer.Offer.has_all_gigs", lambda x: True)
    service = OfferService(offer)

    # Act
    with pytest.raises(OfferPushNotificationException) as exc:
        service.send_push_notification()

    # Assert
    assert "Offer already has all gigs. Cannot send push notification" in exc.exconly()


def test_offer_send_push_notification_sends_default_pn_message(
    monkeypatch, offer, post, device_factory
):
    monkeypatch.setattr("takumi.models.Influencer.device", device_factory())
    monkeypatch.setattr("takumi.models.Influencer.has_device", True)
    # Arrange
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    offer.campaign.push_notification_message = None
    offer.campaign.advertiser.name = "1337"
    service = OfferService(offer)

    # Act
    with mock.patch("takumi.services.offer.OfferLog.add_event") as mock_send_pn_event:
        service.send_push_notification()

    # Assert
    mock_send_pn_event.assert_called_once_with(
        "send_push_notification", dict(message="New campaign opportunity from 1337")
    )


def test_offer_send_push_notification_sends_campaign_pn_message(
    monkeypatch, offer, post, device_factory
):
    monkeypatch.setattr("takumi.models.Influencer.device", device_factory())
    monkeypatch.setattr("takumi.models.Influencer.has_device", True)
    # Arrange
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    offer.campaign.push_notification_message = "Wabba labba dub duub"
    service = OfferService(offer)

    # Act
    with mock.patch("takumi.services.offer.OfferLog.add_event") as mock_send_pn_event:
        service.send_push_notification()

    # Assert
    mock_send_pn_event.assert_called_once_with(
        "send_push_notification", dict(message="Wabba labba dub duub")
    )


def test_offer_send_push_notification_no_device_raises_error(monkeypatch, offer, post):
    monkeypatch.setattr("takumi.models.Influencer.device", None)
    # Arrange
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    offer.campaign.push_notification_message = "Wabba labba dub duub"
    service = OfferService(offer)

    # Act
    with pytest.raises(OfferPushNotificationException) as exc:
        service.send_push_notification()

    assert "has no registered device" in exc.exconly()


def test_offer_update_engagements_per_post(offer):
    service = OfferService(offer)
    with mock.patch("takumi.models.offer.Offer.calculate_engagements_per_post", return_value=100):
        with mock.patch(
            "takumi.services.offer.OfferLog.add_event"
        ) as mock_update_engagements_event:
            service.update_engagements_per_post()

    assert mock_update_engagements_event.called
    mock_update_engagements_event.assert_called_once_with(
        "update_engagement",
        {"engagements_per_post": 100, "old_engagements_per_post": offer.engagements_per_post},
    )


def test_offer_reject_when_pending_participation_request(offer):
    offer.state = STATES.PENDING

    OfferService(offer).reject()

    assert offer.state == STATES.REJECTED
