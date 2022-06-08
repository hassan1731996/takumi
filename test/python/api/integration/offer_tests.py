# encoding=utf-8
import datetime as dt

import pytest

from takumi.constants import ENGAGEMENT_ESTIMATION_MODIFIER
from takumi.models import Campaign, Influencer, InstagramAccount, Offer, User
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import ENGAGEMENTS_GATE_HOURS
from takumi.services import OfferService

utc = dt.timezone.utc


@pytest.fixture(scope="function")
def db_influencer_bob(db_session, interest, db_region):
    user = User(role_name="123")
    influencer = Influencer(
        state="verified",
        is_signed_up=True,
        interests=[interest],
        target_region=db_region,
        user=user,
    )
    instagram_account = InstagramAccount(
        ig_username="bob",
        ig_is_private=False,
        ig_user_id="123",
        ig_media_id="123",
        token="123",
        followers=20000,
        media_count=20000,
        influencer=influencer,
    )
    db_session.add(influencer)
    db_session.add(instagram_account)
    db_session.commit()
    return influencer


@pytest.fixture(scope="function")
def db_influencer_alice(db_session, interest, db_region):
    user = User(role_name="123")
    influencer = Influencer(
        state="verified",
        interests=[interest],
        target_region=db_region,
        is_signed_up=True,
        user=user,
    )
    instagram_account = InstagramAccount(
        ig_username="alice",
        ig_is_private=False,
        ig_user_id="1234",
        ig_media_id="1234",
        token="1234",
        followers=20000,
        media_count=20000,
        influencer=influencer,
    )
    db_session.add(influencer)
    db_session.add(instagram_account)
    db_session.commit()
    return influencer


def test_offer_is_submitted(
    db_session, db_post, db_influencer_bob, db_influencer_alice, gig_factory, instagram_post_factory
):
    db_post.campaign.state = "launched"

    offer = OfferService.create(db_post.campaign.id, db_influencer_bob.id)
    with OfferService(offer) as service:
        service.reserve()
    offer2 = OfferService.create(db_post.campaign.id, db_influencer_alice.id)
    with OfferService(offer2) as service:
        service.reserve()

    gig = gig_factory(state=GIG_STATES.APPROVED, offer=offer, post=db_post, is_verified=True)

    instagram_post = instagram_post_factory(gig=gig)

    db_session.add(gig)
    db_session.add(instagram_post)
    db_session.add(offer)
    db_session.add(offer2)
    db_session.commit()

    assert Offer.query.filter(Campaign.id == db_post.campaign.id, Offer.is_submitted).count() == 1
    assert (
        Offer.query.filter(Campaign.id == db_post.campaign.id, Offer.is_submitted).first() == offer
    )


def test_offer_live_since_property_returns_earliest_gig_posted_time(
    db_session, db_offer, db_gig, db_instagram_post, gig_factory, instagram_post_factory
):
    db_gig.is_verified = True
    db_instagram_post.posted = dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc)
    gig = gig_factory(state=GIG_STATES.APPROVED, offer=db_offer, is_verified=True)
    gig.instagram_post = instagram_post_factory(
        gig=gig, posted=dt.datetime(2018, 1, 2, tzinfo=dt.timezone.utc)
    )
    assert db_offer.live_since == dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc)
    db_gig.is_verified = False
    assert db_offer.live_since == dt.datetime(2018, 1, 2, tzinfo=dt.timezone.utc)


def _test_offer_engagement_progress_expression(db_offer):
    # Test the expression as well
    assert (
        Offer.query.filter(Offer.engagements_progress == db_offer.engagements_progress).first()
        == db_offer
    )


def test_offer_engagements_progress_uses_estimate_if_posted_within_gate_hours(
    db_session, db_offer, db_gig, db_instagram_post
):

    db_offer.engagements_per_post = 123
    db_offer.estimated_engagements_per_post = 999
    db_gig.is_verified = True

    gate_threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=ENGAGEMENTS_GATE_HOURS)

    db_instagram_post.posted = gate_threshold + dt.timedelta(seconds=1)
    assert db_offer.engagements_progress == 999
    _test_offer_engagement_progress_expression(db_offer)

    db_instagram_post.posted = gate_threshold
    assert db_offer.engagements_progress == 123
    _test_offer_engagement_progress_expression(db_offer)


def test_offer_engagements_progress_handles_no_live_gigs(
    db_session, db_offer, db_gig, db_instagram_post
):

    db_offer.engagements_per_post = 123
    db_offer.estimated_engagements_per_post = 999

    gate_threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=ENGAGEMENTS_GATE_HOURS)

    db_instagram_post.posted = gate_threshold + dt.timedelta(seconds=1)
    assert db_offer.engagements_progress == 999
    assert db_gig.is_live is False
    _test_offer_engagement_progress_expression(db_offer)


def test_offer_engagement_progress_with_unposted_and_posted(
    db_session,
    db_campaign,
    db_post,
    db_offer,
    db_gig,
    db_instagram_post,
    db_influencer,
    post_factory,
    gig_factory,
):

    # arrange
    N_POSTS = 2
    new_post = post_factory(campaign=db_campaign)
    db_offer.estimated_engagements_per_post = db_influencer.estimated_engagements_per_post
    db_campaign.posts = [db_post, new_post]
    db_instagram_post.likes = 100
    db_instagram_post.comments = 10
    db_instagram_post.posted = dt.datetime.now(dt.timezone.utc)
    db_gig.is_verified = True

    new_gig = gig_factory(offer=db_offer, post=new_post, is_verified=True)
    db_offer.gigs.append(new_gig)
    db_session.add(db_offer)
    db_session.commit()

    # act
    with OfferService(db_offer) as srv:
        srv.update_engagements_per_post()

    # assert that the real engagements value has been updated
    assert (
        db_offer.engagements_per_post
        == (
            db_gig.engagements
            + (db_influencer.estimated_engagements_per_post / ENGAGEMENT_ESTIMATION_MODIFIER)
        )
        / N_POSTS
    )  # noqa: E501
    _test_offer_engagement_progress_expression(db_offer)

    # assert engagement_progress is still the estimate value
    assert db_offer.engagements_progress == db_offer.estimated_engagements_per_post
    _test_offer_engagement_progress_expression(db_offer)

    # act to make one gig older than GATE HOURS
    db_instagram_post.posted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        hours=ENGAGEMENTS_GATE_HOURS, seconds=1
    )

    # assert engagement_progress is the "real" value, which has some estimations built in when multi-posting
    assert db_offer.engagements_progress == db_offer.engagements_per_post
    _test_offer_engagement_progress_expression(db_offer)
