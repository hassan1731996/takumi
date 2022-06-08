from math import floor

import mock
import pytest

from core.testing.factories import InfluencerFactory, InstagramAccountFactory

from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes


def _get_influencer(followers):
    ig_account = InstagramAccountFactory()(followers=followers)
    return InfluencerFactory()(instagram_account=ig_account)


def test_campaign_is_not_fulfilled_with_no_offers(campaign):
    assert len(campaign.offers) == 0
    assert not campaign.is_fulfilled


def test_asset_campaign_is_not_fulfilled_until_enough_claimable_offers(campaign, offer_factory):
    for _ in range(campaign.units - 1):
        offer_factory(campaign=campaign, is_claimable=True)

    assert not campaign.is_fulfilled

    offer_factory(campaign=campaign, is_claimable=True)

    assert campaign.is_fulfilled


def test_reach_campaign_is_not_fulfilled_until_enough_claimable_offers(
    reach_campaign, reach_post, offer_factory, gig_factory, instagram_post_factory
):
    number_of_influencers = 10
    for _ in range(number_of_influencers - 1):
        followers = int(reach_campaign.units / number_of_influencers)
        influencer = _get_influencer(followers=followers)
        offer = offer_factory(campaign=reach_campaign, is_claimable=True, influencer=influencer)
        gig_factory(
            offer=offer,
            post=reach_post,
            state=GIG_STATES.REJECTED,  # Will make it claimable
            instagram_post=instagram_post_factory(followers=followers),
        )

    assert not reach_campaign.is_fulfilled

    influencer = _get_influencer(followers=int(reach_campaign.units / number_of_influencers))
    offer = offer_factory(campaign=reach_campaign, is_claimable=True, influencer=influencer)
    gig_factory(
        offer=offer,
        post=reach_post,
        state=GIG_STATES.REJECTED,  # Will make it claimable
        instagram_post=instagram_post_factory(followers=followers),
    )

    assert reach_campaign.is_fulfilled


def test_campaign_is_not_fulfilled_if_all_offers_are_not_claimable(campaign, offer_factory):
    for _ in range(campaign.units):
        offer_factory(campaign=campaign, is_claimable=False)

    assert not campaign.is_fulfilled

    for offer in campaign.offers:
        offer.is_claimable = True

    assert campaign.is_fulfilled


def test_campaign_cost_per_engagement(campaign, monkeypatch):
    campaign.price = 5000 * 100  # 5k budget
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.posts",
        [
            mock.Mock(likes=90, comments=10),
            mock.Mock(likes=90, comments=10),
            mock.Mock(likes=90, comments=10),
        ],
    )

    assert campaign.cost_per_engagement == floor(5000 * 100 / 300)


def test_campaign_video_engagement(campaign, monkeypatch):
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.posts",
        [
            mock.Mock(post_type=PostTypes.standard, video_engagement=0),
            mock.Mock(post_type=PostTypes.video, video_engagement=0.2),
            mock.Mock(post_type=PostTypes.video, video_engagement=0.4),
        ],
    )

    assert campaign.video_engagement == pytest.approx(0.3)


def mock_cost_per_engagement(return_value=None):
    return mock.patch(
        "takumi.models.campaign.Campaign.cost_per_engagement",
        new_callable=mock.PropertyMock,
        return_value=return_value,
    )


def test_campaign_projected_cost_per_engagement_no_engagement(campaign):
    with mock_cost_per_engagement(return_value=0):
        assert campaign.projected_cost_per_engagement == 0


def test_campaign_projected_cost_per_engagement_no_progress(campaign, monkeypatch):
    with mock_cost_per_engagement(return_value=5000):
        monkeypatch.setattr(
            "takumi.funds.AssetsFund.get_progress", lambda _: dict(submitted=0, total=25)
        )
        assert campaign.projected_cost_per_engagement == 0


def test_campaign_projected_cost_per_engagement(campaign, monkeypatch):
    with mock_cost_per_engagement(return_value=5000):
        monkeypatch.setattr(
            "takumi.funds.AssetsFund.get_progress", lambda _: dict(submitted=5, total=25)
        )
        assert campaign.projected_cost_per_engagement == 1000
