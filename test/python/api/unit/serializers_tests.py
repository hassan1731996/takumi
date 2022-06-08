# encoding=utf-8

import datetime as dt

from takumi.serializers import InstagramAccountFollowersHistorySerializer
from takumi.serializers.events import parse_date


def test_parse_date_converts_naive_timezones():
    date_string = "2016-06-07T04:08:33.830507"
    assert parse_date(date_string) == "June 07, 2016"


def test_serializer_with_0_or_1_data_returns_empty_list():
    events_1 = iter([])
    events_2 = iter([(dt.date(2017, 1, 9), 1000, 1000)])
    serializer_1 = InstagramAccountFollowersHistorySerializer(events_1)
    serializer_2 = InstagramAccountFollowersHistorySerializer(events_2)

    stats_list_1 = serializer_1.serialize()
    stats_list_2 = serializer_2.serialize()
    assert stats_list_1 == []
    assert stats_list_2 == []


def test_get_larger_followers_difference_returns_min_when_min_has_greater_diff():
    assert InstagramAccountFollowersHistorySerializer._get_larger_followers_difference(
        100, 10, 20
    ) == (10, -90)
    assert InstagramAccountFollowersHistorySerializer._get_larger_followers_difference(
        100, 90, 101
    ) == (90, -10)


def test_get_larger_followers_difference_returns_max_when_max_has_greater_diff():
    assert InstagramAccountFollowersHistorySerializer._get_larger_followers_difference(
        100, 110, 200
    ) == (200, 100)
    assert InstagramAccountFollowersHistorySerializer._get_larger_followers_difference(
        100, 50, 151
    ) == (151, 51)


def test_create_follower_stats_list_with_10_day_gap():
    events = iter(
        [
            (dt.date(2017, 1, 9), 1000, 1000),
            (dt.date(2017, 1, 10), 1000, 1000),
            (dt.date(2017, 1, 20), 2000, 2000),
        ]
    )

    stats_list = InstagramAccountFollowersHistorySerializer(events).serialize()
    assert stats_list[0]["followers"] == 1000
    assert stats_list[0]["prev_followers"] == 1000
    assert stats_list[0]["avg_followers_diff"] == 0

    assert stats_list[1]["prev_followers"] == 1000
    assert stats_list[1]["followers"] == 2000
    assert stats_list[1]["avg_followers_diff"] == 100  # 1000 / 10 days
    assert stats_list[1]["perc"] == 0.1  # 10%


def test_serializer_with_additional_data():
    events = iter(
        [
            (dt.date(2017, 1, 9), 1000, 1000, 2),
            (dt.date(2017, 1, 10), 1000, 1000, 0),
            (dt.date(2017, 1, 20), 2000, 2000, 1),
        ]
    )
    additional_data = ["during_post_type"]

    stats_list = InstagramAccountFollowersHistorySerializer(events, additional_data).serialize()
    assert stats_list[0]["during_post_type"] == 0
    assert stats_list[1]["during_post_type"] == 1


def test_serializer_with_0_previous_followers():
    events = iter(
        [(dt.date(2017, 1, 9), 0, 0), (dt.date(2017, 1, 10), 0, 1), (dt.date(2017, 1, 11), 4, 4)]
    )

    stats_list = InstagramAccountFollowersHistorySerializer(events).serialize()
    assert stats_list[0]["followers"] == 1
    assert stats_list[0]["prev_followers"] == 0
    assert stats_list[0]["avg_followers_diff"] == 1
    assert stats_list[0]["perc"] == 1.0  # 100#

    assert stats_list[1]["prev_followers"] == 1
    assert stats_list[1]["followers"] == 4
    assert stats_list[1]["avg_followers_diff"] == 3
    assert stats_list[1]["perc"] == 3.0  # 300%
