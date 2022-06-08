from flask_login import current_user
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import load_only

from takumi.gql import arguments, fields
from takumi.gql.db import filter_gigs
from takumi.gql.exceptions import QueryException
from takumi.gql.utils import get_post_or_404
from takumi.models import Campaign, Gig, Influencer, Offer, Post
from takumi.models.gig import STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.roles import permissions
from takumi.services import GigService


def gig_query():
    """Return a gig query which filters to only accepted offers."""
    return (
        filter_gigs()
        .unique_join(Offer, Offer.id == Gig.offer_id)
        .filter(Offer.state == OFFER_STATES.ACCEPTED)
    )


class GigQuery:
    _filters = {
        "campaign_id": arguments.UUID(),
        "post_id": arguments.UUID(),
        "influencer_id": arguments.UUID(),
        "state": arguments.String(),
        "unreviewed": arguments.Boolean(),
        "unverified": arguments.Boolean(),
        "reported": arguments.Boolean(),
        "mine": arguments.Boolean(),
        "posted": arguments.Boolean(),
    }
    gig = fields.Field("Gig", id=arguments.UUID(required=True))
    gigs = fields.ConnectionField("GigConnection", **_filters)
    gig_pagination = fields.Field("GigPagination", id=arguments.UUID(required=True), **_filters)
    gigs_for_influencer = fields.ConnectionField(
        "GigConnection", username=arguments.String(), id=arguments.UUID()
    )
    gig_for_post = fields.Field(
        "Gig",
        id=arguments.UUID(
            required=True,
            description="The ID for the post to get the latest gig for as an influencer",
        ),
    )

    @permissions.public.require()
    def resolve_gig(root, info, id):
        return gig_query().filter(Gig.id == id).one_or_none()

    @staticmethod  # noqa: C901: Too complex
    def _gigs(
        campaign_id, post_id, influencer_id, state, unreviewed, unverified, reported, mine, posted
    ):
        query = gig_query().filter(Gig.state != STATES.REQUIRES_RESUBMIT)
        if campaign_id:
            query = query.filter(Campaign.id == campaign_id)
        if post_id:
            query = query.filter(Post.id == post_id)
        if influencer_id:
            query = query.join(Influencer).filter(Influencer.id == influencer_id)
        if state:
            if state not in STATES.values():
                raise QueryException(f"{state} is an invalid gig state")
            query = query.filter(Gig.state == state)
        if unreviewed:
            if current_user.role_name == "advertiser":
                filter_unreviewed = Gig.state == STATES.REVIEWED
            else:
                filter_unreviewed = and_(
                    Gig.reviewer == None, Gig.state.in_([STATES.SUBMITTED, STATES.APPROVED])
                )  # noqa: E711, E501
            query = query.filter(filter_unreviewed)
        if unverified:
            query = query.filter(Gig.is_posted, ~Gig.is_verified)
        if reported:
            query = query.filter(Gig.state == STATES.REPORTED)
        if mine:
            query = query.filter(
                or_(
                    Campaign.owner_id == current_user.id,
                    Campaign.campaign_manager_id == current_user.id,
                    Campaign.community_manager_id == current_user.id,
                )
            )
        if posted:
            query = query.filter(Gig.is_live)

        return query.order_by(
            case(
                value=Gig.state,
                whens={
                    STATES.APPROVED: 1,
                    STATES.REVIEWED: 2,
                    STATES.SUBMITTED: 3,
                    STATES.REPORTED: 4,
                    STATES.REJECTED: 5,
                    STATES.REQUIRES_RESUBMIT: 6,
                },
            ),
            Gig.created.desc(),
        )

    @permissions.public.require()
    def resolve_gigs(
        root,
        info,
        campaign_id=None,
        post_id=None,
        influencer_id=None,
        state=None,
        unreviewed=False,
        unverified=False,
        reported=False,
        mine=False,
        posted=False,
    ):
        return GigQuery._gigs(
            campaign_id,
            post_id,
            influencer_id,
            state,
            unreviewed,
            unverified,
            reported,
            mine,
            posted,
        )

    @permissions.public.require()
    def resolve_gig_pagination(
        root,
        info,
        id,
        campaign_id=None,
        post_id=None,
        influencer_id=None,
        state=None,
        unreviewed=False,
        unverified=False,
        reported=False,
        mine=False,
        posted=False,
    ):
        class GigCursor:
            def __init__(self, next, previous):
                self.next = next
                self.previous = previous

        query = GigQuery._gigs(
            campaign_id,
            post_id,
            influencer_id,
            state,
            unreviewed,
            unverified,
            reported,
            mine,
            posted,
        )
        items = [gig.id for gig in query.options(load_only("id"))]

        try:
            current_index = items.index(id)
        except ValueError:
            return GigCursor(next=None, previous=None)

        return GigCursor(
            next=items[current_index + 1] if current_index + 1 < len(items) else None,
            previous=items[current_index - 1] if current_index > 0 else None,
        )

    @permissions.public.require()
    def resolve_gigs_for_influencer(root, info, username=None, id=None):
        influencer = None

        if username:
            influencer = Influencer.by_username(username)
        if id:
            influencer = Influencer.query.get(id)

        if influencer is None:
            return None

        query = gig_query().filter(Offer.influencer == influencer).order_by(Gig.created.desc())

        return query

    @permissions.influencer.require()
    def resolve_gig_for_post(root, info, id):
        post = get_post_or_404(id)
        return GigService.get_latest_influencer_gig_of_a_post(current_user.influencer.id, post.id)
