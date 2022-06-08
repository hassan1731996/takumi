import datetime as dt
import re
from collections import defaultdict
from typing import Optional, Type

import iso8601
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy.schema import Index
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SoftEnum, UUIDString, deprecated_column
from core.common.utils import States

from takumi.constants import (
    IMGIX_TAKUMI_URL,
    LATEST_PRIVACY_TIMESTAMP,
    LATEST_TERMS_TIMESTAMP,
    USD_ALLOWED_BEFORE_1099,
)
from takumi.extensions import db
from takumi.models.market import us_market
from takumi.utils import uuid4_str

from .currency import Currency
from .helpers import hybrid_method_subquery, hybrid_property_subquery
from .influencer_campaign_mixin import InfluencerCampaignMixin
from .influencer_targeting_mixin import InfluencerTargetingMixin
from .instagram_account import InstagramAccount
from .offer import Offer
from .payment_authorization import PaymentAuthorization
from .region import Region
from .user import User


class STATES(States):
    DISABLED = "disabled"
    REVIEWED = "reviewed"
    COOLDOWN = "cooldown"
    VERIFIED = "verified"
    NEW = "new"


influencer_interests = db.Table(
    "influencer_interests",
    db.Model.metadata,
    db.Column("influencer_id", UUIDString, db.ForeignKey("influencer.id"), primary_key=True),
    db.Column("interest_id", UUIDString, db.ForeignKey("interest.id"), primary_key=True),
)


def is_timestamp_newer(dictionary, key, value, default=None):
    """Parse dictionary[key] as an ISO8601 date string and return
    whether that datetime object is newer than the date passed in `value`

    If the key is missing false is returned, unless a fallback timestamp
    was provided by the `default` parameter.
    """

    try:
        user_timestamp = iso8601.parse_date(dictionary[key], default_timezone=dt.timezone.utc)
    except KeyError:
        if default is not None:
            user_timestamp = default
        else:
            return False
    return user_timestamp > value


class MissingFacebookPage(Exception):
    pass


class FacebookPageDeactivated(Exception):
    pass


