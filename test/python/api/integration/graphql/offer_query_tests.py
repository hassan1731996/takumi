from test.python.api.utils import (
    _gig,
    _influencer,
    _instagram_post,
    _instagram_post_insight,
    _offer,
)

import mock

from takumi.gql.query.offer import OfferQuery
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES as OFFER_STATES


def test_get_active_offers_for_influencer(client, db_influencer, developer_user, db_offer, db_post):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.ACCEPTED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="active"
        )
        assert offers.all() == [db_offer]


def test_get_requested_offers_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.REQUESTED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="requested"
        )
        assert offers.all() == [db_offer]


def test_get_offer_history_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post, db_payment
):
    # Make offer campaign active
    db_payment.successful = True
    db_offer.campaign.state = CAMPAIGN_STATES.COMPLETED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="history"
        )
        assert offers.all() == [db_offer]


def test_get_awaiting_response_offers_for_influencer(
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
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="awaiting_response"
        )
        assert [offer.campaign for offer in offers] == [public_campaign, db_offer.campaign]


def test_get_offer_revoked_or_rejected_for_influencer(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.state = OFFER_STATES.REJECTED
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="revoked_or_rejected"
        )
        assert offers.all() == [db_offer]


def test_get_offer_expired_for_influencer(client, db_influencer, developer_user, db_offer, db_post):
    # Make offer campaign active
    db_offer.state = OFFER_STATES.INVITED
    db_offer.campaign.state = CAMPAIGN_STATES.COMPLETED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="expired"
        )
        assert offers.all() == [db_offer]


def test_get_offers_for_influencer_no_params(
    client, db_influencer, developer_user, db_offer, db_post
):
    # Make offer campaign active
    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer("info", username=db_influencer.username)
        assert offers.all() == [db_offer]


def test_get_offers_for_two_differently_targeted_influencers(
    client, db_session, db_influencer, developer_user, db_offer, db_post, influencer_factory
):

    db_offer.campaign.state = CAMPAIGN_STATES.LAUNCHED
    other_influencer = influencer_factory()
    db_session.add(other_influencer)
    db_session.commit()

    with client.user_request_context(developer_user):
        offers = OfferQuery().resolve_offers_for_influencer(
            "info", username=db_influencer.username, state="awaiting_response"
        )
        assert offers == [db_offer]

        offers_for_other_influencer = OfferQuery().resolve_offers_for_influencer(
            "info", username=other_influencer.username, state="awaiting_response"
        )
        assert offers_for_other_influencer == []


def test_facebook_link_missing_flag(monkeypatch, db_offer):
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.requires_facebook", mock.PropertyMock(return_value=True)
    )
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.has_facebook_page",
        mock.PropertyMock(return_value=False),
    )
    assert db_offer.facebook_link_missing is True
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.requires_facebook", mock.PropertyMock(return_value=True)
    )
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.has_facebook_page",
        mock.PropertyMock(return_value=True),
    )
    assert db_offer.facebook_link_missing is False
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.requires_facebook", mock.PropertyMock(return_value=False)
    )
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.has_facebook_page",
        mock.PropertyMock(return_value=True),
    )
    assert db_offer.facebook_link_missing is False
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.requires_facebook", mock.PropertyMock(return_value=False)
    )
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.has_facebook_page",
        mock.PropertyMock(return_value=False),
    )
    assert db_offer.facebook_link_missing is False


def test_resolve_top_offers_in_campaign_accepted(
    db_offer, db_session, client, account_manager, db_instagram_post_insight
):
    db_offer.state = OFFER_STATES.ACCEPTED
    db_instagram_post_insight.engagement = 100
    db_session.commit()

    with client.user_request_context(account_manager):
        offers = OfferQuery().resolve_top_offers_in_campaign("info", db_offer.campaign.id)

    assert db_offer in offers


def test_resolve_top_offers_in_campaign_ordering(
    db_offer,
    db_session,
    client,
    account_manager,
    db_campaign,
    db_influencer,
    db_gig,
    db_post,
    db_instagram_post_insight,
    influencer_user,
    db_region,
):
    additional_influencer = _influencer(influencer_user, db_region)
    additional_offer = _offer(db_campaign, additional_influencer)
    additional_offer.state = OFFER_STATES.ACCEPTED
    additional_gig = _gig(db_post, additional_offer)
    additional_instagram_post = _instagram_post(additional_gig)
    additional_instagram_post_insight = _instagram_post_insight(additional_instagram_post)
    additional_instagram_post_insight.engagement = 13.5
    additional_gig.instagram_post.instagram_post_insights.append(additional_instagram_post_insight)
    db_offer.state = OFFER_STATES.ACCEPTED
    db_instagram_post_insight.engagement = 24.5
    db_session.commit()

    with client.user_request_context(account_manager):
        offers = OfferQuery().resolve_top_offers_in_campaign("info", db_offer.campaign.id)

    expected_offers_ordering = [db_offer, additional_offer]
    assert expected_offers_ordering == offers
