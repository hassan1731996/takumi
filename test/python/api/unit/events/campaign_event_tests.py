# encoding=utf-8

import datetime as dt
from unittest import TestCase

import pytest
from freezegun import freeze_time

from takumi.events import EventApplicationException
from takumi.events.campaign import CampaignLaunch, CampaignLaunchValidationException, CampaignLog
from takumi.models import Advertiser, Campaign
from takumi.utils import uuid4_str


class CampaignLogTests(TestCase):
    def _campaign(self):
        campaign = Campaign(advertiser=Advertiser(), market_slug="uk")
        return campaign

    def setUp(self):
        self.campaign = self._campaign()
        self.log = CampaignLog(self.campaign)

    def test_create_campaign_intializes_campaign_columns(self):
        self.log.add_event(
            "create",
            {
                "units": 1337,
                "advertiser_id": self.campaign.advertiser_id,
                "pricing_id": None,
                "timezone": "Europe/Berlin",
                "shipping_required": True,
                "require_insights": True,
                "price": 1337,
                "list_price": 1337,
                "custom_reward_units": None,
                "reward_model": "assets",
                "owner_id": uuid4_str(),
                "campaign_manager_id": uuid4_str(),
                "secondary_campaign_manager_id": uuid4_str(),
                "community_manager_id": uuid4_str(),
                "market_slug": "is",
                "pictures": ["pictures"],
                "prompts": [],
                "name": "Campaign",
                "description": "Description",
                "tags": [],
                "has_nda": False,
                "brand_safety": False,
                "extended_review": False,
                "industry": "Alcohol",
                "opportunity_product_id": None,
                "apply_first": True,
                "brand_match": False,
                "pro_bono": False,
            },
        )
        assert self.campaign.units == 1337
        assert self.campaign.reward_model == "assets"
        assert self.campaign.market_slug == "is"
        assert self.campaign.shipping_required

    def test_set_units(self):
        self.log.add_event("set_units", {"units": 1337})
        assert self.campaign.units == 1337

    def test_set_shipping_required(self):
        self.log.add_event("set_shipping_required", {"shipping_required": True})
        assert self.campaign.shipping_required

    def test_set_name(self):
        self.log.add_event("set_name", {"name": "Sam Smith"})
        assert self.campaign.name == "Sam Smith"

    def test_set_description(self):
        self.log.add_event("set_description", {"description": "Sam Smith"})
        assert self.campaign.description == "Sam Smith"

    def test_set_pictures(self):
        self.log.add_event(
            "set_pictures", {"pictures": [{"url": "http://test-images.net/test1.png"}]}
        )
        assert len(self.campaign.pictures) == 1

        self.log.add_event(
            "set_pictures", {"pictures": [{"url": "http://test-images.net/test2.png"}]}
        )
        assert len(self.campaign.pictures) == 1
        assert self.campaign.pictures[0]["url"] == "http://test-images.net/test2.png"

    def test_set_tags(self):
        self.log.add_event("set_tags", {"tags": ["one", "two"]})
        assert len(self.campaign.tags) == 2
        assert "one" in self.campaign.tags
        assert "two" in self.campaign.tags

    def test_set_owner(self):
        u_id = uuid4_str()
        self.log.add_event("set_owner", {"owner_id": u_id})
        assert self.campaign.owner_id == u_id

    def test_set_campaign_manager(self):
        u_id = uuid4_str()
        self.log.add_event("set_campaign_manager", {"campaign_manager_id": u_id})
        assert self.campaign.campaign_manager_id == u_id

    def test_set_secondary_campaign_manager(self):
        u_id = uuid4_str()
        self.log.add_event(
            "set_secondary_campaign_manager", {"secondary_campaign_manager_id": u_id}
        )
        assert self.campaign.secondary_campaign_manager_id == u_id

    def test_set_community_manager(self):
        u_id = uuid4_str()
        self.log.add_event("set_community_manager", {"community_manager_id": u_id})
        assert self.campaign.community_manager_id == u_id

    def test_set_has_nda(self):
        self.log.add_event("set_has_nda", {"has_nda": True})
        assert self.campaign.has_nda

    def test_set_industry(self):
        self.log.add_event("set_industry", {"industry": "Alcohol"})
        assert self.campaign.industry == "Alcohol"

    def test_set_no_industry(self):
        self.campaign.industry = "Toiletries cosmetics (general)"
        self.log.add_event("set_industry", {"industry": ""})
        self.assertIsNone(self.campaign.industry)

    def test_set_invalid_industry(self):
        self.campaign.industry = "Toiletries cosmetics (general)"
        with self.assertRaises(EventApplicationException):
            self.log.add_event("set_industry", {"industry": "Non existing industry"})
        self.assertEqual(self.campaign.industry, "Toiletries cosmetics (general)")

    def test_set_brand_match(self):
        self.log.add_event("set_brand_match", {"brand_match": True})
        assert self.campaign.brand_match
        self.log.add_event("set_brand_match", {"brand_match": False})
        assert not self.campaign.brand_match

    def test_set_apply_first(self):
        self.log.add_event("set_apply_first", {"apply_first": True})
        assert self.campaign.apply_first
        self.log.add_event("set_apply_first", {"apply_first": False})
        assert not self.campaign.apply_first

    def test_set_report_token(self):
        u_id = uuid4_str()
        self.log.add_event(
            "set_report_token", {"new_token": u_id, "old_token": self.campaign.report_token}
        )
        assert self.campaign.report_token == u_id

    def test_set_custom_reward_units(self):
        self.log.add_event("set_custom_reward_units", {"custom_reward_units": 1337})
        assert self.campaign.custom_reward_units == 1337

    def test_set_price(self):
        self.log.add_event("set_price", {"price": 1337})
        assert self.campaign.price == 1337

    def test_set_list_price(self):
        self.log.add_event("set_list_price", {"list_price": 1337})
        assert self.campaign.list_price == 1337


