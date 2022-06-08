import graphene

from .campaign import ForceStashCampaign, ReassignCampaigns, SetCampaignPricing
from .gig import SwapGigPosts
from .offer import MarkAsPaid
from .region import AddRegionByCountryCode
from .user import DisableUser


class UnstableMutation(graphene.ObjectType):
    """Developer-only mutations that aren't production ready"""

    add_region_by_country_code = AddRegionByCountryCode.Field()
    disable_user = DisableUser.Field()
    force_stash_campaign = ForceStashCampaign.Field()
    mark_as_paid = MarkAsPaid.Field()
    reassign_campaigns = ReassignCampaigns.Field()
    set_campaign_pricing = SetCampaignPricing.Field()
    swap_gig_posts = SwapGigPosts.Field()
