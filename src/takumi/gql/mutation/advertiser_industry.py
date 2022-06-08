from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.roles import permissions
from takumi.services import AdvertiserIndustryService


class AdvertiserIndustryFormMutation(Mutation):
    class Arguments:
        advertiser_id = arguments.UUID(required=True)
        advertiser_industry_id = arguments.UUID(required=True)

    advertiser_industry = fields.Field("AdvertiserIndustryChild")

    @permissions.account_manager.require()
    def mutate(root, info, advertiser_id, advertiser_industry_id):
        if not AdvertiserIndustryService.check_if_advertiser_has_advertiser_industry(
            advertiser_id, advertiser_industry_id
        ):
            advertiser_industry = AdvertiserIndustryService.add_advertiser_industry_to_advertiser(
                advertiser_id, advertiser_industry_id
            )
            return AdvertiserIndustryFormMutation(ok=True, advertiser_industry=advertiser_industry)

        return AdvertiserIndustryService.remove_advertiser_industry_from_advertiser(
            advertiser_id, advertiser_industry_id
        )


class AdvertiserIndustryMutation:
    advertiser_industry_form = AdvertiserIndustryFormMutation.Field()
