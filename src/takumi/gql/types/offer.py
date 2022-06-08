import datetime as dt

from flask_login import current_user
from graphene import ObjectType

from takumi.gql import arguments, fields
from takumi.gql.relay import Connection, Node
from takumi.gql.utils import get_brand_profile_user
from takumi.models import Currency
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.offer import STATES_MAP as OFFER_STATES_MAP
from takumi.roles import permissions
from takumi.roles.needs import (
    influencer_role,
    manage_influencers,
    manage_payments,
    view_offer_reward_info,
)
from takumi.services import OfferService


class PushNotification(ObjectType):
    last_sent = fields.DateTime()
    count = fields.Int()


class RewardBreakdown(ObjectType):
    net_value = fields.Field("Currency")
    vat_value = fields.Field("Currency")
    total_value = fields.Field("Currency")
    show_net_and_vat = fields.Boolean()


class OfferEvent(ObjectType):
    created = fields.DateTime()
    creator = fields.Field("User", source="creator_user")


class CampaignAnswer(ObjectType):
    prompt = fields.String()
    answer = fields.List(fields.String)


class InfluencerMetrics(ObjectType):
    engagement_rate_static = fields.Float()
    engagement_rate_story = fields.Float()
    reach = fields.Float()
    total_impressions = fields.Float()


