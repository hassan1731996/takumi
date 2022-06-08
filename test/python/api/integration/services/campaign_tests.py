import datetime as dt
from test.python.api.utils import _gig, _instagram_story_frame_insight, _post, _story_frame

import mock
import pytest
from freezegun import freeze_time

from takumi.constants import ENGAGEMENT_PER_ASSET, REACH_PER_ASSET
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services.campaign import (
    CampaignCompleteException,
    CampaignLaunchException,
    CampaignService,
    InfluencerNotFound,
    InvalidCampaignStateException,
    InvalidOfferIdException,
    NegativePriceException,
    ServiceException,
)
from takumi.utils import uuid4_str


def test_campaign_service_get_by_id(db_campaign):
    campaign = CampaignService.get_by_id(db_campaign.id)
    assert campaign == db_campaign


def test_get_by_report_token_returns_campaign(db_campaign):
    # Act
    campaign = CampaignService.get_by_report_token(db_campaign.report_token)

    # Assert
    assert campaign == db_campaign


def test_get_by_report_token_returns_none_if_not_found(db_session):
    # Act & Assert
    assert CampaignService.get_by_report_token(uuid4_str()) is None


def test_campaign_service_create_campaign(db_advertiser, db_developer_user, market):
    # Act
    new_campaign = CampaignService.create_campaign(
        advertiser_id=db_advertiser.id,
        market=market,
        reward_model="reach",
        units=10,
        price=100_000,
        list_price=100_000,
        custom_reward_units=None,
        shipping_required=False,
        require_insights=False,
        name="name",
        description="description",
        pictures=["pictures"],
        prompts=[],
        owner_id=db_developer_user.id,
        campaign_manager_id=db_developer_user.id,
        secondary_campaign_manager_id=db_developer_user.id,
        community_manager_id=db_developer_user.id,
        tags=["UPPERCASE"],
        has_nda=True,
        brand_safety=True,
        extended_review=False,
        industry="Beauty",
        opportunity_product_id=None,
        brand_match=False,
        pro_bono=False,
    )

    # Assert
    res = CampaignService.get_by_id(new_campaign.id)
    assert new_campaign == res
    assert new_campaign.advertiser_id == db_advertiser.id
    assert new_campaign.market_slug == market.slug
    assert new_campaign.reward_model == "reach"
    assert new_campaign.units == 10
    assert new_campaign.shipping_required is False
    assert new_campaign.require_insights is False
    assert new_campaign.name == "name"
    assert new_campaign.description == "description"
    assert new_campaign.pictures == ["pictures"]
    assert new_campaign.tags == ["uppercase"]
    assert new_campaign.owner == db_developer_user
    assert new_campaign.campaign_manager == db_developer_user
    assert new_campaign.secondary_campaign_manager == db_developer_user
    assert new_campaign.community_manager == db_developer_user
    assert new_campaign.has_nda is True
    assert new_campaign.industry == "Beauty"
    assert new_campaign.brand_match is False
    assert new_campaign.apply_first is True


def test_campaign_service_update_units(db_campaign):
    assert db_campaign.units != 1337

    with CampaignService(db_campaign) as service:
        service.update_units(1337)

    assert db_campaign.units == 1337


def test_campaign_service_update_shipping_required(db_campaign):
    assert db_campaign.shipping_required is False

    with CampaignService(db_campaign) as service:
        service.update_shipping_required(True)

    assert db_campaign.shipping_required is True


def test_campaign_service_update_name(db_campaign):
    assert db_campaign.name != "new name"

    with CampaignService(db_campaign) as service:
        service.update_name("new name")

    assert db_campaign.name == "new name"


def test_campaign_service_update_description(db_campaign):
    assert db_campaign.description != "new description"

    with CampaignService(db_campaign) as service:
        service.update_description("new description")

    assert db_campaign.description == "new description"


def test_campaign_service_update_pictures(db_campaign):
    assert db_campaign.pictures != ["new picture"]

    with CampaignService(db_campaign) as service:
        service.update_pictures(["new pictures"])

    assert db_campaign.pictures == ["new pictures"]


