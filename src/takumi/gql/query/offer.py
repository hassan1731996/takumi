from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from takumi.gql import arguments, fields
from takumi.gql.db import filter_offers
from takumi.models import Campaign, Gig, Influencer, Offer, Post
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.rewards import RewardCalculator
from takumi.roles import permissions
from takumi.roles.permissions import manage_influencers
from takumi.services import OfferService
from takumi.utils import uuid4_str


class OfferFilteringStates(arguments.Enum):
    active = "active"
    awaiting_response = "awaiting_response"
    expired = "expired"
    history = "history"
    requested = "requested"
    revoked_or_rejected = "revoked_or_rejected"


class OfferAnswer(arguments.InputObjectType):
    prompt = arguments.String(required=True)
    answer = arguments.List(of_type=arguments.String, required=True)


class OfferQuery:
    offer = fields.Field("Offer", id=arguments.UUID(required=True), campaign_id=arguments.UUID())
    offers_for_campaign = fields.ConnectionField(
        "OfferConnection",
        id=arguments.UUID(required=True),
        state=arguments.String(),
        awaiting_submission=arguments.Boolean(),
        answer=OfferAnswer(),
    )
    offers_for_influencer = fields.ConnectionField(
        "OfferConnection", username=arguments.String(required=True), state=OfferFilteringStates()
    )
    offers_for_post = fields.ConnectionField(
        "OfferConnection", id=arguments.UUID(required=True), submitted=arguments.Boolean()
    )
    offer_for_influencer_in_campaign = fields.Field(
        "Offer", username=arguments.String(required=True), campaign_id=arguments.UUID(required=True)
    )
    top_offers_in_campaign = fields.ConnectionField(
        "OfferConnection", campaign_id=arguments.UUID(required=True)
    )

    @permissions.public.require()
    def resolve_offer(root, info, id, campaign_id=None):
        query = filter_offers()
        offer = query.filter(Offer.id == id).one_or_none()

        if offer is None and OfferService.get_by_id(id) is None and campaign_id is not None:
            from takumi.gql.utils import get_offer_for_public_campaign

            offer = get_offer_for_public_campaign(campaign_id, id, commit=True)

        return offer

    @permissions.public.require()
    def resolve_offers_for_campaign(
        root, info, id, state=None, awaiting_submission=False, answer=None
    ):
        query = (
            filter_offers()
            .filter(Offer.campaign_id == id)
            .order_by(Offer.accepted.desc(), Offer.created.desc())
            .options(joinedload(Offer.influencer).joinedload(Influencer.address))
        )

        if state is not None:
            query = query.filter(Offer.state == state)

        if awaiting_submission:
            query = query.filter(Offer.submitted_gig_count == 0)

        if answer:
            query = query.filter(Offer.answers.contains([answer]))

        return query

    @permissions.public.require()
    def resolve_top_offers_in_campaign(root, info, campaign_id):
        """Resolver, which returns top-performing Creators on a single campaign analytics page.

        Args:
            campaign_id (UUID): The campaign's id.

        Returns:
            list: List of top most successful creators.
        """
        return OfferService.get_top_offers_in_campaign(campaign_id)

    @permissions.public.require()  # noqa: C901
    def resolve_offers_for_influencer(root, info, username, state=None):
        influencer = Influencer.by_username(username.strip())
        if influencer is None:
            return None
        if current_user.influencer != influencer and not manage_influencers.can():
            return None

        if state is not None:
            if state == OfferFilteringStates.active:
                # active campaigns = accepted offers that aren’t claimed
                return influencer.active_campaigns.with_entities(Offer)
            elif state == OfferFilteringStates.requested:
                return influencer.requested_campaigns.with_entities(Offer)
            elif state == OfferFilteringStates.history:
                # history = claimed offers.
                return influencer.campaign_history.with_entities(Offer)
            elif state == OfferFilteringStates.awaiting_response:
                # offers = offers that aren’t accepted or campaign is public
                offers = []
                for campaign, offer in influencer.targeted_campaigns.with_entities(Campaign, Offer):
                    if offer:
                        offers.append(offer)
                        continue
                    state = OFFER_STATES.PENDING if campaign.apply_first else OFFER_STATES.INVITED
                    offers.append(
                        Offer(
                            id=uuid4_str(),
                            state=state,
                            reward=RewardCalculator(campaign).calculate_reward_for_influencer(
                                influencer
                            ),
                            campaign=campaign,
                            influencer=influencer,
                        )
                    )
                return offers
            elif state == OfferFilteringStates.revoked_or_rejected:
                return influencer.revoked_or_rejected_campaigns.with_entities(Offer)
            elif state == OfferFilteringStates.expired:
                # expired = offers that didn't get acted upon (are still in new and the campaign has finished)
                return influencer.expired_campaigns.with_entities(Offer)

        return influencer.campaigns.with_entities(Offer)

    @permissions.public.require()
    def resolve_offers_for_post(root, info, id, submitted=None):
        query = (
            filter_offers()
            .join(Post)
            .filter(Offer.state == OFFER_STATES.ACCEPTED, Post.id == id)
            .order_by(Offer.accepted.desc())
        )
        if submitted is None:
            return query

        submitted_states = (
            GIG_STATES.SUBMITTED,
            GIG_STATES.REVIEWED,
            GIG_STATES.APPROVED,
            GIG_STATES.REJECTED,
        )

        if submitted:
            return query.join(Gig, Gig.offer_id == Offer.id).filter(
                Offer.gigs.any(and_(Gig.post_id == id, Gig.state.in_(submitted_states)))
            )
        else:
            return [
                o
                for o in query
                if not [g for g in o.gigs if g.post_id == id and g.state in submitted_states]
            ]

    @permissions.public.require()
    def resolve_offer_for_influencer_in_campaign(root, info, username, campaign_id):
        influencer = Influencer.by_username(username.strip()) or Influencer.from_url(
            username.strip()
        )
        if not influencer:
            return None

        return (
            filter_offers()
            .filter(Offer.influencer_id == influencer.id, Offer.campaign_id == campaign_id)
            .one_or_none()
        )
