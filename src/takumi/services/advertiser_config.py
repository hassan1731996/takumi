from typing import Optional

from takumi.extensions import db
from takumi.models import AdvertiserConfig
from takumi.services import Service


class AdvertiserConfigService(Service):
    """
    Represents the business model for Advertiser. This isolates the database
    from the application.
    """

    SUBJECT = AdvertiserConfig

    @staticmethod
    def get_config_by_advertiser_id(advertiser_id: str) -> Optional[AdvertiserConfig]:
        return AdvertiserConfig.query.filter(
            AdvertiserConfig.advertiser_id == advertiser_id
        ).first()

    @staticmethod
    def update_advertiser_config(
        advertiser_id: str,
        impressions: bool,
        engagement_rate: bool,
        benchmarks: bool,
        campaign_type: bool,
        budget: bool,
        view_rate: bool,
        brand_campaigns_page: bool,
        dashboard_page: bool,
    ) -> Optional[AdvertiserConfig]:
        config = AdvertiserConfig.query.filter(
            AdvertiserConfig.advertiser_id == advertiser_id
        ).one_or_none()
        if config:
            config.impressions = impressions
            config.engagement_rate = engagement_rate
            config.benchmarks = benchmarks
            config.campaign_type = campaign_type
            config.budget = budget
            config.view_rate = view_rate
            config.brand_campaigns_page = brand_campaigns_page
            config.dashboard_page = dashboard_page
            db.session.commit()
        return config

    @staticmethod
    def create_advertiser_config(
        id: str,
        impressions: bool,
        engagement_rate: bool,
        benchmarks: bool,
        campaign_type: bool,
        budget: bool,
        view_rate: bool,
        brand_campaigns_page: bool,
        dashboard_page: bool,
    ) -> AdvertiserConfig:
        config = AdvertiserConfig(
            advertiser_id=id,
            impressions=impressions,
            engagement_rate=engagement_rate,
            benchmarks=benchmarks,
            campaign_type=campaign_type,
            budget=budget,
            view_rate=view_rate,
            brand_campaigns_page=brand_campaigns_page,
            dashboard_page=dashboard_page,
        )
        db.session.add(config)
        db.session.commit()
        return config

    @staticmethod
    def check_if_config_exists_by_advertiser_id(advertiser_id: str) -> bool:
        return (
            AdvertiserConfig.query.filter(
                AdvertiserConfig.advertiser_id == advertiser_id
            ).one_or_none()
            is not None
        )
