import datetime as dt
import pickle
from functools import wraps
from uuid import UUID

from flask import g

from takumi.constants import MINIMUM_CLIENT_VERSION
from takumi.exceptions import client_version_is_lower_than_min_version
from takumi.extensions import redis
from takumi.gql.exceptions import GraphQLException
from takumi.i18n import gettext as _
from takumi.models import (
    Advertiser,
    Announcement,
    Campaign,
    Gig,
    Influencer,
    Insight,
    Market,
    Media,
    Offer,
    Payment,
    Post,
    Region,
    StoryFrame,
    User,
)
from takumi.rewards import RewardCalculator
from takumi.services import (
    AdvertiserService,
    CampaignService,
    GigService,
    InfluencerService,
    InsightService,
    InstagramStoryService,
    MediaService,
    OfferService,
    PaymentService,
    PostService,
    RegionService,
    UserService,
)
from takumi.services.user import BRAND_PROFILE_ACCESS_LEVEL


def get_region_or_404(id) -> Region:
    region = RegionService.get_by_id(id)
    if region is None:
        raise GraphQLException(f"Region ({id}) not found")
    return region


def get_insight_or_404(id) -> Insight:
    insight = InsightService.get_by_id(id)
    if insight is None:
        raise GraphQLException(f"Insight ({id}) not found")
    return insight


def get_insight_media_or_404(id) -> Media:
    media = MediaService.get_insight_media_by_id(id)
    if media is None:
        raise GraphQLException(f"Media ({id}) not found")
    return media


def get_advertiser_or_404(id) -> Advertiser:
    advertiser = AdvertiserService.get_by_id(id)
    if advertiser is None:
        raise GraphQLException(f"Advertiser ({id}) not found")
    return advertiser


def get_gig_or_404(id) -> Gig:
    gig = GigService.get_by_id(id)
    if gig is None:
        raise GraphQLException(f"Gig ({id}) not found")
    return gig


def get_announcement_or_404(id) -> Announcement:
    announcement = Announcement.query.get(id)
    if announcement is None:
        raise GraphQLException(f"Announcement ({id}) not found")
    return announcement


def get_influencer_or_404(id) -> Influencer:
    try:
        influencer = InfluencerService.get_by_id(str(UUID(id)))
    except ValueError:
        influencer = InfluencerService.get_by_username(id)

    if influencer is None:
        raise GraphQLException(f"Influencer ({id}) not found")
    return influencer


def get_offer_or_404(id) -> Offer:
    offer = OfferService.get_by_id(id)
    if offer is None:
        raise GraphQLException(f"Offer ({id}) not found")
    return offer


def get_payment_or_404(id) -> Payment:
    payment = PaymentService.get_by_id(id)
    if payment is None:
        raise GraphQLException(f"Payment ({id}) not found")
    return payment


def get_campaign_or_404(id) -> Campaign:
    campaign = CampaignService.get_by_id(id)
    if campaign is None:
        raise GraphQLException(f"Campaign ({id}) not found")
    return campaign


def get_story_frame_or_404(id) -> StoryFrame:
    story_frame = InstagramStoryService.get_story_frame_by_id(id)
    if story_frame is None:
        raise GraphQLException(f"StoryFrame ({id}) not found")
    return story_frame


def get_user_or_404(id) -> User:
    user = UserService.get_by_id(id)
    if user is None:
        raise GraphQLException(f"User ({id}) not found")
    return user


def get_market_or_404(slug) -> Market:
    market = Market.get_market(slug)
    if market is None:
        raise GraphQLException(f"Market ({slug}) not found")
    return market


def get_post_or_404(id) -> Post:
    post = PostService.get_by_id(id)
    if post is None:
        raise GraphQLException(f"Post ({id}) not found")
    return post


def influencer_post_step(  # noqa: C901: Function too complex
    post, influencer, gig=None, client_version=None
):
    """Consolidate the potential complexity of all different models for finding out influencer post step"""
    offer = OfferService.get_for_influencer_in_campaign(influencer.id, post.campaign.id)

    if offer is None:
        if post.campaign.public:
            if post.campaign.apply_first:
                return "REQUEST_TO_PARTICIPATE"
            else:
                return "ACCEPT_OFFER"
        else:
            # You shouldn't be able to see this campaign
            return "UNKNOWN"

    if offer.state == Offer.STATES.REJECTED:
        return "OFFER_REJECTED"

    if offer.state == Offer.STATES.REVOKED:
        return "OFFER_REVOKED"

    if offer.state == Offer.STATES.PENDING:
        return "REQUEST_TO_PARTICIPATE"

    if offer.state in [
        Offer.STATES.REQUESTED,
        Offer.STATES.CANDIDATE,
        Offer.STATES.APPROVED_BY_BRAND,
    ]:
        return "REQUESTED"

    if offer.claimed is not None:
        return "CLAIMED"

    if offer.is_claimable:
        return "CLAIM_REWARD"

    if offer.state == Offer.STATES.INVITED:
        return "ACCEPT_OFFER"

    if offer.address_missing:
        return "MISSING_SHIPPING_INFO"

    if post.campaign.shipping_required and not offer.in_transit:
        return "AWAITING_SHIPPING"

    gig = gig or GigService.get_latest_influencer_gig_of_a_post(offer.influencer_id, post.id)
    if gig is None:
        return "SUBMIT_FOR_APPROVAL"

    if gig.state == Gig.STATES.REJECTED:
        return "CLIENT_REJECTED"

    if gig.state == Gig.STATES.REQUIRES_RESUBMIT:
        return "RESUBMIT"

    if gig.post.campaign.brand_safety and gig.state in (
        Gig.STATES.SUBMITTED,
        Gig.STATES.REVIEWED,
        Gig.STATES.REPORTED,
    ):
        return "IN_REVIEW"

    if not gig.post.campaign.brand_safety and gig.state in (
        Gig.STATES.SUBMITTED,
        Gig.STATES.REPORTED,
    ):
        return "IN_REVIEW"

    if offer.campaign.require_insights:
        if gig.insight is not None:
            if gig.insight.state == Insight.STATES.SUBMITTED:
                return "VERIFY_INSIGHTS"

        if gig.is_missing_insights and gig.is_passed_review_period:
            return "SUBMIT_INSIGHTS"

    if client_version and client_version >= (5, 7, 0):
        if gig.is_verified:
            return "VERIFIED"

    if gig.is_posted:
        return "POSTED"

    if gig.can_post_to_instagram:
        return "POST_TO_INSTAGRAM"

    return "WAITING_TO_POST"


