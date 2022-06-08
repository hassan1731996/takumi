from typing import List, Optional

from takumi.extensions import db
from takumi.models import Advertiser, AdvertiserIndustry
from takumi.services import Service


class AdvertiserIndustryService(Service):
    SUBJECT = AdvertiserIndustry

    @property
    def advertiser_industry(self) -> AdvertiserIndustry:
        return self.advertiser_industry

    @staticmethod
    def get_industry_tree() -> List[AdvertiserIndustry]:
        return AdvertiserIndustry.query.filter(AdvertiserIndustry.parent_id == None).all()

    @staticmethod
    def get_advertiser_industries_by_advertiser_id(
        advertiser_id: str,
    ) -> Optional[List[AdvertiserIndustry]]:
        if advertiser := Advertiser.query.filter_by(id=advertiser_id).one_or_none():
            return AdvertiserIndustry.query.filter(
                AdvertiserIndustry.advertisers.contains(advertiser),
                AdvertiserIndustry.parent_id != None,
            ).all()
        return None

    @staticmethod
    def add_advertiser_industry_to_advertiser(
        advertiser_id: str, advertiser_industry_id: str
    ) -> Optional[AdvertiserIndustry]:
        if advertiser := Advertiser.query.filter_by(id=advertiser_id).one_or_none():
            if advertiser_industry := AdvertiserIndustry.query.filter(
                AdvertiserIndustry.id == advertiser_industry_id,
                AdvertiserIndustry.active == True,
                AdvertiserIndustry.parent_id != None,
            ).one_or_none():
                advertiser.advertiser_industries.extend(
                    [advertiser_industry, advertiser_industry.parent]
                )
                db.session.commit()

                return advertiser_industry
        return None

    @staticmethod
    def remove_advertiser_industry_from_advertiser(
        advertiser_id: str, advertiser_industry_id: str
    ) -> None:
        if advertiser_industry := AdvertiserIndustry.query.filter(
            AdvertiserIndustry.id == advertiser_industry_id, AdvertiserIndustry.parent_id != None
        ).one_or_none():
            if advertiser := Advertiser.query.filter(
                Advertiser.id == advertiser_id,
                Advertiser.advertiser_industries.contains(advertiser_industry),
            ).one_or_none():
                advertiser.advertiser_industries.remove(advertiser_industry)

                if (
                    AdvertiserIndustry.query.filter(
                        AdvertiserIndustry.advertisers.contains(advertiser),
                        AdvertiserIndustry.parent_id == advertiser_industry.parent_id,
                    ).count()
                    == 0
                ):
                    advertiser.advertiser_industries.remove(advertiser_industry.parent)
                db.session.commit()
        return None

    @staticmethod
    def check_if_advertiser_has_advertiser_industry(
        advertiser_id: str, advertiser_industry_id: str
    ) -> Optional[bool]:
        if advertiser_industry := AdvertiserIndustry.query.filter(
            AdvertiserIndustry.id == advertiser_industry_id, AdvertiserIndustry.parent_id != None
        ).one_or_none():
            return (
                Advertiser.query.filter(
                    Advertiser.id == advertiser_id,
                    Advertiser.advertiser_industries.contains(advertiser_industry),
                ).count()
                != 0
            )
        return None
