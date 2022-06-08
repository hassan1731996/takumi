from takumi.gql import arguments, fields
from takumi.roles import permissions
from takumi.services import AdvertiserIndustryService


class AdvertiserIndustryQuery:
    industries = fields.List("AdvertiserIndustry")
    advertiser_industries = fields.List(
        "AdvertiserIndustryChild", advertiser_id=arguments.UUID(required=True)
    )

    @permissions.public.require()
    def resolve_industries(root, info):
        return AdvertiserIndustryService.get_industry_tree()

    @permissions.public.require()
    def resolve_advertiser_industries(root, info, advertiser_id):
        return AdvertiserIndustryService.get_advertiser_industries_by_advertiser_id(advertiser_id)