class Influencer(db.Model, InfluencerCampaignMixin, InfluencerTargetingMixin):

    __tablename__ = "influencer"
    __table_args__ = (Index("ix_influencer_signed_up_state", "is_signed_up", "state"),)

    STATES: Type[STATES] = STATES

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    user_id = db.Column(UUIDString, db.ForeignKey(User.id, ondelete="restrict"), index=True)
    user = relationship(User, backref=backref("influencer", uselist=False), lazy="joined")

    interests = db.relationship("Interest", secondary=influencer_interests, lazy="joined")

    target_region_id = db.Column("region_id", UUIDString, db.ForeignKey(Region.id), index=True)
    target_region = relationship(Region, primaryjoin=Region.id == target_region_id, lazy="joined")

    current_region_id = db.Column(UUIDString, db.ForeignKey(Region.id))
    current_region = relationship(Region, primaryjoin=Region.id == current_region_id)

    info = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    oauth_login_id = deprecated_column("oauth_login_id", db.String)
    provider_alias = deprecated_column("provider_alias", db.String)

    # states = [new -> reviewed -> disabled/verified]
    state = db.Column(
        SoftEnum(*STATES.values()), server_default=STATES.NEW, nullable=False, index=True
    )

    cooldown_ends = db.Column(UtcDateTime)
    deletion_date = db.Column(UtcDateTime)
    scheduled_jobs = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    disabled_reason = db.Column(db.String)
    is_signed_up = db.Column(db.Boolean, nullable=False, server_default="t")

    skip_self_tagging = db.Column(db.Boolean, nullable=False, server_default="f")

    audience_insight_expires = db.Column(UtcDateTime)

    _impressions_ratio = deprecated_column("impressions_ratio", db.Float)

    _social_accounts_chosen = db.Column(
        "social_accounts_chosen", db.Boolean, nullable=False, server_default="f"
    )

    vat_number = db.Column(db.String)
    vat_number_validated = db.Column(db.Boolean, server_default="f")
    is_vat_registered = db.Column(db.Boolean)

    # XXX: Temporary while we transition from Avalara to a different service
    w9_tax_years_submitted = db.Column(
        MutableList.as_mutable(JSONB), nullable=False, server_default="[]"
    )

    @property
    def profile_picture(self):
        if self.instagram_account:
            return self.instagram_account.profile_picture
        return f"{IMGIX_TAKUMI_URL}/anonymous.jpg"

    @property
    def oauth_login(self):
        return None

    @classmethod
    def by_username(cls, username) -> Optional["Influencer"]:
        instagram_account = InstagramAccount.by_username(username)
        if instagram_account is not None and instagram_account.influencer is not None:
            return instagram_account.influencer

        tiktok_user = User.query.filter(
            func.lower(User.tiktok_username) == username.strip().lower()
        ).first()
        if tiktok_user and tiktok_user.influencer is not None:
            return tiktok_user.influencer

        return None

    @classmethod
    def from_url(cls, url: str) -> Optional["Influencer"]:
        """Get influencer based on an admin url"""
        import re

        pattern = r".*/influencers/(?P<influencer_id>[0-9a-fA-F\-]{36}).*"

        if match := re.match(pattern, url):
            return cls.query.get(match.group("influencer_id"))
        return None

    @property
    def has_valid_audience_insight(self):
        if self.audience_insight_expires is None:
            return False
        return self.audience_insight_expires > dt.datetime.now(dt.timezone.utc)

    @property
    def email(self):
        if self.user is None:
            if "email" in self.info:
                return self.info["email"]
            return None
        if self.user.email_login:
            return self.user.email_login.email

    @hybrid_property_subquery
    def instagram_audience_insight_id(cls):
        return db.session.query(InstagramAccount.instagram_audience_insight_id).filter(
            InstagramAccount.influencer_id == cls.id
        )

    @hybrid_property_subquery
    def has_at_least_one_social_account(cls):
        AliasedInfluencer = aliased(cls)
        AliasedUser = aliased(User)

        instagram_account_linked = and_(InstagramAccount.id != None, InstagramAccount.active)

        youtube_account_linked = AliasedUser.youtube_channel_url != None
        tiktok_account_linked = AliasedUser.tiktok_username != None

        return (
            db.session.query(
                or_(instagram_account_linked, tiktok_account_linked, youtube_account_linked)
            )
            .select_from(AliasedInfluencer)
            .join(AliasedUser, AliasedUser.id == AliasedInfluencer.user_id)
            .outerjoin(InstagramAccount)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_property_subquery
    def social_accounts_chosen(cls):
        AliasedInfluencer = aliased(cls)

        return db.session.query(
            and_(
                AliasedInfluencer._social_accounts_chosen == True,
                AliasedInfluencer.has_at_least_one_social_account,
            )
        ).filter(AliasedInfluencer.id == cls.id)

    @property
    def instagram_audience_insight(cls):
        from takumi.models import InstagramAudienceInsight

        if not cls.instagram_audience_insight_id:
            return None

        return InstagramAudienceInsight.query.get(cls.instagram_audience_insight_id)

    @hybrid_property_subquery
    def audience_insight_id(cls):
        from takumi.models import AudienceInsight

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(AudienceInsight.id)
            .join(AliasedInfluencer)
            .filter(AliasedInfluencer.id == cls.id)
            .order_by(AudienceInsight.created.desc())
            .limit(1)
        )

    @property
    def audience_insight(cls):
        from takumi.models import AudienceInsight

        if not cls.audience_insight_id:
            return None

        return AudienceInsight.query.get(cls.audience_insight_id)

    @property
    def username(self):
        if self.instagram_account:
            return self.instagram_account.ig_username
        if self.tiktok_username:
            return self.tiktok_username
        if self.user and self.user.full_name:
            return re.sub(
                r"[^\x00-\x7f]", r"", self.user.full_name.strip().replace(" ", "_").lower()
            )
        return ""

    @hybrid_property
    def followers(self):
        if self.instagram_account:
            return self.instagram_account.followers
        return None

    @followers.expression  # type: ignore
    def followers(cls):
        return (
            select([InstagramAccount.followers])
            .where(InstagramAccount.influencer_id == cls.id)
            .as_scalar()
        )

    @property
    def disabled(self):
        return self.state == "disabled"

    @property
    def total_rewards(self):
        """Sum up total rewards in all currencies the user has received. We
        will want to either return a list of reward balances for each currency
        or do the conversion and present total earnings to the influencer in
        their preferred currency.
        """
        from takumi.services import InfluencerService

        total_rewards = InfluencerService.get_total_rewards(self.id)
        if len(total_rewards) > 0:
            currency = total_rewards[0].currency
            # At this point we can `dict.pop` prefered currency and do currency
            # conversion to show estimated total earnings in prefered currency
            amount = total_rewards[0].reward
        else:
            # No balances, try to set currency to user region currency
            if self.target_region and self.target_region.market is not None:
                currency = self.target_region.market.currency
            else:
                currency = "USD"  # Default to USD
            amount = 0

        return Currency(amount=amount, currency=currency)

    @property
    def total_rewards_breakdown(self):
        from takumi.models import Payment

        if self.target_region and self.target_region.market:
            currency = self.target_region.market.currency
        else:
            currency = "GBP"

        result = (
            db.session.query(
                func.sum(Payment.amount).label("total"),
                func.sum(Payment.amount / (1 + Offer.vat_percentage)).label("net"),
            )
            .join(Offer)
            .filter(
                Payment.currency == currency, Offer.influencer_id == self.id, Payment.is_successful
            )
        ).one()

        return {
            "net_value": result.net or 0,
            "vat_value": (result.total or 0) - (result.net or 0),
            "total_value": result.total or 0,
        }

    @hybrid_property_subquery
    def gig_engagement(cls):
        return db.session.query(InstagramAccount.gig_engagement).filter(
            InstagramAccount.influencer_id == cls.id
        )

    @property
    def latest_audit(self):
        if not self.audits:
            return None
        return self.audits[0]

    @property
    def engagement(self):
        if not self.instagram_account:
            return 0
        if self.instagram_account.engagement is None:
            return 0
        return self.instagram_account.engagement

    def has_w9_info(self, year: int = None) -> bool:
        # XXX: Temporary manual handling of W9 forms while we transition from Avalara
        if not year:
            year = dt.date.today().year

        return year in self.w9_tax_years_submitted

    def income(self, start_date, end_date):
        offers = (
            Offer.query.filter(Offer.influencer_id == self.id)
            .filter(Offer.payable != None)  # noqa: E711
            .filter(Offer.is_claimable)
            .filter(func.date(Offer.payable) >= start_date)
            .filter(func.date(Offer.payable) <= end_date)
        )
        income = defaultdict(int)
        for offer in offers:
            income[offer.campaign.market.currency] += offer.reward

        return [(currency, amount) for (currency, amount) in income.items()]

    def get_payment_authorizations_for_slugs(self, slugs):
        return PaymentAuthorization.query.filter(
            PaymentAuthorization.influencer_id == self.id, PaymentAuthorization.slug.in_(slugs)
        ).all()

    @property
    def remaining_usd_before_1099(self):
        this_year = dt.date.today().year
        from takumi.services import InfluencerService

        total_usd_this_year = InfluencerService.get_market_income(self.id, us_market, this_year)

        return max(0, USD_ALLOWED_BEFORE_1099 - total_usd_this_year)

    @property
    def tiktok_username(self):
        if self.user:
            return self.user.tiktok_username
        return None

    @property
    def youtube_channel_url(self):
        return self.user.youtube_channel_url

    @property
    def has_tiktok_account(self):
        return bool(self.tiktok_username)

    @property  # type: ignore
    def has_interests(cls):
        return db.session.execute(
            f"""
            SELECT count(1) > 0
            FROM public.influencer_interests interests
            WHERE interests.influencer_id = '{cls.id}';
            """
        ).first()[0]

    @property
    def has_youtube_channel(self):
        return bool(self.youtube_channel_url)

    @classmethod
    def get_legacy_by_email(cls, email):
        # info['email'] was used to persist contact info when OAuthLogin users
        # issued payments, so we can use this for a lookup
        return (cls.query.filter(func.lower(cls.info["email"].astext) == func.lower(email))).first()

    @hybrid_property_subquery
    def device_id(cls):
        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(User.device_id)
            .join(AliasedInfluencer)
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_property_subquery
    def is_verified(self):
        return db.session.query(func.count(InstagramAccount.id) > 0).filter(
            InstagramAccount.influencer_id == self.id, InstagramAccount.ig_is_verified.is_(True)
        )

    @hybrid_method_subquery
    def is_in_region(cls, region):
        from takumi.models import Region

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(AliasedInfluencer.id) > 0)
            .join(Region, Region.id == AliasedInfluencer.target_region_id)
            .filter(Region.is_under_or_equals(region))
            .filter(AliasedInfluencer.id == cls.id)
        )

    @hybrid_property_subquery
    def impressions_ratio(cls):
        from takumi.models import InstagramAccount

        return db.session.query(InstagramAccount.impressions_ratio).filter(
            InstagramAccount.influencer_id == cls.id
        )

    @property
    def device(self):
        return self.user.device

    @property
    def has_device(self):
        return self.device is not None

    def force_logout(self, value=None):
        if value is None:
            if self.info:
                return self.info.get("force_logout", False) is True
            return False
        else:
            self.info["force_logout"] = bool(value)

    def has_address(self):
        return self.address is not None

    @property
    def estimated_engagements_per_post(self):
        if self.instagram_account:
            return self.instagram_account.estimated_engagements_per_post
        return 0

    @hybrid_property_subquery
    def estimated_impressions(cls):
        from takumi.models import InstagramAccount

        return db.session.query(InstagramAccount.estimated_impressions).filter(
            InstagramAccount.influencer_id == cls.id
        )

    @property
    def active_reservation_count(self):
        return len([o for o in self.offers if o.is_reserved and not o.is_paid])

    @property
    def has_accepted_latest_terms(self):
        return is_timestamp_newer(self.info, "terms_accepted", LATEST_TERMS_TIMESTAMP)

    @property
    def has_accepted_latest_privacy(self):
        return is_timestamp_newer(self.info, "privacy_accepted", LATEST_PRIVACY_TIMESTAMP)

    @property
    def instagram_api(self):
        facebook_page = self.instagram_account and self.instagram_account.facebook_page
        if not facebook_page:
            raise MissingFacebookPage("Facebook Page not Linked")
        if not facebook_page.active:
            raise FacebookPageDeactivated("Facebook Page is deactivated")
        if facebook_page.page_access_token == "dummy_access_token":
            raise FacebookPageDeactivated("Facebook Page is deactivated")
        return facebook_page.instagram_api

    @hybrid_property_subquery
    def has_facebook_page(cls):
        from takumi.models import FacebookPage

        AliasedInfluencer = aliased(cls)

        return (
            db.session.query(func.count(FacebookPage.id) > 0)
            .join(InstagramAccount)
            .join(AliasedInfluencer)
            .filter(FacebookPage.active)
            .filter(AliasedInfluencer.id == cls.id)
        )

    def __repr__(self):
        return f"<Influencer: {self.id} {self.username}>"


class InfluencerEvent(db.Model):
    """An influencer event

    The influencer events are a log of all mutations to the influencer
    """

    __tablename__ = "influencer_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey(User.id), index=True)
    creator_user = relationship(User, lazy="joined")

    influencer_id = db.Column(
        UUIDString, db.ForeignKey(Influencer.id, ondelete="restrict"), index=True, nullable=False
    )
    influencer = relationship(
        Influencer,
        backref=backref("events", uselist=True, order_by="InfluencerEvent.created"),
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index("ix_influencer_event_influencer_type_created", "influencer_id", "type", "created"),
    )

    def __repr__(self):
        return "<InfluencerEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "InfluencerEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
