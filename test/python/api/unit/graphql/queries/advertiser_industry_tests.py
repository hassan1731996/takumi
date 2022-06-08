import mock

from takumi.gql.query.advertiser_industry import AdvertiserIndustryQuery
from takumi.models import AdvertiserIndustry
from takumi.utils import uuid4_str


def test_get_existing_advertiser_industries(advertiser):
    advertiser_industry = AdvertiserIndustry(id=uuid4_str(), title="Test industry")
    advertiser_industry.advertisers.append(advertiser)

    with mock.patch(
        "takumi.gql.query.advertiser_industry.AdvertiserIndustryService."
        "get_advertiser_industries_by_advertiser_id",
        return_value=advertiser_industry,
    ) as mock_request:
        response = AdvertiserIndustryQuery().resolve_advertiser_industries("info", advertiser.id)

    mock_request.assert_called_once_with(advertiser.id)
    assert advertiser in response.advertisers


def test_advertiser_industries_not_have_advertiser(advertiser):
    with mock.patch(
        "takumi.gql.query.advertiser_industry.AdvertiserIndustryService."
        "get_advertiser_industries_by_advertiser_id"
    ) as mock_request:
        response = AdvertiserIndustryQuery().resolve_advertiser_industries("info", advertiser.id)

    mock_request.assert_called_once_with(advertiser.id)
    assert advertiser not in response.advertisers


def test_get_advertiser_industries_missing_advertiser_id(advertiser):
    with mock.patch(
        "takumi.gql.query.advertiser_industry.AdvertiserIndustryService."
        "get_advertiser_industries_by_advertiser_id"
    ) as mock_request:
        AdvertiserIndustryQuery().resolve_advertiser_industries("info", advertiser.id)

    mock_request.assert_called_once_with(advertiser.id)


def test_get_advertiser_industry_tree():
    advertiser_industry = AdvertiserIndustry.query

    with mock.patch(
        "takumi.gql.query.advertiser_industry.AdvertiserIndustryService.get_industry_tree",
        return_value=advertiser_industry,
    ) as mock_request:
        AdvertiserIndustryQuery().resolve_industries("info")

    mock_request.assert_called_once()
