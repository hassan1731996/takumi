from takumi.models.advertiser import AdvertiserConfig
from takumi.services.advertiser_config import AdvertiserConfigService


def test_get_config_by_advertiser_id(db_session, db_advertiser):
    config = AdvertiserConfig(advertiser_id=db_advertiser.id)
    db_session.add(config)
    db_session.commit()

    result = AdvertiserConfigService.get_config_by_advertiser_id(db_advertiser.id)
    assert result.advertiser_id == db_advertiser.id


def test_update_advertiser_config(db_session, db_advertiser):
    config = AdvertiserConfig(advertiser_id=db_advertiser.id)
    db_session.add(config)
    db_session.commit()
    assert config.impressions is False
    assert config.engagement_rate is False
    assert config.benchmarks is False
    assert config.campaign_type is False
    assert config.budget is False
    assert config.view_rate is False
    assert config.brand_campaigns_page is False
    assert config.dashboard_page is False

    result = AdvertiserConfigService.update_advertiser_config(
        db_advertiser.id, True, True, False, False, False, False, False, False
    )

    assert result.impressions is True
    assert result.engagement_rate is True
    assert result.benchmarks is False
    assert result.campaign_type is False
    assert result.budget is False
    assert result.brand_campaigns_page is False
    assert result.dashboard_page is False


def test_create_advertiser_config(db_advertiser):
    AdvertiserConfigService.create_advertiser_config(
        db_advertiser.id, False, False, False, False, False, False, False, False
    )
    expected_result = AdvertiserConfig.query.filter(
        AdvertiserConfig.advertiser_id == db_advertiser.id
    ).first()

    assert expected_result.advertiser_id == db_advertiser.id
    assert expected_result.impressions is False
    assert expected_result.engagement_rate is False
    assert expected_result.benchmarks is False
    assert expected_result.campaign_type is False
    assert expected_result.budget is False
    assert expected_result.view_rate is False
    assert expected_result.brand_campaigns_page is False
    assert expected_result.dashboard_page is False


def test_check_if_config_exists_by_advertiser_id_true(db_session, db_advertiser):
    config = AdvertiserConfig(advertiser_id=db_advertiser.id)
    db_session.add(config)
    db_session.commit()

    assert AdvertiserConfigService.check_if_config_exists_by_advertiser_id(db_advertiser.id) is True


def test_check_if_config_exists_by_advertiser_id_false(db_advertiser):

    assert (
        AdvertiserConfigService.check_if_config_exists_by_advertiser_id(db_advertiser.id) is False
    )
