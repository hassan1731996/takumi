import mock
import pytest

from takumi.constants import MAX_IMPRESSIONS_RATIO, MIN_IMPRESSIONS_RATIO
from takumi.services import InfluencerService


def test_influencer_update_impressions_ratio_doesnt_do_anything_with_no_insights(
    app, influencer, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda *_: iter([]))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    assert not mock_log.called


def test_influencer_update_impressions_ratio_sets_ratio_from_insights(app, influencer, monkeypatch):
    insights = [mock.Mock(impressions=1000, followers=10000)]

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda _: iter(insights))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    mock_log.assert_called_once_with("set_impressions_ratio", {"ratio": pytest.approx(0.1)})


def test_influencer_update_impressions_ratio_sets_averages_ratio_of_insights(
    app, influencer, monkeypatch
):
    insights = [
        mock.Mock(impressions=1000, followers=10000),
        mock.Mock(impressions=1500, followers=10000),
        mock.Mock(impressions=2000, followers=10000),
    ]

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda _: iter(insights))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    mock_log.assert_called_once_with("set_impressions_ratio", {"ratio": pytest.approx(0.15)})


def test_influencer_update_impressions_ratio_uses_influencer_follows_if_missing_from_insight(
    app, influencer, gig, monkeypatch
):
    insights = [mock.Mock(impressions=1000, followers=None, gig=gig)]
    influencer.instagram_account.followers = 20000

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda _: iter(insights))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    mock_log.assert_called_once_with("set_impressions_ratio", {"ratio": pytest.approx(0.05)})


def test_influencer_update_impressions_ratio_doesnt_set_if_too_high(
    app, influencer, gig, monkeypatch
):
    followers = 10000
    insights = [
        mock.Mock(impressions=followers * MAX_IMPRESSIONS_RATIO + 1, followers=followers, gig=gig)
    ]

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda _: iter(insights))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    assert not mock_log.called


def test_influencer_update_impressions_ratio_doesnt_set_if_too_low(
    app, influencer, gig, monkeypatch
):
    followers = 10000
    insights = [
        mock.Mock(impressions=followers * MIN_IMPRESSIONS_RATIO - 1, followers=followers, gig=gig)
    ]

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda _: iter(insights))

    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        InfluencerService(influencer).update_impressions_ratio()

    assert not mock_log.called


def test_influencer_update_vat_number_sets_valid_vat_number(app, influencer):
    with mock.patch("takumi.services.influencer.VatLayer"):
        with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
            InfluencerService(influencer).update_vat_number("ab12", is_vat_registered=True)
            InfluencerService(influencer).update_vat_number("ab1234567", is_vat_registered=True)
            InfluencerService(influencer).update_vat_number(
                "ab1234567890123", is_vat_registered=True
            )
            InfluencerService(influencer).update_vat_number(
                "ab123abc7890123", is_vat_registered=True
            )

    assert mock_log.call_args_list == [
        mock.call("vat_number", {"vat_number": "AB12", "is_vat_registered": True}),
        mock.call("vat_number", {"vat_number": "AB1234567", "is_vat_registered": True}),
        mock.call("vat_number", {"vat_number": "AB1234567890123", "is_vat_registered": True}),
        mock.call("vat_number", {"vat_number": "AB123ABC7890123", "is_vat_registered": True}),
    ]
