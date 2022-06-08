import pytest

from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.services import CampaignService
from takumi.services.exceptions import (
    CampaignStashException,
    InvalidCampaignStateException,
    NegativePriceException,
)


def test_campaign_update_price(app, campaign):
    assert campaign.price != 12345

    CampaignService(campaign).update_price(12345)

    assert campaign.price == 12345


def test_campaign_update_price_raises_on_negative_budget(app, campaign):
    with pytest.raises(NegativePriceException, match="Price can't be negative"):
        CampaignService(campaign).update_price(-1)


def test_campaign_stash_stashes_draft_campaign(app, campaign):
    assert campaign.state == CAMPAIGN_STATES.DRAFT

    CampaignService(campaign).stash()

    assert campaign.state == CAMPAIGN_STATES.STASHED


def test_campaign_stash_stashes_launched_campaign_if_no_offers(app, campaign):
    campaign.state = CAMPAIGN_STATES.LAUNCHED

    CampaignService(campaign).stash()

    assert campaign.state == CAMPAIGN_STATES.STASHED


def test_campaign_stash_raises_if_campaign_has_offers(app, campaign, offer):
    campaign.state = CAMPAIGN_STATES.LAUNCHED

    assert len(campaign.offers) > 0

    with pytest.raises(CampaignStashException, match="Unable to stash campaign with offers in it"):
        CampaignService(campaign).stash()

    assert campaign.state == CAMPAIGN_STATES.LAUNCHED


def test_campaign_update_brand_safety_allows_turning_on_with_offers(app, campaign, offer):
    assert len(campaign.offers) > 0
    assert campaign.brand_safety == False

    CampaignService(campaign).update_brand_safety(True)

    assert campaign.brand_safety == True


def test_campaign_update_brand_safety_allows_turning_off_with_no_offers(app, campaign):
    assert len(campaign.offers) == 0
    campaign.brand_safety = True

    CampaignService(campaign).update_brand_safety(False)

    assert campaign.brand_safety == False


def test_campaign_update_brand_safety_raises_if_turning_off_with_offers(app, campaign, offer):
    assert len(campaign.offers) > 0
    campaign.brand_safety = True

    with pytest.raises(InvalidCampaignStateException, match="Unable to turn off brand safety"):
        CampaignService(campaign).update_brand_safety(False)


def test_campaign_update_brand_match_allows_turning_on_with_offers(app, campaign, offer):
    assert len(campaign.offers) > 0
    assert campaign.brand_match == False

    CampaignService(campaign).update_brand_match(True)

    assert campaign.brand_match == True


def test_campaign_update_brand_match_allows_turning_off_with_no_offers(app, campaign):
    assert len(campaign.offers) == 0
    campaign.brand_match = True

    CampaignService(campaign).update_brand_match(False)

    assert campaign.brand_match == False


def test_campaign_update_brand_match_raises_if_turning_off_with_offers(app, campaign, offer):
    assert len(campaign.offers) > 0
    campaign.brand_match = True

    with pytest.raises(InvalidCampaignStateException, match="Unable to turn off brand match"):
        CampaignService(campaign).update_brand_match(False)
