from flask_login import current_user
from sqlalchemy import and_, func, or_

from takumi.constants import ALL_SUPPORTED_REGIONS
from takumi.extensions import db
from takumi.gql import constants
from takumi.gql.exceptions import QueryException
from takumi.models import (
    Advertiser,
    Campaign,
    EmailLogin,
    Gig,
    Influencer,
    InstagramAccount,
    Offer,
    Post,
    Region,
    User,
    UserAdvertiserAssociation,
)
from takumi.models.advertiser_industry import AdvertiserIndustry
from takumi.models.campaign import CampaignMetric
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.targeting import Targeting
from takumi.roles import permissions
from takumi.search.sql import search_advertisers_query, search_campaigns_query

"""
Resource access control:

    Queries are composed in here in a tree-like manner. If you want to access
    an advertiser, you either have access to them or not, that is, they're at
    the top of the tree. If you want to access a campaign, you need to have
    access to the advertiser that this campaign belongs to and so on.

    To be able to access influencers, they need to be a part of campaigns that
    you have access to, have an offer to one of them (XXX: Decide on this?)
"""


def filter_campaigns_by_date_range(start, end, query=None):
    if query is None:
        return Campaign.query
    query = query.filter(
        and_(
            func.date(Campaign.started) >= start,
            func.date(Campaign.started) <= end,
            Campaign.started.isnot(None),
        )
    )
    return query


def filter_advertisers(query=None):
    if query is None:
        query = Advertiser.query

    if not permissions.access_all_advertisers.can():
        advertisers = getattr(current_user, "advertisers", [])
        query = query.filter(Advertiser.id.in_([a.id for a in advertisers]))

    return query


def filter_campaigns(query=None):
    if query is None:
        query = Campaign.query

    # If you can access all advertisers, you can access all campaigns
    # This also make campaign preview work for team members
    if permissions.access_all_advertisers.can():
        return query.unique_join(Advertiser)

    if current_user.role_name == "influencer":
        return query.unique_join(Offer).filter(Offer.influencer == current_user.influencer)

    return filter_advertisers(query.unique_join(Advertiser))


def filter_campaigns_by_region(query=None, region_id=None):
    if query is None:
        query = Campaign.query

    if region_id and region_id != ALL_SUPPORTED_REGIONS:
        country = Region.query.get(region_id)
        if country is None:
            raise QueryException(f'No country with id "{region_id}" found')
        query = query.join(Targeting).filter(
            Targeting.regions.any((Region.path[1] == country.id) | (Region.id == country.id))
        )

    return query


def filter_mine_campaigns(query=None, mine=None):
    if query is None:
        query = Campaign.query

    if mine:
        query = query.filter(
            or_(
                Campaign.owner_id == current_user.id,
                Campaign.campaign_manager_id == current_user.id,
                Campaign.community_manager_id == current_user.id,
            )
        )

    return query


def filter_unassigned_campaigns(query=None, unassigned=None):
    if query is None:
        query = Campaign.query

    if unassigned:
        query = query.filter(Campaign.campaign_manager_id == None)  # noqa: E711

    return query


def filter_campaigns_by_search_string(query=None, search=None):
    if query is None:
        query = Campaign.query

    if search is not None:
        query = search_campaigns_query(query, search)

    return query


def filter_campaigns_by_advertiser_name(query=None, search_advertiser=None):
    if query is None:
        query = Campaign.query

    if search_advertiser is not None:
        query = search_advertisers_query(query, search_advertiser)

    return query


def filter_campaigns_by_industry(query=None, advertiser_industries_ids=None):
    if query is None:
        query = Campaign.query

    if advertiser_industries_ids:
        query = query.filter(
            Advertiser.advertiser_industries.any(
                AdvertiserIndustry.id.in_(advertiser_industries_ids)
            )
        )

    return query


def filter_campaigns_by_campaign_filters(query=None, **filters):
    if query is None:
        query = Campaign.query

    for filter in filters:
        if filter in constants.campaign_filters:
            query = query.filter(getattr(Campaign, filter) == filters[filter])

    return query


def sort_campaigns_by_order(query=None, order=None):
    """Order campaigns in ascending or descending order if the order parameter is passed.
    Otherwise, it will be sorted by creation date.

    Args:
        query (Any): Campaign's query.

    Returns:
        Ordered query in a specific way.
    """
    if query is None:
        query = Campaign.query

    if order:
        query = (
            query.outerjoin(Campaign.campaign_metric).order_by(
                CampaignMetric.engagement_rate_total.asc().nullsfirst()
            )
            if order == "asc"
            else query.outerjoin(Campaign.campaign_metric).order_by(
                CampaignMetric.engagement_rate_total.desc().nullslast()
            )
        )
    else:
        query = query.order_by(Campaign.started.desc().nullslast(), Campaign.created.desc())

    return query


def paginate_query(query, offset=0, limit=0):

    if offset >= 0 and (limit and limit >= 0):
        query = query.limit(limit).offset(offset)

    return query


def filter_posts(query=None):
    if query is None:
        query = Post.query

    if current_user.role_name == "influencer":
        return (
            query.unique_join(Campaign)
            .unique_join(Offer)
            .filter(Offer.influencer == current_user.influencer)
        )

    return filter_campaigns(query.unique_join(Campaign))


def filter_offers(query=None):
    if query is None:
        query = Offer.query

    if current_user.role_name == "influencer":
        return query.unique_join(Campaign).filter(Offer.influencer == current_user.influencer)

    return filter_campaigns(query.unique_join(Campaign))


def filter_gigs(query=None):
    if query is None:
        query = Gig.query

    if permissions.access_all_gigs.can():
        return filter_posts(query.unique_join(Post))

    visible_states = [GIG_STATES.REVIEWED, GIG_STATES.APPROVED]

    if permissions.see_reported_gigs.can():
        visible_states += [GIG_STATES.REPORTED]

    query = query.filter(Gig.state.in_(visible_states))

    return filter_posts(query.unique_join(Post))


def filter_users(query=None):
    """Filter advertiser users"""
    if query is None:
        query = User.query

    query = query.outerjoin(EmailLogin, EmailLogin.user_id == User.id)

    if permissions.access_all_users.can():
        return query

    query = query.unique_join(UserAdvertiserAssociation).unique_join(Advertiser)

    return filter_advertisers(query)


def filter_influencers(query=None):
    """Filter influencers query

    If the current user doesn't have permission to see all influencers in the
    system, the influencer list is filtered to only include influencers that
    have been a part of the advertisers the user has access to in any way.
    """
    if query is None:
        query = Influencer.query

    query = (
        query.outerjoin(Region, Influencer.target_region_id == Region.id)
        .outerjoin(User)
        .unique_outerjoin(InstagramAccount)
        .outerjoin(EmailLogin)
    )

    if permissions.access_all_influencers.can():
        return query

    offer_subquery = filter_offers(
        db.session.query(Offer.influencer_id).filter(
            Offer.state.in_([OFFER_STATES.ACCEPTED, OFFER_STATES.CANDIDATE])
        )
    ).subquery()

    query = query.filter(Influencer.id.in_(offer_subquery))
    return query