""" Legacy functions for public campaigns

These helper functions return temporary offers and filter the campaign/post
based on if the influencer is targeted in the public campaign.

TODO: These functions below should be removed when public is removed, when
campaigns are self-driving.
"""


def get_offer_for_public_campaign(campaign_id, offer_id, commit=False):
    from flask_login import current_user

    from takumi.events.offer import OfferLog
    from takumi.extensions import db
    from takumi.models import Offer

    campaign = CampaignService.get_by_id(campaign_id)
    influencer = current_user.influencer
    if campaign is None or not campaign.public:
        # Bail out early, this is just hacky code to handle public campaigns
        return None

    # First check if the influencer might have an offer with another id
    offer = Offer.query.filter(Offer.campaign == campaign, Offer.influencer == influencer).first()
    if offer:
        return offer

    if campaign.targeting.targets_influencer(influencer):
        if not campaign.fund.is_reservable():
            raise GraphQLException("Sorry the campaign has already been filled")

        if commit:
            # Use the normal means creating the offer if we're committing it
            offer = Offer(id=offer_id)
            log = OfferLog(offer)
            log.add_event(
                "create" if campaign.apply_first else "create_invite",
                {
                    "campaign_id": campaign.id,
                    "influencer_id": influencer.id,
                    "reward": RewardCalculator(campaign).calculate_reward_for_influencer(
                        influencer
                    ),
                    "followers_per_post": influencer.instagram_account.followers,
                    "engagements_per_post": influencer.estimated_engagements_per_post,
                },
            )

            db.session.add(offer)
            db.session.commit()
            return offer

        return Offer(
            id=offer_id,
            state=Offer.STATES.INVITED,
            reward=RewardCalculator(campaign).calculate_reward_for_influencer(influencer),
            campaign=campaign,
            influencer=influencer,
        )
    return None


def get_post_for_public_campaign(post_id):
    from flask_login import current_user

    post = PostService.get_by_id(post_id)

    if post is None or not post.campaign.public:
        return None

    if not post.campaign.targeting.targets_influencer(current_user.influencer):
        return None

    return post


def get_public_campaign(campaign_id):
    from flask_login import current_user

    campaign = get_campaign_or_404(campaign_id)
    if not campaign.public or not campaign.targeting.targets_influencer(current_user.influencer):
        return None

    return campaign


def cached(ttl=dt.timedelta(hours=1)):
    def decorator(func):
        @wraps(func)
        def wrapped(root, info, **kwargs):
            key = "cached_resolver:" + "_".join(info.path) + str(kwargs)
            conn = redis.get_connection()
            cached_result = conn.get(key)
            if cached_result is not None:
                try:
                    return pickle.loads(cached_result.encode("latin1"))
                except pickle.UnpicklingError:
                    pass
            result = func(root, info, **kwargs)
            pickled = pickle.dumps(result)
            conn.setex(key, int(ttl.total_seconds()), pickled.decode("latin1"))
            return result

        return wrapped

    return decorator


def min_version_required(version=MINIMUM_CLIENT_VERSION):
    def decorator(func):
        @wraps(func)
        def wrapped(root, info, *args, **kwargs):
            client_version = info.context.get("client_version")
            if client_version and client_version_is_lower_than_min_version(client_version, version):
                raise GraphQLException(
                    _("Takumi app is out of date")
                    + ". "
                    + _("Update to the latest version to continue using Takumi.")
                )
            return func(root, info, *args, **kwargs)

        return wrapped

    return decorator


def update_last_active(func):
    def wrapper(self, *args, **kwargs):
        from flask_login import current_user

        if not (hasattr(g, "is_developer") and g.is_developer):
            if hasattr(current_user, "role_name") and current_user.role_name == "influencer":
                current_user.update_last_active()
        return func(self, *args, **kwargs)

    return wrapper


def get_brand_profile_user(user_id, campaign):
    brand_user_profile = next(
        filter(
            lambda user: user.access_level == BRAND_PROFILE_ACCESS_LEVEL
            and user.user_id == user_id
            and user.advertiser_id == campaign.advertiser.id,
            campaign.advertiser.users_association,
        ),
        None,
    )
    return brand_user_profile
