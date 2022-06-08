# encoding=utf-8

from test.python.api.utils import _instagram_story_frame_insight, _story_frame

from takumi.models import Gig
from takumi.models.gig import STATES


def _get_gig_by_id(gig_id):
    return Gig.query.filter(Gig.id == gig_id).with_entities(Gig.is_live).one()


def test_is_live_expression_returns_true_if_approved_and_is_verified(db_session, db_gig):
    # Arrange
    db_gig.is_verified = True
    db_gig.state = STATES.APPROVED
    db_session.add(db_gig)

    # Act & Assert
    assert _get_gig_by_id(db_gig.id) == (True,)


def test_is_live_expression_returns_false_if_approved_and_not_posted(db_session, db_gig):
    # Arrange
    db_gig.is_verified = False
    db_gig.state = STATES.APPROVED
    db_session.add(db_gig)

    # Act & Assert
    assert _get_gig_by_id(db_gig.id) == (False,)


def test_is_live_expression_returns_false_if_not_approved_and_is_verified(db_session, db_gig):
    # Arrange
    db_gig.is_verified = True
    db_gig.state = STATES.SUBMITTED
    db_session.add(db_gig)

    # Act & Assert
    assert _get_gig_by_id(db_gig.id) == (False,)


def test_is_live_expression_returns_false_if_not_approved_and_not_posted(db_session, db_gig):
    # Arrange
    db_gig.is_verified = False
    db_gig.state = STATES.SUBMITTED
    db_session.add(db_gig)

    # Act & Assert
    assert _get_gig_by_id(db_gig.id) == (False,)


def test_engagements_static(db_session, db_gig, db_instagram_post_insight, db_instagram_post):
    db_instagram_post_insight.engagement = 200
    db_gig.instagram_post = db_instagram_post

    expected_engagements_static = 200
    assert db_gig.engagements_static == expected_engagements_static


def test_engagements_static_without_insights(db_session, db_gig):
    expected_engagements_static = 0
    assert db_gig.engagements_static == expected_engagements_static


def test_engagements_story(
    db_session,
    db_gig,
    db_instagram_story_frame_insight,
    db_story_frame,
    db_instagram_story,
    db_influencer,
):
    additional_db_story_frame = _story_frame(influencer=db_influencer)
    additional_db_instagram_story_frame_insight = _instagram_story_frame_insight(
        story_frame=additional_db_story_frame
    )
    db_session.add_all((additional_db_story_frame, additional_db_instagram_story_frame_insight))
    db_session.commit()

    db_instagram_story.story_frames.extend([db_story_frame, additional_db_story_frame])
    db_instagram_story_frame_insight.replies = 700
    additional_db_instagram_story_frame_insight.replies = 400

    db_gig.instagram_story = db_instagram_story

    expected_engagements_story = 1100
    assert db_gig.engagements_story == expected_engagements_story


def test_engagements_story_without_insights(db_session, db_gig):
    expected_engagements_story = 0
    assert db_gig.engagements_story == expected_engagements_story
