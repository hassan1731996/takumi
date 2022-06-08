import datetime as dt
from typing import Optional

from flask_limiter.util import get_remote_address
from sentry_sdk import capture_exception

from takumi import slack
from takumi.constants import PASSWORD_HASH_METHOD
from takumi.error_codes import (
    BRAND_ARCHIVED_ERROR_CODE,
    EMAIL_NOT_FOUND_ERROR_CODE,
    PASSWORD_INVALID_ERROR_CODE,
)
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.ig.profile import refresh_on_interval
from takumi.location import update_influencer_location_by_ip
from takumi.models import User
from takumi.rate_limiter import RateLimitReachedError, check_rate_limit
from takumi.roles import permissions
from takumi.services import UserService
from takumi.services.exceptions import (
    BrandArchivedException,
    EmailNotFoundException,
    InvalidPasswordException,
)
from takumi.tokens import get_token_for_user
from takumi.utils import is_emaily


class Login(Mutation):
    class Arguments:
        email = arguments.String(required=True, description="User email")
        password = arguments.String(required=True, description="User password")

    user = fields.Field("User")
    token = fields.String()

    @permissions.public.require()
    def mutate(root, info, email, password):
        """Log in an advertiser user to the Takumi platform"""
        error_message = "Please enter a correct email and password. Note that both fields may be case-sensitive."

        try:
            # Allow 10 login attemps per IP a minute
            with check_rate_limit(
                "ADMIN_LOGIN:" + get_remote_address(), timeframe=dt.timedelta(seconds=60), limit=10
            ):
                try:
                    user = UserService.login(email, password)
                except EmailNotFoundException:
                    raise MutationException(error_message, error_code=EMAIL_NOT_FOUND_ERROR_CODE)
                except InvalidPasswordException:
                    raise MutationException(error_message, error_code=PASSWORD_INVALID_ERROR_CODE)
                except BrandArchivedException as brand_archived_error:
                    raise MutationException(
                        brand_archived_error, error_code=BRAND_ARCHIVED_ERROR_CODE
                    )

                token = get_token_for_user(user)

                email_login = user.email_login

                if PASSWORD_HASH_METHOD not in email_login.password_hash:
                    email_login.set_password(password)
                return Login(user=user, token=token, ok=True)

        except RateLimitReachedError:
            raise MutationException("Too many attempts. Please try again in a few minutes.")


class CreateOTP(Mutation):
    class Arguments:
        email = arguments.String(required=True, description="Email")
        timestamp = arguments.DateTime(description="Optional Timestamp to put in email subject")
        app_uri = arguments.String(required=True, description="App URI")
        new_signup = arguments.String(
            description="Whether the user is trying to sign up. Will create a user if True",
            default_value=True,
        )

    @permissions.public.require()
    def mutate(
        root,
        info,
        email: str,
        app_uri: str,
        timestamp: Optional[dt.datetime] = None,
        new_signup: bool = True,
    ):
        email = email.strip()

        if email.lower() == "facebook.review@takumi.com":
            # For facebook review
            slack.notify_debug("Facebook review email login request")
            return CreateOTP(ok=True)

        if not is_emaily(email):
            raise MutationException("Email is invalid")

        try:
            # Allow 10 Create OTP mutations per IP a minute
            with check_rate_limit(
                "CREATE_OTP:" + get_remote_address(), timeframe=dt.timedelta(seconds=60), limit=10
            ):
                UserService.send_otp_by_email(
                    app_uri, email=email, new_signup=new_signup, timestamp=timestamp
                )
        except RateLimitReachedError:
            # Pretend everything went fine
            pass
        except Exception as e:
            # Capture anything else for debugging purposes for now
            capture_exception()
            raise e

        return CreateOTP(ok=True)


class OTPLogin(Mutation):
    class Arguments:
        otp = arguments.String(required=True, description="Login Token")

    user = fields.Field("User")
    token = fields.String()

    @permissions.public.require()
    def mutate(root, info, otp):
        # For facebook review
        if otp == "facebook.zvZA4wW3GWsnr7bEcZ":
            slack.notify_debug("Facebook review token input")

            user = User.query.get("3de6055a-6e04-4fc2-b0bf-f74c46e6be6b")
            access_token = get_token_for_user(user, is_developer=False)
            return OTPLogin(user=user, token=access_token, ok=True)

        try:
            # Allow 10 OTP login attempts per IP a minute
            with check_rate_limit(
                "OTP_LOGIN:" + get_remote_address(), timeframe=dt.timedelta(seconds=60), limit=10
            ):
                user, is_developer = UserService.login_with_otp(otp)
                access_token = get_token_for_user(user, is_developer=is_developer)
                if user.influencer:
                    refresh_on_interval(user.influencer)
                    if not is_developer:
                        update_influencer_location_by_ip(user.influencer)
                return OTPLogin(user=user, token=access_token, ok=True)
        except RateLimitReachedError:
            raise MutationException("Too many attempts. Please try again in a few minutes.")


class InfluencerFacebookLogin(Mutation):
    class Arguments:
        instagram_username = arguments.String(required=True, description="Instagram Username")
        facebook_token = arguments.String(required=True, description="Facebook Login Token")

    user = fields.Field("User")
    token = fields.String()

    @permissions.public.require()
    def mutate(root, info, instagram_username, facebook_token):
        user = UserService.login_with_facebook(instagram_username, facebook_token)
        access_token = get_token_for_user(user, is_developer=False)
        if user.influencer:
            refresh_on_interval(user.influencer)
        return InfluencerFacebookLogin(user=user, token=access_token, ok=True)


class AuthenticationMutation:
    login = Login.Field()
    create_otp = CreateOTP.Field()
    otp_login = OTPLogin.Field()
    influencer_facebook_login = InfluencerFacebookLogin.Field()