def test_campaign_service_update_push_notification_message(db_campaign):
    assert db_campaign.push_notification_message != "new push notification message"

    with CampaignService(db_campaign) as service:
        service.update_push_notification_message("new push notification message")

    assert db_campaign.push_notification_message == "new push notification message"


def test_campaign_service_update_owner(db_campaign, db_developer_user):
    assert db_campaign.owner_id != db_developer_user.id

    with CampaignService(db_campaign) as service:
        service.update_owner(db_developer_user.id)

    assert db_campaign.owner_id == db_developer_user.id


def test_campaign_service_update_campaign_manager(db_campaign, db_developer_user):
    assert db_campaign.campaign_manager_id != db_developer_user.id

    with CampaignService(db_campaign) as service:
        service.update_campaign_manager(db_developer_user.id)

    assert db_campaign.campaign_manager_id == db_developer_user.id


def test_campaign_service_update_secondary_campaign_manager(db_campaign, db_developer_user):
    assert db_campaign.secondary_campaign_manager_id != db_developer_user.id

    with CampaignService(db_campaign) as service:
        service.update_secondary_campaign_manager(db_developer_user.id)

    assert db_campaign.secondary_campaign_manager_id == db_developer_user.id


def test_campaign_service_update_community_manager(db_campaign, db_developer_user):
    assert db_campaign.community_manager_id != db_developer_user.id

    with CampaignService(db_campaign) as service:
        service.update_community_manager(db_developer_user.id)

    assert db_campaign.community_manager_id == db_developer_user.id


def test_campaign_service_update_has_nda(db_campaign):
    assert db_campaign.has_nda is False

    with CampaignService(db_campaign) as service:
        service.update_has_nda(True)

    assert db_campaign.has_nda is True


def test_campaign_service_update_industry(db_campaign):
    assert db_campaign.industry != "Beauty"

    with CampaignService(db_campaign) as service:
        service.update_industry("Beauty")

    assert db_campaign.industry == "Beauty"


def test_campaign_service_update_public(db_campaign):
    assert db_campaign.public is False

    with CampaignService(db_campaign) as service:
        service.update_public(True)

    assert db_campaign.public is True


