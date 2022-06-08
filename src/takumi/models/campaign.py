import datetime as dt
import operator
from collections import Counter
from functools import reduce
from typing import TYPE_CHECKING, Type

from flask import current_app
from sqlalchemy import Index, and_, case, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SimpleTSVectorType, SoftEnum, UUIDString, unnest_func
from core.common.utils import States

from takumi.constants import ENGAGEMENT_PER_ASSET, REACH_PER_ASSET
from takumi.extensions import db
from takumi.models.market import Market
from takumi.models.post import PostTypes
from takumi.utils import uuid4_str

from .helpers import hybrid_method_subquery, hybrid_property_subquery

if TYPE_CHECKING:
    from takumi.models import Advertiser, Post, Targeting, User  # noqa


class STATES(States):
    DRAFT = "draft"
    LAUNCHED = "launched"
    COMPLETED = "completed"
    STASHED = "stashed"


class RewardModels:
    assets = "assets"
    cash = "cash"
    engagement = "engagement"
    reach = "reach"
    impressions = "impressions"

    @staticmethod
    def get_models():
        return [
            RewardModels.assets,
            RewardModels.cash,
            RewardModels.engagement,
            RewardModels.reach,
            RewardModels.impressions,
        ]


class Campaign(db.Model):
    """A database entry representing a Takumi post series, a wrapper for posts."""

    __tablename__ = "campaign"

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    started = db.Column(UtcDateTime)

    candidates_submitted = db.Column(UtcDateTime)

    pre_approval = db.Column(db.Boolean, server_default="t")
    apply_first = db.Column(db.Boolean, server_default="t", nullable=False)

    brand_safety = db.Column(db.Boolean, server_default="f", nullable=False)
    brand_match = db.Column(db.Boolean, server_default="f", nullable=False)

    extended_review = db.Column(db.Boolean, server_default="f", nullable=False)
    require_insights = db.Column(db.Boolean, server_default="f", nullable=False)

    advertiser_id = db.Column(
        UUIDString, db.ForeignKey("advertiser.id", ondelete="restrict"), nullable=False, index=True
    )
    advertiser = relationship("Advertiser", backref="campaigns")

    market_slug = db.Column(SoftEnum(*Market.get_all_slugs()), nullable=False, index=True)

    timezone = db.Column(db.String, nullable=False)

    reward_model = db.Column(
        SoftEnum(*RewardModels.get_models()), server_default=RewardModels.assets, nullable=False
    )
    price = db.Column(db.Integer, nullable=False)
    list_price = db.Column(db.Integer, nullable=False)

    custom_reward_units = db.Column(db.Integer)
    pre_custom_reward_units = db.Column(db.Boolean, server_default="f")

    state = db.Column(
        SoftEnum(*STATES.values()), server_default=STATES.DRAFT, nullable=False, index=True
    )

    owner_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    owner = relationship("User", primaryjoin="User.id == Campaign.owner_id")

    units = db.Column(db.Integer, server_default=text("0"), nullable=False)

    targeting = relationship("Targeting", uselist=False, back_populates="campaign")

    campaign_manager_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    campaign_manager = relationship("User", primaryjoin="User.id == Campaign.campaign_manager_id")

    secondary_campaign_manager_id = db.Column(
        UUIDString, db.ForeignKey("user.id", ondelete="restrict")
    )
    secondary_campaign_manager = relationship(
        "User", primaryjoin="User.id == Campaign.secondary_campaign_manager_id"
    )

    community_manager_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="restrict"))
    community_manager = relationship("User", primaryjoin="User.id == Campaign.community_manager_id")

    has_nda = db.Column(db.Boolean, server_default="f", nullable=False)
    shipping_required = db.Column(db.Boolean, server_default="f")

    media_updated = db.Column(UtcDateTime)

    # Indicates if there is callback-scheduler recursive loop process active, and when it last updated
    media_updating = db.Column(db.Boolean, nullable=False, server_default="f")

    scheduled_jobs = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    pictures = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")

    prompts = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")

    name = db.Column(db.String)
    description = db.Column(db.String)

    industry = db.Column(db.String)

    tags = db.Column(
        MutableList.as_mutable(ARRAY(db.String)),
        nullable=False,
        server_default=text("ARRAY[]::varchar[]"),
    )

    push_notification_message = db.Column(db.String)

    report_summary = db.Column(db.String)

    report_token = db.Column(UUIDString, default=uuid4_str, index=True, unique=True)
    submissions_token = db.Column(UUIDString, default=uuid4_str, index=True, unique=True)
    insights_token = db.Column(UUIDString, default=uuid4_str, index=True, unique=True)
    opportunity_product_id = db.Column(db.String)

    search_vector = db.Column(
        SimpleTSVectorType("name", "tags", weigths={"name": "A", "tags": "D"}), index=True
    )

    full = db.Column(db.Boolean, nullable=False, server_default="f")
    public = db.Column(db.Boolean, nullable=False, server_default="f")
    allow_currency_conversion = db.Column(db.Boolean, nullable=False, server_default="f")
    pro_bono = db.Column(db.Boolean, nullable=False, server_default="f")

    candidate_order = db.Column(
        MutableList.as_mutable(ARRAY(UUIDString)),
        nullable=False,
        server_default=text("ARRAY[]::uuid[]"),
    )

    @property
    def requires_facebook(self):
        return any(post.post_type in ["standard", "story", "video"] for post in self.posts)

    @classmethod
    def from_url(cls, url):
        """Get campaign based on an admin url"""
        import re

        pattern = r".*/brands/\w+/(?P<campaign_id>[0-9a-fA-F\-]{36}).*"

        if match := re.match(pattern, url):
            return cls.query.get(match.group("campaign_id"))
        return None

    @property
    def insights_count(self):
        from takumi.services import CampaignService

        return CampaignService.get_insights_count(self.id)

    @property
    def ordered_candidates_q(self):
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        offer_q = db.session.query(Offer).filter(
            Offer.campaign == self, Offer.state == OFFER_STATES.CANDIDATE
        )

        if self.candidate_order != []:
            order_q = unnest_func(self.candidate_order)
            offer_q = offer_q.outerjoin(
                order_q, Offer.id == cast(order_q.c.unnest, UUIDString)
            ).order_by(order_q.c.ordinality, Offer.id)
        else:
            offer_q = offer_q.order_by(Offer.id)

        return offer_q

    @property
    def candidates_hash(self):
        from takumi.models import Offer

        ids = [offer.id for offer in self.ordered_candidates_q.with_entities(Offer.id)]
        return str(abs(hash(str(ids))))

    posts = relationship(
        "Post",
        primaryjoin="and_(Post.campaign_id==Campaign.id, ~Post.archived)",
        order_by="Post.opened, Post.id",
    )

    def __repr__(self):
        return f"<Campaign: {self.id} ({self.name})>"

    @property
    def market(self):
        from takumi.models import Market

        return Market.get_market(self.market_slug)

    @property
    def fund(self):
        from takumi.funds import AssetsFund, CashFund, EngagementFund, ImpressionsFund, ReachFund

        if self.reward_model == "reach":
            return ReachFund(self)
        if self.reward_model == "assets":
            return AssetsFund(self)
        if self.reward_model == "cash":
            return CashFund(self)
        if self.reward_model == "engagement":
            return EngagementFund(self)
        if self.reward_model == "impressions":
            return ImpressionsFund(self)

        raise ValueError(f"Invalid reward model: {self.reward_model}")

    @hybrid_property_subquery
    def payment_sum(cls):
        from takumi.models import Offer, Payment

        AliasedCampaign = aliased(Campaign)

        return (
            db.session.query(func.sum(Payment.amount))
            .join(Offer)
            .join(AliasedCampaign)
            .filter(Payment.is_successful)
            .filter(AliasedCampaign.id == cls.id)
        )

    @hybrid_property_subquery
    def margin(cls):
        AliasedCampaign = aliased(Campaign)
        return db.session.query(AliasedCampaign.price - AliasedCampaign.payment_sum).filter(
            AliasedCampaign.id == cls.id, AliasedCampaign.state == STATES.COMPLETED
        )

    @property
    def reserved_offers(self):
        return [offer for offer in self.offers if offer.is_reserved]

    @property
    def all_claimable(self) -> bool:
        return all(offer.is_claimable for offer in self.reserved_offers)

    @property
    def is_fulfilled(self) -> bool:
        return self.fund.is_fulfilled()

    def is_fully_reserved(self) -> bool:
        return not self.fund.is_reservable()

    @hybrid_property
    def archived(self):
        return self.state == STATES.STASHED

    @property
    def post_count(self):
        return len(self.posts)

    @property
    def posts_with_stats(self):
        return [post for post in self.posts if post.supports_stats]

    @property
    def comment_sentiment(self):
        comment_sentiment = [
            post.average_sentiment()["comments"]
            for post in self.posts_with_stats
            if post.average_sentiment()["comments"] is not None
        ]
        if len(comment_sentiment) > 0:
            return sum(comment_sentiment) / len(comment_sentiment)

    @property
    def caption_sentiment(self):
        caption_sentiments = [
            post.average_sentiment()["captions"]
            for post in self.posts_with_stats
            if post.average_sentiment()["captions"] is not None
        ]
        if len(caption_sentiments) > 0:
            return sum(caption_sentiments) / len(caption_sentiments)

    @property
    def emojis(self):
        return sum(
            [post.comment_stat_count()["emojis"] for post in self.posts_with_stats], Counter()
        ).most_common(10)

    @property
    def hashtags(self):
        return sum(
            [post.comment_stat_count()["hashtags"] for post in self.posts_with_stats], Counter()
        ).most_common(13)

    @hybrid_property
    def reach(self):
        return sum([post.reach for post in self.posts_with_stats])

    @reach.expression  # type: ignore
    def reach(cls):
        from takumi.models import Post  # noqa

        return (
            select([func.sum(Post.reach)])
            .where(and_(Post.campaign_id == cls.id, ~Post.archived))
            .label("reach")
        )

    @property
    def posts_static(self):
        return [
            post for post in self.posts if post.post_type in [PostTypes.standard, PostTypes.video]
        ]

    @property
    def posts_story(self):
        return [post for post in self.posts if post.post_type == PostTypes.story]

    @property
    def reach_total(self):
        return sum(post.reach_static for post in self.posts_static) + sum(
            post.reach_story for post in self.posts_story
        )

    @hybrid_property
    def impressions_total(self):
        """int: Total impressions calculated as the sum of story and in-feed impressions."""
        return sum(post.impressions_static for post in self.posts_static) + sum(
            post.impressions_story for post in self.posts_story
        )

    @impressions_total.expression  # type: ignore
    def impressions_total(cls):
        from takumi.models.post import Post  # noqa

        post_impressions = (
            select([func.sum(Post.impressions_static)])
            .where(Post.campaign_id == cls.id)
            .as_scalar()
        )
        story_impressions = (
            select([func.sum(Post.impressions_story)]).where(Post.campaign_id == cls.id).as_scalar()
        )
        return func.coalesce(post_impressions, 0) + func.coalesce(story_impressions, 0)

    @property
    def likes(self):
        return sum([post.likes for post in self.posts_with_stats])

    @property
    def comments(self):
        return sum([post.comments for post in self.posts_with_stats])

    @hybrid_property
    def static_engagements(self):
        """int: The sum of in-feed engagements of all gigs for all posts."""
        return sum([sum([gig.engagements_static for gig in post.gigs]) for post in self.posts])

    @static_engagements.expression  # type: ignore
    def static_engagements(cls):
        from takumi.models.gig import Gig  # noqa
        from takumi.models.post import Post  # noqa

        return (
            select([func.sum(Gig.engagements_static)])
            .where(and_(Post.campaign_id == cls.id, Gig.post_id == Post.id))
            .label("static_engagements")
        )

    @hybrid_property
    def story_engagements(self):
        """int: The sum of story engagements of all gigs for all posts."""
        return sum([sum([gig.engagements_story for gig in post.gigs]) for post in self.posts])

    @story_engagements.expression  # type: ignore
    def story_engagements(cls):
        from takumi.models.gig import Gig  # noqa
        from takumi.models.post import Post  # noqa

        return (
            select([func.sum(Gig.engagements_story)])
            .where(and_(Post.campaign_id == cls.id, Gig.post_id == Post.id))
            .label("story_engagements")
        )

    @hybrid_property
    def number_of_accepted_followers(self):
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        followers = (
            Offer.query.filter(
                Offer.state == OFFER_STATES.ACCEPTED, Offer.campaign_id == self.id
            ).with_entities(func.sum(Offer.followers_influencer))
        ).scalar()
        return followers if followers else 0

    @number_of_accepted_followers.expression  # type: ignore
    def number_of_accepted_followers(cls):
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        return (
            select([func.sum(Offer.followers_influencer)])
            .where(and_(Offer.state == OFFER_STATES.ACCEPTED, Offer.campaign_id == cls.id))
            .label("accepted_followers")
        )

    @property
    def video_views(self):
        return sum([post.video_views for post in self.posts_with_stats])

    @property
    def video_engagement(self):
        video_posts = [post for post in self.posts_with_stats if post.post_type == PostTypes.video]
        return sum([post.video_engagement for post in video_posts]) / max(len(video_posts), 1)

    @property
    def engagements(self):
        return self.likes + self.comments

    @property
    def engagement(self):
        if not self.reach:
            return 0
        return self.engagements / self.reach

    @property
    def engagements_total(self):
        return self.story_engagements + self.static_engagements

    @hybrid_property
    def engagement_rate_total(self):
        """int: Calculated total engagment rate as sum of in-feed and story engagament rates."""
        return self.engagement_rate_story + self.engagement_rate_static

    @engagement_rate_total.expression  # type: ignore
    def engagement_rate_total(cls):
        return func.coalesce(cls.engagement_rate_story, 0) + func.coalesce(
            cls.engagement_rate_static, 0
        )

    @hybrid_property
    def engagement_rate_static(self):
        try:
            return self.static_engagements / self.number_of_accepted_followers * 100
        except ZeroDivisionError:
            return 0

    @engagement_rate_static.expression  # type: ignore
    def engagement_rate_static(cls):
        return case(
            [
                (
                    cls.number_of_accepted_followers != 0,
                    cls.static_engagements / cls.number_of_accepted_followers * 100,
                )
            ],
            else_=0,
        )

    @hybrid_property
    def engagement_rate_story(self):
        try:
            return self.story_engagements / self.number_of_accepted_followers * 100
        except ZeroDivisionError:
            return 0

    @engagement_rate_story.expression  # type: ignore
    def engagement_rate_story(cls):
        return case(
            [
                (
                    cls.number_of_accepted_followers != 0,
                    cls.story_engagements / cls.number_of_accepted_followers * 100,
                )
            ],
            else_=0,
        )

    @hybrid_property
    def engagement_rate(self):
        try:
            return (self.likes + self.comments) / self.reach * 100
        except ZeroDivisionError:
            return 0

    @engagement_rate.expression  # type: ignore
    def engagement_rate(cls):
        from takumi.models import Post  # noqa

        engagements = (
            select([func.sum(Post.engagements)])
            .where(and_(Post.campaign_id == cls.id, ~Post.archived))
            .label("engagements")
        )
        engagement_rate = case(
            [(cls.reach == 0, 0)],
            else_=engagements / cls.reach * 100,
        )
        return engagement_rate

    @property
    def impressions(self):
        return sum(post.impressions for post in self.posts_with_stats)

    @property
    def s3_storage_info(self):
        return current_app.config["S3_IMAGE_BUCKET"], f"campaigns/{self.id}"

    @property
    def zip_url(self):
        bucket, directory = self.s3_storage_info
        return "https://{bucket}.s3.amazonaws.com/{directory}/images.zip".format(
            bucket=bucket, directory=directory
        )

    @property
    def cost_per_engagement(self):
        total_engaged = sum(post.likes + post.comments for post in self.posts_with_stats)
        if total_engaged > 0:
            return self.price // total_engaged
        return 0

    @property
    def projected_cost_per_engagement(self):
        if self.cost_per_engagement == 0:
            return 0

        progress = self.fund.get_progress()

        if progress["total"] == 0:
            return 0

        completed = progress["submitted"] / progress["total"]
        return self.cost_per_engagement * completed

    @property
    def submitted_gigs(self):
        return reduce(operator.concat, [offer.submitted_gigs for offer in self.offers], [])

    @hybrid_property_subquery
    def first_post_id(cls):
        from takumi.models.post import Post  # noqa

        AliasedPost = aliased(Post)

        return (
            db.session.query(AliasedPost.id)
            .filter(AliasedPost.campaign_id == cls.id)
            .order_by(AliasedPost.opened)
            .limit(1)
        )

    @hybrid_property_subquery
    def submission_deadline(cls):
        from takumi.models.post import Post  # noqa

        AliasedPost = aliased(Post)

        return (
            db.session.query(AliasedPost.submission_deadline)
            .filter(AliasedPost.campaign_id == cls.id)
            .filter(~AliasedPost.archived)
            .order_by(AliasedPost.submission_deadline)
            .limit(1)
        )

    @hybrid_property_subquery
    def deadline(cls):
        from takumi.models.post import Post  # noqa

        AliasedPost = aliased(Post)

        return (
            db.session.query(AliasedPost.deadline)
            .filter(AliasedPost.campaign_id == cls.id)
            .filter(~AliasedPost.archived)
            .order_by(AliasedPost.deadline)
            .limit(1)
        )

    @hybrid_property_subquery
    def opened(cls):
        from takumi.models.post import Post  # noqa

        AliasedPost = aliased(Post)

        return (
            db.session.query(AliasedPost.opened)
            .filter(AliasedPost.campaign_id == cls.id)
            .order_by(AliasedPost.opened)
            .limit(1)
        )

    @hybrid_method_subquery
    def is_participating(cls, influencer):
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        AliasedOffer = aliased(Offer)

        return db.session.query(func.count(AliasedOffer.id) > 0).filter(
            AliasedOffer.campaign_id == cls.id,
            AliasedOffer.state == OFFER_STATES.ACCEPTED,
            AliasedOffer.influencer_id == influencer.id,
        )

    @hybrid_property_subquery
    def earliest_live_post_date(cls) -> dt.datetime:
        from takumi.models import Gig, Post  # noqa

        AliasedCampaign = aliased(Campaign)

        return (
            db.session.query(Gig.posted)
            .join(Post)
            .join(AliasedCampaign)
            .filter(AliasedCampaign.id == cls.id)
            .order_by(Gig.posted)
            .limit(1)
        )

    @hybrid_property_subquery
    def earliest_submitted_and_claimed(cls) -> dt.datetime:
        """A special property used in finance reports

        In the reports we need a date for when we have the earliest live post
        (`earliest_live_post_date` above), or, when a campaign doesn't have a
        live post but we've still paid out (shouldn't go live, or custom
        YouTube campaigns for example) then we need to earliest submission date
        on a gig that has been claimed.
        """
        from takumi.models import Gig, Offer, Post, Submission  # noqa

        AliasedCampaign = aliased(Campaign)

        return (
            db.session.query(Submission.created)
            .join(Gig)
            .join(Offer)
            .join(Post)
            .join(AliasedCampaign)
            .filter(
                AliasedCampaign.id == cls.id,
                Offer.claimed != None,
                Gig.posted == None,
            )
            .order_by(Submission.created)
            .limit(1)
        )

    @classmethod
    def is_reach_campaign_reservable(cls, alias=None):
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        AliasedCampaign = alias if alias else cls

        min_reach_campaign_offer_count_met = (
            func.sum(case([(Offer.state == OFFER_STATES.ACCEPTED, 1)], else_=0))
            >= AliasedCampaign.units / REACH_PER_ASSET
        )

        expected_reach_met = (
            func.greatest(
                0,
                AliasedCampaign.units
                - func.sum(
                    case(
                        [(Offer.state == OFFER_STATES.ACCEPTED, Offer.followers_per_post)], else_=0
                    )
                ),
            )
            == 0
        )

        return and_(
            AliasedCampaign.state == STATES.LAUNCHED,
            AliasedCampaign.reward_model == "reach",
            or_(~min_reach_campaign_offer_count_met, ~expected_reach_met),
        )

    @classmethod
    def is_assets_campaign_reservable(cls, alias=None):
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        AliasedCampaign = alias if alias else cls

        # assets
        min_assets_campaign_offer_count_met = (
            func.sum(case([(Offer.state == OFFER_STATES.ACCEPTED, 1)], else_=0))
            >= AliasedCampaign.units
        )

        return and_(
            AliasedCampaign.state == STATES.LAUNCHED,
            AliasedCampaign.reward_model == RewardModels.assets,
            ~min_assets_campaign_offer_count_met,
        )

    @classmethod
    def is_engagement_campaign_reservable(cls, alias=None):
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        AliasedCampaign = alias if alias else cls

        min_engagement_campaign_offer_count_met = (
            func.sum(case([(Offer.state == OFFER_STATES.ACCEPTED, 1)], else_=0))
            >= AliasedCampaign.units / ENGAGEMENT_PER_ASSET
        )

        expected_engagement_met = (
            func.greatest(
                0,
                AliasedCampaign.units
                - func.sum(
                    case(
                        [(Offer.state == OFFER_STATES.ACCEPTED, Offer.engagements_per_post)],
                        else_=0,
                    )
                ),  # noqa
            )
            == 0
        )

        return and_(
            AliasedCampaign.state == STATES.LAUNCHED,
            AliasedCampaign.reward_model == RewardModels.engagement,
            or_(~min_engagement_campaign_offer_count_met, ~expected_engagement_met),
        )

    @classmethod
    def is_impressions_campaign_reservable(cls, alias=None):
        from takumi.models import Influencer
        from takumi.models.offer import STATES as OFFER_STATES
        from takumi.models.offer import Offer

        AliasedCampaign = alias if alias else cls

        # impressions
        expected_impressions_met = (
            func.greatest(
                0,
                AliasedCampaign.units
                - func.sum(
                    case(
                        [(Offer.state == OFFER_STATES.ACCEPTED, Influencer.estimated_impressions)],
                        else_=0,
                    )
                ),  # noqa
            )
            == 0
        )

        return and_(
            AliasedCampaign.state == STATES.LAUNCHED,
            AliasedCampaign.reward_model == RewardModels.impressions,
            ~expected_impressions_met,
        )

    @hybrid_property_subquery
    def is_active(cls):
        from takumi.models import Influencer
        from takumi.models.offer import Offer

        AliasedCampaign = aliased(cls, name="active_campaigns")

        return (
            db.session.query(func.count(AliasedCampaign.id) > 0)
            .outerjoin(Offer)
            .outerjoin(Influencer)
            .filter(AliasedCampaign.id == cls.id)
            .having(
                or_(
                    cls.is_reach_campaign_reservable(AliasedCampaign),
                    cls.is_assets_campaign_reservable(AliasedCampaign),
                    cls.is_engagement_campaign_reservable(AliasedCampaign),
                    cls.is_impressions_campaign_reservable(AliasedCampaign),
                )
            )
            .group_by(AliasedCampaign.id)
        )

    @property
    def requires_tiktok_account(self):
        return any([p.post_type == PostTypes.tiktok for p in self.posts])


