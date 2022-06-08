import datetime as dt
from typing import Optional, Tuple, cast

from flask import current_app
from flask_login import login_user
from itsdangerous import BadData, BadTimeSignature, SignatureExpired
from sentry_sdk import capture_exception
from sqlalchemy.exc import IntegrityError

from takumi.constants import EMAIL_ENROLLMENT_SIGNER_NAMESPACE, OTP_MAX_AGE
from takumi.emails import (
    AdminUserCreatedEmail,
    AdvertiserUserEnrollmentEmail,
    AdvertiserUserEnrollmentVerificationEmail,
)
from takumi.events.user import UserLog
from takumi.extensions import db, get_locale
from takumi.i18n import gettext as _
from takumi.models import Advertiser, EmailLogin, User, UserAdvertiserAssociation
from takumi.models.user_advertiser_association import create_user_advertiser_association
from takumi.roles.roles import AdvertiserRole, InfluencerRole, roles
from takumi.services import Service
from takumi.services.exceptions import (
    BadDataException,
    BrandArchivedException,
    EmailAlreadyExistsException,
    EmailNotFoundException,
    EnrollException,
    ExpiredLoginException,
    InvalidLoginCodeException,
    InvalidLoginException,
    InvalidOTPException,
    InvalidPasswordException,
    InvalidRoleException,
    PasswordTooShortException,
    SignupNotFoundException,
    UserAlreadyExists,
    UserInactiveException,
)
from takumi.signers import url_signer
from takumi.utils import uuid4_str
from takumi.utils.login import (
    OTPNotFound,
    convert_login_code_to_otp_if_needed,
    parse_payload,
    send_otp,
)
from takumi.utils.user import create_user

BRAND_PROFILE_ACCESS_LEVEL = "brand_profile"


def verify_otp(token, email_login):
    try:
        url_signer.loads(token, salt=email_login.otp_salt, max_age=OTP_MAX_AGE)
    except SignatureExpired:
        raise ExpiredLoginException(_("The login link has expired. Please try again."))
    except BadTimeSignature:
        raise InvalidLoginException(_("The login link is invalid. Please try again."))
    except BadData:
        capture_exception()
        raise BadDataException("Bad Data")


def verify_otp_if_not_apple_user(otp, email_login):
    APPLE_TEST_ACCOUNT_ID = "793314cb-f32f-494c-b3e2-b0c4661858c8"
    if email_login.user_id != APPLE_TEST_ACCOUNT_ID:
        verify_otp(otp, email_login)


def send_advertiser_invite(
    email_login: EmailLogin, advertiser: Advertiser, enlisting_user_email: str
) -> Optional[str]:
    invite_url = None

    if email_login.verified:
        AdvertiserUserEnrollmentEmail(
            {
                "enlisting_user_email": enlisting_user_email,
                "advertiser_name": advertiser.name,
                "advertiser_domain": advertiser.domain,
            }
        ).send(email_login.email)
    else:
        # Email not verified, send a verification email
        token = url_signer.dumps(
            dict(email=email_login.email), salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE
        )
        url_base = current_app.config["WEBAPP_URL"]
        AdvertiserUserEnrollmentVerificationEmail(
            {
                "enlisting_user_email": enlisting_user_email,
                "advertiser_name": advertiser.name,
                "token": token,
            }
        ).send(email_login.email)
        invite_url = f"{str(url_base)}/enroll/verify/{str(token)}"
    return invite_url


