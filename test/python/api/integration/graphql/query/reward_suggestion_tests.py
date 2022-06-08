from takumi.gql.query import RewardSuggestionQuery
from takumi.models.market import eu_market, uk_market, us_market


def test_resolve_get_reward_suggestion_for_uk(client, developer_user):
    with client.user_request_context(developer_user):
        asset_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=uk_market.slug,
            reward_model="assets",
            units=20,
            list_price=3600,
            shipping_required=False,
        )

        asset_reward_with_shipping = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=uk_market.slug,
            reward_model="assets",
            units=20,
            list_price=4000,
            shipping_required=True,
        )

        reach_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=uk_market.slug,
            reward_model="reach",
            units=1_000_000,
            list_price=10000,
            shipping_required=False,
        )

        engagement_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=uk_market.slug,
            reward_model="engagement",
            units=20000,
            list_price=11000,
            shipping_required=False,
        )

    assert asset_reward.value == 90
    assert asset_reward_with_shipping.value == 90
    assert reach_reward.value == 5.5
    assert engagement_reward.value == 6.05


def test_resolve_get_reward_suggestion_for_eu(client, developer_user):
    with client.user_request_context(developer_user):
        asset_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=eu_market.slug,
            reward_model="assets",
            units=20,
            list_price=4000,
            shipping_required=False,
        )

        asset_reward_with_shipping = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=eu_market.slug,
            reward_model="assets",
            units=20,
            list_price=4400,
            shipping_required=True,
        )

        reach_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=eu_market.slug,
            reward_model="reach",
            units=1_000_000,
            list_price=10000,
            shipping_required=False,
        )

        engagement_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=eu_market.slug,
            reward_model="engagement",
            units=20000,
            list_price=11000,
            shipping_required=False,
        )

    assert asset_reward.value == 100
    assert asset_reward_with_shipping.value == 100
    assert reach_reward.value == 5.5
    assert engagement_reward.value == 6.05


def test_resolve_get_reward_suggestion_for_us(client, developer_user):
    with client.user_request_context(developer_user):
        asset_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=us_market.slug,
            reward_model="assets",
            units=20,
            list_price=6000,
            shipping_required=False,
        )

        asset_reward_with_shipping = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=us_market.slug,
            reward_model="assets",
            units=20,
            list_price=6400,
            shipping_required=True,
        )

        reach_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=us_market.slug,
            reward_model="reach",
            units=1_000_000,
            list_price=10000,
            shipping_required=False,
        )

        engagement_reward = RewardSuggestionQuery().resolve_get_reward_suggestion(
            "info",
            market_slug=us_market.slug,
            reward_model="engagement",
            units=20000,
            list_price=11000,
            shipping_required=False,
        )

    assert asset_reward.value == 100
    assert asset_reward_with_shipping.value == 100
    assert reach_reward.value == 5.5
    assert engagement_reward.value == 6.05