class CampaignEvent(db.Model):
    __tablename__ = "campaign_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey("user.id"), index=True)
    creator_user = relationship("User", lazy="joined")

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="restrict"), index=True, nullable=False
    )
    campaign = relationship(
        "Campaign",
        backref=backref("events", uselist=True, order_by="CampaignEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index("ix_campaign_event_campaign_type_created", "campaign_id", "type", "created"),
    )

    def __repr__(self):
        return "<CampaignEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "CampaignEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )


class CampaignMetric(db.Model):
    __tablename__ = "campaign_metric"
    __table_args__ = (
        Index(
            "ix_campaign_metric_campaign_created",
            "campaign_id",
            "created",
        ),
    )

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    campaign_id = db.Column(
        UUIDString,
        db.ForeignKey("campaign.id", ondelete="cascade"),
        index=True,
        nullable=False,
        unique=True,
    )
    campaign = relationship(
        "Campaign",
        backref=backref("campaign_metric", uselist=False, order_by="CampaignMetric.created"),
        lazy="joined",
    )

    engagement_rate_total = db.Column(db.Float)
    engagement_rate_static = db.Column(db.Float)
    engagement_rate_story = db.Column(db.Float)
    impressions_total = db.Column(db.Integer)
    reach_total = db.Column(db.Integer)
    assets = db.Column(db.Integer)

    def __repr__(self):
        return f"<Campaign Metric: {self.id} ({self.campaign.name})>"
