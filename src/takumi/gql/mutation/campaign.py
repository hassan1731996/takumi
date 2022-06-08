from flask_login import current_user

from takumi.constants import INDUSTRY_CHOICES
from takumi.gql import arguments, fields
from takumi.gql.enums.campaign import RewardModel
from takumi.gql.enums.offer import RevokeOfferState
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import (
    get_advertiser_or_404,
    get_campaign_or_404,
    get_market_or_404,
    get_user_or_404,
)
from takumi.models import Offer
from takumi.models.campaign import RewardModels
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.roles import permissions, provide_advertiser_access_need
from takumi.services import CampaignService, OfferService, PostService, TargetingService
from takumi.services.payment import PaymentService
from takumi.services.payment.types import PaymentDataDict


class PromptType(arguments.Enum):
    confirm = "confirm"
    multiple_choice = "multiple_choice"
    single_choice = "single_choice"
    text_input = "text_input"


class Prompt(arguments.InputObjectType):
    type = PromptType(required=True)
    text = arguments.String()
    choices = arguments.List(arguments.String)
    brand_visible = arguments.Boolean(default_value=False)


class CreateCampaign(Mutation):
    class Arguments:
        advertiser_id = arguments.UUID(required=True)
        market_slug = arguments.String(required=True)
        reward_model = RewardModel(required=True, description="The campaign unit type")
        brand_match = arguments.Boolean(default_value=False)
        units = arguments.Int(default_value=0)
        shipping_required = arguments.Boolean(default_value=False)
        require_insights = arguments.Boolean(default_value=False)
        price = arguments.Int(required=True, description="The price that the client was charged")
        list_price = arguments.Int(
            required=True, description="The list price, according to the rate cards"
        )

        custom_reward_units = arguments.Int(
            description="If not provided, the reward will be calculated from the platform margins"
        )

        name = arguments.String()
        description = arguments.String()
        pictures = arguments.List(arguments.PictureInput, default_value=[])
        prompts = arguments.List(Prompt, default_value=[])

        tags = arguments.List(arguments.String)
        owner = arguments.UUID()
        campaign_manager = arguments.UUID()
        secondary_campaign_manager = arguments.UUID()
        community_manager = arguments.UUID()
        has_nda = arguments.Boolean(default_value=False)
        brand_safety = arguments.Boolean(default_value=False)
        pro_bono = arguments.Boolean(default_value=False)
        extended_review = arguments.Boolean(default_value=False)
        industry = arguments.String()

        opportunity_product_id = arguments.String()

    campaign = fields.Field("Campaign")

    @permissions.edit_campaign.require()
    def mutate(
        root,
        info,
        advertiser_id,
        market_slug,
        reward_model,
        units,
        shipping_required,
        require_insights,
        price,
        list_price,
        pictures,
        has_nda,
        brand_safety,
        pro_bono,
        extended_review,
        brand_match,
        prompts,
        tags=None,
        custom_reward_units=None,
        owner=None,
        name=None,
        description=None,
        campaign_manager=None,
        secondary_campaign_manager=None,
        community_manager=None,
        industry=None,
        opportunity_product_id=None,
    ):

        if industry and industry not in INDUSTRY_CHOICES:
            raise MutationException(f'"{industry}" is not a valid `industry` value')

        if campaign_manager:
            get_user_or_404(campaign_manager)
        if secondary_campaign_manager:
            get_user_or_404(secondary_campaign_manager)
        if community_manager:
            get_user_or_404(community_manager)

        advertiser = get_advertiser_or_404(advertiser_id)

        owner = get_user_or_404(owner) if owner else current_user
        market = get_market_or_404(market_slug)

        if custom_reward_units is not None:
            custom_reward_units = custom_reward_units if custom_reward_units >= 0 else None

        campaign = CampaignService.create_campaign(
            advertiser_id=advertiser.id,
            market=market,
            reward_model=reward_model,
            units=units,
            shipping_required=shipping_required,
            require_insights=require_insights,
            price=price * 100,
            list_price=list_price * 100,
            custom_reward_units=custom_reward_units,
            name=name,
            description=description,
            pictures=pictures,
            owner_id=owner.id,
            prompts=prompts,
            campaign_manager_id=campaign_manager,
            secondary_campaign_manager_id=secondary_campaign_manager,
            community_manager_id=community_manager,
            tags=tags,
            has_nda=has_nda,
            brand_safety=brand_safety,
            extended_review=extended_review,
            industry=industry,
            opportunity_product_id=opportunity_product_id,
            brand_match=brand_match,
            pro_bono=pro_bono,
        )

        TargetingService.create_targeting(campaign.id, campaign.market, advertiser)

        # Default max followers in asset campaigns
        if campaign.reward_model == RewardModels.assets:
            with TargetingService(campaign.targeting) as service:
                service.update_followers(min_followers=None, max_followers=40_000)

        # create one post for this campaign
        PostService.create_post(campaign.id, PostTypes.standard)

        return CreateCampaign(campaign=campaign, ok=True)


