# encoding=utf-8

from unittest import TestCase

from takumi.events.campaign import CampaignLog
from takumi.events.post import PostLog
from takumi.models import Advertiser, Campaign, Post
from takumi.utils import uuid4_str


def test_standard_post_requires_review():
    # Arrange
    post = Post(requires_review_before_posting=True)
    post_log = PostLog(post)

    # Act
    post_log.add_event(
        "create", {"post_type": "standard", "campaign_id": uuid4_str(), "conditions": []}
    )

    # Assert
    assert post.requires_review_before_posting is True


class Influencer:
    def __init__(self, followers):
        self.followers = followers


class PostLogTests(TestCase):
    def _post(self, props=None):
        campaign = Campaign(state="launched", advertiser=Advertiser(), market_slug="uk")
        if props is not None:
            log = CampaignLog(campaign)
            log.add_event("create", props)

        post = Post(campaign=campaign)
        return post

    def setUp(self):
        self.post = self._post()
        self.log = PostLog(self.post)

        self.create_properties = {
            "post_type": "standard",
            "campaign_id": uuid4_str(),
            "conditions": [],
        }
        self.campaign_properties = {
            "reward_model": "assets",
            "advertiser_id": "5678",
            "market_slug": "uk",
            "units": 10,
            "timezone": "Europe/London",
            "shipping_required": False,
            "description": "This one is easy, just post a picture, no mentions or hashtags",
        }
        self.log.add_event("create", self.create_properties)

    def test_set_schedule_with_okay_schedule(self):
        assert self.post.submission_deadline != "2017-01-01T00:00:00.000Z"
        assert self.post.opened != "2017-01-02T00:00:00.000Z"
        assert self.post.deadline != "2017-01-03T00:00:00.000Z"

        self.log.add_event(
            "set_schedule",
            {
                "submission_deadline": "2017-01-01T00:00:00.000Z",
                "deadline": "2017-01-03T00:00:00.000Z",
                "opened": "2017-01-02T00:00:00.000Z",
            },
        )

        assert self.post.submission_deadline == "2017-01-01T00:00:00.000Z"
        assert self.post.deadline == "2017-01-03T00:00:00.000Z"
        assert self.post.opened == "2017-01-02T00:00:00.000Z"

    def test_set_conditions_doesnt_set_empty_conditions(self):
        assert self.post.conditions == []

        self.log.add_event(
            "set_conditions",
            {
                "mention": "",
                "hashtags": ["", "ad", ""],
                "location": "",
                "swipe_up_link": "",
                "start_first_hashtag": False,
            },
        )

        assert self.post.conditions == [{"type": "hashtag", "value": "ad"}]

    def test_set_gallery_photo_count(self):
        self.log.add_event("set_gallery_photo_count", {"gallery_photo_count": 1337})
        assert self.post.gallery_photo_count == 1337
