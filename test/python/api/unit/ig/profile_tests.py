import datetime as dt

import mock
import pytest

from takumi.ig.profile import refresh_on_interval, should_update


def get_media_data(caption="", username="foo", created="2017-02-16T20:30:56+00:00"):
    return {
        "id": "fake-id",
        "url": "https://instagram.com/image.jpg",
        "link": "https://instagram.com/p/deadbeef",
        "type": "image",
        "caption": caption,
        "created": created,
        "likes": 100,
        "comments": 10,
        "owner": {"username": username},
    }


def test_should_update_if_update_dt_is_none():
    assert should_update(None, max_age=0)


def test_should_update_if_update_dt_over_max():
    assert should_update(dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3), max_age=2)


def test_should_not_update_if_update_dt_under_max():
    assert not should_update(dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3), max_age=4)


@pytest.fixture(autouse=True)
def patch_refresh_on_interval():
    with mock.patch("takumi.ig.profile.refresh_on_interval"):
        yield


def test_refresh_on_interval_calls_refresh_if_should_update(influencer, monkeypatch):
    monkeypatch.setattr("takumi.ig.profile.get_last_refresh", lambda _: mock.Mock())
    monkeypatch.setattr("takumi.ig.profile.should_update", lambda *_: True)

    with mock.patch(
        "takumi.ig.profile.refresh_instagram_account", return_value=None
    ) as mock_refresh:
        refresh_on_interval(influencer)

    mock_refresh.assert_called_with(influencer.instagram_account)


def test_refresh_on_interval_doesnt_call_refresh_if_shouldnt_update(influencer, monkeypatch):
    monkeypatch.setattr("takumi.ig.profile.get_last_refresh", lambda _: mock.Mock())
    monkeypatch.setattr("takumi.ig.profile.should_update", lambda *_: False)

    with mock.patch(
        "takumi.ig.profile.refresh_instagram_account", return_value=None
    ) as mock_refresh:
        refresh_on_interval(influencer)

    mock_refresh.assert_not_called()
