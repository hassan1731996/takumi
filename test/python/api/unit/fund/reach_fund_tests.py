import mock

from takumi.constants import MAX_FOLLOWERS_BEYOND_REWARD_POOL
from takumi.funds import ReachFund


def test_reach_reservations_met(reach_campaign):
    with mock.patch(
        "takumi.funds.ReachFund.minimum_reservations",
        new_callable=mock.PropertyMock,
        return_value=10,
    ):
        with mock.patch("takumi.funds.reach.ReachFund.reserved_offer_count", 1):
            assert reach_campaign.fund.minimum_reservations_met() is False
        with mock.patch("takumi.funds.reach.ReachFund.reserved_offer_count", 10):
            assert reach_campaign.fund.minimum_reservations_met() is True


def test_reach_fund_is_reservable_while_minimum_reservations_not_met(reach_campaign):
    reach_campaign.units = 1_000_000

    with mock.patch("takumi.funds.reach.ReachFund._remaining_reach", return_value=0):
        with mock.patch(
            "takumi.funds.reach.ReachFund.minimum_reservations_met", return_value=False
        ):
            assert reach_campaign.fund.is_reservable()

        with mock.patch("takumi.funds.reach.ReachFund.minimum_reservations_met", return_value=True):
            assert not reach_campaign.fund.is_reservable()


def test_reach_fund_is_reservable_while_minimum_asset_count_not_met_for_larger_campaign(
    reach_campaign,
):
    reach_campaign.units = 2_000_000

    with mock.patch("takumi.funds.reach.ReachFund._remaining_reach", return_value=0):
        with mock.patch(
            "takumi.funds.fund.Fund.reserved_offer_count",
            new_callable=mock.PropertyMock,
            return_value=5,
        ):
            assert reach_campaign.fund.is_reservable()

        with mock.patch(
            "takumi.funds.fund.Fund.reserved_offer_count",
            new_callable=mock.PropertyMock,
            return_value=10,
        ):
            assert not reach_campaign.fund.is_reservable()


def test_reach_min_followers(reach_campaign):
    assert reach_campaign.fund.min_followers == 15000


def test_reach_fund_can_reserve_units(app, monkeypatch):
    monkeypatch.setattr("takumi.funds.reach.ReachFund._remaining_reach", lambda _: 500_000)
    monkeypatch.setattr("takumi.funds.reach.ReachFund.minimum_reservations_met", lambda _: True)

    fund = ReachFund(campaign=mock.Mock(units=1_000_000))
    assert fund.is_reservable()

    assert fund.can_reserve_units(100_000)
    assert fund.can_reserve_units(500_000)
    assert fund.can_reserve_units(500_000 + MAX_FOLLOWERS_BEYOND_REWARD_POOL)
    assert not fund.can_reserve_units(500_000 + MAX_FOLLOWERS_BEYOND_REWARD_POOL + 1)
