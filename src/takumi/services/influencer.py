import datetime as dt
import time
from contextlib import contextmanager
from statistics import median

from flask import current_app
from sentry_sdk import capture_exception
from sqlalchemy import case, extract, func, literal

from core.facebook.instagram import InstagramError
from core.vat import HMRCException, InvalidVAT, VatClient, VatHMRC, VatLayer, VatLayerException

import takumi.tasks.influencer as influencer_tasks
from takumi.constants import (
    EMAIL_CHANGE_SIGNER,
    MAX_IMPRESSIONS_RATIO,
    MAX_INSIGHT_IMPRESSIONS_AGE,
    MIN_IMPRESSIONS_RATIO,
    TARGETING_FIELDS_MAX_UPDATE_AGE,
)
from takumi.emails import ChangeEmailNotificationEmail, VerificationEmail
from takumi.events.influencer import BirthdayException, InfluencerLog
from takumi.extensions import db, instascrape, redis
from takumi.facebook_account import unlink_on_permission_error
from takumi.i18n import locale_context
from takumi.models import (
    Campaign,
    EmailLogin,
    Gig,
    GigEvent,
    Influencer,
    InfluencerEvent,
    InfluencerInformation,
    InstagramAudienceInsight,
    Offer,
    OfferEvent,
    Payment,
    PostInsight,
    TargetingUpdate,
)
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.influencer import FacebookPageDeactivated
from takumi.models.influencer_information import EyeColour, HairColour, HairType, Tag
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.notifications import NotificationClient
from takumi.notifications.exceptions import NotificationException
from takumi.roles.needs import send_recruitment_dm
from takumi.search.influencer import InfluencerIndex, InfluencerSearch
from takumi.services import Service
from takumi.services.exceptions import (
    DeletingInfluencerSoonerThanScheduledException,
    FetchingAudienceInsightsFailed,
    ForbiddenException,
    InfluencerAlreadyExistsException,
    InfluencerAlreadyScheduledForDeletionException,
    InfluencerCannotBeDeletedException,
    InfluencerEyeColourNotFound,
    InfluencerHairColorNotFound,
    InfluencerHairTypeNotFound,
    InfluencerNotFound,
    InfluencerNotScheduledForDeletionException,
    SendInfluencerMessageError,
    ServiceException,
)
from takumi.signers import url_signer
from takumi.utils import uuid4_str

from .instagram_account import InstagramAccountService
from .user import UserService


@contextmanager
def limited_targeting_update(user, field):
    """Limit frequency of updating user details which affect targeting. This
    is done to avoid people to update their age/gender to reserve posts not
    intended for them.
    """

    last_updated = (
        db.session.query(func.max(TargetingUpdate.created))
        .filter(TargetingUpdate.user == user, TargetingUpdate.field_name == field)
        .scalar()
    )
    if last_updated is not None and last_updated > (
        dt.datetime.now(dt.timezone.utc) - TARGETING_FIELDS_MAX_UPDATE_AGE
    ):
        raise ServiceException(
            "Cannot update {} more than once every {} days".format(
                field, TARGETING_FIELDS_MAX_UPDATE_AGE.days
            ),
            422,
        )
    obj = TargetingUpdate(user=user, field_name=field)
    yield obj
    db.session.add(obj)


