import mock

from takumi.constants import ENGAGEMENT_PER_ASSET
from takumi.models.gig import STATES as GIG_STATES

MILLION = 1_000_000


def test_engagement_reservations_met(engagement_campaign):
    with mock.patch(
        "takumi.funds.EngagementFund.minimum_reservations",
        new_callable=mock.PropertyMock,
        return_value=10,
    ):
        with mock.patch("takumi.funds.engagement.EngagementFund.reserved_offer_count", 1):
            assert engagement_campaign.fund.minimum_reservations_met() is False
        with mock.patch("takumi.funds.engagement.EngagementFund.reserved_offer_count", 10):
            assert engagement_campaign.fund.minimum_reservations_met() is True


def test_engagement_fund_is_reservable_while_minimum_reservations_not_met(
    engagement_campaign, monkeypatch
):
    engagement_campaign.units = MILLION

    monkeypatch.setattr("takumi.funds.engagement.EngagementFund._remaining_engagement", lambda _: 0)

    with mock.patch(
        "takumi.funds.engagement.EngagementFund.minimum_reservations_met", return_value=False
    ):
        assert engagement_campaign.fund.is_reservable()

    with mock.patch(
        "takumi.funds.engagement.EngagementFund.minimum_reservations_met", return_value=True
    ):
        assert not engagement_campaign.fund.is_reservable()


def test_engagement_fund_is_reservable_while_minimum_asset_count_not_met_for_larger_campaign(
    engagement_campaign, monkeypatch
):
    engagement_campaign.units = 200_000
    minimal_reservation = engagement_campaign.units / ENGAGEMENT_PER_ASSET

    monkeypatch.setattr("takumi.funds.engagement.EngagementFund._remaining_engagement", lambda _: 0)

    with mock.patch(
        "takumi.funds.fund.Fund.reserved_offer_count",
        new_callable=mock.PropertyMock,
        return_value=minimal_reservation - 1,
    ):
        assert engagement_campaign.fund.is_reservable()

    with mock.patch(
        "takumi.funds.fund.Fund.reserved_offer_count",
        new_callable=mock.PropertyMock,
        return_value=minimal_reservation,
    ):
        assert not engagement_campaign.fund.is_reservable()


def test_engagement_min_followers(engagement_campaign):
    assert engagement_campaign.fund.min_followers == 15000


def test_engagements_is_fulfilled(
    engagement_campaign, engagement_post, offer_factory, gig_factory, instagram_post_factory
):
    engagement_campaign.units = 20000
    gig_factory(
        post=engagement_post,
        state=GIG_STATES.REJECTED,  # Makes it claimable
        instagram_post=instagram_post_factory(likes=10000, comments=1000),
    )

    assert engagement_campaign.fund.is_fulfilled() is False

    gig_factory(
        post=engagement_post,
        state=GIG_STATES.REJECTED,  # Makes it claimable
        instagram_post=instagram_post_factory(likes=10000, comments=1000),
    )
    assert engagement_campaign.fund.is_fulfilled() is True
