from takumi.gql.query.insight import InsightQuery


def test_insight_service_get_insights_with_invalid_pagination(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": -10,
        "limit": -10,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 2


def test_insight_service_get_insights_with_pagination(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": 0,
        "limit": 1,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 1


def test_insight_service_get_insights_with_pagination_offset(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": 1,
        "limit": 1,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 1


def test_insight_service_get_insights_with_pagination_offset_too_big(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": 3,
        "limit": 1,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 0


def test_insight_service_get_insights_with_pagination_limit(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": 0,
        "limit": 2,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 2


def test_insight_service_get_insights_with_pagination_limit_too_big(
    db_post_insight, db_story_insight, client, db_developer_user
):
    pagination_kwargs = {
        "offset": 0,
        "limit": 10,
    }

    with client.user_request_context(db_developer_user):
        insights = InsightQuery().resolve_insights("info", **pagination_kwargs)

    assert insights.count() == 2
