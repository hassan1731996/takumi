from takumi.gql.mutation.influencer_campaign import (
    RejectCampaign,
    RequestParticipationInCampaign,
    ReserveCampaign,
)
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES as OFFER_STATES


def test_influencer_campaign_reserve_campaign_reserves_campaign(
    client, developer_user, db_session, db_campaign, db_offer, es_influencer, campaign_factory
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.influencer = es_influencer

    public_campaign = campaign_factory()
    public_campaign.state = CAMPAIGN_STATES.LAUNCHED
    public_campaign.public = True
    public_campaign.targeting.regions = [es_influencer.target_region]
    db_session.add(public_campaign)
    db_session.add(db_campaign)
    db_session.commit()

    # Act
    with client.user_request_context(developer_user):
        reserved_offer = ReserveCampaign.mutate(
            "root", "info", db_campaign.id, username=es_influencer.username
        ).offer
        public_offer = ReserveCampaign.mutate(
            "root", "info", public_campaign.id, username=es_influencer.username
        ).offer

    # Assert
    assert reserved_offer == db_offer
    assert db_offer.state == OFFER_STATES.ACCEPTED
    assert public_offer.state == OFFER_STATES.ACCEPTED


def test_influencer_campaign_request_participation_requests_participation_campaign(
    client, developer_user, db_session, db_campaign, db_offer, es_influencer, campaign_factory
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.apply_first = True
    db_offer.influencer = es_influencer
    db_offer.state = OFFER_STATES.PENDING

    public_campaign = campaign_factory()
    public_campaign.apply_first = True
    public_campaign.state = CAMPAIGN_STATES.LAUNCHED
    public_campaign.public = True
    public_campaign.targeting.regions = [es_influencer.target_region]
    db_session.add(public_campaign)
    db_session.add(db_campaign)
    db_session.commit()

    # Act
    with client.user_request_context(developer_user):
        requested_offer = RequestParticipationInCampaign.mutate(
            "root",
            "info",
            db_campaign.id,
            answers=[dict(question="what is your favorite color?", answer="turqoise")],
            username=es_influencer.username,
        ).offer
        public_offer = RequestParticipationInCampaign.mutate(
            "root", "info", public_campaign.id, username=es_influencer.username
        ).offer

    # Assert
    assert requested_offer == db_offer
    assert db_offer.state == OFFER_STATES.REQUESTED
    assert public_offer.state == OFFER_STATES.REQUESTED

    # Test that answers went through
    assert len(requested_offer.answers) == 1
    assert len(public_offer.answers) == 0


def test_influencer_campaign_request_participation_twice_is_allowed(
    client, db_session, db_campaign, db_offer, es_influencer
):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.apply_first = True
    db_offer.influencer = es_influencer
    db_offer.state = OFFER_STATES.PENDING

    db_session.add(db_campaign)
    db_session.commit()

    with client.user_request_context(db_offer.influencer.user):
        response = RequestParticipationInCampaign().mutate(
            "info", username=db_offer.influencer.username, campaign_id=db_offer.campaign.id
        )

    assert response.offer.state == OFFER_STATES.REQUESTED

    with client.user_request_context(db_offer.influencer.user):
        response = RequestParticipationInCampaign().mutate(
            "info", username=db_offer.influencer.username, campaign_id=db_offer.campaign.id
        )

    assert response.offer.state == OFFER_STATES.REQUESTED


def test_influencer_campaign_reject_campaign_rejects_campaign(
    client, developer_user, db_session, db_campaign, db_offer, es_influencer, campaign_factory
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.influencer = es_influencer
    db_offer.state = OFFER_STATES.INVITED

    public_campaign = campaign_factory()
    public_campaign.state = CAMPAIGN_STATES.LAUNCHED
    public_campaign.public = True
    public_campaign.targeting.regions = [es_influencer.target_region]
    db_session.add(public_campaign)
    db_session.add(db_campaign)
    db_session.commit()

    # Act
    with client.user_request_context(developer_user):
        rejected_offer = RejectCampaign.mutate(
            "root", "info", db_campaign.id, username=es_influencer.username
        ).offer
        public_offer = RejectCampaign.mutate(
            "root", "info", public_campaign.id, username=es_influencer.username
        ).offer

    # Assert
    assert rejected_offer == db_offer
    assert rejected_offer.state == OFFER_STATES.REJECTED
    assert public_offer.state == OFFER_STATES.REJECTED