def test_campaign_service_stash(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with CampaignService(db_campaign) as service:
        service.stash()

    assert db_campaign.state == CAMPAIGN_STATES.STASHED


def test_campaign_service_restore(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.STASHED
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with CampaignService(db_campaign) as service:
        service.restore()

    assert db_campaign.state == CAMPAIGN_STATES.DRAFT


def test_campaign_service_restore_with_invalid_state_raises_exception(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(InvalidCampaignStateException) as exc:
        CampaignService(db_campaign).restore()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.DRAFT
    assert (
        "Campaign has to be in `stashed` state in order to restore. Current state: draft"
        in exc.exconly()
    )


def test_campaign_service_launch_fails_if_state_is_not_draft(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(CampaignLaunchException) as exc:
        CampaignService(db_campaign).launch()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.LAUNCHED
    assert (
        "Campaign has to be in draft state to be launched. Current state: launched" in exc.exconly()
    )


def test_campaign_service_launch_success(db_session, db_campaign, db_post, monkeypatch):
    # Arrange
    db_campaign.state = "draft"
    db_campaign.units = 10
    db_campaign.price = 850_000
    db_campaign.posts = [db_post]  # Needed to pass validation
    monkeypatch.setattr(
        "takumi.rewards.RewardCalculator.calculate_suggested_reward", mock.Mock(return_value=10000)
    )
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with CampaignService(db_campaign) as service:
        service.launch()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.LAUNCHED


def test_campaign_service_launch_fails_if_no_price(db_session, db_campaign, db_post):
    # Arrange
    db_campaign.state = "draft"
    db_campaign.price = 0
    db_campaign.posts = [db_post]  # Needed to pass validation
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(CampaignLaunchException) as exc:
        CampaignService(db_campaign).launch()

    # Assert
    assert db_campaign.state != CAMPAIGN_STATES.LAUNCHED
    assert "Campaign can't be launched without a price. Current budget: 0" in exc.exconly()


def test_campaign_service_launch_fails_if_post_has_min_gallery_photo_count(
    db_session, db_campaign, db_post
):
    # Arrange
    db_post.gallery_photo_count = -1
    db_campaign.state = "draft"
    db_campaign.posts = [db_post]  # Needed to pass validation
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(CampaignLaunchException) as exc:
        CampaignService(db_campaign).launch()

    # Assert
    assert db_campaign.state != CAMPAIGN_STATES.LAUNCHED
    assert (
        "Campaign has to have 0 to 3 `gallery photo count` in order to be launched" in exc.exconly()
    )


def test_campaign_service_launch_fails_if_post_has_max_gallery_photo_count(
    db_session, db_campaign, db_post
):
    # Arrange
    db_post.gallery_photo_count = 4
    db_campaign.state = "draft"
    db_campaign.posts = [db_post]  # Needed to pass validation
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(CampaignLaunchException) as exc:
        CampaignService(db_campaign).launch()

    # Assert
    assert db_campaign.state != CAMPAIGN_STATES.LAUNCHED
    assert (
        "Campaign has to have 0 to 3 `gallery photo count` in order to be launched" in exc.exconly()
    )


def test_campaign_service_new_report_token(db_campaign):
    # Arrange
    old_report_token = db_campaign.report_token

    # Act
    with CampaignService(db_campaign) as service:
        service.new_report_token()

    # Assert
    assert db_campaign.report_token != old_report_token


def test_campaign_service_preview_fails_for_non_existing_influencer(db_campaign):
    with pytest.raises(InfluencerNotFound) as exc:
        CampaignService(db_campaign).preview("non-existing influencer")

    assert "No influencer found with the username {}".format("non-existing ") in exc.exconly()


def test_campaign_service_preview_success(db_campaign, db_influencer, db_device):
    # Act
    db_influencer.user.device = db_device
    with mock.patch("takumi.services.campaign.NotificationClient.from_influencer") as mock_client:
        with CampaignService(db_campaign) as service:
            service.preview(db_influencer.username)

    # Assert
    assert mock_client.return_value.send_campaign.called


def test_campaign_service_complete_fails_if_state_is_not_launched(
    db_session, db_campaign, monkeypatch
):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.all_claimable", mock.PropertyMock(return_value=True)
    )
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(
        CampaignCompleteException, match="Campaign has to be in launched state to be completed"
    ):
        CampaignService(db_campaign).complete()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.DRAFT


def test_campaign_service_complete_fails_if_not_all_offers_are_claimable(
    db_session, db_campaign, monkeypatch
):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.all_claimable", mock.PropertyMock(return_value=False)
    )
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(
        CampaignCompleteException, match="Campaign has to be in launched state to be completed"
    ):
        CampaignService(db_campaign).complete()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.DRAFT


def test_campaign_service_complete_fails_if_there_are_no_reserved_offers(
    db_session, db_campaign, db_offer, monkeypatch
):
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.all_claimable", mock.PropertyMock(return_value=False)
    )
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(
        CampaignCompleteException,
        match="Campaign needs at least one reserved offer to be completed",
    ):
        CampaignService(db_campaign).complete()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.DRAFT


def test_campaign_service_complete_success(db_session, db_campaign, db_offer, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.all_claimable", mock.PropertyMock(return_value=True)
    )
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.ACCEPTED
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with CampaignService(db_campaign) as service:
        service.complete()

    # Assert
    assert db_campaign.state == CAMPAIGN_STATES.COMPLETED


def test_get_submissions_count_returns_count_of_total_submissions(
    db_campaign, db_post, offer_factory, gig_factory
):
    # Arrange
    offer_1 = offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)
    offer_2 = offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)
    offer_3 = offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)
    offer_4 = offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)

    gig_factory(offer=offer_1, post=db_post, state=GIG_STATES.SUBMITTED)
    gig_factory(offer=offer_2, post=db_post, state=GIG_STATES.APPROVED)
    gig_factory(offer=offer_3, post=db_post, state=GIG_STATES.REVIEWED)
    gig_factory(offer=offer_4, post=db_post, state=GIG_STATES.REJECTED)

    db_campaign.offers = [offer_1, offer_2, offer_3, offer_4]

    # Act
    total_submissions = CampaignService.get_submissions_count(db_campaign.id)

    # Assert
    assert total_submissions == 4


