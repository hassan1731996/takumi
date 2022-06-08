import mock

from takumi.gql.mutation.offer import MakeCustomOffer, RequestParticipation
from takumi.models.offer import STATES as OFFER_STATES


def test_offer_request_participation_twice_is_allowed(client, db_session, db_campaign, db_offer):
    db_offer.state = OFFER_STATES.PENDING
    db_session.commit()

    with client.user_request_context(db_offer.influencer.user):
        response = RequestParticipation().mutate("info", id=db_offer.id)

    assert response.offer.state == OFFER_STATES.REQUESTED

    with client.user_request_context(db_offer.influencer.user):
        response = RequestParticipation().mutate("info", id=db_offer.id)

    assert response.offer.state == OFFER_STATES.REQUESTED


def test_offer_make_custom_offer_doesnt_notify_if_no_device(
    client, db_session, db_campaign, db_influencer, db_developer_user
):
    assert db_influencer.has_device is False

    with mock.patch("takumi.services.offer.OfferService.send_push_notification") as mock_push:
        with client.user_request_context(db_developer_user):
            response = MakeCustomOffer().mutate(
                "info",
                campaign_id=db_campaign.id,
                username=db_influencer.username,
                reward=100_00,
                force_reserve=False,
            )

    assert response.offer.state == OFFER_STATES.INVITED
    assert mock_push.called is False


def test_offer_make_custom_offer_does_notify_if_device(
    client, db_session, db_campaign, db_influencer, db_developer_user, device_factory
):
    db_influencer.user.device = device_factory()
    db_session.commit()

    assert db_influencer.has_device is True

    with mock.patch("takumi.services.offer.OfferService.send_push_notification") as mock_push:
        with client.user_request_context(db_developer_user):
            response = MakeCustomOffer().mutate(
                "info",
                campaign_id=db_campaign.id,
                username=db_influencer.username,
                reward=100_00,
                force_reserve=False,
            )

    assert response.offer.state == OFFER_STATES.INVITED
    assert mock_push.called is True
