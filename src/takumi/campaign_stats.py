import datetime as dt

from sqlalchemy import distinct, func

from takumi.extensions import db
from takumi.models import (
    Campaign,
    CampaignEvent,
    Currency,
    Gig,
    Influencer,
    InstagramPost,
    InstagramPostInsight,
    InstagramStory,
    InstagramStoryFrameInsight,
    Interest,
    Market,
    Offer,
    Payment,
    Post,
    Region,
    StoryFrame,
    Targeting,
)
from takumi.models.campaign import STATES as CAMPAIGN_STATES

POUNDS_TO_A_DOLLAR = 0.8
POUNDS_TO_A_EURO = 0.9


def _quarter(year, quarternum):
    def gen_date(day, month, year=year):
        return dt.datetime(tzinfo=dt.timezone.utc, year=year, day=day, month=month)

    if quarternum == 1:
        return (gen_date(1, 1), gen_date(1, 4))
    elif quarternum == 2:
        return (gen_date(1, 4), gen_date(1, 7))
    elif quarternum == 3:
        return (gen_date(1, 7), gen_date(1, 10))
    elif quarternum == 4:
        return (gen_date(1, 10), gen_date(1, 1, year + 1))
    raise Exception(f"INVALID QUARTERNUM {quarternum}")


def _get_years():
    first_year = (
        db.session.query(func.min(Campaign.started))
        .filter(Campaign.state == CAMPAIGN_STATES.COMPLETED)
        .scalar()
    ).year
    current_year = dt.datetime.now().year
    return [year for year in range(first_year, current_year + 1)]


