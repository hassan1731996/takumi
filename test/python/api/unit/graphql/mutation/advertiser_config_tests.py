import mock

from takumi.gql.mutation.advertiser_config import AdvertiserConfigMutation
from takumi.models import AdvertiserConfig
from takumi.utils import uuid4_str


def test_create_advertiser_config(monkeypatch, account_manager, client):
    advertiser_id = uuid4_str()
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser_config.AdvertiserConfigService.check_if_config_exists_by_advertiser_id",
        lambda x: False,
    )

    with client.user_request_context(account_manager):
        with mock.patch(
            "takumi.gql.mutation.advertiser_config.AdvertiserConfigService.create_advertiser_config",
            return_value=AdvertiserConfig(advertiser_id=advertiser_id),
        ) as mock_create_config:
            AdvertiserConfigMutation().mutate(info="info", advertiser_id=advertiser_id)

    assert mock_create_config.called
    assert mock_create_config.call_args[0] == (
        advertiser_id,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )


def test_update_advertiser_config(monkeypatch, account_manager, client):
    advertiser_id = uuid4_str()
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser_config.AdvertiserConfigService.check_if_config_exists_by_advertiser_id",
        lambda x: True,
    )

    with client.user_request_context(account_manager):
        with mock.patch(
            "takumi.gql.mutation.advertiser_config.AdvertiserConfigService.update_advertiser_config",
            return_value=AdvertiserConfig(advertiser_id=advertiser_id),
        ) as mock_create_config:
            AdvertiserConfigMutation().mutate(
                info="info",
                advertiser_id=advertiser_id,
                view_rate=True,
                budget=True,
            )

    assert mock_create_config.called
    assert mock_create_config.call_args[0] == (
        advertiser_id,
        False,
        False,
        False,
        False,
        True,
        True,
        False,
        False,
    )
