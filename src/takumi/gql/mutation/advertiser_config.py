from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.roles import permissions
from takumi.services import AdvertiserConfigService


class AdvertiserConfigMutation(Mutation):
    class Arguments:
        advertiser_id = arguments.UUID(required=True)
        impressions = arguments.Boolean()
        engagement_rate = arguments.Boolean()
        benchmarks = arguments.Boolean()
        campaign_type = arguments.Boolean()
        budget = arguments.Boolean()
        view_rate = arguments.Boolean()
        # pages config
        brand_campaigns_page = arguments.Boolean()
        dashboard_page = arguments.Boolean()

    advertiser_config = fields.Field("AdvertiserConfig")

    @permissions.create_brand.require()
    def mutate(
        root,
        info,
        advertiser_id,
        impressions=False,
        engagement_rate=False,
        benchmarks=False,
        campaign_type=False,
        budget=False,
        view_rate=False,
        brand_campaigns_page=False,
        dashboard_page=False,
    ):
        if AdvertiserConfigService.check_if_config_exists_by_advertiser_id(advertiser_id):
            config = AdvertiserConfigService.update_advertiser_config(
                advertiser_id,
                impressions,
                engagement_rate,
                benchmarks,
                campaign_type,
                budget,
                view_rate,
                brand_campaigns_page,
                dashboard_page,
            )
        else:
            config = AdvertiserConfigService.create_advertiser_config(
                advertiser_id,
                impressions,
                engagement_rate,
                benchmarks,
                campaign_type,
                budget,
                view_rate,
                brand_campaigns_page,
                dashboard_page,
            )

        return AdvertiserConfigMutation(ok=True, advertiser_config=config)


class AdvertiserConfigFormMutation:
    advertiser_config_form = AdvertiserConfigMutation.Field()
