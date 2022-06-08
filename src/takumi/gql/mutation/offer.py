from flask_login import current_user

from takumi import slack
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_offer_or_404
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.roles import permissions
from takumi.services import InfluencerService, OfferService
from takumi.services.exceptions import AlreadyRequestedException


class RevokeOffer(Mutation):
    """Revoke an offer. This is done by a team member."""

    class Arguments:
        id = arguments.UUID(required=True, description="The ID of the offer being cancelled")

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.revoke()

        return RevokeOffer(offer=offer, ok=True)


class MakeOffer(Mutation):
    """Create an offer for an influencer to a campaign"""

    class Arguments:
        campaign_id = arguments.UUID(required=True, description="The ID of the campaign")
        influencer_id = arguments.UUID(required=True, description="The ID of the influencer")
        skip_targeting = arguments.Boolean(
            description="Developer only: Whether to skip targeting or not", default_value=False
        )

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, campaign_id, influencer_id, skip_targeting):
        if skip_targeting and not permissions.developer.can():
            raise MutationException("Developer permission required to skip targeting")

        offer = OfferService.create(campaign_id, influencer_id, skip_targeting=skip_targeting)
        if offer.campaign.state == CAMPAIGN_STATES.LAUNCHED and offer.influencer.has_device:
            with OfferService(offer) as service:
                service.send_push_notification()

        return MakeOffer(offer=offer, ok=True)


class MakeCustomOffer(Mutation):
    """Create an accepted offer with a custom reward"""

    class Arguments:
        campaign_id = arguments.UUID(required=True, description="The ID of the campaign")
        id = arguments.UUID(description="The ID of the influencer")
        username = arguments.String(required=True, description="The username of the influencer")
        reward = arguments.Int(required=True, description="The reward")
        force_reserve = arguments.Boolean(
            default_value=True, description="Whether to force reserve the offer for the influencer"
        )

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, campaign_id, reward, force_reserve, username=None, id=None):
        if not any([username, id]):
            raise MutationException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        influencer = InfluencerService.get_by_username(username)

        if influencer is None:
            raise MutationException(f"Influencer ({username}) not found")

        offer = OfferService.get_for_influencer_in_campaign(influencer.id, campaign_id)

        if offer is None:
            offer = OfferService.create(
                campaign_id, influencer.id, reward=reward * 100, skip_targeting=True
            )
            if influencer.has_device:
                with OfferService(offer) as service:
                    service.send_push_notification()
        else:
            with OfferService(offer) as service:
                service.update_reward(reward * 100)

        if force_reserve:
            campaign = offer.campaign
            if campaign.apply_first:
                with OfferService(offer) as service:
                    service.request_participation()
            else:
                with OfferService(offer) as service:
                    service.force_reserve()

        return MakeCustomOffer(offer=offer, ok=True)


class UpdateReward(Mutation):
    """Update the reward on an offer. Allows campaign managers to boost rewards."""

    class Arguments:
        id = arguments.UUID(required=True, description="The offer ID")
        reward = arguments.Int(
            required=True, description="The reward in whole pounds, euros or dollars"
        )

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, reward):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.update_reward(reward * 100)

        return UpdateReward(offer=offer, ok=True)


class MarkDispatched(Mutation):
    """For a campaign that requires shipping, mark the offer as dispatched"""

    class Arguments:
        id = arguments.UUID(required=True, description="The ID of the offer being cancelled")
        tracking_code = arguments.String(description="The tracking code")

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, tracking_code=None):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.mark_dispatched(tracking_code)

        return MarkDispatched(offer=offer, ok=True)


class SendOfferPushNotification(Mutation):
    """Send a push notification for an active offer"""

    class Arguments:
        id = arguments.UUID(
            required=True, description="The ID of the offer that the push notification is sent for"
        )

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)
        if offer.campaign.is_fully_reserved():
            raise MutationException("Can't send a push notification for a fully reserved campaign")

        with OfferService(offer) as service:
            service.send_push_notification()

        return SendOfferPushNotification(offer=offer, ok=True)


