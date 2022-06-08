from takumi.constants import MAX_FOLLOWERS_BEYOND_REWARD_POOL, MILLE
from takumi.models.campaign import RewardModels
from takumi.rewards import RewardCalculator


def test_calculate_fixed_reward_when_custom_reward_units_is_provided(campaign, influencer):
    # Arrange
    campaign.reward_model = RewardModels.assets
    campaign.custom_reward_units = 5000
    calculator = RewardCalculator(campaign)

    # Act
    reward_suggested = calculator.calculate_suggested_reward()
    reward_influencer = calculator.calculate_reward_for_influencer(influencer)

    # Assert
    assert reward_suggested == 5000
    assert reward_influencer == 5000


def test_calculate_fixed_reward_with_no_units_returns_0(campaign, influencer):
    # Arrange
    campaign.reward_model = RewardModels.assets
    campaign.custom_reward_units = None
    campaign.shipping_required = True
    campaign.units = 0
    campaign.list_price = 1_000_000
    calculator = RewardCalculator(campaign)

    # Act
    reward_suggested = calculator.calculate_suggested_reward()
    reward_influencer = calculator.calculate_reward_for_influencer(influencer)

    # Assert
    assert reward_suggested == 0
    assert reward_influencer == 0


def test_calculate_fixed_reward_with_shipping_required(campaign, influencer):
    # Arrange
    campaign.reward_model = RewardModels.assets
    campaign.custom_reward_units = None
    campaign.shipping_required = True
    campaign.units = 10
    campaign.list_price = 1_000_000
    calculator = RewardCalculator(campaign)

    # Act
    reward_suggested = calculator.calculate_suggested_reward()
    reward_influencer = calculator.calculate_reward_for_influencer(influencer)

    # Assert
    assert reward_suggested == 49000
    assert reward_influencer == 49000


def test_calculate_fixed_reward_whithout_shipping_required(campaign, influencer):
    # Arrange
    campaign.reward_model = RewardModels.assets
    campaign.custom_reward_units = None
    campaign.shipping_required = False
    campaign.units = 10
    campaign.list_price = 1_000_000
    calculator = RewardCalculator(campaign)

    # Act
    reward_suggested = calculator.calculate_suggested_reward()
    reward_influencer = calculator.calculate_reward_for_influencer(influencer)

    # Assert
    assert reward_suggested == 50000
    assert reward_influencer == 50000


def test_calculate_cpfm_reward_with_no_cap_with_custom_reward_units(
    campaign, influencer, monkeypatch
):
    # Arrange
    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda *args: iter([]))
    campaign.reward_model = RewardModels.reach
    campaign.custom_reward_units = 50000
    influencer.instagram_account.followers = 2000

    # Act
    reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

    # Assert
    assert reward == 100_000


def test_calculate_cpfm_reward_capped_followers_over_reward_pool_with_custom_reward_units(
    campaign, influencer, monkeypatch, offer_factory
):
    campaign.reward_model = RewardModels.reach
    campaign.units = 1_000_000
    campaign.custom_reward_units = 50000
    remaining_units_left = 10000
    reserved_offer = offer_factory(followers_per_post=campaign.units - remaining_units_left)
    influencer.instagram_account.followers = campaign.units  # Can cover the whole campaign

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda *args: iter([reserved_offer]))
    reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

    assert (
        reward
        == campaign.custom_reward_units
        * (remaining_units_left + MAX_FOLLOWERS_BEYOND_REWARD_POOL)
        / MILLE
    )


def test_calculate_cpfm_reward_with_no_cap_from_campaign(campaign, influencer, monkeypatch):
    # Arrange
    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda *args: iter([]))
    campaign.reward_model = RewardModels.reach
    campaign.custom_reward_units = None
    campaign.units = 1_000_000
    campaign.list_price = 1_000_000

    # Act
    reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

    # Assert
    assert reward == 500


def test_calculate_cpfm_reward_with_no_units_returns_0(campaign, influencer):
    # Arrange
    campaign.custom_reward_units = None
    campaign.units = 0

    # Act
    reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

    # Assert
    assert reward == 0


def test_calculate_reward_removes_currency_fraction(
    campaign, influencer, offer_factory, monkeypatch
):
    campaign.reward_model = RewardModels.reach
    campaign.units = 1_000_000
    remaining_units_left = 10000
    reserved_offer = offer_factory(followers_per_post=campaign.units - remaining_units_left)
    influencer.instagram_account.followers = campaign.units  # Can cover the whole campaign

    monkeypatch.setattr("sqlalchemy.orm.query.Query.__iter__", lambda *args: iter([reserved_offer]))

    influencer.instagram_account.followers = 12500

    assert int(campaign.fund.get_reward(influencer.followers)) == 687
    assert RewardCalculator(campaign).calculate_reward_for_influencer(influencer) == 600

    influencer.instagram_account.followers = 13000

    assert int(campaign.fund.get_reward(influencer.followers)) == 715
    assert RewardCalculator(campaign).calculate_reward_for_influencer(influencer) == 700


def test_reward_breakdown(offer):
    offer.reward = 80 * 100
    offer.vat_percentage = 0.19
    assert offer.reward_breakdown["total_value"] == 80 * 100
    assert offer.reward_breakdown["vat_value"] == 1277.3109243697472
    assert offer.reward_breakdown["net_value"] == 6722.689075630253
