# encoding=utf-8
import mock

from takumi.models.campaign import Campaign
from takumi.tasks.campaign import create_or_update_campaign_metric, notify_all_targeted


def test_campaign_task_notify_all_targets(db_session, db_campaign, db_influencer, db_device):
    from takumi.models import Notification

    db_influencer.user.device = db_device
    db_campaign.public = True

    with mock.patch("takumi.notifications.client.tiger") as mock_tiger:
        notify_all_targeted(db_campaign.id)

    assert (
        db_session.query(Notification).filter(Notification.campaign_id == db_campaign.id)
    ).count() == 1
    assert mock_tiger.tiger.delay.called


def test_campaign_metric_task_create_or_update_campaign_metric_creation(db_campaign, monkeypatch):
    monkeypatch.setattr("takumi.models.Campaign.engagement_rate_total", 0.76)
    monkeypatch.setattr("takumi.models.Campaign.impressions_total", 1500)
    monkeypatch.setattr("takumi.models.Campaign.reach_total", 500)

    create_or_update_campaign_metric(db_campaign.id)

    expected_engagement_rate_total = 0.76
    expected_impressions_total = 1500
    expected_reach_total = 500
    expected_assets = 10

    assert db_campaign.campaign_metric
    assert db_campaign.campaign_metric.modified == None
    assert db_campaign.campaign_metric.engagement_rate_total == expected_engagement_rate_total
    assert db_campaign.campaign_metric.impressions_total == expected_impressions_total
    assert db_campaign.campaign_metric.reach_total == expected_reach_total
    assert db_campaign.campaign_metric.assets == expected_assets


def test_campaign_metric_task_create_or_update_campaign_metric_updating(
    db_campaign, db_campaign_metric, db_session, monkeypatch
):
    db_campaign.state = Campaign.STATES.LAUNCHED
    db_session.commit()

    monkeypatch.setattr("takumi.models.Campaign.engagement_rate_total", 0.76)
    monkeypatch.setattr("takumi.models.Campaign.impressions_total", 1500)
    monkeypatch.setattr("takumi.models.Campaign.reach_total", 500)

    create_or_update_campaign_metric(db_campaign.id)

    expected_engagement_rate_total = 0.76
    expected_impressions_total = 1500
    expected_reach_total = 500
    expected_assets = 10

    assert db_campaign.campaign_metric
    assert db_campaign.campaign_metric.modified != None
    assert db_campaign.campaign_metric.engagement_rate_total == expected_engagement_rate_total
    assert db_campaign.campaign_metric.impressions_total == expected_impressions_total
    assert db_campaign.campaign_metric.reach_total == expected_reach_total
    assert db_campaign.campaign_metric.assets == expected_assets
