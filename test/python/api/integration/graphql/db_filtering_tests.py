import mock
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import TSVECTOR

from core.testing.factories import AdvertiserFactory, GigFactory, OfferFactory, UserFactory

from takumi.gql.db import (
    filter_advertisers,
    filter_campaigns_by_advertiser_name,
    filter_gigs,
    filter_influencers,
    filter_users,
)
from takumi.models import Campaign
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.user_advertiser_association import create_user_advertiser_association
from takumi.roles import permissions


def test_filter_advertisers_to_your_advertisers(
    db_session, db_advertiser, db_advertiser_user, advertiser_factory, monkeypatch
):
    monkeypatch.setattr("takumi.gql.db.current_user", db_advertiser_user)
    assert db_advertiser in db_advertiser_user.advertisers

    private_advertiser = advertiser_factory(
        domain="djamm", primary_region=db_advertiser.primary_region
    )

    db_session.add(private_advertiser)
    db_session.commit()

    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: False)):
        result = filter_advertisers().all()

    assert db_advertiser in result
    assert private_advertiser not in result


def test_filter_advertisers_access_all_advertisers(
    db_session, db_advertiser, db_advertiser_user, advertiser_factory, monkeypatch
):
    monkeypatch.setattr("takumi.gql.db.current_user", db_advertiser_user)
    assert db_advertiser in db_advertiser_user.advertisers

    private_advertiser = advertiser_factory(
        domain="djamm", primary_region=db_advertiser.primary_region
    )

    db_session.add(private_advertiser)
    db_session.commit()

    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: True)):
        result = filter_advertisers().all()

    assert db_advertiser in result
    assert private_advertiser in result


def test_filter_gigs_access_all_gigs(db_session, db_post, monkeypatch):
    monkeypatch.setattr("takumi.gql.db.filter_posts", lambda q: q)

    submitted_gig = _generate_gig(db_post, GIG_STATES.SUBMITTED)
    reported_gig = _generate_gig(db_post, GIG_STATES.REPORTED)
    rejected_gig = _generate_gig(db_post, GIG_STATES.REJECTED)
    resubmit_gig = _generate_gig(db_post, GIG_STATES.REQUIRES_RESUBMIT)

    db_session.add_all([submitted_gig, reported_gig, rejected_gig, resubmit_gig])
    db_session.commit()

    with mock.patch.object(permissions, "access_all_gigs", mock.Mock(can=lambda: True)):
        result = filter_gigs().all()

    assert submitted_gig in result
    assert reported_gig in result
    assert rejected_gig in result
    assert resubmit_gig in result


def test_filter_gigs_see_reported_gigs(db_session, db_post, monkeypatch):
    monkeypatch.setattr("takumi.gql.db.filter_posts", lambda q: q)

    approved_gig = _generate_gig(db_post, GIG_STATES.APPROVED)
    reported_gig = _generate_gig(db_post, GIG_STATES.REPORTED)
    rejected_gig = _generate_gig(db_post, GIG_STATES.REJECTED)
    resubmit_gig = _generate_gig(db_post, GIG_STATES.REQUIRES_RESUBMIT)

    db_session.add_all([approved_gig, reported_gig, rejected_gig, resubmit_gig])
    db_session.commit()

    with mock.patch.object(permissions, "access_all_gigs", mock.Mock(can=lambda: False)):
        with mock.patch.object(permissions, "see_reported_gigs", mock.Mock(can=lambda: True)):
            result = filter_gigs().all()

    assert approved_gig in result
    assert reported_gig in result
    assert rejected_gig not in result
    assert resubmit_gig not in result


def test_filter_gigs_with_no_extra_permissions(db_session, db_post, monkeypatch):
    monkeypatch.setattr("takumi.gql.db.filter_posts", lambda q: q)

    approved_gig = _generate_gig(db_post, GIG_STATES.APPROVED)
    reported_gig = _generate_gig(db_post, GIG_STATES.REPORTED)
    rejected_gig = _generate_gig(db_post, GIG_STATES.REJECTED)
    resubmit_gig = _generate_gig(db_post, GIG_STATES.REQUIRES_RESUBMIT)

    db_session.add_all([approved_gig, reported_gig, rejected_gig, resubmit_gig])
    db_session.commit()

    with mock.patch.object(permissions, "access_all_gigs", mock.Mock(can=lambda: False)):
        with mock.patch.object(permissions, "see_reported_gigs", mock.Mock(can=lambda: False)):
            result = filter_gigs().all()

    assert approved_gig in result
    assert reported_gig not in result
    assert rejected_gig not in result
    assert resubmit_gig not in result