def test_get_submissions_count_returns_0_if_no_gigs(db_campaign, db_post):
    # Arrange
    db_campaign.posts = [db_post]
    db_post.gigs = []

    # Act
    total_submissions = CampaignService.get_submissions_count(db_campaign.id)

    # Assert
    assert total_submissions == 0


def test_get_active_campaigns_returns_correct_campaign_ids(
    db_session, db_region, campaign_factory, offer_factory
):
    # Arrange
    c1 = campaign_factory(region=db_region, units=REACH_PER_ASSET * 2, reward_model="reach")
    c2 = campaign_factory(region=db_region, units=REACH_PER_ASSET, reward_model="reach")
    c3 = campaign_factory(region=db_region, units=REACH_PER_ASSET, reward_model="reach")

    c4 = campaign_factory(region=db_region, units=1, reward_model="assets")
    c5 = campaign_factory(region=db_region, units=2, reward_model="assets")

    c6 = campaign_factory(
        region=db_region, units=ENGAGEMENT_PER_ASSET * 2, reward_model="engagement"
    )
    c7 = campaign_factory(region=db_region, units=ENGAGEMENT_PER_ASSET, reward_model="engagement")
    c8 = campaign_factory(region=db_region, units=ENGAGEMENT_PER_ASSET, reward_model="engagement")

    # launch campaigns
    for c in [c1, c2, c3, c4, c5, c6, c7, c8]:
        c.state = CAMPAIGN_STATES.LAUNCHED

    c9 = campaign_factory(region=db_region, units=200_000)

    o1 = offer_factory(campaign=c1, state=OFFER_STATES.ACCEPTED, followers_per_post=c1.units)
    o2 = offer_factory(campaign=c2, state=OFFER_STATES.ACCEPTED, followers_per_post=c2.units)
    o3 = offer_factory(campaign=c3, state=OFFER_STATES.ACCEPTED, followers_per_post=c3.units / 2)
    o4 = offer_factory(campaign=c3, state=OFFER_STATES.INVITED, followers_per_post=c3.units * 2)

    o5 = offer_factory(campaign=c4, state=OFFER_STATES.ACCEPTED)
    o6 = offer_factory(campaign=c5, state=OFFER_STATES.ACCEPTED)
    o7 = offer_factory(campaign=c5, state=OFFER_STATES.INVITED)

    o8 = offer_factory(campaign=c6, state=OFFER_STATES.ACCEPTED, engagements_per_post=c6.units)
    o9 = offer_factory(campaign=c7, state=OFFER_STATES.ACCEPTED, engagements_per_post=c7.units)

    o10 = offer_factory(campaign=c8, state=OFFER_STATES.ACCEPTED, engagements_per_post=c8.units / 2)
    o11 = offer_factory(campaign=c8, state=OFFER_STATES.INVITED, engagements_per_post=c8.units * 2)

    db_session.add_all(
        [c1, c2, c3, c4, c5, c6, c7, c8, c9, o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11]
    )

    # Act
    campaign_ids = CampaignService.get_active_campaigns()

    # Assert
    assert len(campaign_ids) == 5
    assert (c1.id,) in campaign_ids
    assert (c3.id,) in campaign_ids
    assert (c5.id,) in campaign_ids
    assert (c6.id,) in campaign_ids
    assert (c8.id,) in campaign_ids