class UserService(Service):
    """
    Represents the business model for User. This isolates the database
    from the application.
    """

    SUBJECT = User
    LOG = UserLog

    @property
    def user(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id: str) -> Optional[User]:
        return User.query.get(id)

    # POST
    @staticmethod
    def enroll_to_advertiser(
        email: str, advertiser: Advertiser, enrolled_by: User, access_level: str = "member"
    ) -> Tuple[User, Optional[str]]:
        email_login: Optional[EmailLogin] = EmailLogin.get(email)

        user: User
        if email_login:
            if email_login.user.role_name == InfluencerRole.name:
                raise EnrollException("Email already in use by an influencer")
            user = email_login.user
        else:
            # User doesn't exist, create her
            user = create_user(email=email, role_name=AdvertiserRole.name)

        if advertiser not in user.advertisers:
            create_user_advertiser_association(user, advertiser, access_level)
            db.session.add(advertiser)
            db.session.commit()

        invite_url = send_advertiser_invite(
            user.email_login, advertiser, cast(str, enrolled_by.email)
        )
        return user, invite_url

    # POST
    @staticmethod
    def enroll_brand_profile_to_advertiser(email: str, advertiser: Advertiser) -> User:
        user: User
        email_login: Optional[EmailLogin] = EmailLogin.get(email)
        if email_login:
            raise EnrollException(
                "User with this Email already exists in the system or was archived."
            )

        user = create_user(email=email, role_name=AdvertiserRole.name, brand_profile=True)
        create_user_advertiser_association(user, advertiser, BRAND_PROFILE_ACCESS_LEVEL)
        db.session.add(advertiser)
        db.session.commit()
        return user

    # POST
    @staticmethod
    def send_brand_profile_invitation(email: str, advertiser: Advertiser, sent_by: User) -> bool:
        user: User
        email_login: Optional[EmailLogin] = EmailLogin.get(email)
        sent = False
        if email_login and email_login.has_invitation_sent is False:
            invite_url = send_advertiser_invite(email_login, advertiser, cast(str, sent_by.email))
            if invite_url:
                email_login.invitation_sent = True
                db.session.add(email_login)
                db.session.commit()
                sent = True
        return sent

    @staticmethod
    def check_is_brand_archived_for_brand_profile(user_id: str) -> User:
        brand_user_profile = (
            User.query.join(
                UserAdvertiserAssociation, User.id == UserAdvertiserAssociation.user_id
            ).filter(
                User.id == user_id,
                User.advertisers_association.any(),
                UserAdvertiserAssociation.access_level == BRAND_PROFILE_ACCESS_LEVEL,
            )
        ).one_or_none()
        return brand_user_profile

    @staticmethod
    def create_user(email, created_by, name=None, role=AdvertiserRole.name):
        if role not in roles:
            raise InvalidRoleException(f"{role} is not a valid role name")

        email_login = EmailLogin.get(email)
        if email_login:
            raise UserAlreadyExists("User already exists")

        user = create_user(email=email, role_name=role, name=name)
        # Send email
        AdminUserCreatedEmail(
            {
                "enlisting_user_email": created_by.email,
                "token": url_signer.dumps(
                    dict(email=user.email), salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE
                ),
            }
        ).send(email)

        return user

    @staticmethod
    def login(email, password):
        email_login = EmailLogin.get(email)
        if not email_login:
            raise EmailNotFoundException(f"Email ({email}) not found")

        valid_password = email_login.check_password(password)
        if not valid_password:
            raise InvalidPasswordException("Invalid password")

        if not email_login.user.is_active:
            raise UserInactiveException(f"User ({email_login.user.id}) is inactive")

        login_user(email_login.user)
        email_login.user.last_login = dt.datetime.now(dt.timezone.utc)

        db.session.add(email_login.user)
        db.session.commit()

        brand_user_profile = UserService.check_is_brand_archived_for_brand_profile(
            email_login.user.id
        )
        if brand_user_profile and brand_user_profile.advertisers[0].archived:
            raise BrandArchivedException(
                f"Brand ({brand_user_profile.advertisers[0].name}) has been archived"
            )
        return email_login.user

    @staticmethod
    def send_otp_by_email(
        app_uri: str, email: str, new_signup: bool = False, timestamp: Optional[dt.datetime] = None
    ) -> None:
        """Sent OTP by email

        Create a new EmailLogin if it doesn't exist and it's a new signup. If
        it's not a new signup, simply return, doing nothing.
        """
        from takumi.models import Influencer

        email_login = EmailLogin.get(email)

        if email_login is None:
            if new_signup:
                user = create_user(email, InfluencerRole.name)
                email_login = user.email_login
                user.influencer = Influencer(id=uuid4_str(), user=user, is_signed_up=False)
                db.session.add(user)
                db.session.add(user.influencer)
                db.session.add(user.email_login)
            else:
                # Doesn't exist and isn't a new signup
                return
        else:
            # Email existed, it's not a new signup. Send normal login email
            new_signup = False

        email_login.reset_otp()
        email_login.user.locale = get_locale()
        db.session.add(email_login)
        db.session.commit()

        if not email_login or not email_login.user.influencer:
            return

        send_otp(email_login, app_uri=app_uri, timestamp=timestamp, new_signup=new_signup)

    @staticmethod
    def login_with_otp(otp):
        try:
            otp = convert_login_code_to_otp_if_needed(otp)
        except OTPNotFound:
            raise InvalidLoginCodeException(_("Invalid login code"))

        _ok, payload = url_signer.loads_unsafe(otp)
        email, is_developer = parse_payload(payload)
        if email is None:
            raise InvalidOTPException(_("Invalid login code"))

        email_login = EmailLogin.get(email)

        if email_login is None:
            raise SignupNotFoundException(_("Sorry, we can’t find a signup from this device."))
        else:
            verify_otp_if_not_apple_user(otp, email_login)
            email_login.verified = True

        user = email_login.user
        login_user(user)

        if not is_developer:
            user.last_login = dt.datetime.now(dt.timezone.utc)
            user.last_active = dt.datetime.now(dt.timezone.utc)
        try:
            db.session.commit()
        except IntegrityError:
            # Handle race condition with multiple requests at a time
            capture_exception()  # Log them to sentry
            raise EmailAlreadyExistsException("Email already exists")

        return email_login.user, is_developer

    @staticmethod
    def login_with_facebook(instagram_username, facebook_token):
        from .facebook import FacebookService
        from .influencer import InfluencerService

        influencer = InfluencerService.get_by_username(instagram_username)
        if not influencer:
            influencer = InfluencerService.create_prewarmed_influencer(instagram_username)

        user = influencer.user

        if influencer.username == "joemoidustein":
            from takumi.slack.client import SlackClient

            client = SlackClient(username="Facebook Login", icon_emoji=":dance:")
            client.post_message(
                channel="project-instagram-api",
                text=None,
                attachments=[{"text": "Facebook Reviewer Logged in!"}],
            )

        FacebookService.authenticate(user.id, facebook_token)

        login_user(user)

        user.last_login = dt.datetime.now(dt.timezone.utc)
        user.last_active = dt.datetime.now(dt.timezone.utc)
        db.session.commit()

        with InfluencerService(user.influencer) as srv:
            srv.fetch_and_save_audience_insights()

        return user

    @staticmethod
    def create_user_with_no_email(profile_picture, full_name, role_name):
        user = User(
            profile_picture=profile_picture, full_name=full_name.strip(), role_name=role_name
        )

        db.session.add(user)
        db.session.commit()

        return user

    @staticmethod
    def delete_user(user):
        for user_advertiser_association in user.advertisers_association:
            """An ugly hack that ensures that no association remains between deleted user and advertisers
            Sqlalchemy tries to synchronize the association before cascading it resulting in an attempt to blank out
            a primary key of a row.

            Other suggested solution to the 'many-to-many orphan problem involve catching all after_flush events
            verify inside the catch that we have a case of parent deletion and delete all orphans.
            See:
              https://stackoverflow.com/questions/12653824/delete-children-after-parent-is-deleted-in-sqlalchemy
              https://stackoverflow.com/questions/9234082/setting-delete-orphan-on-sqlalchemy-relationship-causes-assertionerror-this-att/9264556#9264556

            It is an overkill to catch all after_flush events when we can prevent the orphan problem at service level
            """
            db.session.delete(user_advertiser_association)
        db.session.commit()
        db.session.delete(user.email_login)
        db.session.delete(user)
        db.session.commit()

    # PUT
    def update_role(self, role):
        if role not in roles:
            raise InvalidRoleException(f"{role} is not a valid role name")

        self.user.role_name = role

    def update_full_name(self, name):
        self.user.full_name = name.strip()

    def update_youtube_channel_url(self, url):
        self.user.youtube_channel_url = url
        if not url:
            self.user.influencer._social_accounts_chosen = False

    def update_tiktok_username(self, username):
        from takumi.tasks.tiktok import notify_new_tiktok

        self.user.tiktok_username = username

        if not username:
            self.user.influencer._social_accounts_chosen = False

        if self.user.tiktok_username:
            notify_new_tiktok.delay(self.user.influencer.id)

    def update_password(self, password):
        min_pass_len = 6
        if len(password) < min_pass_len:
            raise PasswordTooShortException(
                f"Password has to be at least {min_pass_len} characters"
            )
        self.user.email_login.set_password(password)

    def update_profile_picture(self, profile_picture):
        self.user.profile_picture = profile_picture

    def reset_email_invite(self):
        self.user.email_login.created = dt.datetime.now(dt.timezone.utc)

    def update_email_notification_preference(self, email_notification_preference):
        self.user.email_notification_preference = email_notification_preference

    def update_device(self, device):
        self.log.add_event("set_device", {"device_id": device.id})
