# encoding=utf-8

from takumi.models import Campaign
from takumi.utils import uuid4_str

POST_SKELETON = {
    "campaign_type": "standard",
    "reward_model": "assets",
    "market": "uk",
    "shipping_required": "false",
    "pricing_id": "11111111-2222-3333-4444-555555555555",
}


class FakePost:
    id = uuid4_str()
    campaign = Campaign(advertiser_id=uuid4_str())


def CONDITION_SKELETON(type="hashtag", value="bylgjulestin"):
    return {"type": type, "value": value}


def test_post_engagement_percent(post, instagram_post):
    reach = 1000
    likes = 90
    comments = 10

    instagram_post.followers = reach
    instagram_post.likes = likes
    instagram_post.comments = comments
    post.gigs = [instagram_post.gig]

    assert post.engagement == float(likes + comments) / reach
