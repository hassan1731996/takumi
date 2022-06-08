import datetime as dt

from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection
from takumi.models import Currency
from takumi.rewards import RewardCalculator
from takumi.roles.needs import influencer_role, manage_influencers


def _reward(root):
    if root.Offer:
        return root.Offer.reward
    else:
        return RewardCalculator(root.Campaign).calculate_reward_for_influencer(root.Influencer)


class InfluencerCampaignAndOffer(ObjectType):
    campaign = fields.Field("Campaign", source="Campaign")
    offer = fields.Field("Offer", source="Offer")
    reward = fields.AuthenticatedField("Currency", needs=[manage_influencers, influencer_role])
    reward_breakdown = fields.AuthenticatedField(
        "RewardBreakdown", needs=[manage_influencers, influencer_role]
    )

    def resolve_reward(root, info):
        reward = _reward(root)
        return Currency(amount=reward, currency=root.Campaign.market.currency)

    def resolve_reward_breakdown(root, info):
        if root.Offer:
            breakdown = root.Offer.reward_breakdown
        else:
            reward = _reward(root)
            if root.Influencer.target_region:
                vat_percentage = (
                    root.Influencer.target_region.get_vat_percentage(
                        dt.datetime.now(dt.timezone.utc).date()
                    )
                    or 0
                )
            else:
                vat_percentage = 0

            net_value = reward / (1.0 + vat_percentage)
            vat_value = reward - net_value
            breakdown = {
                "net_value": net_value,
                "vat_value": vat_value,
                "total_value": reward,
                "show_net_and_vat": bool(root.Influencer.vat_number),
            }
        for key in ["net_value", "vat_value", "total_value"]:
            breakdown[key] = Currency(
                breakdown[key], currency=root.Campaign.market.currency, currency_digits=True
            )
        breakdown["show_net_and_vat"] = bool(root.Influencer.vat_number)
        return breakdown


class InfluencerCampaignAndOfferConnection(Connection):
    class Meta:
        node = InfluencerCampaignAndOffer
