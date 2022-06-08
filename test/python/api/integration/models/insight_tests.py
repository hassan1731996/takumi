from takumi.models import PostInsight, StoryInsight


#
# hybrid properties
#
def test_story_insight_interactions_hybrid_property(db_story_insight):
    # Arrange
    db_story_insight.link_clicks = 1000
    db_story_insight.profile_visits = None
    db_story_insight.sticker_taps = 337

    # Act & Assert
    assert db_story_insight.interactions == 1337


def test_post_insight_interactions_hybrid_property(db_post_insight):
    # Arrange
    db_post_insight.profile_visits = 1337
    db_post_insight.website_clicks = None

    # Act & Assert
    assert db_post_insight.interactions == 1337


def test_post_insight_interactions_hybrid_property_returns_0_when_none(db_post_insight):
    # Arrange
    db_post_insight.profile_visits = None
    db_post_insight.website_clicks = None

    # Act & Assert
    assert db_post_insight.interactions == 0


def test_story_insight_navigation_hybrid_property(db_story_insight):
    # Arrange
    db_story_insight.back_navigations = 2
    db_story_insight.forward_navigations = 2
    db_story_insight.next_story_navigations = None
    db_story_insight.exited_navigations = 2

    # Act & Assert
    assert db_story_insight.navigations == 6


def test_story_insight_navigation_hybrid_property_returns_0_when_none(db_story_insight):
    # Arrange
    db_story_insight.back_navigations = None
    db_story_insight.forward_navigations = None
    db_story_insight.next_story_navigations = None
    db_story_insight.exited_navigations = None

    # Act & Assert
    assert db_story_insight.navigations == 0


def test_post_insight_impressions_hybrid_property(db_post_insight):
    # Arrange
    db_post_insight.from_home_impressions = 2
    db_post_insight.from_profile_impressions = 2
    db_post_insight.from_other_impressions = None

    # Act & Assert
    assert db_post_insight.impressions == 4


def test_post_insight_impressions_hybrid_property_returns_0_when_none(db_post_insight):
    # Arrange
    db_post_insight.from_home_impressions = None
    db_post_insight.from_profile_impressions = None
    db_post_insight.from_other_impressions = None

    # Act & Assert
    assert db_post_insight.impressions == 0


#
# expressions
#
def test_story_insight_interactions_expression(db_story_insight, db_session):
    # Arrange
    db_story_insight.link_clicks = 1000
    db_story_insight.profile_visits = None
    db_story_insight.sticker_taps = 337
    db_session.commit()

    # Act
    res = (
        StoryInsight.query.filter(StoryInsight.id == db_story_insight.id)
        .with_entities(StoryInsight.interactions)
        .scalar()
    )

    # Assert
    assert res == 1337


def test_post_insight_interactions_expression(db_post_insight, db_session):
    # Arrange
    db_post_insight.profile_visits = 1337
    db_post_insight.website_clicks = None
    db_session.commit()

    # Act
    res = (
        PostInsight.query.filter(PostInsight.id == db_post_insight.id)
        .with_entities(PostInsight.interactions)
        .scalar()
    )

    # Assert
    assert res == 1337


def test_post_insight_interactions_expression_returns_0_when_none(db_post_insight, db_session):
    # Arrange
    db_post_insight.profile_visits = None
    db_post_insight.website_clicks = None
    db_session.commit()

    # Act
    res = (
        PostInsight.query.filter(PostInsight.id == db_post_insight.id)
        .with_entities(PostInsight.interactions)
        .scalar()
    )

    # Assert
    assert res == 0


def test_story_insight_navigation_expression(db_story_insight, db_session):
    # Arrange
    db_story_insight.back_navigations = 2
    db_story_insight.forward_navigations = 2
    db_story_insight.next_story_navigations = None
    db_story_insight.exited_navigations = 2
    db_session.commit()

    # Act
    res = (
        StoryInsight.query.filter(StoryInsight.id == db_story_insight.id)
        .with_entities(StoryInsight.navigations)
        .scalar()
    )

    # Assert
    assert res == 6


def test_story_insight_navigation_expression_returns_0_when_none(db_story_insight, db_session):
    # Arrange
    db_story_insight.back_navigations = None
    db_story_insight.forward_navigations = None
    db_story_insight.next_story_navigations = None
    db_story_insight.exited_navigations = None
    db_session.commit()

    # Act
    res = (
        StoryInsight.query.filter(StoryInsight.id == db_story_insight.id)
        .with_entities(StoryInsight.navigations)
        .scalar()
    )

    # Assert
    assert res == 0


def test_post_insight_impressions_expression(db_post_insight, db_session):
    # Arrange
    db_post_insight.from_home_impressions = 2
    db_post_insight.from_profile_impressions = 2
    db_post_insight.from_other_impressions = None
    db_session.commit()

    # Act
    res = (
        PostInsight.query.filter(PostInsight.id == db_post_insight.id)
        .with_entities(PostInsight.impressions)
        .scalar()
    )

    # Assert
    assert res == 4


def test_post_insight_impressions_expression_returns_0_when_none(db_post_insight, db_session):
    # Arrange
    db_post_insight.from_home_impressions = None
    db_post_insight.from_profile_impressions = None
    db_post_insight.from_other_impressions = None
    db_session.commit()

    # Act
    res = (
        PostInsight.query.filter(PostInsight.id == db_post_insight.id)
        .with_entities(PostInsight.impressions)
        .scalar()
    )

    # Assert
    assert res == 0
