from flask_login import current_user

from takumi import slack
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_campaign_or_404, get_offer_or_404
from takumi.models import Offer
from takumi.models.offer import STATES as OFFER_STATES
from takumi.roles import permissions
from takumi.services import CampaignService, OfferService

####################################
# Picking candidates for the brand #
####################################


class PromoteToCandidate(Mutation):
    """Set offer as candidate for brand reviewal"""

    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.campaign_manager.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        with OfferService(offer) as service:
            service.set_as_candidate()

        return PromoteToCandidate(ok=True, offer=offer)


class PromoteSelectedToCandidate(Mutation):
    """Sets all selected offers in requested state to candidates"""

    class Arguments:
        campaign_id = arguments.UUID(required=True)

    offers = fields.List("Offer")
    campaign = fields.Field("Campaign")

    @permissions.campaign_manager.require()
    def mutate(root, info, campaign_id):
        campaign = get_campaign_or_404(campaign_id)

        offers = OfferService.get_from_filter(
            filter_by=[
                Offer.state == OFFER_STATES.REQUESTED,
                Offer.is_selected,
                Offer.campaign_id == campaign_id,
            ]
        )
        for offer in offers:
            with OfferService(offer) as service:
                service.set_as_candidate()

        return PromoteSelectedToCandidate(ok=True, offers=offers, campaign=campaign)


############################################
# Picking accepted offers for the campaign #
############################################


class PromoteToAccepted(Mutation):
    """Promote offer to accepted"""

    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.campaign_manager.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        with OfferService(offer) as service:
            service.accept_request()

        return PromoteToAccepted(ok=True, offer=offer)


class PromoteSelectedToAccepted(Mutation):
    """Promote all relevant selected offers to accepted"""

    class Arguments:
        campaign_id = arguments.UUID(required=True, description="The campaign id")
        force = arguments.Boolean(
            default_value=False,
            description="Whether to force accept all offers, even if it overfills the campaign",
        )

    offers = fields.List("Offer")
    campaign = fields.Field("Campaign")

    @permissions.campaign_manager.require()
    def mutate(root, info, campaign_id, force):
        campaign = get_campaign_or_404(campaign_id)

        if not campaign.apply_first:
            raise MutationException(
                "Unable to promote campaign selected in campaign that's not apply first"
            )

        if campaign.brand_match:
            with CampaignService(campaign) as service:
                offers = service.promote_selected_approved_by_brand_to_accepted(force=force)
        else:
            with CampaignService(campaign) as service:
                offers = service.promote_selected_requested_to_accepted(force=force)

        return PromoteSelectedToAccepted(ok=True, offers=offers, campaign=campaign)


##################################
# Approving/Rejecting candidates #
##################################


class ApproveCandidate(Mutation):
    """Approve a candidate for a campaign"""

    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        if current_user.role_name not in ("developer", "campaign_manager"):
            if current_user.role_name == "advertiser":
                if offer.campaign.advertiser not in current_user.advertisers:
                    raise MutationException(f"Offer ({offer_id}) not found")
            else:
                raise MutationException("Only brand can approve candidates")

        with OfferService(offer) as service:
            service.approve_candidate()

        return ApproveCandidate(ok=True, offer=offer)


class ApproveCandidates(Mutation):
    """Approve all candidates for a campaign"""

    class Arguments:
        campaign_id = arguments.UUID(required=True)

    offers = fields.List("Offer")
    campaign = fields.Field("Campaign")

    @permissions.public.require()
    def mutate(root, info, campaign_id):
        campaign = get_campaign_or_404(campaign_id)

        if current_user.role_name not in ("developer", "campaign_manager"):
            if current_user.role_name == "advertiser":
                if campaign.advertiser not in current_user.advertisers:
                    raise MutationException(f"Campaign ({campaign_id}) not found")
            else:
                raise MutationException("Only brand can approve candidates")

        offers = OfferService.get_from_filter(
            filter_by=[Offer.campaign_id == campaign_id, Offer.state == OFFER_STATES.CANDIDATE]
        )

        with CampaignService(campaign) as service:
            service.approve_candidates()

        slack.brand_approved_influencers(campaign, current_user)

        return ApproveCandidates(ok=True, offers=offers, campaign=campaign)