def test_filter_users_to_users_in_your_advertisers_only(
    db_session, db_advertiser, db_advertiser_user, monkeypatch
):
    monkeypatch.setattr("takumi.gql.db.current_user", db_advertiser_user)
    private_user = _get_private_user(db_session, db_advertiser.primary_region)
    friend_user = _get_same_advertiser_user(db_session, db_advertiser)

    # Filtering depends filter_advertisers, so mock out permissions in there as well
    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: False)):
        with mock.patch.object(permissions, "access_all_users", mock.Mock(can=lambda: False)):
            result = filter_users().all()

    assert db_advertiser_user in result
    assert friend_user in result
    assert private_user not in result


def test_filter_users_doesnt_filter_if_access_all_users(
    db_session, db_advertiser, db_advertiser_user, monkeypatch
):
    monkeypatch.setattr("takumi.gql.db.current_user", db_advertiser_user)
    private_user = _get_private_user(db_session, db_advertiser.primary_region)

    with mock.patch.object(permissions, "access_all_users", mock.Mock(can=lambda: True)):
        result = filter_users().all()

    assert db_advertiser_user in result
    assert private_user in result


def test_filter_influencers_to_your_campaigns(
    db_session, db_advertiser_user, db_campaign, offer_factory, influencer_factory, monkeypatch
):
    monkeypatch.setattr("takumi.gql.db.current_user", db_advertiser_user)
    influencer_not_in_a_campaign = influencer_factory(
        target_region=db_campaign.targeting.regions[0]
    )

    influencer_rejected_from_your_campaign = influencer_factory(
        target_region=db_campaign.targeting.regions[0]
    )
    rejected_offer = offer_factory(
        campaign=db_campaign,
        influencer=influencer_rejected_from_your_campaign,
        state=OFFER_STATES.REJECTED,
    )

    influencer_accepted_in_your_campaign = influencer_factory(
        target_region=db_campaign.targeting.regions[0]
    )
    accepted_offer = offer_factory(
        campaign=db_campaign,
        influencer=influencer_accepted_in_your_campaign,
        state=OFFER_STATES.ACCEPTED,
    )

    db_session.add_all(
        [
            influencer_not_in_a_campaign,
            influencer_rejected_from_your_campaign,
            rejected_offer,
            influencer_accepted_in_your_campaign,
            accepted_offer,
        ]
    )
    db_session.commit()

    # Filtering depends filter_advertisers, so mock out permissions in there as well
    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: False)):
        with mock.patch.object(permissions, "access_all_influencers", mock.Mock(can=lambda: False)):
            result = filter_influencers().all()

    assert influencer_not_in_a_campaign not in result
    assert influencer_rejected_from_your_campaign not in result
    assert influencer_accepted_in_your_campaign in result


def test_filter_campaign_by_advertiser_name_found(
    db_session, db_region, db_campaign, db_advertiser
):
    _generate_search_vector_for_advertiser(db_session, db_advertiser)

    query = Campaign.query
    result = filter_campaigns_by_advertiser_name(query, db_advertiser.name).all()
    expected_campaign_id = db_campaign.id
    assert len(result) == 1
    assert expected_campaign_id == result[0].id


def test_filter_campaign_by_advertiser_name_not_found(
    db_session, db_region, db_campaign, db_advertiser
):
    _generate_search_vector_for_advertiser(db_session, db_advertiser)

    query = Campaign.query
    wrong_search_string = "wrong advertiser name"
    result = filter_campaigns_by_advertiser_name(query, wrong_search_string).all()
    assert len(result) == 0


##########################
# Helper functions below #
##########################


def _generate_gig(post, state):
    offer = OfferFactory()(campaign=post.campaign)
    offer.state = OFFER_STATES.ACCEPTED
    return GigFactory()(offer=offer, post=post, state=state)


def _get_same_advertiser_user(session, advertiser):
    user = UserFactory()(role_name="advertiser")

    create_user_advertiser_association(user, advertiser, "member")

    session.add_all([advertiser, user])
    session.commit()

    return user


def _get_private_user(session, primary_region):
    private_advertiser = AdvertiserFactory()(primary_region=primary_region)
    private_user = UserFactory()(role_name="advertiser")

    create_user_advertiser_association(private_user, private_advertiser, "member")

    session.add_all([private_advertiser, private_user])
    session.commit()

    return private_user


def _generate_search_vector_for_advertiser(session, advertiser):
    search_vector = session.execute(
        select([func.to_tsvector("simple", f"{advertiser.name} {advertiser.domain}")])
    ).fetchone()
    advertiser.search_vector = select([cast(list(search_vector)[0], TSVECTOR)])
    session.commit()
    return None