def test_update_brand_safety_updates_brand_safety(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_campaign.brand_safety = True
    db_session.commit()

    # Act
    with CampaignService(db_campaign) as service:
        service.update_brand_safety(False)

    # Assert
    assert db_campaign.brand_safety is False


def test_update_extended_review_raises_exception_if_campaign_is_not_in_draft_state_and_has_offers(
    db_session, db_campaign, db_offer
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.extended_review = True
    db_session.commit()

    # Act
    with pytest.raises(InvalidCampaignStateException) as exc:
        CampaignService(db_campaign).update_extended_review(False)

    # Assert
    assert db_campaign.extended_review is True
    assert (
        "Campaign has to be in `draft` state in order to update extended review. Current state: launched"
    ) in exc.exconly()


def test_update_extended_review_updates_extended_review(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_campaign.extended_review = False
    db_session.commit()

    # Act
    with CampaignService(db_campaign) as service:
        service.update_extended_review(True)

    # Assert
    assert db_campaign.extended_review is True


def test_get_campaigns_with_gigs_ready_for_approval_returns_no_campaigns(
    db_session, gig_factory, post_factory, campaign_factory
):
    # Arrange
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1.5)
    campaign_1 = campaign_factory(brand_safety=True)
    campaign_2 = campaign_factory()
    post_1 = post_factory(campaign=campaign_1)
    post_2 = post_factory(campaign=campaign_2)
    gig_1 = gig_factory(
        post=post_1,
        review_date=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2),
        state=GIG_STATES.REVIEWED,
    )
    gig_2 = gig_factory(
        post=post_1,
        review_date=dt.datetime.now(dt.timezone.utc),
        state=GIG_STATES.REQUIRES_RESUBMIT,
    )
    gig_3 = gig_factory(
        post=post_2, review_date=dt.datetime.now(dt.timezone.utc), state=GIG_STATES.REVIEWED
    )
    db_session.add_all([campaign_1, campaign_2, post_1, post_2, gig_1, gig_2, gig_3])
    db_session.commit()

    # Act
    campaigns = CampaignService.get_campaigns_with_gigs_ready_for_approval(time_period_ago)

    # Assert
    assert len(campaigns) == 0


def test_get_campaigns_with_gigs_ready_for_approval_returns_campaigns(
    db_session, db_campaign, gig_factory, post_factory, campaign_factory
):
    # Arrange
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1.5)
    campaign_1 = campaign_factory(brand_safety=True)
    campaign_2 = campaign_factory(brand_safety=True)
    post_1 = post_factory(campaign=campaign_1)
    post_2 = post_factory(campaign=campaign_2)
    post_3 = post_factory(campaign=campaign_2)
    gig_1 = gig_factory(
        post=post_1, review_date=dt.datetime.now(dt.timezone.utc), state=GIG_STATES.REVIEWED
    )
    gig_2 = gig_factory(
        post=post_1,
        review_date=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
        state=GIG_STATES.REVIEWED,
    )
    gig_3 = gig_factory(
        post=post_2, review_date=dt.datetime.now(dt.timezone.utc), state=GIG_STATES.REVIEWED
    )
    gig_4 = gig_factory(
        post=post_2, review_date=dt.datetime.now(dt.timezone.utc), state=GIG_STATES.REVIEWED
    )
    db_session.add_all([campaign_1, campaign_2, post_1, post_2, post_3, gig_1, gig_2, gig_3, gig_4])
    db_session.commit()

    # Act
    campaigns = CampaignService.get_campaigns_with_gigs_ready_for_approval(time_period_ago)

    # Assert
    assert len(campaigns) == 2
    assert campaign_1 in campaigns
    assert campaign_2 in campaigns


def test_campaign_update_price_updates_price(db_campaign):
    # Act
    with CampaignService(db_campaign) as service:
        service.update_price(1337)

    assert db_campaign.price == 1337


def test_campaign_update_price_raises_if_price_is_negative(db_campaign):
    # Act
    with pytest.raises(NegativePriceException) as exc:
        CampaignService(db_campaign).update_price(-1)

    # Assert
    assert "Price can't be negative" in exc.exconly()


def test_campaign_update_list_price_raises_if_not_draft_state(db_campaign, db_session):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_session.commit()

    # Act
    with pytest.raises(InvalidCampaignStateException) as exc:
        CampaignService(db_campaign).update_list_price(500)

    # Assert
    assert (
        "Campaign has to be in `draft` state in order to update list price. Current state: launched"
        in exc.exconly()
    )


def test_campaign_update_list_price_updates_list_price(db_campaign):
    # Act
    with CampaignService(db_campaign) as service:
        service.update_list_price(1337)

    assert db_campaign.list_price == 1337


def test_campaign_update_list_price_raises_if_list_price_is_negative(db_campaign):
    # Act
    with pytest.raises(NegativePriceException) as exc:
        CampaignService(db_campaign).update_list_price(-1)

    # Assert
    assert "List price can't be negative" in exc.exconly()


