import datetime as dt

from takumi.gql.query import InfluencerCampaignQuery
from takumi.models import Campaign
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.offer import STATES as OFFER_STATES


def _get_campaign(username, campaign_id):
    return InfluencerCampaignQuery().resolve_influencer_campaign(
        "info", username=username, campaign_id=campaign_id
    )


def test_get_active_campaigns_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.ACCEPTED

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_active_campaigns("info", username=db_influencer.username)
            .all()
        )
        assert len(campaigns) == 1
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_get_requested_campaigns_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.REQUESTED

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_requested_campaigns("info", username=db_influencer.username)
            .all()
        )
        assert len(campaigns) == 1
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_get_requested_campaigns_for_influencer_includes_fulfilled_campaign_if_still_launched(
    client, db_session, db_influencer, developer_user, db_offer, db_post, offer_factory
):

    # Set up the campaign(Launched with 1 asset)
    db_offer.campaign.units = 1
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    db_offer.state = OFFER_STATES.REQUESTED

    # Accepted offer by another influencer, making the campaign fulfilled
    accepted_offer = offer_factory(campaign=db_offer.campaign)
    accepted_offer.state = OFFER_STATES.ACCEPTED
    db_session.add(accepted_offer)
    db_session.commit()

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_requested_campaigns("info", username=db_influencer.username)
            .all()
        )
        assert len(campaigns) == 1
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_get_campaign_history_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post, db_payment
):
    # Make offer campaign active
    db_payment.successful = True
    db_offer.campaign.state = CAMPAIGN_STATES.COMPLETED

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_campaign_history("info", username=db_influencer.username)
            .all()
        )
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_get_awaiting_response_campaigns_for_influencer(
    client,
    db_session,
    db_influencer,
    db_post,
    developer_user,
    db_offer,
    campaign_factory,
    post_factory,
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Setup a public campaign targeted to influencer
    public_campaign = campaign_factory()
    public_campaign.public = True
    public_campaign.state = CAMPAIGN_STATES.LAUNCHED
    public_campaign.targeting.regions = [db_influencer.target_region]
    post = post_factory()
    post.campaign = public_campaign
    db_session.add(public_campaign)
    db_session.add(post)

    db_session.commit()

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_targeted_campaigns("info", username=db_influencer.username)
            .all()
        )
        assert len(campaigns) == 2

        assert campaigns[0].Campaign == public_campaign
        assert campaigns[0].Offer == None
        assert campaigns[0].Influencer == db_influencer

        assert campaigns[1].Campaign == db_offer.campaign
        assert campaigns[1].Offer == db_offer
        assert campaigns[1].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]
        assert _get_campaign(db_influencer.username, campaigns[1].Campaign.id) == campaigns[1]


def test_get_campaign_offer_revoked_or_rejected_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.state = OFFER_STATES.REJECTED
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_revoked_or_rejected_campaigns("info", username=db_influencer.username)
            .all()
        )

        assert len(campaigns) == 1
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_get_campaign_expired_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.state = OFFER_STATES.INVITED
    db_offer.campaign.state = CAMPAIGN_STATES.COMPLETED

    with client.user_request_context(developer_user):
        campaigns = (
            InfluencerCampaignQuery()
            .resolve_expired_campaigns("info", username=db_influencer.username)
            .all()
        )

        assert len(campaigns) == 1
        assert campaigns[0].Campaign == db_offer.campaign
        assert campaigns[0].Offer == db_offer
        assert campaigns[0].Influencer == db_offer.influencer
        assert _get_campaign(db_influencer.username, campaigns[0].Campaign.id) == campaigns[0]


def test_influencer_with_offer_in_draft_campaign_doesnt_see_campaign(
    client,
    db_session,
    db_influencer,
    db_post,
    developer_user,
    db_offer,
    campaign_factory,
    post_factory,
    offer_factory,
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Setup a draft campaign with an offer for influencer
    draft_campaign = campaign_factory()
    draft_campaign.public = True
    draft_campaign.state = CAMPAIGN_STATES.DRAFT
    draft_campaign.targeting.regions = [db_influencer.target_region]
    post = post_factory()
    post.campaign = draft_campaign
    draft_offer = offer_factory()
    draft_offer.influencer = db_influencer
    draft_offer.campaign = draft_campaign
    db_session.add(draft_offer)
    db_session.add(draft_campaign)
    db_session.add(post)

    db_session.commit()

    # Verify campaign not visible
    assert draft_campaign not in db_influencer.campaigns.with_entities(Campaign).all()

    draft_campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Verify visible after launching
    assert draft_campaign in db_influencer.campaigns.with_entities(Campaign).all()


def test_influencer_on_cooldown_for_advertiser_doesnt_see_public_campaigns_for_that_advertiser(
    client,
    db_session,
    db_influencer,
    db_post,
    developer_user,
    campaign_factory,
    post_factory,
    offer_factory,
):
    public_campaign = campaign_factory()
    public_campaign.public = True
    public_campaign.state = CAMPAIGN_STATES.LAUNCHED
    public_campaign.targeting.regions = [db_influencer.target_region]
    public_campaign.advertiser.influencer_cooldown = 1
    post = post_factory()
    post.campaign = public_campaign
    db_session.add(public_campaign)
    db_session.add(post)
    db_session.commit()

    # Verify campaign visible when no previous offers are there
    assert public_campaign in db_influencer.campaigns.with_entities(Campaign).all()

    # Setup a previous offer for influencer with same advertiser
    prev_campaign = campaign_factory()
    prev_campaign.state = CAMPAIGN_STATES.COMPLETED
    prev_campaign.advertiser = public_campaign.advertiser
    prev_offer = offer_factory()
    prev_offer.influencer = db_influencer
    prev_offer.campaign = prev_campaign
    prev_offer.state = OFFER_STATES.ACCEPTED
    prev_offer.accepted = dt.datetime.now(dt.timezone.utc)
    db_session.add(prev_offer)
    db_session.commit()

    # Verify campaign not visible when previous offer exists within cooldown period
    assert db_influencer.is_on_cooldown_for_advertiser(public_campaign.advertiser)
    assert public_campaign not in db_influencer.campaigns.with_entities(Campaign).all()

    # Change the date of offer accepted so that it happens before the cooldown period
    prev_offer.accepted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        days=public_campaign.advertiser.influencer_cooldown + 1
    )

    # Verify campaign visible when cooldown is over
    assert not db_influencer.is_on_cooldown_for_advertiser(public_campaign.advertiser)
    assert public_campaign in db_influencer.campaigns.with_entities(Campaign).all()

    # Verify campaign is not visible when influencer is in cooldown state
    db_influencer.state = INFLUENCER_STATES.COOLDOWN
    assert db_influencer.is_on_cooldown_for_advertiser(public_campaign.advertiser)
    assert public_campaign not in db_influencer.campaigns.with_entities(Campaign).all()