class Influencer:
    def __init__(self, followers):
        self.followers = followers


@freeze_time(dt.datetime(2016, 1, 10, 0, 0))
def test_campaign_launch_campaign_sets_started(campaign, post):
    assert campaign.started is None
    CampaignLaunch({}).apply(campaign)
    assert campaign.started == dt.datetime.now(dt.timezone.utc)


def test_campaign_launch_validate_campaign_with_no_name_raises(campaign):
    campaign.name = None
    with pytest.raises(CampaignLaunchValidationException, match="Campaign name is missing"):
        CampaignLaunch({})._validate_campaign(campaign)

    campaign.name = ""
    with pytest.raises(CampaignLaunchValidationException, match="Campaign name is missing"):
        CampaignLaunch({})._validate_campaign(campaign)


def test_campaign_launch_validate_campaign_with_no_brief_raises(campaign, post):
    campaign.posts[0].brief = []
    with pytest.raises(CampaignLaunchValidationException, match="Campaign posts missing briefs"):
        CampaignLaunch({})._validate_campaign(campaign)


def test_campaign_launch_validates_brief_instead_of_instructions(campaign, post):
    campaign.posts[0].instructions = None
    campaign.posts[0].brief = []
    campaign.description = None

    with pytest.raises(CampaignLaunchValidationException):
        CampaignLaunch({})._validate_campaign(campaign)

    campaign.posts[0].brief = [{"type": "heading", "value": "Brief title"}]

    CampaignLaunch({})._validate_campaign(campaign)


def test_campaign_launch_validate_campaign_with_no_pictures_raises(campaign):
    campaign.pictures = []
    with pytest.raises(CampaignLaunchValidationException, match="Campaign is missing pictures"):
        CampaignLaunch({})._validate_campaign(campaign)


@freeze_time(dt.datetime(2016, 1, 10, 0, 0))
def test_campaign_launch_success(campaign, post):
    campaign.pictures = ["picture"]
    campaign.name = "Name"
    campaign.description = "This is a test. I repeat, this is a test."

    CampaignLaunch({})._validate_campaign(campaign)


def test_campaign_launch_validate_campaign_with_no_regions_raises(campaign, post):
    campaign.targeting.regions = []
    with pytest.raises(CampaignLaunchValidationException, match="Campaign is missing regions"):
        CampaignLaunch({})._validate_campaign(campaign)
