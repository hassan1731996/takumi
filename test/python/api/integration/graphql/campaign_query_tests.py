import datetime
from test.python.api.utils import _campaign

from takumi.gql.query.campaign import CampaignQuery
from takumi.models import Notification
from takumi.utils import uuid4_str


def test_graphql_query_campaign_notifications(
    client, db_session, db_influencer, db_developer_user, db_campaign, db_device
):
    db_campaign.public = True
    db_influencer.user.device = db_device

    notification = Notification(campaign_id=db_campaign.id, device_id=db_influencer.user.device.id)
    db_session.add(notification)
    db_session.commit()

    with client.user_request_context(db_developer_user):
        notification_result = (
            CampaignQuery().resolve_campaign_notifications("info", id=db_campaign.id).first()
        )
        assert notification_result.Influencer == db_influencer
        assert notification_result.last_notification_sent == notification.sent
        assert notification_result.notification_count == 1


def test_campaigns(client, db_developer_user, db_advertiser_industry, db_campaign):
    db_advertiser_industry.advertisers.append(db_campaign.advertiser)

    filters = {
        "advertiser_industries_ids": [db_advertiser_industry.id],
        "shipping_required": False,
        "brand_safety": False,
        "brand_match": False,
        "archived": False,
        "has_nda": False,
    }

    with client.user_request_context(db_developer_user):
        response = CampaignQuery().resolve_campaigns("info", **filters)

    assert db_campaign in response.all()


def test_campaigns_with_nonexisting_industry(client, db_developer_user, db_campaign):
    filters = {
        "advertiser_industries_ids": [uuid4_str(), uuid4_str()],
        "shipping_required": False,
        "brand_safety": False,
        "brand_match": False,
        "archived": False,
        "has_nda": False,
    }

    with client.user_request_context(db_developer_user):
        response = CampaignQuery().resolve_campaigns("info", **filters)

    assert db_campaign not in response.all()


def test_campaigns_with_invalid_pagination(
    client, account_manager, db_advertiser, db_campaign, db_region
):
    _campaign(advertiser=db_advertiser, region=db_region)

    pagination_params = {
        "offset": -10,
        "limit": -10,
    }

    with client.user_request_context(account_manager):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 2


def test_campaigns_with_pagination(client, account_manager, db_campaign):
    pagination_params = {
        "offset": 0,
        "limit": 1,
    }

    with client.user_request_context(account_manager):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 1


def test_campaigns_with_pagination_offset_too_big(client, account_manager, db_campaign):
    pagination_params = {
        "offset": 3,
        "limit": 1,
    }

    with client.user_request_context(account_manager):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 0


def test_campaigns_with_pagination_limit_less_than_count(
    client, account_manager, db_campaign, db_advertiser, db_region
):
    _campaign(advertiser=db_advertiser, region=db_region)

    pagination_params = {
        "offset": 0,
        "limit": 1,
    }

    with client.user_request_context(account_manager):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 1


def test_campaigns_with_pagination_with_offset(
    client, account_manager, db_campaign, db_advertiser, db_region
):
    _campaign(advertiser=db_advertiser, region=db_region)

    pagination_params = {
        "offset": 1,
        "limit": 1,
    }

    with client.user_request_context(account_manager):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 1


def test_campaigns_with_pagination_brand(client, db_brand_profile_user, db_campaign):
    pagination_params = {
        "offset": 0,
        "limit": 1,
    }

    with client.user_request_context(db_brand_profile_user):
        response = CampaignQuery().resolve_campaigns("info", **pagination_params)

    assert response.count() == 1


def test_campaigns_by_date_range_success(client, account_manager, db_campaign, db_session):
    db_campaign.state = "launched"
    db_campaign.started = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()

    with client.user_request_context(account_manager):
        start_date = datetime.date.today() - datetime.timedelta(days=5)
        end_date = datetime.date.today() + datetime.timedelta(days=1)
        response = CampaignQuery().resolve_campaigns(
            "info",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    assert response.count() == 1


def test_campaigns_by_date_range_campaign_out_of_range(
    client, account_manager, db_campaign, db_session
):
    db_campaign.state = "launched"
    db_campaign.started = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()

    with client.user_request_context(account_manager):
        start_date = datetime.date.today() - datetime.timedelta(days=5)
        end_date = datetime.date.today() - datetime.timedelta(days=2)
        response = CampaignQuery().resolve_campaigns(
            "info",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    assert response.count() == 0


def test_campaigns_by_date_range_invalid_range(client, account_manager, db_campaign, db_session):
    db_campaign.state = "launched"
    db_campaign.started = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()

    with client.user_request_context(account_manager):
        start_date = datetime.date.today() - datetime.timedelta(days=1)
        end_date = datetime.date.today() - datetime.timedelta(days=5)
        response = CampaignQuery().resolve_campaigns(
            "info",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    assert response.count() == 0


def test_campaigns_by_date_range_campaigns_without_started_ignored(
    client, account_manager, db_campaign, db_session
):
    db_campaign.state = "launched"
    db_session.commit()

    with client.user_request_context(account_manager):
        start_date = datetime.date.today() - datetime.timedelta(days=1)
        end_date = datetime.date.today()
        response = CampaignQuery().resolve_campaigns(
            "info",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    assert response.count() == 0


def test_campaigns_by_date_range_success_brand_user(
    client, db_brand_profile_user, db_campaign, db_session
):
    db_campaign.state = "launched"
    db_campaign.started = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()

    with client.user_request_context(db_brand_profile_user):
        start_date = datetime.date.today() - datetime.timedelta(days=5)
        end_date = datetime.date.today() + datetime.timedelta(days=1)
        response = CampaignQuery().resolve_campaigns(
            "info",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
    assert response.count() == 1