def test_campaign_update_custom_reward_raises_if_state_is_not_draft(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign

    # Act
    with pytest.raises(InvalidCampaignStateException) as exc:
        CampaignService(db_campaign).update_custom_reward_units(1337)

    # Assert
    assert (
        "Campaign has to be in `draft` state in order to change reward base. Current state: launched"
        in exc.exconly()
    )


def test_campaign_update_custom_reward_updates_custom_reward_units(db_session, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.DRAFT
    db_session.commit()  # Make sure that we don't start CampaignService with a dirty campaign
    assert db_campaign.custom_reward_units != 1337

    # Act
    with CampaignService(db_campaign) as service:
        service.update_custom_reward_units(1337)

    # Assert
    assert db_campaign.custom_reward_units == 1337


def test_update_tags_updates_tags_with_lower_case(db_campaign):
    # Act
    with CampaignService(db_campaign) as service:
        service.update_tags(["onE", "TWo"])

    # Assert
    assert db_campaign.tags == ["one", "two"]


def test_campaign_service_set_new_candidate_position_moves_offer_to_correct_position(
    db_session, db_campaign, db_region, user_factory, influencer_factory, offer_factory
):
    offers = [
        offer_factory(
            state=OFFER_STATES.CANDIDATE,
            influencer=influencer_factory(
                state="reviewed", target_region=db_region, user=user_factory()
            ),
            campaign=db_campaign,
        )
        for i in range(4)
    ]
    db_session.add_all(offers)
    db_session.commit()

    offers = db_campaign.ordered_candidates_q.all()
    target_offer = offers[0]

    # Move first offer to the second position
    with CampaignService(db_campaign) as service:
        service.set_new_candidate_position(
            target_offer.id, offers[1].id, db_campaign.candidates_hash
        )

    ordered_offers = db_campaign.ordered_candidates_q.all()
    assert ordered_offers[0] == offers[1]
    assert ordered_offers[1] == offers[0]
    assert ordered_offers[2] == offers[2]
    assert ordered_offers[3] == offers[3]

    # Move the same offer the the last position
    with CampaignService(db_campaign) as service:
        service.set_new_candidate_position(
            target_offer.id, offers[3].id, db_campaign.candidates_hash
        )

    ordered_offers = db_campaign.ordered_candidates_q.all()
    assert ordered_offers[0] == offers[1]
    assert ordered_offers[1] == offers[2]
    assert ordered_offers[2] == offers[3]
    assert ordered_offers[3] == offers[0]


def test_campaign_service_set_new_candidate_position_raises_on_invalid_position(
    db_session, db_campaign, db_region, user_factory, influencer_factory, offer_factory
):
    offers = [
        offer_factory(
            state=OFFER_STATES.CANDIDATE,
            influencer=influencer_factory(
                state="reviewed", target_region=db_region, user=user_factory()
            ),
            campaign=db_campaign,
        )
        for i in range(4)
    ]
    db_session.add_all(offers)
    db_session.commit()

    with pytest.raises(InvalidOfferIdException):
        with CampaignService(db_campaign) as service:
            service.set_new_candidate_position(offers[0].id, "not-in-the-list")

    # Shouldn't raise
    with CampaignService(db_campaign) as service:
        service.set_new_candidate_position(offers[0].id, offers[1].id, db_campaign.candidates_hash)

    with CampaignService(db_campaign) as service:
        service.set_new_candidate_position(offers[1].id, offers[0].id, db_campaign.candidates_hash)


def test_campaign_service_get_devices_grouped_by_locale_groups_devices_correctly(
    db_session,
    db_campaign,
    db_region,
    user_factory,
    influencer_factory,
    offer_factory,
    device_factory,
    app,
):
    locales = app.config["AVAILABLE_LOCALES"]
    offers = [
        offer_factory(
            state=OFFER_STATES.REQUESTED,
            influencer=influencer_factory(
                state="reviewed",
                target_region=db_region,
                user=user_factory(device=device_factory(), locale=locale),
            ),
            campaign=db_campaign,
        )
        for locale in locales
    ]
    db_session.add_all(offers)
    db_session.commit()

    with CampaignService(db_campaign) as service:
        devices = service.get_devices_grouped_by_locale(OFFER_STATES.REQUESTED)

    assert set(devices.keys()) == set(locales)
    for devices in devices.values():
        assert len(devices) == 1


def test_campaign_service_revoke_requested_offers(
    db_session,
    db_campaign,
    db_region,
    user_factory,
    influencer_factory,
    offer_factory,
    device_factory,
    app,
    monkeypatch,
):
    monkeypatch.setattr("takumi.notifications.NotificationClient.send_rejection", lambda *_: None)
    offers = [
        offer_factory(
            state=OFFER_STATES.REQUESTED,
            influencer=influencer_factory(
                state="reviewed",
                target_region=db_region,
                user=user_factory(device=device_factory(), locale=locale),
            ),
            campaign=db_campaign,
        )
        for locale in app.config["AVAILABLE_LOCALES"]
    ]
    db_session.add_all(offers)
    db_session.commit()

    with CampaignService(db_campaign) as service:
        service.revoke_requested_offers(OFFER_STATES.REQUESTED)


@freeze_time(dt.datetime(2019, 1, 10, tzinfo=dt.timezone.utc))
def test_campaign_service_notify_all_fails_if_deadline_passed(
    db_session, db_influencer, db_campaign, db_post
):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_post.deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 9, tzinfo=dt.timezone.utc)
    db_session.commit()

    with pytest.raises(
        ServiceException, match="A submission deadline for the campaign has already passed"
    ):
        CampaignService(db_campaign).send_notifications_to_all_targets()

    db_post.deadline = dt.datetime(2019, 1, 9, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)

    with pytest.raises(ServiceException, match="A deadline for the campaign has already passed"):
        CampaignService(db_campaign).send_notifications_to_all_targets()

    db_post.deadline = dt.datetime(2019, 1, 12, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)

    CampaignService(db_campaign).send_notifications_to_all_targets()


def test_campaign_get_number_of_accepted_influencers(db_session, db_campaign, db_offer):
    db_offer.state = OFFER_STATES.ACCEPTED
    db_session.commit()
    expected_result = 1
    number_of_accepted_influencers = CampaignService(
        db_campaign
    ).get_number_of_accepted_influencers([db_campaign.id])
    assert number_of_accepted_influencers == expected_result


def test_campaign_get_number_of_accepted_influencers_default_zero(
    db_session, db_campaign, db_offer
):
    expected_result = 0
    number_of_accepted_influencers = CampaignService(
        db_campaign
    ).get_number_of_accepted_influencers([db_campaign.id])
    assert number_of_accepted_influencers == expected_result


def test_campaign_get_campaigns_impressions(
    db_session,
    db_campaign,
    db_instagram_story,
    db_influencer,
    db_instagram_story_frame_insight,
    db_story_frame,
    db_instagram_post,
    db_instagram_post_insight,
    db_campaign_metric,
    db_offer,
):
    additional_db_story_frame = _story_frame(influencer=db_influencer)
    additional_db_instagram_story_frame_insight = _instagram_story_frame_insight(
        story_frame=additional_db_story_frame
    )

    db_session.add_all((additional_db_story_frame, additional_db_instagram_story_frame_insight))
    db_session.commit()

    db_instagram_story.story_frames.extend([db_story_frame, additional_db_story_frame])
    db_instagram_story_frame_insight.impressions = 700
    additional_db_instagram_story_frame_insight.impressions = 600

    db_instagram_post_insight.impressions = 200
    _gig(_post(db_campaign), db_offer, instagram_post=db_instagram_post)

    db_campaign_metric.impressions_total = db_campaign.impressions_total
    db_session.commit()

    expected_result = 1500
    number_of_accepted_influencers = CampaignService(db_campaign).get_campaigns_impressions(
        [db_campaign.id]
    )
    assert number_of_accepted_influencers == expected_result


def test_campaign_get_campaigns_impressions_default_zero(db_session, db_campaign, db_post_insight):
    expected_result = 0
    number_of_accepted_influencers = CampaignService(db_campaign).get_campaigns_impressions(
        [db_campaign.id]
    )
    assert number_of_accepted_influencers == expected_result
