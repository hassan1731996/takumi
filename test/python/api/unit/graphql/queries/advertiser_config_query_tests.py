import mock

from takumi.gql.query.advertiser_config import AdvertiserConfigQuery
from takumi.models import AdvertiserConfig
from takumi.utils import uuid4_str


def test_get_existing_advertiser_config():
    advertiser_id = uuid4_str()
    with mock.patch(
        "takumi.gql.query.advertiser_config.AdvertiserConfigService.get_config_by_advertiser_id",
        return_value=AdvertiserConfig(id=123, advertiser_id=advertiser_id),
    ) as mock_get:
        AdvertiserConfigQuery().resolve_advertiser_config("info", advertiser_id)
    assert mock_get.called
    assert mock_get.call_args[0] == (advertiser_id,)


def test_fail_advertiser_id_missed():
    with mock.patch(
        "takumi.gql.query.advertiser_config.AdvertiserConfigService.get_config_by_advertiser_id"
    ) as mock_get:
        AdvertiserConfigQuery().resolve_advertiser_config("info")
    assert mock_get.call_count == 0
