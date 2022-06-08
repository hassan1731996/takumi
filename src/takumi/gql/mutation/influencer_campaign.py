from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.models import Campaign, Offer
from takumi.roles import permissions
from takumi.services import OfferService
from takumi.services.exceptions import AlreadyRequestedException


class Answer(arguments.InputObjectType):
    prompt = arguments.String(required=True)
    answer = arguments.List(arguments.String, required=True)


def get_offer(influencer, campaign_id):
    result = (
        influencer.campaigns.filter(Campaign.id == campaign_id)
        .with_entities(Campaign, Offer)
        .one_or_none()
    )
    if not result:
        raise MutationException(f"Campaign ({campaign_id}) not found")
    if not result.Offer:
        return OfferService.create(campaign_id, influencer.id)
    return result.Offer


class ReserveCampaign(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()
        campaign_id = arguments.UUID(required=True)
        answers = arguments.List(Answer)

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, campaign_id, id=None, username=None, answers=None):
        influencer = get_influencer_or_404(id or username)
        offer = get_offer(influencer, campaign_id)
        with OfferService(offer) as service:
            service.reserve(answers=answers or [])
        return ReserveCampaign(offer=offer, ok=True)


class RequestParticipationInCampaign(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()
        campaign_id = arguments.UUID(required=True)
        answers = arguments.List(Answer)

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, campaign_id, username=None, id=None, answers=None):
        if not any([username, id]):
            raise MutationException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        influencer = get_influencer_or_404(id or username)
        offer = get_offer(influencer, campaign_id)

        try:
            with OfferService(offer) as service:
                service.request_participation(answers=answers or [])
        except AlreadyRequestedException:
            pass

        return RequestParticipationInCampaign(offer=offer, ok=True)


class RejectCampaign(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()
        campaign_id = arguments.UUID(required=True)

    offer = fields.Field("Offer")

    @permissions.public.require()
    def mutate(root, info, campaign_id, username=None, id=None):
        if not any([username, id]):
            raise MutationException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        influencer = get_influencer_or_404(id or username)
        offer = get_offer(influencer, campaign_id)
        with OfferService(offer) as service:
            service.reject()
        return RequestParticipationInCampaign(offer=offer, ok=True)


class InfluencerCampaignMutation:
    request_participation_influencer_campaign = RequestParticipationInCampaign.Field()
    reserve_influencer_campaign = ReserveCampaign.Field()
    reject_influencer_campaign = RejectCampaign.Field()
