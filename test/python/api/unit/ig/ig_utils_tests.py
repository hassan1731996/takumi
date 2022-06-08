from takumi.ig.utils import calculate_engagement_median, calculate_hashtag_stats


def test_calculate_engagement_median():

    # Scraped
    scraped_profile = {
        "media": {
            "nodes": [
                {"comments": {"count": 0}, "likes": {"count": 0}},
                {"comments": {"count": 50}, "likes": {"count": 50}},
                {"comments": {"count": 45}, "likes": {"count": 45}},  # The median
                {"comments": {"count": 55}, "likes": {"count": 55}},  # The median
                {"comments": {"count": 50}, "likes": {"count": 50}},
                {"comments": {"count": 500}, "likes": {"count": 500}},
            ]
        },
        "followers": 1000,
    }

    # From Instagram API
    api_profile = {
        "media": {
            "nodes": [
                {"comments_count": 0, "like_count": 0},
                {"comments_count": 50, "like_count": 50},
                {"comments_count": 45, "like_count": 45},
                {"comments_count": 55, "like_count": 55},
                {"comments_count": 50, "like_count": 50},
                {"comments_count": 500, "like_count": 500},
            ]
        },
        "followers": 1000,
    }

    # (90 + 110) / 2 == 100 engagement for the two middle nodes => 0.1 engagement rate
    assert calculate_engagement_median(scraped_profile) == 0.1
    assert calculate_engagement_median(api_profile) == 0.1


def test_calculate_engagement_no_followers():
    profile = {"media": {"nodes": []}, "followers": 0}

    assert calculate_engagement_median(profile) == 0


def test_calculate_hashtag_stats_returns_expected_result():
    # Arrange
    data = [
        {"caption": "This pic is so great #ad #amazing"},
        {"caption": "This one is also great #ad"},
    ]

    # Act
    result = calculate_hashtag_stats(data)

    # Assert
    assert result == [("ad", 2), ("amazing", 1)]


def test_calculate_hashtag_stats_with_no_media():
    # Arrange
    data = []

    # Act
    result = calculate_hashtag_stats(data)

    # Assert
    assert result == []