class CampaignStats:
    def __init__(self, region=None):
        self.region = region
        self.regions = [region] if self.region else Region.get_supported_regions().all()

    @classmethod
    def budget_sum_by_currency(cls, filter_function=lambda x: x):
        return [
            Currency(currency=Market.get_market(market_slug).currency, amount=total)
            for (market_slug, total) in filter_function(
                db.session.query(Campaign.market_slug, func.sum(Campaign.price))
                .join(Post, Post.id == Campaign.first_post_id)
                .filter(~Campaign.state.in_(("draft", "stashed")))
                .filter(Post.opened != None)
                .group_by(Campaign.market_slug)
            ).all()
        ]

    def _budget_by_time_period_query(self, region):
        def inner(self, begin=None, end=None):
            return (
                db.session.query(func.sum(Campaign.price))
                .join(Post, Post.id == Campaign.first_post_id)
                .join(Targeting)
                .filter(~Campaign.state.in_(("draft", "stashed")))
                .filter(Targeting.is_under_region(region))
                .filter(Post.opened != None)
                .filter((Campaign.started >= begin) if begin else True)
                .filter((Campaign.started < end) if end else True)
            )

        return inner

    def _budget_by_month_query(self, region):
        month = func.date_trunc("month", Post.opened)
        return (
            db.session.query(month, func.sum(Campaign.price))
            .join(Campaign, Post.id == Campaign.first_post_id)
            .join(Targeting)
            .filter(~Campaign.state.in_(("draft", "stashed")))
            .filter(Targeting.is_under_region(region))
            .filter(Post.opened != None)
            .group_by(month)
            .order_by(month)
        )

    def _margin_by_month_query(self, region):
        month = func.date_trunc("month", Post.opened)
        return (
            db.session.query(month, func.sum(Campaign.margin))
            .join(Campaign, Post.id == Campaign.first_post_id)
            .join(Targeting)
            .filter(Targeting.is_under_region(region))
            .filter(Post.opened != None)
            .group_by(month)
            .order_by(month)
        )

    def _payments_by_month_query(self, currency):
        month = func.date_trunc("month", Payment.created)
        return (
            db.session.query(month, func.sum(Payment.amount))
            .filter(Payment.currency == currency)
            .filter(Payment.is_successful)
            .group_by(month)
            .order_by(month)
        )

    def _campaigns_by_month_query(self, region):
        month = func.date_trunc("month", Post.opened)
        return (
            db.session.query(month, func.count(distinct(Campaign.id)))
            .join(Campaign, Post.id == Campaign.first_post_id)
            .join(Targeting)
            .filter(Targeting.is_under_region(region))
            .filter(Post.opened != None)
            .filter(~Campaign.state.in_(("draft", "stashed")))
            .group_by(month)
            .order_by(month)
        )

    def _gigs_by_month_query(self, region):
        month = func.date_trunc("month", Gig.created)
        return (
            db.session.query(month, func.count(Gig.id))
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Targeting.is_under_region(region))
            .group_by(month)
            .order_by(month)
        )

    def _new_participants_by_month_query(self, region):
        month = func.date_trunc("month", Offer.created)
        return (
            db.session.query(month, func.count(distinct(Offer.influencer_id)))
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.is_influencers_first_accepted_offer)
            .filter(Targeting.is_under_region(region))
            .group_by(month)
            .order_by(month)
        )

    def _unique_participants_by_month_query(self, region):
        month = func.date_trunc("month", Offer.created)
        return (
            db.session.query(month, func.count(distinct(Offer.influencer_id)))
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.state == "accepted")
            .filter(Targeting.is_under_region(region))
            .group_by(month)
            .order_by(month)
        )

    def _instagram_post_impressions_by_month_query(self, region):
        month = func.date_trunc("month", InstagramPostInsight.created)
        return (
            db.session.query(month, func.sum(distinct(InstagramPostInsight.impressions)))
            .join(InstagramPost, InstagramPost.instagram_post_insight_id == InstagramPostInsight.id)
            .join(Gig)
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.is_claimable)
            .filter(Targeting.is_under_region(region))
            .group_by(month)
            .order_by(month)
        )

    def _instagram_story_impressions_by_month_query(self, region):
        month = func.date_trunc("month", InstagramStoryFrameInsight.created)
        return (
            db.session.query(month, func.sum(distinct(InstagramStoryFrameInsight.impressions)))
            .join(
                StoryFrame,
                StoryFrame.instagram_story_frame_insight_id == InstagramStoryFrameInsight.id,
            )
            .join(InstagramStory)
            .join(Gig)
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.is_claimable)
            .filter(Targeting.is_under_region(region))
            .group_by(month)
            .order_by(month)
        )

    def _campaign_reward_model_distribution_query(self, begin=None, end=None):
        return (
            db.session.query(Campaign.reward_model, func.count(distinct(Campaign.id)))
            .join(Targeting)
            .filter(~Campaign.state.in_(("draft", "stashed")))
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .group_by(Campaign.reward_model)
            .filter((Campaign.started >= begin) if begin else True)
            .filter((Campaign.started < end) if end else True)
        )

    def _campaign_interests_query(self):
        interest_id_query = (
            db.session.query(func.unnest(Targeting.interest_ids).label("interest_id"))
            .join(Campaign)
            .filter(~Campaign.state.in_(("draft", "stashed")))
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .distinct(Targeting.id)
            .subquery()
        )

        return (
            db.session.query(Interest.name, func.count(Interest.id))
            .join(interest_id_query, interest_id_query.c.interest_id == Interest.id)
            .group_by(Interest.id)
            .order_by(func.count(Interest.id))
        )

    def _participants_by_time_period_query(self, begin=None, end=None):
        return (
            db.session.query(func.count(distinct(Influencer.id)))
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.is_claimable)
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .filter((Campaign.started >= begin) if begin else True)
            .filter((Campaign.started < end) if end else True)
        )

    def _campaigns_by_time_period_query(self, begin=None, end=None):
        return (
            db.session.query(func.count(distinct(Campaign.id)))
            .join(Targeting)
            .filter(Campaign.state.in_((CAMPAIGN_STATES.COMPLETED, CAMPAIGN_STATES.LAUNCHED)))
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .filter((Campaign.started >= begin) if begin else True)
            .filter((Campaign.started < end) if end else True)
        )

    def _gigs_by_time_period_query(self, begin=None, end=None):
        return (
            db.session.query(func.count(distinct(Gig.id)))
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Offer.is_claimable)
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .filter((Campaign.started >= begin) if begin else True)
            .filter((Campaign.started < end) if end else True)
        )

    def _extract_quarters(self, query_func):
        queries = []
        labels = []
        for year in _get_years():
            for i in range(1, 5):
                label = f"{year}_Q{i}"
                queries.append(query_func(*_quarter(year, i)).subquery().as_scalar().label(label))
                labels.append(label)
        result = db.session.query(*[q for q in queries]).first()
        return {label: getattr(result, label) for label in labels}

    @property
    def budget_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): Currency(
                    amount=r[1], currency=region.market.currency
                )
                for r in self._budget_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def payments_by_month(self):
        currencies = list({region.market.currency for region in self.regions})
        return {
            currency: {
                dt.date.strftime(r[0], "%Y-%m"): Currency(amount=r[1], currency=currency)
                for r in self._payments_by_month_query(currency)
            }
            for currency in currencies
        }

    @property
    def margin_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): Currency(
                    amount=int(r[1]), currency=region.market.currency
                )
                for r in self._margin_by_month_query(region)
                if r[1] is not None and int(r[1]) > 0
            }
            for region in self.regions
        }

    @property
    def campaigns_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1]
                for r in self._campaigns_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def gigs_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1] for r in self._gigs_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def instagram_post_impressions_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1]
                for r in self._instagram_post_impressions_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def instagram_story_impressions_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1]
                for r in self._instagram_story_impressions_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def unique_participants_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1]
                for r in self._unique_participants_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def new_participants_by_month(self):
        return {
            region.name: {
                dt.date.strftime(r[0], "%Y-%m"): r[1]
                for r in self._new_participants_by_month_query(region)
            }
            for region in self.regions
        }

    @property
    def campaign_reward_model_distribution(self):
        result = self._campaign_reward_model_distribution_query().all()
        return {r[0]: r[1] for r in result}

    @property
    def campaign_interests(self):
        result = self._campaign_interests_query().all()
        return {interest_name: count for (interest_name, count) in result}

    @property
    def participants_by_quarter(self):
        return self._extract_quarters(self._participants_by_time_period_query)

    @property
    def campaigns_by_quarter(self):
        return self._extract_quarters(self._campaigns_by_time_period_query)

    def budget_by_quarter(self, year, quarterno):
        result = {}
        begin, end = _quarter(year, quarterno)
        for region in self.regions:
            region_result = self._budget_by_time_period_query(region)(begin, end).first()[0]
            if not region_result:
                continue
            result[region.name] = Currency(
                currency=Market.get_market(region.market_slug).currency, amount=region_result
            )
        return result

    def campaigns_reward_model_distribution_by_quarter(self, year, quarter):
        begin, end = _quarter(year, quarter)
        result = self._campaign_reward_model_distribution_query(begin, end).all()
        return {r[0]: r[1] for r in result}

    @property
    def gigs_by_quarter(self):
        return self._extract_quarters(self._gigs_by_time_period_query)

    @property
    def running_campaign_count(self):
        return (
            Campaign.query.filter(Campaign.is_active)
            .join(Targeting)
            .filter(Targeting.is_under_region(self.region) if self.region else True)
        ).count()

    @property
    def campaign_count(self):
        return (
            Campaign.query.join(Targeting)
            .filter(~Campaign.state.in_(("draft", "stashed")))
            .filter(Targeting.is_under_region(self.region) if self.region else True)
        ).count()

    @property
    def gig_count(self):
        return (
            Gig.query.join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Targeting.is_under_region(self.region) if self.region else True)
        ).count()

    @property
    def submitted_gig_count(self):
        return (
            db.session.query(Gig)
            .join(Offer)
            .join(Campaign)
            .join(Targeting)
            .filter(Campaign.is_active)
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .count()
        )

    @property
    def active_gig_count(self):
        return (
            db.session.query(Offer)
            .join(Campaign)
            .join(Targeting)
            .join(Post)
            .filter(Campaign.is_active, Offer.state == "accepted")
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .count()
        )

    def campaigns_launched_in_time_period_with_deadline_in_time_period(
        self, min_launch_date, max_launch_date, min_deadline, max_deadline
    ):
        return (
            db.session.query(Campaign.id, Campaign.name, CampaignEvent.created, Post.deadline)
            .join(CampaignEvent)
            .join(Post)
            .join(Targeting)
            .filter(Campaign.state == CAMPAIGN_STATES.LAUNCHED)
            .filter(CampaignEvent.type == "launch")
            .filter(Targeting.is_under_region(self.region) if self.region else True)
            .filter(CampaignEvent.created >= min_launch_date)
            .filter(CampaignEvent.created < max_launch_date)
            .filter(Post.deadline >= min_deadline)
            .filter(Post.deadline < max_deadline)
            .distinct(Campaign.id)
        )
