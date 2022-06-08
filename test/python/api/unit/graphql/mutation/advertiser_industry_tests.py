import mock

from takumi.gql.mutation.advertiser_industry import AdvertiserIndustryFormMutation
from takumi.utils import uuid4_str


def test_add_advertiser_industry_to_advertiser_mutation(
    monkeypatch, account_manager, client, advertiser_industry
):
    advertiser_id = uuid4_str()

    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser_industry.AdvertiserIndustryService."
        "check_if_advertiser_has_advertiser_industry",
        lambda x, y: False,
    )

    with client.user_request_context(account_manager):
        with mock.patch(
            "takumi.gql.mutation.advertiser_industry.AdvertiserIndustryService."
            "add_advertiser_industry_to_advertiser",
            return_value=advertiser_industry,
        ) as mock_request:
            AdvertiserIndustryFormMutation().mutate(
                info="info",
                advertiser_id=advertiser_id,
                advertiser_industry_id=advertiser_industry.id,
            )

    mock_request.assert_called_once_with(advertiser_id, advertiser_industry.id)


def test_add_advertiser_industry_to_advertiser(
    monkeypatch, account_manager, client, advertiser_industry
):
    advertiser_id = uuid4_str()

    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser_industry.AdvertiserIndustryService."
        "check_if_advertiser_has_advertiser_industry",
        lambda advertiser_id, advertiser_industry_id: True,
    )

    with client.user_request_context(account_manager):
        with mock.patch(
            "takumi.gql.mutation.advertiser_industry.AdvertiserIndustryService."
            "remove_advertiser_industry_from_advertiser",
            return_value=advertiser_industry,
        ) as mock_request:
            AdvertiserIndustryFormMutation().mutate(
                info="info",
                advertiser_id=advertiser_id,
                advertiser_industry_id=advertiser_industry.id,
            )

    mock_request.assert_called_once_with(advertiser_id, advertiser_industry.id)
