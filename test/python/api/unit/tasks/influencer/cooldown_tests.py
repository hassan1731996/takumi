import datetime as dt

import mock

from takumi.tasks.influencer.cooldown import end_cooldown


def test_end_cooldown_cooled_down_influencer(influencer, monkeypatch):
    influencer.state = "cooldown"
    influencer.cooldown_ends = dt.datetime.now(dt.timezone.utc)
    with mock.patch("sqlalchemy.orm.session.SessionTransaction.commit"):
        with mock.patch("flask_sqlalchemy.BaseQuery.get") as mock_get:
            mock_get.return_value = influencer
            end_cooldown(influencer.id)
    assert influencer.state == "reviewed"
    assert influencer.cooldown_ends is None


def test_end_cooldown_non_cooled_down_influencer(influencer, monkeypatch):
    influencer.state = "reviewed"
    influencer.cooldown_ends = None
    with mock.patch("sqlalchemy.orm.session.SessionTransaction.commit"):
        with mock.patch("flask_sqlalchemy.BaseQuery.get") as mock_get:
            mock_get.return_value = influencer
            end_cooldown(influencer.id)
    assert influencer.state == "reviewed"
    assert influencer.cooldown_ends is None
