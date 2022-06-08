from sqlalchemy import desc, func, or_
from sqlalchemy_searchable import parse_search_query
from sqlalchemy_searchable.parser import SearchQueryParser

from takumi.models import Advertiser, Campaign, EmailLogin, Influencer, InstagramAccount, User
from takumi.utils import is_uuid


def search_advertisers_query(query, search_string, sort=False):
    """Search through advertisers

    Columns searched are:
        Advertiser.name
        Advertiser.domain

    Returns a list of Advertiser objects found
    """
    if is_uuid(search_string):
        by_id_q = query.filter(Advertiser.id == search_string)
        if by_id_q.count() > 0:
            return by_id_q

    search_query = parse_search_query(search_string)
    unaccented_query = func.unaccent(search_query)

    result_query = query.filter(Advertiser.search_vector.match(unaccented_query))

    if sort:
        result_query = result_query.order_by(
            desc(func.ts_rank(Advertiser.search_vector, func.to_tsquery(unaccented_query)))
        )
    return result_query


def search_advertiser_users_query(query, search_string, sort=False):
    """Search through advertiser users

    columns searched are:
        User.full_name,
        EmailLogin.email
    """
    if is_uuid(search_string):
        by_id_q = User.query.filter(User.id == search_string)
        if by_id_q.count() > 0:
            return by_id_q

    parser = SearchQueryParser(emails_as_tokens=True)
    search_query = parse_search_query(search_string, parser=parser)
    unaccented_query = func.unaccent(search_query)

    combined_search_vectors = func.coalesce(User.search_vector, "") | func.coalesce(
        EmailLogin.search_vector, ""
    )

    result_query = query.filter(
        User.advertisers != None, combined_search_vectors.match(unaccented_query)  # noqa: E711
    )

    if sort:
        result_query = result_query.order_by(
            desc(func.ts_rank(User.search_vector, func.to_tsquery(unaccented_query)))
        )
    return result_query


def search_influencers_query(query, search_string, sort=False):
    """Search through influencers

    Columns searched are:
        User.full_name
        InstagramAccount.ig_username
        InstagramAccount.ig_biography
        EmailLogin.email

    Returns a list of User objects found
    """
    if is_uuid(search_string):
        by_id_q = Influencer.query.filter(
            or_(Influencer.id == search_string, Influencer.user_id == search_string)
        )
        if by_id_q.count() > 0:
            return by_id_q

    combined_search_vectors = (
        func.coalesce(User.search_vector, "")
        | func.coalesce(InstagramAccount.search_vector_full, "")
        | func.coalesce(EmailLogin.search_vector, "")
    )

    parser = SearchQueryParser(emails_as_tokens=True)
    search_query = parse_search_query(search_string, parser=parser)

    unaccented_query = func.unaccent(search_query)

    result_query = query.filter(combined_search_vectors.match(unaccented_query))

    if sort:
        return result_query.order_by(
            desc(func.ts_rank(combined_search_vectors, func.to_tsquery(unaccented_query)))
        )
    else:
        return result_query


def search_campaigns_query(query, search_string, sort=False):
    """Search through campaigns

    Columns searched are:
        Campaign.name
        Campaign.tags

    Returns a list of Campaign objects found
    """
    if is_uuid(search_string):
        by_id_q = Campaign.query.filter(Campaign.id == search_string)
        if by_id_q.count() > 0:
            return by_id_q

    search_vector = func.coalesce(Campaign.search_vector, "")

    parser = SearchQueryParser()
    search_query = parse_search_query(search_string, parser=parser)

    unaccented_query = func.unaccent(search_query)

    result_query = query.filter(search_vector.match(unaccented_query))

    if sort:
        return result_query.order_by(
            desc(func.ts_rank(search_vector, func.to_tsquery(unaccented_query)))
        )
    else:
        return result_query
