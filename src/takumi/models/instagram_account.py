from typing import TYPE_CHECKING

from sqlalchemy import Float, Index, Integer, and_, case, cast, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SimpleTSVectorType, UUIDString

from takumi.constants import ENGAGEMENT_ESTIMATION_MODIFIER, MEDIAN_IMPRESSIONS_RATIO
from takumi.extensions import db
from takumi.utils import uuid4_str

from .helpers import hybrid_property_subquery
from .user import User

if TYPE_CHECKING:
    from takumi.models import FacebookPage, Influencer  # noqa


class InstagramAccount(db.Model):
    """This object represents an Instagram account in our system.  In order to
    connect it to an influencer, we need to verify that the requesting party
    indeed has access to the account.
    """

    __tablename__ = "instagram_account"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    ig_username = db.Column(db.String, nullable=False, index=True)
    ig_user_id = db.Column(db.String, nullable=False, unique=True)
    ig_media_id = db.Column(db.String, nullable=False)
    ig_is_private = db.Column(db.Boolean, nullable=False, server_default="f")
    ig_biography = db.Column(db.String)
    ig_is_business_account = db.Column(db.Boolean)
    ig_is_verified = db.Column(db.Boolean)

    supports_insights = db.Column(db.Boolean, server_default="f")

    profile_picture = db.Column(db.String)

    token = db.Column(db.String, nullable=False)
    verified = db.Column(db.Boolean, server_default="f")
    followers = db.Column(db.Integer, server_default=text("0"))
    engagement = db.Column(db.Float, server_default=text("0"))
    follows = db.Column(db.Integer, server_default=text("0"))
    media_count = db.Column(db.Integer)
    impressions_ratio = db.Column(
        db.Float
    )  # This is based on impressions from insight, to be removed
    recent_media_updated = db.Column(UtcDateTime)
    recent_media = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")

    influencer_id = db.Column(UUIDString, db.ForeignKey("influencer.id", ondelete="restrict"))
    influencer = relationship(
        "Influencer", backref=backref("instagram_account", uselist=False, lazy="joined")
    )

    facebook_page_id = db.Column(UUIDString, db.ForeignKey("facebook_page.id", ondelete="restrict"))
    facebook_page = relationship(
        "FacebookPage", backref=backref("instagram_account", uselist=False, lazy="joined")
    )

    info = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    # Whether this account has been boosted by fake numbers from instascrape
    # See BOOSTED_ACCOUNTS in instascrape_api/schemas.py
    boosted = db.Column(db.Boolean, server_default="f")

    scraped_email = db.Column(db.String)

    search_vector = db.Column(SimpleTSVectorType("ig_username"), index=True)
    search_vector_full = db.Column(
        SimpleTSVectorType(
            "ig_username", "ig_biography", weights={"ig_username": "A", "ig_biography": "D"}
        ),
        index=True,
    )

    followers_history_anomalies = db.Column(
        MutableList.as_mutable(JSONB), nullable=False, server_default="[]"
    )

    __table_args__ = (
        Index("idx_ig_username_lower", text("lower(ig_username)"), unique=True),
        Index("ix_instagram_account_influencer_id", "influencer_id"),
        Index(
            "ix_instagram_account_too_few_followers",
            "influencer_id",
            postgresql_where=(followers < 1000),
        ),
    )

    @hybrid_property_subquery
    def active(cls):
        from takumi.models import FacebookPage as FBPage

        AliasedFacebookPage = aliased(FBPage)
        AliasedInstagramAccount = aliased(cls)

        return (
            db.session.query(func.count(AliasedInstagramAccount.id) > 0)
            .join(
                AliasedFacebookPage,
                and_(
                    AliasedFacebookPage.active == True,
                    AliasedInstagramAccount.facebook_page_id == AliasedFacebookPage.id,
                ),
            )
            .filter(AliasedInstagramAccount.id == cls.id)
        )

    @hybrid_property_subquery
    def instagram_audience_insight_id(cls):
        from takumi.models import InstagramAudienceInsight

        return (
            db.session.query(InstagramAudienceInsight.id)
            .filter(InstagramAudienceInsight.instagram_account_id == cls.id)
            .order_by(InstagramAudienceInsight.created.desc())
            .limit(1)
        )

    @property
    def instagram_audience_insight(cls):
        from takumi.models import InstagramAudienceInsight

        if not cls.instagram_audience_insight_id:
            return None

        return InstagramAudienceInsight.query.get(cls.instagram_audience_insight_id)

    @classmethod
    def create_from_user_data(cls, user_data):
        return cls(
            id=uuid4_str(),
            ig_user_id=user_data["id"],
            ig_username=user_data["username"],
            scraped_email=user_data["email"],
            ig_media_id="",
            token="",
            verified=False,
        )

    @classmethod
    def by_signup_email(cls, email):
        return cls.query.filter(
            func.lower(cls.info[("email_signup", "email")].astext) == func.lower(email)
        ).first()

    @classmethod
    def by_username(cls, username):
        return cls.query.filter(func.lower(cls.ig_username) == func.lower(username.strip())).first()

    @property
    def followers_history(self):
        from takumi.serializers import InstagramAccountFollowersHistorySerializer
        from takumi.services import InstagramAccountService

        history = InstagramAccountService.get_followers_history(self.id)
        data = InstagramAccountFollowersHistorySerializer(history)

        return data.serialize()

    @property
    def estimated_engagements_per_post(self):
        """Estimate the engagement for a post of the influencer

        Estimations are made with their current follower counts and their
        current engagement of latest 12 posts. We then apply a modifier,
        defined in the constants, to underestimate slightly and rather
        overdeliver than underdeliver in campaigns that depend on this.
        """
        followers = self.followers or 0
        engagement = self.engagement or 0

        return int(followers * engagement * ENGAGEMENT_ESTIMATION_MODIFIER)

    @hybrid_property
    def estimated_impressions(self):
        if self.impressions_ratio is not None:
            ratio = self.impressions_ratio
        else:
            ratio = MEDIAN_IMPRESSIONS_RATIO

        followers = self.followers or 0

        return int(followers * ratio)

    @estimated_impressions.expression  # type: ignore
    def estimated_impressions(cls):
        ratio = case(
            [(cls.impressions_ratio != None, cls.impressions_ratio)],  # noqa: E711
            else_=MEDIAN_IMPRESSIONS_RATIO,
        )

        return cast(cls.followers * ratio, Integer)

    @hybrid_property_subquery
    def gig_engagement(cls):
        from takumi.models.gig import Gig
        from takumi.models.instagram_post import InstagramPost

        return (
            db.session.query(
                func.coalesce(
                    func.avg(
                        case(
                            [
                                (
                                    InstagramPost.followers > 0,
                                    cast(InstagramPost.likes + InstagramPost.comments, Float)
                                    / InstagramPost.followers,
                                )
                            ],
                            else_=0,
                        )
                    ),
                    0,
                )
            )
            .join(Gig)
            .filter(Gig.is_live)
            .filter(InstagramPost.instagram_account_id == cls.id)
        )

    def __repr__(self):
        return f"<InstagramAccount: {self.id} ({self.ig_username})>"


class InstagramAccountEvent(db.Model):
    """An instagram account event
    The instagram account events are a log of all mutations to the instagram account
    """

    __tablename__ = "instagram_account_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str, index=True)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey(User.id), index=True)
    creator_user = relationship(User, lazy="joined")

    instagram_account_id = db.Column(
        UUIDString,
        db.ForeignKey("instagram_account.id", ondelete="restrict"),
        index=True,
        nullable=False,
    )
    instagram_account = relationship(
        "InstagramAccount",
        backref=backref("events", uselist=True),
        order_by="InstagramAccountEvent.created",
        lazy="joined",
    )

    event = db.Column(JSONB)

    __table_args__ = (
        Index(
            "ix_instagram_account_event_instagram_account_type_created",
            "instagram_account_id",
            "type",
            "created",
        ),
    )

    def __repr__(self):
        return "<InstagramAccountEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "InstagramAccountEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
