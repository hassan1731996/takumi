from typing import Optional

from takumi.events.campaign import CampaignLog
from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.models import Campaign
from takumi.roles import permissions
from takumi.services import CampaignService
from takumi.tasks.campaign import force_stash


class ForceStashCampaign(Mutation):
    """Close a campaign that has offers

    Every offer in the campaign will be revoked, then the campaign will be archived.
    If an offer has any gigs, they will have to be manually revoked, to prevent
    accidentally using this on a campaign that shouldn't be stashed
    """

    class Arguments:
        campaign_id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.super_admin.require()
    def mutate(root, info, campaign_id: str) -> "ForceStashCampaign":
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            raise MutationException("Campaign not found")
        if any(o.is_claimable for o in campaign.offers):
            raise MutationException("There are some claimable campaigns, unable to revoke")

        force_stash.delay(campaign.id)

        return ForceStashCampaign(campaign=campaign, ok=True)


class SetCampaignPricing(Mutation):
    """Force set campaign pricing after it's launched

    This will ignore any guards by setting the price, list_price, units and
    custom reward units even if a campaign has been launched.

    Will *not* change any existing rewards!
    """

    class Arguments:
        campaign_id = arguments.UUID(required=True)
        price = arguments.Int(
            required=True, description="The price for the campaign. In whole units. £123 is 12300"
        )
        list_price = arguments.Int(
            required=True,
            description="The list price for the campaign. In whole units. £123 is 12300",
        )
        custom_reward_units = arguments.Int(
            description="The custom reward units. In whole units. £123 is 12300"
        )
        units = arguments.Int(
            description="The campaign size. Number of assets/reach/impressions/engagements"
        )

    campaign = fields.Field("Campaign")

    @permissions.super_admin.require()
    def mutate(
        root,
        info,
        campaign_id: str,
        price: int,
        list_price: int,
        custom_reward_units: Optional[int] = None,
        units: Optional[int] = None,
    ) -> "SetCampaignPricing":
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            raise MutationException("Campaign not found")

        log = CampaignLog(campaign)

        log.add_event("set_list_price", {"list_price": list_price})
        log.add_event("set_price", {"price": price})

        if custom_reward_units is not None:
            log.add_event("set_custom_reward_units", {"custom_reward_units": custom_reward_units})

        if units:
            log.add_event("set_units", {"units": units})

        db.session.commit()

        return SetCampaignPricing(ok=True, campaign=campaign)


class ReassignCampaigns(Mutation):
    """
    Transfer the campaigns owned or managed by a user to a different user.
    Useful if a campaign manager is going on holiday.
    """

    class Arguments:
        from_user_id = arguments.UUID(required=True)
        to_user_id = arguments.UUID(required=True)
        campaign_state = arguments.String(
            default_value="launched", description="Only reassign campaigns in this state"
        )

    updated_count = fields.Int()

    @permissions.developer.require()
    def mutate(root, info, from_user_id, to_user_id, campaign_state):
        updated_count = 0

        query = Campaign.query.filter(Campaign.state == campaign_state)

        for campaign in query.filter(Campaign.owner_id == from_user_id):
            with CampaignService(campaign) as service:
                service.update_owner(to_user_id)
            updated_count += 1

        for campaign in query.filter(Campaign.campaign_manager_id == from_user_id):
            with CampaignService(campaign) as service:
                service.update_campaign_manager(to_user_id)
            updated_count += 1

        for campaign in query.filter(Campaign.community_manager_id == from_user_id):
            with CampaignService(campaign) as service:
                service.update_community_manager(to_user_id)
            updated_count += 1

        return ReassignCampaigns(updated_count=updated_count, ok=True)
