import mock

from takumi.ocr.documents import OcrValue
from takumi.services import InsightService


def test_update_story_insight_updates_all_arguments(db_story_insight):
    # Act
    with InsightService(db_story_insight) as service:
        service.update_story_insight(
            dict(
                back_navigations=55,
                exited_navigations=56,
                forward_navigations=57,
                impressions=58,
                next_story_navigations=59,
                processed=True,
                reach=60,
                replies=61,
                views=62,
            )
        )

    # Assert
    assert db_story_insight.back_navigations == 55
    assert db_story_insight.exited_navigations == 56
    assert db_story_insight.forward_navigations == 57
    assert db_story_insight.impressions == 58
    assert db_story_insight.next_story_navigations == 59
    assert db_story_insight.reach == 60
    assert db_story_insight.replies == 61
    assert db_story_insight.views == 62


def test_update_post_insight_updates_all_arguments(db_post_insight):
    # Act
    with InsightService(db_post_insight) as service:
        service.update_post_insight(
            dict(
                bookmarks=55,
                comments=56,
                follows=57,
                from_home_impressions=58,
                from_other_impressions=59,
                from_profile_impressions=60,
                likes=61,
                non_followers_reach=55.5,
                processed=True,
                profile_visits=62,
                reach=63,
                website_clicks=64,
            )
        )

    # Assert
    assert db_post_insight.bookmarks == 55
    assert db_post_insight.comments == 56
    assert db_post_insight.follows == 57
    assert db_post_insight.from_home_impressions == 58
    assert db_post_insight.from_other_impressions == 59
    assert db_post_insight.from_profile_impressions == 60
    assert db_post_insight.likes == 61
    assert db_post_insight.profile_visits == 62
    assert db_post_insight.reach == 63
    assert db_post_insight.website_clicks == 64
    assert db_post_insight.non_followers_reach == 55.5


def test_insight_service_run_ocr(db_post_insight):
    mock_values = {
        "foo": OcrValue(value=10, confidence=0.9),
        "bar": OcrValue(value=20, confidence=0.8),
        "baz": OcrValue(value=30, confidence=0.7),
    }

    with mock.patch("takumi.services.insight.analyse_post_insight", return_value=mock_values):
        with InsightService(db_post_insight) as service:
            service.run_ocr()

    assert db_post_insight.ocr_values == {
        "foo": {"value": 10, "confidence": 0.9},
        "bar": {"value": 20, "confidence": 0.8},
        "baz": {"value": 30, "confidence": 0.7},
    }
