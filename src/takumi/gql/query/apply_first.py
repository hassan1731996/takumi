from flask_login import current_user
from sqlalchemy import func

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import GraphQLException
from takumi.models import Campaign, Influencer, InstagramAccount, Offer, OfferEvent
from takumi.models.offer import STATES as OFFER_STATES
from takumi.roles import permissions
from takumi.services import OfferService

from .offer import OfferAnswer


def get_campaign(campaign_id):
    campaign = Campaign.query.get(campaign_id)

    if campaign is None:
        raise GraphQLException(f"Campaign ({campaign_id}) not found")

    if not permissions.team_member.can() and campaign.advertiser not in current_user.advertisers:
        # Verify user has access to the advertiser
        raise GraphQLException(f"Campaign ({campaign_id}) not found")

    if not campaign.apply_first:
        raise GraphQLException(f"Campaign ({campaign_id}) is not apply first")

    return campaign


class ApplyFirstQuery:
    offers_interested = fields.ConnectionField(
        "OfferConnection",
        campaign_id=arguments.UUID(required=True),
        answer=OfferAnswer(),
        min_er=arguments.Int(default_value=1),
    )
    offers_candidates = fields.ConnectionField(
        "OfferConnection", campaign_id=arguments.UUID(required=True), answer=OfferAnswer()
    )
    offers_approved_by_brand = fields.ConnectionField(
        "OfferConnection",
        campaign_id=arguments.UUID(required=True),
        answer=OfferAnswer(),
        include_accepted=arguments.Boolean(default_value=True),
    )
    offers_rejected_by_brand = fields.ConnectionField(
        "OfferConnection", campaign_id=arguments.UUID(required=True), answer=OfferAnswer()
    )
    offers_selected_for_campaign = fields.ConnectionField(
        "OfferConnection", campaign_id=arguments.UUID(required=True), answer=OfferAnswer()
    )
    offers_declined = fields.ConnectionField(
        "OfferConnection", campaign_id=arguments.UUID(required=True), answer=OfferAnswer()
    )

    @permissions.team_member.require()
    def resolve_offers_interested(root, info, campaign_id, answer=None, min_er=None):
        campaign = get_campaign(campaign_id)
        if not campaign.apply_first:
            raise GraphQLException(f"Campaign ({campaign_id}) is not brand match")

        query = Offer.query.filter(
            Offer.campaign_id == campaign_id,
            Offer.state == OFFER_STATES.REQUESTED,
            Offer.answers.contains([answer]) if answer else True,
        ).order_by(Offer.is_selected.desc(), Offer.request_participation_ts.desc(), Offer.id)

        if min_er:
            query = (
                query.join(Influencer)
                .join(InstagramAccount)
                .filter(InstagramAccount.engagement > (min_er / 100))
            )

        return query

    @permissions.public.require()
    def resolve_offers_candidates(root, info, campaign_id, answer=None):
        campaign = get_campaign(campaign_id)
        if not campaign.brand_match:
            raise GraphQLException(f"Campaign ({campaign_id}) is not brand match")
        return campaign.ordered_candidates_q.filter(
            Offer.answers.contains([answer]) if answer else True
        )

    @permissions.public.require()
    def resolve_offers_approved_by_brand(root, info, campaign_id, include_accepted, answer=None):
        campaign = get_campaign(campaign_id)
        if not campaign.brand_match:
            raise GraphQLException(f"Campaign ({campaign_id}) is not brand match")

        states = [OFFER_STATES.APPROVED_BY_BRAND]
        if include_accepted:
            states.append(OFFER_STATES.ACCEPTED)

        return OfferService.get_from_filter(
            filter_by=[
                Offer.campaign_id == campaign_id,
                Offer.state.in_(states),
                Offer.answers.contains([answer]) if answer else True,
            ],
            order_by=[Offer.is_selected.desc()],
        )

    @permissions.public.require()
    def resolve_offers_rejected_by_brand(root, info, campaign_id, answer=None):
        campaign = get_campaign(campaign_id)
        if not campaign.brand_match:
            raise GraphQLException(f"Campaign ({campaign_id}) is not brand match")
        return OfferService.get_from_filter(
            filter_by=[
                Offer.campaign_id == campaign_id,
                Offer.state == OFFER_STATES.REJECTED_BY_BRAND,
                Offer.answers.contains([answer]) if answer else True,
            ]
        )

    @permissions.team_member.require()
    def resolve_offers_selected_for_campaign(root, info, campaign_id, answer=None):
        campaign = get_campaign(campaign_id)

        query = Offer.query.filter(Offer.campaign == campaign, Offer.is_selected)

        if campaign.brand_match:
            query = query.filter(Offer.state == OFFER_STATES.APPROVED_BY_BRAND)
        else:
            query = query.filter(Offer.state == OFFER_STATES.REQUESTED)

        if answer:
            query = query.filter(Offer.answers.contains([answer]))

        return query

    @permissions.team_member.require()
    def resolve_offers_declined(root, info, campaign_id, answer=None):
        reject_date_subq = (
            db.session.query(
                OfferEvent.offer_id, func.max(OfferEvent.created).label("rejected_date")
            )
            .filter(OfferEvent.type.in_(("reject", "revoke", "reject_candidate")))
            .group_by(OfferEvent.offer_id)
        ).subquery()

        return (
            db.session.query(Offer)
            .join(reject_date_subq, reject_date_subq.c.offer_id == Offer.id)
            .filter(
                Offer.campaign_id == campaign_id,
                Offer.state.in_(
                    (OFFER_STATES.REJECTED, OFFER_STATES.REVOKED, OFFER_STATES.REJECTED_BY_BRAND)
                ),
                Offer.answers.contain([answer]) if answer else True,
            )
            .order_by(reject_date_subq.c.rejected_date.desc())
        )