class Offer(ObjectType):
    class Meta:
        interfaces = (Node,)

    created = fields.DateTime()
    modified = fields.DateTime()
    accepted = fields.DateTime()
    revoke_event = fields.Field(OfferEvent)
    rejected = fields.DateTime()
    acknowledged = fields.DateTime()
    is_selected = fields.Boolean()
    units = fields.Int()

    gigs = fields.List("Gig")

    answers = fields.List(CampaignAnswer)
    brand_visible_answers = fields.List(CampaignAnswer)

    state = fields.String()
    formatted_state = fields.String()
    is_accepted = fields.Boolean()
    in_transit = fields.Boolean()
    tracking_code = fields.String()
    address_missing = fields.Boolean()

    can_be_notified = fields.AuthenticatedField(fields.Boolean, needs=manage_influencers)
    push_notification = fields.AuthenticatedField(PushNotification, needs=manage_influencers)

    # XXX: can be removed once the admin/client start using the followers_per_post field instead
    reach = fields.Int(source="followers_per_post")
    followers_per_post = fields.Int()
    engagements_per_post = fields.Int()
    estimated_engagements_per_post = fields.Int()

    comments = fields.AdvertiserField(fields.List("Comment"))

    influencer = fields.Field("Influencer")
    campaign = fields.Field("Campaign")

    claimed = fields.AuthenticatedField(fields.DateTime, needs=view_offer_reward_info)
    is_claimable = fields.AuthenticatedField(fields.Boolean, needs=view_offer_reward_info)
    payable = fields.AuthenticatedField(fields.DateTime, needs=view_offer_reward_info)
    is_paid = fields.AuthenticatedField(fields.Boolean, needs=view_offer_reward_info)

    reward = fields.AuthenticatedField("Currency", needs=[manage_influencers, influencer_role])
    reward_breakdown = fields.AuthenticatedField(
        RewardBreakdown, needs=[manage_influencers, influencer_role]
    )
    reward_per_post = fields.AuthenticatedField(
        "Currency",
        needs=[manage_influencers, influencer_role],
        post_id=arguments.UUID(),
        deprecation_reason="Rewards are going to be for offers as a whole, use Offer.reward",
    )
    claimable_amount = fields.AuthenticatedField(
        "Currency",
        needs=[manage_influencers, influencer_role],
        deprecation_reason="Partial payouts are being phased out because of custom campaign rewards",
    )

    payment = fields.AuthenticatedField("Payment", needs=manage_payments)

    tax_info_missing = fields.AuthenticatedField(fields.Boolean, needs=influencer_role)

    revertable_state = fields.AuthenticatedField(fields.String, needs=manage_influencers)

    facebook_link_missing = fields.Boolean()

    influencer_metrics = fields.Field(
        InfluencerMetrics,
        description="Metrics from all Creator's Posts within this Campaign if they are calculated.",
    )

    def resolve_influencer_metrics(offer, info):
        current_user_id = current_user.get_id()
        brand_user_profile = get_brand_profile_user(current_user_id, offer.campaign)

        if brand_user_profile and not brand_user_profile.advertiser.advertiser_config:
            return dict(
                engagement_rate_static=None,
                engagement_rate_story=None,
                reach=None,
                total_impressions=None,
            )

        engagement_rate_static, engagement_rate_story = None, None
        if (
            not brand_user_profile
            or brand_user_profile.advertiser.advertiser_config.engagement_rate
        ):
            engagement_rate_static = offer.engagement_rate_static
            engagement_rate_story = offer.engagement_rate_story

        total_impressions = (
            offer.total_impressions
            if not brand_user_profile or brand_user_profile.advertiser.advertiser_config.impressions
            else None
        )
        reach = offer.reach

        return dict(
            engagement_rate_static=engagement_rate_static,
            engagement_rate_story=engagement_rate_story,
            reach=reach,
            total_impressions=total_impressions,
        )

    def resolve_answers(offer, info):
        if permissions.team_member.can():
            # Team members can see the answers
            return offer.answers
        if current_user == offer.influencer.user:
            # The influencers can see their own
            return offer.answers
        return []

    def resolve_brand_visible_answers(offer, info):
        brand_visible_prompts = [
            prompt["text"]
            for prompt in offer.campaign.prompts
            if prompt.get("brand_visible", False)
        ]
        return [answer for answer in offer.answers if answer["prompt"] in brand_visible_prompts]

    def resolve_reward_breakdown(offer, info):
        reward_breakdown = offer.reward_breakdown
        currency = offer.campaign.market.currency
        for key in ["net_value", "vat_value", "total_value"]:
            reward_breakdown[key] = Currency(
                reward_breakdown[key], currency=currency, currency_digits=True
            )
        reward_breakdown["show_net_and_vat"] = bool(offer.influencer.vat_number)
        return reward_breakdown

    def resolve_reward(offer, info):
        currency = offer.campaign.market.currency
        return Currency(amount=offer.reward, currency=currency)

    def resolve_reward_per_post(offer, info, post_id=None):
        post_count = len(offer.campaign.posts)
        reward = offer.reward

        currency = offer.campaign.market.currency
        return Currency(amount=(reward / post_count), currency=currency)

    def resolve_claimable_amount(offer, info):
        if offer.is_claimable:
            amount = offer.reward
        else:
            amount = 0

        currency = offer.campaign.market.currency
        return Currency(amount=amount, currency=currency)

    def resolve_is_accepted(offer, info):
        return offer.state == OFFER_STATES.ACCEPTED

    def resolve_can_be_notified(offer, info):
        if not offer.influencer.has_device:
            return False
        push_notifications = OfferService.get_push_notifications(offer.id)
        if len(push_notifications) > 0:
            # Avoid spamming the influencer. At least one day must pass before sending another pn.
            if push_notifications[0].created > (
                dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
            ):
                return False

        if offer.state == OFFER_STATES.ACCEPTED:
            return not offer.is_claimable
        return offer.state == OFFER_STATES.INVITED

    def resolve_push_notification(offer, info):
        push_notifications = OfferService.get_push_notifications(offer.id)
        pn_count = len(push_notifications)

        return {"last_sent": push_notifications[0].created if pn_count else None, "count": pn_count}

    def resolve_revoke_event(offer, info):
        return OfferService.get_revoke_event(offer.id)

    def resolve_rejected(offer, info):
        return OfferService.get_rejected_date(offer.id)

    def resolve_units(offer, info):
        return offer.campaign.fund.get_offer_units(offer)

    def resolve_formatted_state(offer, info):
        return OFFER_STATES_MAP.get(offer.state, offer.state.replace("_", " ").title())

    def resolve_revertable_state(offer, info):
        """Return the previous state if the offer can be reverted"""
        if offer.state == OFFER_STATES.REVOKED:
            event = offer.get_event("revoke")
        elif offer.state == OFFER_STATES.REJECTED:
            event = offer.get_event("reject")
        elif offer.state == OFFER_STATES.REJECTED_BY_BRAND:
            event = offer.get_event("reject_candidate")
        else:
            return None

        if "_from_state" in event.event:
            previous_state = event.event["_from_state"]
            return OFFER_STATES_MAP.get(previous_state)


class OfferConnection(Connection):
    class Meta:
        node = Offer