class AcceptSingleCampaignRequest(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The campaign ID")
        offer_id = arguments.UUID(required=True, description="The offer ID to accept")

    campaign = fields.Field("Campaign")
    offer = fields.Field("Offer")

    @permissions.campaign_manager.require()
    def mutate(root, info, id, offer_id):
        return AcceptSingleCampaignRequest(ok=True)


class UpdateCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

        units = arguments.Int()
        price = arguments.Int(description="The price that the client was charged")
        list_price = arguments.Int(description="The list price, according to the rate cards")
        shipping_required = arguments.Boolean()
        require_insights = arguments.Boolean()

        custom_reward_units = arguments.Int(
            description=(
                "If not provided, the reward will be calculated from the platform margins. "
                "To unset the field, provide a value that's less than `0`. Optimally we'd pass "
                "in `null`, but Graphene doesn't support that"
            )
        )

        name = arguments.String()
        description = arguments.String()
        pictures = arguments.List(arguments.PictureInput)

        owner = arguments.UUID()
        prompts = arguments.List(Prompt)
        campaign_manager = arguments.UUID()
        secondary_campaign_manager = arguments.UUID()
        community_manager = arguments.UUID()
        has_nda = arguments.Boolean()
        brand_safety = arguments.Boolean()
        brand_match = arguments.Boolean()
        pro_bono = arguments.Boolean()
        extended_review = arguments.Boolean()
        industry = arguments.String()

        tags = arguments.List(arguments.String)
        public = arguments.Boolean()
        push_notification_message = arguments.String()
        opportunity_product_id = arguments.String()

    campaign = fields.Field("Campaign")

    @staticmethod
    def _validate_view_model(
        campaign, owner, campaign_manager, secondary_campaign_manager, community_manager
    ):
        if owner is not None:
            get_user_or_404(owner)
        if campaign_manager is not None:
            get_user_or_404(campaign_manager)
        if secondary_campaign_manager is not None:
            get_user_or_404(secondary_campaign_manager)
        if community_manager is not None:
            get_user_or_404(community_manager)

    @permissions.edit_campaign.require()
    def mutate(  # noqa: C901
        root,
        info,
        id,
        units=None,
        shipping_required=None,
        price=None,
        list_price=None,
        name=None,
        description=None,
        pictures=None,
        owner=None,
        campaign_manager=None,
        secondary_campaign_manager=None,
        community_manager=None,
        has_nda=None,
        brand_safety=None,
        brand_match=None,
        extended_review=None,
        industry=None,
        tags=None,
        public=None,
        prompts=None,
        push_notification_message=None,
        opportunity_product_id=None,
        custom_reward_units=None,
        require_insights=None,
        pro_bono=None,
    ):
        campaign = get_campaign_or_404(id)
        UpdateCampaign._validate_view_model(
            campaign, owner, campaign_manager, secondary_campaign_manager, community_manager
        )

        with CampaignService(campaign) as service:
            if units is not None:
                service.update_units(units)
            if shipping_required is not None:
                service.update_shipping_required(shipping_required)
            if name is not None:
                service.update_name(name)
            if description is not None:
                service.update_description(description)
            if pictures is not None:
                service.update_pictures(pictures)
            if prompts is not None:
                service.update_prompts(prompts)
            if owner is not None:
                service.update_owner(owner)
            if campaign_manager is not None:
                service.update_campaign_manager(campaign_manager)
            if secondary_campaign_manager is not None:
                service.update_secondary_campaign_manager(secondary_campaign_manager)
            if community_manager is not None:
                service.update_community_manager(community_manager)
            if has_nda is not None:
                service.update_has_nda(has_nda)
            if brand_safety is not None:
                if campaign.brand_safety != brand_safety:
                    service.update_brand_safety(brand_safety)
            if brand_match is not None:
                if campaign.brand_match != brand_match:
                    service.update_brand_match(brand_match)
            if extended_review is not None:
                if campaign.extended_review != extended_review:
                    service.update_extended_review(extended_review)
            if industry is not None:
                service.update_industry(industry)
            if tags is not None:
                service.update_tags(tags)
            if public is not None:
                service.update_public(public)
            if push_notification_message is not None:
                service.update_push_notification_message(push_notification_message)
            if opportunity_product_id is not None:
                service.update_opportunity_product_id(opportunity_product_id)
            if price is not None and price * 100 != campaign.price:
                service.update_price(price * 100)
            if list_price is not None and list_price * 100 != campaign.list_price:
                service.update_list_price(list_price * 100)
            if custom_reward_units is not None:
                reward_units = custom_reward_units if custom_reward_units >= 0 else None
                if reward_units != campaign.custom_reward_units:
                    service.update_custom_reward_units(reward_units)
            if require_insights is not None:
                service.update_require_insights(require_insights)
            if pro_bono is not None:
                if campaign.pro_bono != pro_bono:
                    service.update_pro_bono(pro_bono)

        return UpdateCampaign(campaign=campaign, ok=True)


class LaunchCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.launch_campaign.require()
    def mutate(root, info, id):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as service:
            service.launch()

        for offer in campaign.offers:
            with OfferService(offer) as service:
                service.send_push_notification()

        return LaunchCampaign(campaign=campaign, ok=True)


class NotifyAllTargetsInCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        not_notified_in_the_last_hours = arguments.Int()

    campaign = fields.Field("Campaign")

    @permissions.campaign_manager.require()
    def mutate(root, info, id, not_notified_in_the_last_hours=None):
        campaign = get_campaign_or_404(id)

        if not campaign.public:
            with CampaignService(campaign) as service:
                service.update_public(True)

        with CampaignService(campaign) as service:
            service.send_notifications_to_all_targets(not_notified_in_the_last_hours)

        return NotifyAllTargetsInCampaign(campaign=campaign, ok=True)


class RevokeRequestedOffers(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        state = RevokeOfferState(default_value=OFFER_STATES.REQUESTED)

    @permissions.campaign_manager.require()
    def mutate(root, info, id, state):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as srv:
            srv.revoke_requested_offers(state)

        return RevokeRequestedOffers(ok=True)


class GenerateCampaignReportToken(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.public.require()
    def mutate(root, info, id):
        campaign = get_campaign_or_404(id)

        provide_advertiser_access_need(current_user, campaign.advertiser_id)
        permissions.advertiser_member.test()  # Only members can generate campaign report tokens

        with CampaignService(campaign) as service:
            service.new_report_token()

        return GenerateCampaignReportToken(campaign=campaign, ok=True)


class PreviewCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        username = arguments.String(required=True)

    @permissions.preview_campaign.require()
    def mutate(root, info, id, username):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as service:
            service.preview(username)

        return PreviewCampaign(ok=True)


class CompleteCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.mark_campaign_as_completed.require()
    def mutate(root, info, id):
        campaign = get_campaign_or_404(id)

        # If a campaign is pro-bono, we just mark all existing offers as claimed and then complete it
        if campaign.pro_bono:
            offer: Offer
            # Set all accepted offers as claimable
            for offer in (
                o
                for o in campaign.offers
                if o.state == Offer.STATES.ACCEPTED and not o.is_claimable
            ):
                with OfferService(offer) as service:
                    service.set_claimable(force=True)

            # Mark each unclaimed as claimed
            for offer in (o for o in campaign.offers if o.is_claimable and not o.claimed):
                data: PaymentDataDict = {
                    "destination": {"type": "takumi", "value": "pro-bono-campaign"}
                }
                payment = PaymentService.create(offer.id, data=data)
                with PaymentService(payment) as service:
                    service.request(data)

        with CampaignService(campaign) as service:
            service.complete()

        return CompleteCampaign(campaign=campaign, ok=True)


class StashCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.edit_campaign.require()
    def mutate(root, info, id):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as service:
            service.stash()

        return StashCampaign(campaign=campaign, ok=True)


class RestoreCampaign(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    campaign = fields.Field("Campaign")

    @permissions.edit_campaign.require()
    def mutate(root, info, id):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as service:
            service.restore()

        return RestoreCampaign(campaign=campaign, ok=True)


class SetReportSummary(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        summary = arguments.String(description="The report summary for the campaign")

    campaign = fields.Field("Campaign")

    @permissions.edit_campaign.require()
    def mutate(root, info, id, summary):
        campaign = get_campaign_or_404(id)

        with CampaignService(campaign) as service:
            service.update_report_summary(summary)

        return SetReportSummary(campaign=campaign, ok=True)


class CampaignMutation:
    accept_single_campaign_request = AcceptSingleCampaignRequest.Field()
    complete_campaign = CompleteCampaign.Field()
    create_campaign = CreateCampaign.Field()
    generate_campaign_report_token = GenerateCampaignReportToken.Field()
    launch_campaign = LaunchCampaign.Field()
    preview_campaign = PreviewCampaign.Field()
    restore_campaign = RestoreCampaign.Field()
    stash_campaign = StashCampaign.Field()
    update_campaign = UpdateCampaign.Field()
    notify_all_targets_in_campaign = NotifyAllTargetsInCampaign.Field()
    revoke_requested_offers = RevokeRequestedOffers.Field()
    set_report_summary = SetReportSummary.Field()
