import mock

from takumi.funds import AssetsFund


def test_assets_fund_is_reservable_while_minimum_asset_count_not_met(campaign):
    campaign.units = 10

    with mock.patch(
        "takumi.funds.fund.Fund.reserved_offer_count",
        new_callable=mock.PropertyMock,
        return_value=9,
    ):
        assert campaign.fund.is_reservable()

    with mock.patch(
        "takumi.funds.fund.Fund.reserved_offer_count",
        new_callable=mock.PropertyMock,
        return_value=10,
    ):
        assert not campaign.fund.is_reservable()


def test_assets_min_followers(app, campaign):
    assert campaign.fund.min_followers == 1000


def test_assets_fund_can_reserve_units(app):
    fund = AssetsFund(campaign=mock.Mock(units=10, reserved_offers=[i for i in range(8)]))
    assert fund.is_reservable()

    assert fund.can_reserve_units(1)
    assert fund.can_reserve_units(2)
    assert not fund.can_reserve_units(3)
