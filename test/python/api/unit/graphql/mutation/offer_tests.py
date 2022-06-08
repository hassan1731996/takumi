import mock
import pytest

from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.offer import (
    MakeOffer,
    RevokeOffer,
    SendOfferPushNotification,
    UpdateReward,
)
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.services import OfferService


def test_make_offer_mutation_calls_offer_service(offer, campaign, influencer, monkeypatch):
    campaign.state = CAMPAIGN_STATES.LAUNCHED
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.models.influencer.Influencer.has_device", lambda *args: True)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)

    with mock.patch.object(OfferService, "create") as create_offer_mock:
        with mock.patch.object(OfferService, "send_push_notification") as send_pn_mock:
            create_offer_mock.return_value = offer
            MakeOffer().mutate(
                "info", campaign_id=campaign.id, influencer_id=influencer.id, skip_targeting=False
            )

    create_offer_mock.assert_called_once_with(campaign.id, influencer.id, skip_targeting=False)
    send_pn_mock.assert_called_once_with()


def test_cancel_offer_mutation_calls_offer_service(offer, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.offer.get_offer_or_404", lambda _: offer)

    with mock.patch.object(OfferService, "revoke") as revoke_offer_mock:
        RevokeOffer().mutate("info", offer.id)

    revoke_offer_mock.assert_called_once_with()


def test_update_reward_mutation_calls_offer_service(offer, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.offer.get_offer_or_404", lambda _: offer)

    with mock.patch.object(OfferService, "update_reward") as update_reward:
        UpdateReward().mutate("info", offer.id, 100)

    update_reward.assert_called_once_with(100 * 100)


def test_send_push_notification_calls_offer_service(offer, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.offer.get_offer_or_404", lambda _: offer)

    with mock.patch.object(OfferService, "send_push_notification") as mock_send_pn:
        SendOfferPushNotification().mutate("info", id=offer.id)

    mock_send_pn.assert_called_once_with()


def test_send_push_notification_raises_exception_if_campaign_is_fully_reserved(
    offer, post, monkeypatch
):
    # Arrange
    offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    monkeypatch.setattr("takumi.gql.mutation.offer.get_offer_or_404", lambda _: offer)
    monkeypatch.setattr("takumi.models.campaign.Campaign.is_fully_reserved", lambda x: True)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)

    # Act
    with pytest.raises(MutationException) as exc:
        SendOfferPushNotification().mutate("info", id=offer.id)

    # Assert
    assert "Can't send a push notification for a fully reserved campaign" in exc.exconly()
