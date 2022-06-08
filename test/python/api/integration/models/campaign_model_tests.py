# encoding=utf-8

from test.python.api.utils import _instagram_story_frame_insight, _story_frame

from takumi.models import Campaign, Influencer, Offer
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.campaign import CampaignMetric, RewardModels
from takumi.models.offer import STATES as OFFER_STATES
from takumi.utils import uuid4_str


def _campaign_reservable(having):
    return (
        Campaign.query.join(Offer).join(Influencer).having(having).group_by(Campaign.id).count()
        == 1
    )


def test_campaign_is_assets_campaign_reservable(db_session, db_campaign, db_offer):
    db_campaign.reward_model = RewardModels.assets
    db_campaign.units = 1
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.INVITED

    assert _campaign_reservable(Campaign.is_assets_campaign_reservable())
    assert db_campaign.is_active

    db_offer.state = OFFER_STATES.ACCEPTED

    assert not _campaign_reservable(Campaign.is_assets_campaign_reservable())
    assert Campaign.query.filter(Campaign.is_active).first() != db_campaign
    assert not db_campaign.is_active


def test_campaign_is_reach_campaign_reservable(db_session, db_campaign, db_offer):
    db_campaign.units = 10
    db_campaign.reward_model = RewardModels.reach
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.INVITED

    assert _campaign_reservable(Campaign.is_reach_campaign_reservable())
    assert db_campaign.is_active

    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.followers_per_post = 5

    assert _campaign_reservable(Campaign.is_reach_campaign_reservable())
    assert db_campaign.is_active

    db_offer.followers_per_post = db_campaign.units

    assert not _campaign_reservable(Campaign.is_reach_campaign_reservable())
    assert not db_campaign.is_active


def test_campaign_is_engagement_campaign_reservable(db_session, db_campaign, db_offer):
    db_campaign.units = 10
    db_campaign.reward_model = RewardModels.engagement
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.INVITED

    assert _campaign_reservable(Campaign.is_engagement_campaign_reservable())
    assert db_campaign.is_active

    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.engagements_per_post = 5

    assert _campaign_reservable(Campaign.is_engagement_campaign_reservable())
    assert db_campaign.is_active

    db_offer.engagements_per_post = db_campaign.units

    assert not _campaign_reservable(Campaign.is_engagement_campaign_reservable())
    assert not db_campaign.is_active


def test_campaign_is_impressions_campaign_reservable(
    monkeypatch, db_session, db_campaign, db_offer
):
    db_campaign.units = 10
    db_campaign.reward_model = RewardModels.impressions
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.INVITED

    assert _campaign_reservable(Campaign.is_impressions_campaign_reservable())
    assert db_campaign.is_active

    db_offer.state = OFFER_STATES.ACCEPTED
    monkeypatch.setattr("takumi.models.Influencer.estimated_impressions", 5)

    assert _campaign_reservable(Campaign.is_impressions_campaign_reservable())
    assert db_campaign.is_active

    monkeypatch.setattr("takumi.models.Influencer.estimated_impressions", db_campaign.units)

    assert not _campaign_reservable(Campaign.is_impressions_campaign_reservable())
    assert not db_campaign.is_active


def test_engagement_rate_total(monkeypatch, db_campaign):
    monkeypatch.setattr("takumi.models.Campaign.engagement_rate_story", 0.56)
    monkeypatch.setattr("takumi.models.Campaign.engagement_rate_static", 0.2)
    assert db_campaign.engagement_rate_total == 0.76


def test_engagement_rate_story(monkeypatch, db_campaign):
    # story_engagements/followers * 100
    monkeypatch.setattr("takumi.models.Campaign.story_engagements", 5789)
    monkeypatch.setattr("takumi.models.Campaign.number_of_accepted_followers", 12450)
    assert db_campaign.engagement_rate_story == 46.497991967871485


def test_engagement_rate_static(monkeypatch, db_campaign):
    # static_engagements/followers * 100
    monkeypatch.setattr("takumi.models.Campaign.static_engagements", 5789)
    monkeypatch.setattr("takumi.models.Campaign.number_of_accepted_followers", 12450)
    assert db_campaign.engagement_rate_static == 46.497991967871485


def test_static_engagements(
    db_campaign, db_post, db_instagram_post, db_gig, db_instagram_post_insight
):
    db_post.post_type = "video"
    db_gig.instagram_post = db_instagram_post
    db_post.gigs.append(db_gig)
    db_campaign.posts.append(db_post)
    assert len(db_campaign.posts) == 2
    for post in db_campaign.posts:
        assert len(post.gigs) == 2
    assert db_campaign.static_engagements == 400


def test_story_engagements(
    db_campaign,
    db_post,
    db_instagram_story,
    db_gig,
    db_story_frame,
    db_instagram_story_frame_insight,
):
    db_post.post_type = "story"
    db_instagram_story.story_frames.append(db_story_frame)
    db_gig.instagram_story = db_instagram_story
    db_post.gigs.append(db_gig)
    db_campaign.posts.append(db_post)
    assert db_campaign.story_engagements == 404


def test_total_reach(
    db_campaign,
    db_instagram_story_frame_insight,
    db_instagram_post_insight,
    db_instagram_story,
    db_story_frame,
    db_influencer,
    db_session,
):
    db_story_frame_second = _story_frame(influencer=db_influencer)
    db_instagram_story_frame_insight_second = _instagram_story_frame_insight(
        story_frame=db_story_frame_second
    )
    db_session.add(db_story_frame_second)
    db_session.add(db_instagram_story_frame_insight_second)
    db_session.commit()
    db_instagram_story.story_frames.extend([db_story_frame, db_story_frame_second])

    db_instagram_story_frame_insight.reach = 200
    db_instagram_story_frame_insight_second.reach = 200

    db_instagram_post_insight.reach = 200
    expected_result = 600
    assert db_campaign.reach_total == expected_result


def test_total_reach_without_insights(db_campaign):
    expected_result = 0
    assert db_campaign.reach_total == expected_result


def test_total_impressions(
    db_campaign,
    db_instagram_story_frame_insight,
    db_instagram_post_insight,
    db_instagram_story,
    db_story_frame,
    db_influencer,
    db_session,
):
    db_story_frame_second = _story_frame(influencer=db_influencer)
    db_instagram_story_frame_insight_second = _instagram_story_frame_insight(
        story_frame=db_story_frame_second
    )
    db_session.add(db_story_frame_second)
    db_session.add(db_instagram_story_frame_insight_second)
    db_session.commit()
    db_instagram_story.story_frames.extend([db_story_frame, db_story_frame_second])

    db_instagram_story_frame_insight.impressions = 300
    db_instagram_story_frame_insight_second.impressions = 300

    db_instagram_post_insight.impressions = 300
    expected_result = 900
    assert db_campaign.impressions_total == expected_result


def test_total_impressions_without_insights(db_campaign):
    expected_result = 0
    assert db_campaign.impressions_total == expected_result


def test_campaign_metric__repr__(db_campaign):
    campaign_metric_id = uuid4_str()
    campaign_metric = CampaignMetric(id=campaign_metric_id, campaign=db_campaign)

    assert str(campaign_metric) == f"<Campaign Metric: {campaign_metric_id} ({db_campaign.name})>"