class RejectCandidate(Mutation):
    """Reject a candidate for a campaign"""

    class Arguments:
        offer_id = arguments.UUID(required=True)
        reason = arguments.String(description="The candidate reject reason")

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, offer_id, reason=None):
        offer = get_offer_or_404(offer_id)

        if current_user.role_name != "developer":
            if current_user.role_name == "advertiser":
                if offer.campaign.advertiser not in current_user.advertisers:
                    raise MutationException(f"Offer ({offer_id}) not found")
            else:
                raise MutationException("Only brand can reject candidates")

        if offer.state == OFFER_STATES.REJECTED_BY_BRAND:
            # Already been rejected, just silently return
            return RejectCandidate(ok=True, offer=offer)

        with OfferService(offer) as service:
            service.reject_candidate(reason=reason)

        slack.brand_rejected_influencer(offer, current_user)

        return RejectCandidate(ok=True, offer=offer)


####################
# Selecting offers #
####################


class MarkAsSelected(Mutation):
    """Mark offer as selected for promotion to accepted"""

    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.campaign_manager.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        with OfferService(offer) as service:
            service.set_is_selected(True)

        return MarkAsSelected(ok=True, offer=offer)


class UnmarkAsSelected(Mutation):
    """Unmark offer as selected for promotion to accepted"""

    class Arguments:
        offer_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.campaign_manager.require()
    def mutate(root, info, offer_id):
        offer = get_offer_or_404(offer_id)

        with OfferService(offer) as service:
            service.set_is_selected(False)

        return UnmarkAsSelected(ok=True, offer=offer)


#########
# Other #
#########


class SetApplyFirstOfferPosition(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The campaign ID")
        hash = arguments.String(required=True)
        from_index = arguments.Int(required=True, description="The index to move the entry from")
        to_index = arguments.Int(required=True, description="The index to move the entry to")

    offers = fields.ConnectionField("OfferConnection")
    hash = fields.String()

    @permissions.public.require()
    def mutate(root, info, id, from_index, to_index, hash):
        """Reorder offers in an apply first campaign"""
        campaign = get_campaign_or_404(id)

        if current_user.role_name == "advertiser":
            if campaign.advertiser not in current_user.advertisers:
                raise MutationException(f"Campaign ({campaign.id}) not found")
        elif not permissions.team_member.can():
            raise MutationException(f"Campaign ({campaign.id}) not found")

        query = campaign.ordered_candidates_q
        count = query.count()

        if from_index < 0 or from_index > count or to_index < 0 or to_index > count:
            raise MutationException(f"Indexes have to be between 0 and {count}")

        from_entry = query.offset(from_index).first()
        to_entry = query.offset(to_index).first()

        with CampaignService(campaign) as service:
            service.set_new_candidate_position(from_entry.id, to_entry.id, hash)

        return SetApplyFirstOfferPosition(
            ok=True, offers=campaign.ordered_candidates_q, hash=campaign.candidates_hash
        )


class CommentOnOffer(Mutation):
    """Make a comment on offer"""

    class Arguments:
        id = arguments.UUID(required=True, description="The offer ID to accept")
        comment = arguments.String(required=True, description="The comment content")

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, id, comment):
        offer = get_offer_or_404(id)

        if current_user.role_name == "advertiser":
            if offer.campaign.advertiser not in current_user.advertisers:
                raise MutationException(f"Offer ({offer.id}) not found")
        elif not permissions.team_member.can():
            raise MutationException(f"Offer ({offer.id}) not found")

        with OfferService(offer) as service:
            service.make_comment(comment, current_user)

        slack.commented_on_offer(offer, comment, current_user)

        return CommentOnOffer(ok=True, offer=offer)


class ApplyFirstMutation:
    approve_candidate = ApproveCandidate.Field()
    approve_candidates = ApproveCandidates.Field()
    comment_on_offer = CommentOnOffer.Field()
    mark_as_selected = MarkAsSelected.Field()
    promote_selected_to_accepted = PromoteSelectedToAccepted.Field()
    promote_selected_to_candidate = PromoteSelectedToCandidate.Field()
    promote_to_accepted = PromoteToAccepted.Field()
    promote_to_candidate = PromoteToCandidate.Field()
    reject_candidate = RejectCandidate.Field()
    set_apply_first_offer_position = SetApplyFirstOfferPosition.Field()
    unmark_as_selected = UnmarkAsSelected.Field()
