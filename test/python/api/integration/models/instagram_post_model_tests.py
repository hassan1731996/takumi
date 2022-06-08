def test_engagements_insight(db_session, db_instagram_post, db_instagram_post_insight):
    db_instagram_post_insight.engagement = 700
    db_instagram_post.instagram_post_insights = [db_instagram_post_insight]

    expected_post_engagements = 700
    assert db_instagram_post.engagements_insight == expected_post_engagements


def test_engagements_insight_without_insight(db_session, db_instagram_post):
    expected_post_engagements = 0
    assert db_instagram_post.engagements_insight == expected_post_engagements
