import uuid

from takumi.models import AdvertiserIndustry


def test_advertiser_industry___repr__():
    advertiser_industry_id = uuid.UUID("ad9fc8b0-933b-48d9-bed0-14c5548a1313")
    advertiser_industry_title = "Tobacco"
    advertiser_industry = AdvertiserIndustry(
        id=advertiser_industry_id, title=advertiser_industry_title
    )

    assert (
        str(advertiser_industry)
        == "<Advertiser Industry: ad9fc8b0-933b-48d9-bed0-14c5548a1313 (Tobacco)>"
    )
