from test.python.api.utils import _instagram_story_frame_insight, _story_frame


def test_engagements_insight(
    db_session,
    db_instagram_story,
    db_instagram_story_frame_insight,
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
    db_instagram_story_frame_insight.replies = 700
    additional_db_instagram_story_frame_insight.replies = 400

    expected_story_engagements = 1100
    assert db_instagram_story.engagements == expected_story_engagements


def test_engagements_insight_without_insight(db_session, db_instagram_story):
    expected_story_engagements = 0
    assert db_instagram_story.engagements == expected_story_engagements
