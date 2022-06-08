from takumi.gql import arguments, fields
from takumi.gql.enums.campaign import RewardModel
from takumi.gql.utils import get_campaign_or_404, get_influencer_or_404
from takumi.models import Campaign, Currency
from takumi.rewards import RewardCalculator
from takumi.roles import permissions


class RewardSuggestionQuery:
    get_reward_suggestion = fields.Field(
        "Currency",
        market_slug=arguments.String(required=True),
        reward_model=RewardModel(
            required=True,
            description="The reward model must be one of `assets`, `reach` or `engagement`",
        ),
        units=arguments.Int(required=True),
        list_price=arguments.Int(required=True),
        shipping_required=arguments.Boolean(default_value=False),
    )

    get_influencer_reward_suggestion_for_campaign = fields.Field(
        "Currency",
        campaign_id=arguments.UUID(required=True),
        username=arguments.String(required=True),
    )

    @permissions.edit_campaign.require()
    def resolve_get_reward_suggestion(root, info, list_price, **kwargs):
        campaign = Campaign(**dict(kwargs, list_price=list_price * 100))
        reward = RewardCalculator(campaign).calculate_suggested_reward()

        return Currency(reward, campaign.market.currency, currency_digits=True)

    @permissions.edit_campaign.require()
    def resolve_get_influencer_reward_suggestion_for_campaign(root, info, campaign_id, username):
        campaign = get_campaign_or_404(campaign_id)
        influencer = get_influencer_or_404(username)

        reward = 0

        # TODO: Handle rewards for non Instagram influencers
        if influencer.instagram_account:
            reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

        return Currency(reward, campaign.market.currency, currency_digits=True)
