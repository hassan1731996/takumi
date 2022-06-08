from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import AdvertiserConfigService


class AdvertiserConfigQuery:
    advertiser_config = fields.Field(
        "AdvertiserConfig", advertiser_id=arguments.UUID(required=True)
    )

    @permissions.public.require()
    def resolve_advertiser_config(root, info, advertiser_id=None):
        if advertiser_id:
            return AdvertiserConfigService.get_config_by_advertiser_id(advertiser_id)
        return None
