import uuid

from takumi.models import AdvertiserConfig


def test_advertiser_config___repr__():
    advertiser_id = uuid.UUID("b06b8f9d-fc0c-4d57-81d6-a54aee7299f6")
    advertiser_config = AdvertiserConfig(advertiser_id=advertiser_id)
    assert (
        str(advertiser_config)
        == "<Advertiser (b06b8f9d-fc0c-4d57-81d6-a54aee7299f6) Configuration: None>"
    )
