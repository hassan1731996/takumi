# encoding=utf-8

from test.python.api.utils import _gig, _instagram_story_frame_insight, _post, _story_frame

from takumi.models import Offer


def test_offer_claimed_hybrid_expression_with_pending_payment(db_session, db_offer, db_payment):
    db_payment.successful = None
    db_session.commit()

    assert db_offer.claimed == db_payment.created

    assert Offer.query.filter(Offer.claimed == None).one_or_none() is None
    assert Offer.query.filter(Offer.claimed == db_payment.created).one_or_none() is db_offer


def test_offer_claimed_hybrid_expression_with_failed_payment(db_session, db_offer, db_payment):
    db_payment.successful = False
    db_session.commit()

    assert db_offer.claimed is None

    assert Offer.query.filter(Offer.claimed == None).one_or_none() is db_offer
    assert Offer.query.filter(Offer.claimed == db_payment.created).one_or_none() is None


def test_offer_claimed_hybrid_expression_with_successful_payment(db_session, db_offer, db_payment):
    db_payment.successful = True
    db_session.commit()

    assert db_offer.claimed == db_payment.created

    assert Offer.query.filter(Offer.claimed == None).one_or_none() is None
    assert Offer.query.filter(Offer.claimed == db_payment.created).one_or_none() is db_offer


def test_engagement_rate_static(
    db_session, db_offer, db_gig, db_instagram_post_insight, db_instagram_post
):
    db_instagram_post_insight.engagement = 200
    db_gig.instagram_post = db_instagram_post

    expected_engagement_rate_static = 20.0
    assert db_offer.engagement_rate_static == expected_engagement_rate_static


def test_engagement_rate_static_without_insight(db_session, db_offer):
    expected_engagement_rate_static = 0
    assert db_offer.engagement_rate_static == expected_engagement_rate_static


def test_engagement_rate_story(
    db_session,
    db_offer,
    db_gig,
    db_instagram_story_frame_insight,
    db_instagram_story,
    db_influencer,
    db_story_frame,
):
    additional_db_story_frame = _story_frame(influencer=db_influencer)
    additional_db_instagram_story_frame_insight = _instagram_story_frame_insight(
        story_frame=additional_db_story_frame
    )
    db_session.add_all((additional_db_story_frame, additional_db_instagram_story_frame_insight))
    db_session.commit()

    db_instagram_story.story_frames.extend([db_story_frame, additional_db_story_frame])
    db_instagram_story_frame_insight.replies = 600
    additional_db_instagram_story_frame_insight.replies = 400

    db_gig.instagram_story = db_instagram_story

    expected_engagement_rate_story = 100.0
    assert db_offer.engagement_rate_story == expected_engagement_rate_story


def test_engagement_rate_story_without_insight(db_session, db_offer):
    expected_engagement_rate_story = 0
    assert db_offer.engagement_rate_story == expected_engagement_rate_story


def test_reach(
    db_session,
    db_offer,
    db_influencer,
    db_story_frame,
    db_campaign,
    db_instagram_story,
    db_instagram_post,
    db_instagram_story_frame_insight,
    db_gig,
    db_instagram_post_insight,
):
    additional_db_story_frame = _story_frame(influencer=db_influencer)
    additional_db_instagram_story_frame_insight = _instagram_story_frame_insight(
        story_frame=additional_db_story_frame
    )

    db_session.add_all((additional_db_story_frame, additional_db_instagram_story_frame_insight))
    db_session.commit()

    db_instagram_story.story_frames.extend([db_story_frame, additional_db_story_frame])
    db_instagram_story_frame_insight.reach = 700
    additional_db_instagram_story_frame_insight.reach = 400

    db_instagram_post_insight.reach = 200
    _gig(_post(db_campaign), db_offer, instagram_post=db_instagram_post)

    expected_reach = 1300 / 3
    assert db_offer.reach == expected_reach


def test_reach_without_insights(db_session, db_offer):
    expected_reach = 0
    assert db_offer.reach == expected_reach


def test_total_impressions(
    db_session,
    db_offer,
    db_influencer,
    db_story_frame,
    db_campaign,
    db_instagram_story,
    db_instagram_post,
    db_instagram_story_frame_insight,
    db_gig,
    db_instagram_post_insight,
):
    additional_db_story_frame = _story_frame(influencer=db_influencer)
    additional_db_instagram_story_frame_insight = _instagram_story_frame_insight(
        story_frame=additional_db_story_frame
    )

    db_session.add_all((additional_db_story_frame, additional_db_instagram_story_frame_insight))
    db_session.commit()

    db_instagram_story.story_frames.extend([db_story_frame, additional_db_story_frame])
    db_instagram_story_frame_insight.impressions = 700
    additional_db_instagram_story_frame_insight.impressions = 600

    db_instagram_post_insight.impressions = 200
    _gig(_post(db_campaign), db_offer, instagram_post=db_instagram_post)

    expected_impressions = 1500 / 3
    assert db_offer.total_impressions == expected_impressions


def test_total_impressions_without_insights(db_session, db_offer):
    expected_impressions = 0
    assert db_offer.total_impressions == expected_impressions