class InfluencerService(Service):
    """
    Represents the business model for Influencer. This is the bridge between
    the database and the application.
    """

    SUBJECT = Influencer
    LOG = InfluencerLog

    @property
    def influencer(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Influencer.query.get(id)

    @staticmethod
    def get_by_username(username):
        influencer = Influencer.by_username(username)

        # XXX: Hacky, refactor!
        if influencer is None:
            influencer = Influencer.from_url(username)
        return influencer

    def signup_influencer(self, full_name, gender, birthday, email):
        from .user import UserService

        if not self.influencer.is_signed_up:
            with UserService(self.influencer.user) as service:
                service.update_full_name(full_name)

            self.update_gender(gender)

            try:
                self.update_birthday(birthday)
            except BirthdayException as e:
                raise ServiceException(e.args[0])

            if email:
                self.change_email(email)

            self.influencer.is_signed_up = True
            db.session.commit()

    @staticmethod
    def get_influencer_events(id, supported_events=None, date_from=None, date_to=None):
        query = db.session.query(
            InfluencerEvent.created.label("created"),
            InfluencerEvent.type.label("type"),
            InfluencerEvent.id.label("key"),
        ).filter(InfluencerEvent.influencer_id == id)

        if supported_events is not None:
            query = query.filter(InfluencerEvent.type.in_(supported_events))
        if date_from is not None:
            query = query.filter(InfluencerEvent.created >= date_from)
        if date_to is not None:
            query = query.filter(InfluencerEvent.created <= date_to)

        return query

    @staticmethod
    def get_offer_events(id, supported_events=None, date_from=None, date_to=None):
        query = (
            db.session.query(
                OfferEvent.created.label("created"),
                literal("offer").label("type"),
                OfferEvent.id.label("key"),
            )
            .join(Offer)
            .filter(Offer.influencer_id == id)
        )
        if supported_events is not None:
            query = query.filter(OfferEvent.type.in_(supported_events))
        if date_from is not None:
            query = query.filter(OfferEvent.created >= date_from)
        if date_to is not None:
            query = query.filter(OfferEvent.created <= date_to)

        return query

    @staticmethod
    def get_gig_events(id, supported_events=None, date_from=None, date_to=None):
        query = (
            db.session.query(
                GigEvent.created.label("created"),
                literal("gig").label("type"),
                GigEvent.id.label("key"),
            )
            .join(Gig)
            .join(Offer)
            .filter(Offer.influencer_id == id)
        )
        if supported_events is not None:
            query = query.filter(GigEvent.type.in_(supported_events))
        if date_from is not None:
            query = query.filter(GigEvent.created >= date_from)
        if date_to is not None:
            query = query.filter(GigEvent.created <= date_to)

        return query

    @staticmethod
    def get_market_income(id, market, year=None):
        payment_subquery = (
            Payment.query.with_entities(Payment.offer_id, Payment.amount)
            .order_by(
                Payment.offer_id,
                case(
                    value=Payment.state,
                    whens={
                        PAYMENT_STATES.PAID: 0,
                        PAYMENT_STATES.REQUESTED: 1,
                        PAYMENT_STATES.EXPIRED: 2,
                        PAYMENT_STATES.FAILED: 3,
                    },
                ),
            )
            .distinct(Payment.offer_id)
            .subquery()
        )

        query = (
            Offer.query.join(Campaign)
            .outerjoin(payment_subquery, Offer.id == payment_subquery.c.offer_id)
            .filter(
                Campaign.market_slug == market.slug, Offer.influencer_id == id, Offer.is_claimable
            )
            .with_entities(
                func.sum(
                    case(
                        [(Offer.payments == None, Offer.reward)],  # noqa: E711
                        else_=payment_subquery.c.amount,
                    )
                )
            )
        )

        if year:
            query = query.filter(extract("year", Offer.payable) == year)

        return query.scalar() or 0

    @staticmethod
    def get_total_rewards(id):
        return (
            Payment.query.join(Offer)
            .filter(Offer.influencer_id == id, Payment.is_successful)
            .with_entities(func.sum(Payment.amount).label("reward"), Payment.currency)
            .group_by(Payment.currency)
            .all()
        )

    # POST
    @staticmethod
    def create_influencer(instagram_account, user, is_signed_up):
        influencer = Influencer(id=uuid4_str(), user=user, is_signed_up=is_signed_up)
        instagram_account.influencer = influencer
        db.session.add(influencer)
        db.session.commit()

        return influencer

    @staticmethod
    def create_prewarmed_influencer(username):
        if InfluencerService.get_by_username(username):
            raise InfluencerAlreadyExistsException(
                f'Influencer with username "{username}" already exists'
            )

        profile = instascrape.get_user(username)
        ig_account = InstagramAccountService.get_by_username(username)
        if ig_account is not None:
            ig_account.ig_username = profile["username"]
            ig_account.ig_is_private = profile["is_private"]
            ig_account.ig_biography = profile["biography"]
            ig_account.followers = profile["followers"]
            ig_account.follows = profile["following"]
            ig_account.media_count = profile["media_count"]
            ig_account.profile_picture = profile["profile_picture"]
        else:
            ig_account = InstagramAccountService.create_instagram_account(profile)

        user = UserService.create_user_with_no_email(
            profile_picture=None,
            full_name=profile["full_name"],
            role_name="influencer",
        )
        influencer = InfluencerService.create_influencer(
            instagram_account=ig_account, user=user, is_signed_up=False
        )

        return influencer

    def set_influencer_information(  # noqa
        self,
        tag_ids=None,
        account_type=None,
        children=None,
        languages=None,
        hair_colour_id=None,
        hair_type_id=None,
        eye_colour_id=None,
        glasses=None,
    ):
        if not self.influencer.information:
            self.influencer.information = InfluencerInformation()
        information = self.influencer.information

        if tag_ids is not None:
            tags = Tag.get_from_ids(tag_ids)
            information.tag_ids = [t.id for t in tags]
        if children is not None:
            for existing_child in self.influencer.information.children:
                if existing_child not in children:
                    db.session.delete(existing_child)
            information.children = children
        if languages is not None:
            information.languages = languages
        if hair_colour_id is not None:
            hair_colour = HairColour.get(hair_colour_id)
            if hair_colour is None:
                raise InfluencerHairColorNotFound("Hair colour not found!")
            information.hair_colour_id = hair_colour.id
        if hair_type_id is not None:
            hair_type = HairType.get(hair_type_id)
            if hair_type is None:
                raise InfluencerHairTypeNotFound("Hair type not found!")
            information.hair_type_id = hair_type.id
        if eye_colour_id is not None:
            eye_colour = EyeColour.get(eye_colour_id)
            if eye_colour is None:
                raise InfluencerEyeColourNotFound("Eye colour not found!")
            information.eye_colour_id = eye_colour.id
        if glasses is not None:
            information.glasses = glasses
        if account_type is not None:
            information.account_type = account_type
            if account_type in ["business", "creator"]:
                self.influencer.instagram_account.supports_insights = True
            else:
                self.influencer.instagram_account.supports_insights = False

    def schedule_deletion(self):
        if self.influencer.deletion_date is not None:
            raise InfluencerAlreadyScheduledForDeletionException(
                "Influencer already scheduled for deletion"
            )

        # Deletion occurs 24 hours after it is requested
        twenty_four_hours_from_now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
        self.log.add_event("set_deletion_date", {"deletion_date": twenty_four_hours_from_now})
        influencer_tasks.schedule_deletion(self.influencer)

    def cancel_scheduled_deletion(self):
        if self.influencer.deletion_date is None:
            raise InfluencerNotScheduledForDeletionException(
                "Influencer has not been scheduled for deletion"
            )

        self.log.add_event("set_deletion_date", {"deletion_date": None})

        # Clear the scheduled tiger task
        influencer_tasks.clear_deletion(self.influencer)

    def delete(self, force=False):
        influencer = self.influencer

        if not force:
            if influencer.deletion_date is None:
                raise InfluencerCannotBeDeletedException("Deletion date missing")

            if influencer.deletion_date > dt.datetime.now(dt.timezone.utc):
                raise DeletingInfluencerSoonerThanScheduledException("Too soon")

        es_docs = InfluencerSearch().search(influencer.id)

        timestamp = int(time.time())
        removed = f"removed-{timestamp}"

        self.log.add_event("delete", {"removed": removed})
        if influencer.address:
            db.session.delete(influencer.address)
        influencer.force_logout(True)

        es_doc = es_docs.first()
        if es_doc:
            InfluencerIndex.delete(influencer.id)

    def restore(self):
        self.log.add_event("restore")
        self.influencer.force_logout(False)

    def change_email(self, email):
        email_login = EmailLogin.get(email)
        old_email = self.influencer.email

        if email_login is not None:
            raise ServiceException("Email already in use")

        token = url_signer.dumps(
            dict(email=email, influencer_id=self.influencer.id), salt=EMAIL_CHANGE_SIGNER
        )
        self.log.add_event("change_email")

        with locale_context(self.influencer.user.request_locale):
            VerificationEmail(
                {"old_email": old_email or "", "new_email": email, "token": token}
            ).send(email)
            if old_email:
                ChangeEmailNotificationEmail({"old_email": old_email, "new_email": email}).send(
                    old_email
                )

    # PUT
    def update_email(self, email):
        email_login = EmailLogin.get(email)

        if email_login is not None:
            if email_login.user == self.influencer.user:
                return
            raise ServiceException("Email already in use")

        self.log.add_event("set_email", {"email": email})

    def update_interests(self, interests):
        self.log.add_event("interests", {"interests": interests})

    def update_vat_number(self, vat_number: str, is_vat_registered: bool) -> None:
        if not is_vat_registered:
            self.log.add_event("vat_number", {"is_vat_registered": False, "vat_number": None})
        else:
            number = vat_number.strip().upper()
            if self.influencer.vat_number == number:
                # Nothing to update
                return

            vat_client: VatClient
            if vat_number.upper().startswith("GB"):
                conn = redis.get_connection()
                vat_client = VatHMRC(
                    client_id=current_app.config["HMRC_CLIENT_ID"],
                    secret=current_app.config["HMRC_SECRET"],
                    prod=current_app.config["RELEASE_STAGE"] == "production",
                    redis_cache=conn,
                )
            else:
                vat_client = VatLayer(current_app.config["VAT_LAYER_API_KEY"])

            try:
                vat_client.validate(number)
            except InvalidVAT as e:
                raise ServiceException(e)
            except (HMRCException, VatLayerException):
                capture_exception()
                raise ServiceException("Unable to validate VAT")

            self.log.add_event("vat_number", {"is_vat_registered": True, "vat_number": number})

    def update_gender(self, gender, throttle_updates=False):
        if throttle_updates:
            with limited_targeting_update(self.influencer.user, "gender"):
                self.log.add_event("gender", {"gender": gender})
        else:
            self.log.add_event("gender", {"gender": gender})

    def update_birthday(self, birthday, throttle_updates=False):
        if isinstance(birthday, dt.datetime):
            birthday = birthday.date()
        if throttle_updates:
            with limited_targeting_update(self.influencer.user, "birthday"):
                self.log.add_event("birthday", {"birthday": birthday})
        else:
            self.log.add_event("birthday", {"birthday": birthday})

    def update_target_region(self, target_region_id):
        self.log.add_event("set_target_region", {"region_id": target_region_id, "source": "manual"})

    def audience_insight_toggle(self):
        if self.influencer.audience_insight_expires is not None:
            self.log.add_event("audience_insight_expires", {"expires": None})
        else:
            year_from_now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365)
            self.log.add_event("audience_insight_expires", {"expires": year_from_now})

    def review(self):
        if self.influencer.state != INFLUENCER_STATES.NEW:
            raise ServiceException(f"Can't review a {self.influencer.state} influencer")
        self.log.add_event("review")

    def disable(self, reason):
        if self.influencer.state not in (
            INFLUENCER_STATES.NEW,
            INFLUENCER_STATES.REVIEWED,
            INFLUENCER_STATES.VERIFIED,
        ):
            raise ServiceException(f"Can't disable a {self.influencer.state} influencer")
        self.log.add_event("disable", {"reason": reason})

    def enable(self):
        if self.influencer.state != INFLUENCER_STATES.DISABLED:
            raise ServiceException(f"Can't enable a {self.influencer.state} influencer")
        self.log.add_event("enable")

    def cooldown(self, days):
        if self.influencer.state not in (INFLUENCER_STATES.REVIEWED, INFLUENCER_STATES.VERIFIED):
            raise ServiceException(f"Can't cooldown a {self.influencer.state} influencer")
        self.log.add_event("cooldown", {"days": days})
        influencer_tasks.schedule_end_cooldown(self.influencer)

    def cancel_cooldown(self):
        if self.influencer.state != INFLUENCER_STATES.COOLDOWN:
            raise ServiceException(
                f"Can't cancel a cooldown for a {self.influencer.state} influencer"
            )
        self.log.add_event("cancel_cooldown")
        influencer_tasks.clear_cooldown(self.influencer)

    def verify(self):
        if self.influencer.state != INFLUENCER_STATES.REVIEWED:
            raise ServiceException(f"Can't verify a {self.influencer.state} influencer")
        self.log.add_event("verify")

    def unverify(self):
        if self.influencer.state != INFLUENCER_STATES.VERIFIED:
            raise ServiceException(f"Can't unverify a {self.influencer.state} influencer")
        self.log.add_event("unverify")

    def comment_on(self, comment):
        self.log.add_event("comment", {"comment": comment})

    def message(self, takumi_username, text, dm):
        staff_member = InfluencerService.get_by_username(takumi_username)
        if staff_member is None:
            raise InfluencerNotFound(f"No influencer found with the username {takumi_username}")
        if not staff_member.user.can(send_recruitment_dm):
            raise ForbiddenException("Notification should be sent to a staff member's Takumi app")

        if not staff_member.has_device:
            raise SendInfluencerMessageError("User has no device to notify")

        client = NotificationClient.from_influencer(staff_member)
        try:
            if dm:
                client.send_instagram_direct_message(self.influencer.username, text)
            else:
                client.send_instagram_view_profile(self.influencer.username, text)
        except NotificationException:
            raise SendInfluencerMessageError("Failed to send push notification")

        if dm:
            self.log.add_event(
                "send-instagram-direct-message",
                {"takumi_username": staff_member.username, "text": text, "is_dm": dm},
            )

    def accept_terms(self):
        self.influencer.info["terms_accepted"] = dt.datetime.utcnow().isoformat()

    def accept_privacy_policy(self):
        self.influencer.info["privacy_accepted"] = dt.datetime.utcnow().isoformat()

    def update_impressions_ratio(self):
        """Calculate the median impressions ratio for the influencer

        Calculation is done based on their submitted posts insights in a given
        time period, defined by the MAX_INSIGHT_IMPRESSIONS_AGE constant.
        """
        max_insight_age = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            days=MAX_INSIGHT_IMPRESSIONS_AGE
        )

        insights = db.session.query(PostInsight).filter(
            PostInsight.influencer_id == self.influencer.id, PostInsight.created > max_insight_age
        )

        # Filter out where impressions are missing
        insights = [i for i in insights if i.impressions is not None and i.impressions > 0]

        if len(insights) == 0:
            return

        calculate_insight_ratio = lambda insight: insight.impressions / (
            insight.followers or insight.gig.offer.influencer.followers
        )

        ratios = [calculate_insight_ratio(insight) for insight in insights]

        ratios_median = median(ratios)
        if not MIN_IMPRESSIONS_RATIO < ratios_median < MAX_IMPRESSIONS_RATIO:
            # Ignore extremes, likely lacking too data
            return

        self.log.add_event("set_impressions_ratio", {"ratio": median(ratios)})

    def fetch_and_save_audience_insights(self):
        if not self.influencer.instagram_account.facebook_page:
            return
        if not self.influencer.instagram_account.facebook_page.active:
            return
        instagram_account = self.influencer.instagram_account
        insight_made_within_a_day = (
            db.session.query(func.count(InstagramAudienceInsight.id) > 0)
            .filter(
                InstagramAudienceInsight.instagram_account_id == instagram_account.id,
                InstagramAudienceInsight.created
                >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
            )
            .scalar()
        )
        if insight_made_within_a_day:
            return
        try:
            with unlink_on_permission_error(self.influencer.instagram_account.facebook_page):
                insights_raw_value = self.influencer.instagram_api.get_audience_insights()
        except FacebookPageDeactivated:
            raise FetchingAudienceInsightsFailed("Failed to fetch Audience Insights")
        except InstagramError:
            capture_exception()
            raise FetchingAudienceInsightsFailed("Failed to fetch Audience Insights")

        instagram_audience_insight = InstagramAudienceInsight.from_raw_value(insights_raw_value)
        instagram_audience_insight.instagram_account_id = instagram_account.id
        db.session.add(instagram_audience_insight)
        db.session.commit()