class AcceptOffer(Mutation):
    """Accept a previously made offer"""

    class Arguments:
        id = arguments.UUID(required=True, description="The offer ID to accept")
        force = arguments.Boolean(description="Developer only: Force accepting of an offer")
        campaign_id = arguments.UUID()

    offer = fields.Field("Offer")

    @permissions.influencer.require()
    def mutate(root, info, id, force=False, campaign_id=None):
        offer = OfferService.get_by_id(id)
        if offer is None:
            if campaign_id is not None:
                from takumi.gql.utils import get_offer_for_public_campaign

                offer = get_offer_for_public_campaign(campaign_id, id, commit=True)
            if offer is None:
                raise MutationException(f"Offer ({id}) not found")

        skip_owner_verification = force and permissions.developer.can()
        if not skip_owner_verification and offer.influencer != current_user.influencer:
            # Raise the same exception as thrown in get_offer_or_404
            raise MutationException(f"Offer ({id}) not found")

        with OfferService(offer) as service:
            service.reserve()

        slack.offer_reserve(offer)

        return AcceptOffer(offer=offer, ok=True)


class RequestParticipation(Mutation):
    """Request participation on an apply first campaign"""

    class Arguments:
        id = arguments.UUID(required=True, description="The offer ID to accept")

    offer = fields.Field("Offer")

    @permissions.influencer.require()
    def mutate(root, info, id, force=False, campaign_id=None):
        offer = get_offer_or_404(id)

        skip_owner_verification = force and permissions.developer.can()
        if not skip_owner_verification and offer.influencer != current_user.influencer:
            # Raise the same exception as thrown in get_offer_or_404
            raise MutationException(f"Offer ({id}) not found")

        try:
            with OfferService(offer) as service:
                service.request_participation()
        except AlreadyRequestedException:
            pass

        return RequestParticipation(offer=offer, ok=True)


class RejectOffer(Mutation):
    """Reject a previously made offer"""

    class Arguments:
        id = arguments.UUID(required=True, description="The offer ID to reject")
        force = arguments.Boolean(description="Developer only: Force rejecting of an offer")

    offer = fields.Field("Offer")

    @permissions.influencer.require()
    def mutate(root, info, id, force=False):
        offer = get_offer_or_404(id)
        skip_owner_verification = force and permissions.developer.can()
        offer_doesnt_belong_to_user_advertiser = (
            current_user.role_name == "advertiser"
            and offer.campaign.advertiser not in current_user.advertisers
        )
        offer_doesnt_belong_to_user_influencer = (
            not skip_owner_verification and offer.influencer != current_user.influencer
        )

        if offer_doesnt_belong_to_user_advertiser and offer_doesnt_belong_to_user_influencer:
            raise MutationException(f"Offer ({id}) not found")

        with OfferService(offer) as service:
            service.reject()

        return RejectOffer(offer=offer, ok=True)


class ForceReserveOffer(Mutation):
    """Change the state of an rejected offer to accepted

    Used when an influencer has 'accidentally' rejected an offer but contacted support.
    This goes against the current flow of offers but was happening too frequently
    """

    class Arguments:
        id = arguments.UUID(
            required=True, description="The ID of the offer that the push notification is sent for"
        )

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)

        campaign = offer.campaign
        if campaign.apply_first:
            with OfferService(offer) as service:
                service.request_participation(ignore_prompts=True)
        else:
            with OfferService(offer) as service:
                service.force_reserve()

        return ForceReserveOffer(offer=offer, ok=True)


class MarkAsSelected(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.set_is_selected(True)

        return MarkAsSelected(ok=True, offer=offer)


class MarkCommentsAsSeen(Mutation):
    """
    Mark all comments of an offer as seen
    """

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the offer")

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.mark_comments_as_seen_by(current_user)

        return MarkCommentsAsSeen(ok=True, offer=offer)


class UnmarkAsSelected(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        offer = get_offer_or_404(id)

        with OfferService(offer) as service:
            service.set_is_selected(False)

        return UnmarkAsSelected(ok=True, offer=offer)


class RevertRejection(Mutation):
    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.manage_influencers.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        with OfferService(offer) as service:
            service.revert_rejection()

        return RevertRejection(ok=True, offer=offer)


class OfferMutation:
    accept_offer = AcceptOffer.Field()
    force_reserve_offer = ForceReserveOffer.Field()
    make_custom_offer = MakeCustomOffer.Field()
    make_offer = MakeOffer.Field()
    mark_as_selected = MarkAsSelected.Field()
    mark_comments_as_seen = MarkCommentsAsSeen.Field()
    mark_dispatched = MarkDispatched.Field()
    reject_offer = RejectOffer.Field()
    request_participation = RequestParticipation.Field()
    revoke_offer = RevokeOffer.Field()
    send_offer_push_notification = SendOfferPushNotification.Field()
    unmark_as_selected = UnmarkAsSelected.Field()
    update_reward = UpdateReward.Field()
    revert_rejection = RevertRejection.Field()
