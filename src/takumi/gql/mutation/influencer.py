import datetime as dt

from flask_login import current_user

from takumi.emails import WelcomeEmail
from takumi.emails.otp_link_email import create_login_url
from takumi.events.influencer import InfluencerLog
from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException, PreconditionFailedException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.i18n import locale_context
from takumi.models import Address
from takumi.models.offer import STATES as OFFER_STATES
from takumi.roles import permissions
from takumi.services import InfluencerService, InstagramAccountService, OfferService, UserService
from takumi.tokens import create_otp_token
from takumi.utils.login import create_login_code
from takumi.utils.tiktok import parse_username


class AudienceInsightToggleForInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.audience_insight_toggle()

        return AudienceInsightToggleForInfluencer(influencer=influencer, ok=True)


class CancelInfluencerCooldown(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.cancel_cooldown()

        return CancelInfluencerCooldown(influencer=influencer, ok=True)


class CommentOnInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        comment = arguments.String(required=True)

    influencer_event = fields.Field("InfluencerEvent")

    @permissions.community_manager.require()
    def mutate(root, info, id, comment):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.comment_on(comment)

        influencer_event = {
            "text": comment,
            "user": current_user,
            "type": "comment",
            "created": dt.datetime.now(dt.timezone.utc),
        }

        return CommentOnInfluencer(influencer_event=influencer_event, ok=True)


class CooldownInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        days = arguments.Int(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, days):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.cooldown(days)

        return CooldownInfluencer(influencer=influencer, ok=True)


class DismissInfluencerFollowerAnomalies(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InstagramAccountService(influencer.instagram_account) as service:
            service.dismiss_followers_anomalies()

        return DismissInfluencerFollowerAnomalies(influencer=influencer, ok=True)


class CreatePrewarmedInfluencer(Mutation):
    class Arguments:
        username = arguments.String(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, username):
        influencer = InfluencerService.create_prewarmed_influencer(username)

        return CreatePrewarmedInfluencer(influencer=influencer, ok=True)


class DisableInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        reason = arguments.String(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, reason):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.disable(reason)

        for offer in influencer.offers:
            if offer.state == OFFER_STATES.INVITED:
                with OfferService(offer) as service:
                    service.revoke()

        return DisableInfluencer(influencer=influencer, ok=True)


class EnableInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.enable()

        return EnableInfluencer(influencer=influencer, ok=True)


class MessageInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

        text = arguments.String(required=True)
        dm = arguments.Boolean(default_value=True)

    influencer = fields.Field("Influencer")

    @permissions.community_manager.require()
    def mutate(root, info, id, text, dm):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.message(current_user.ig_username, text, dm)

        return MessageInfluencer(influencer=influencer, ok=True)


class ReviewInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.review()
            if influencer.email:
                with locale_context(influencer.user.request_locale):
                    WelcomeEmail().send(influencer.email)

        return ReviewInfluencer(influencer=influencer, ok=True)


class UnverifyInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.unverify()

        return UnverifyInfluencer(influencer=influencer, ok=True)


class UpdateInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

        interest_ids = arguments.List(arguments.UUID)
        gender = arguments.String()
        birthday = arguments.DateTime()
        target_region_id = arguments.UUID()

    influencer = fields.Field("Influencer")

    @staticmethod
    def _validate_view_model(gender):
        if gender is not None and gender not in ("female", "male"):
            raise PreconditionFailedException(
                f'`Gender` must be either "female" or "male". Received "{gender}"', 412
            )

    @permissions.manage_influencers.require()
    def mutate(
        root, info, id, interest_ids=None, gender=None, birthday=None, target_region_id=None
    ):
        UpdateInfluencer._validate_view_model(gender)
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            if interest_ids is not None:
                service.update_interests(interest_ids)
            if gender is not None:
                service.update_gender(gender)
            if birthday is not None:
                service.update_birthday(birthday)
            if target_region_id is not None:
                service.update_target_region(target_region_id)

        return UpdateInfluencer(influencer=influencer, ok=True)


class InfluencerAcceptTermsOfService(Mutation):
    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info):
        influencer = current_user.influencer

        with InfluencerService(influencer) as service:
            service.accept_terms()

        return InfluencerAcceptTermsOfService(influencer=influencer, ok=True)


class InfluencerAcceptPrivacyPolicy(Mutation):
    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info):
        influencer = current_user.influencer

        with InfluencerService(influencer) as service:
            service.accept_privacy_policy()

        return InfluencerAcceptPrivacyPolicy(influencer=influencer, ok=True)


class VerifyInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        influencer = get_influencer_or_404(id)

        with InfluencerService(influencer) as service:
            service.verify()

        return VerifyInfluencer(influencer=influencer, ok=True)


class GetOTPForInfluencer(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()
        valid_hours = arguments.Int(default_value=1, description="How long the token is valid for")
        is_developer = arguments.Boolean(
            default_value=True, description="Whether the user is a developer logging in"
        )

    token = fields.String()
    login_code = fields.String()
    url = fields.String()

    @permissions.developer.require()
    def mutate(
        root,
        info,
        id: str = None,
        username: str = None,
        valid_hours: int = 1,
        is_developer: bool = True,
    ) -> "GetOTPForInfluencer":
        if not any([username, id]):
            raise MutationException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        influencer = get_influencer_or_404(id or username)
        user = influencer.user
        email_login = user.email_login

        token = create_otp_token(email_login, is_developer=is_developer)
        url = create_login_url(token)
        login_code = create_login_code(token, valid_hours=valid_hours)

        return GetOTPForInfluencer(token=token, login_code=login_code, url=url, ok=True)


class InfluencerSignup(Mutation):
    class Arguments:
        full_name = arguments.String(required=True)
        gender = arguments.String(required=True)
        birthday = arguments.Date(required=True)
        email = arguments.String(required=False)

    influencer = fields.Field("Influencer")

    @permissions.public.require()
    def mutate(root, info, full_name, gender, birthday, email=None):
        influencer = current_user.influencer
        if not influencer:
            raise MutationException("Only influencers can run this mutation")
        with InfluencerService(influencer) as service:
            service.signup_influencer(full_name, gender, birthday, email)

        return InfluencerSignup(ok=True, influencer=influencer)


class ConfirmSocialAccounts(Mutation):
    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info):
        influencer = current_user.influencer

        if influencer.has_at_least_one_social_account:
            influencer._social_accounts_chosen = True
            db.session.commit()

        return ConfirmSocialAccounts(ok=True, influencer=influencer)


class UpdateVatNumber(Mutation):
    class Arguments:
        is_vat_registered = arguments.Boolean(
            required=True, description="Whether the influencer is VAT registered"
        )
        vat_number = arguments.String(description="The VAT number if applicable")

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info, is_vat_registered: bool, vat_number: str) -> "UpdateVatNumber":
        influencer = current_user.influencer

        with InfluencerService(influencer) as service:
            service.update_vat_number(vat_number, is_vat_registered)

        return UpdateInfluencer(ok=True, influencer=influencer)


class UpdateInfluencerProfile(Mutation):
    class Arguments:
        full_name = arguments.String()
        profile_picture = arguments.String()
        birthday = arguments.Date()
        gender = arguments.String()
        email = arguments.String()
        vat_number = arguments.String()

        youtube_channel_url = arguments.String()
        tiktok_username = arguments.String()

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(
        root,
        info,
        full_name=None,
        profile_picture=None,
        birthday=None,
        gender=None,
        email=None,
        vat_number=None,
        youtube_channel_url=None,
        tiktok_username=None,
    ):
        influencer = current_user.influencer

        with UserService(influencer.user) as service:
            if profile_picture is not None:
                service.update_profile_picture(profile_picture)
            if full_name is not None:
                service.update_full_name(full_name)
            if youtube_channel_url is not None:
                if youtube_channel_url == "":
                    service.update_youtube_channel_url(None)
                else:
                    service.update_youtube_channel_url(youtube_channel_url)
            if tiktok_username is not None:
                if tiktok_username == "":
                    service.update_tiktok_username(None)
                else:
                    parsed = parse_username(tiktok_username)
                    if not parsed:
                        raise MutationException(
                            "Invalid TikTok username. Only write the actual username"
                        )
                    service.update_tiktok_username(parsed)

        with InfluencerService(influencer) as service:
            if birthday is not None:
                service.update_birthday(birthday, throttle_updates=True)
            if gender is not None:
                service.update_gender(gender, throttle_updates=True)
            if email is not None:
                service.change_email(email)
            if vat_number is not None:
                service.update_vat_number(vat_number, is_vat_registered=True)

        return UpdateInfluencerProfile(ok=True, influencer=influencer)


class InfluencerConfirmAddress(Mutation):
    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info):
        influencer = current_user.influencer
        influencer.address.modified = dt.datetime.now(dt.timezone.utc)
        db.session.commit()

        return InfluencerRemoveAddress(ok=True, influencer=influencer)


class InfluencerRemoveAddress(Mutation):
    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info):
        influencer = current_user.influencer
        if influencer.address is not None:
            db.session.delete(influencer.address)
            db.session.commit()

        return InfluencerRemoveAddress(ok=True, influencer=influencer)


class InfluencerSetAddress(Mutation):
    class Arguments:
        name = arguments.String(default_value="")
        address1 = arguments.String(default_value="")
        address2 = arguments.String(default_value="")
        city = arguments.String(default_value="")
        postal_code = arguments.String(default_value="")
        country = arguments.String(default_value="")
        state = arguments.String(default_value="")
        phonenumber = arguments.String(default_value="")
        is_pobox = arguments.Boolean(default_value=False)

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(
        root,
        info,
        name,
        address1,
        address2,
        city,
        postal_code,
        country,
        state,
        phonenumber,
        is_pobox,
    ):

        influencer = current_user.influencer
        log = InfluencerLog(influencer)

        if influencer.address is None:
            influencer.address = Address.create_for_influencer(influencer)

        if country and country.upper() == "US":
            if not state:
                raise MutationException("State is missing")

        if not phonenumber:
            raise MutationException("Phone number is missing")

        log.add_event(
            "set_address",
            {
                "name": name,
                "address1": address1,
                "address2": address2,
                "city": city,
                "postal_code": postal_code,
                "is_pobox": is_pobox,
                "state": state,
                "phonenumber": phonenumber,
            },
        )

        db.session.add(influencer.address)
        db.session.commit()

        return InfluencerSetAddress(ok=True, influencer=influencer)


class ScheduleInfluencerDeletion(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info, id=None, username=None):
        if (id or username) and current_user.role_name == "developer":
            influencer = get_influencer_or_404(id or username)
        else:
            influencer = current_user.influencer

        with InfluencerService(influencer) as service:
            service.schedule_deletion()

        return ScheduleInfluencerDeletion(ok=True, influencer=influencer)


class CancelScheduledInfluencerDeletion(Mutation):
    class Arguments:
        id = arguments.UUID()
        username = arguments.String()

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    def mutate(root, info, username=None, id=None):
        if (id or username) and current_user.role_name == "developer":
            influencer = get_influencer_or_404(id or username)
        else:
            influencer = current_user.influencer

        with InfluencerService(influencer) as service:
            service.cancel_scheduled_deletion()

        return ScheduleInfluencerDeletion(ok=True, influencer=influencer)


class SetInfluencerEmail(Mutation):
    class Arguments:
        id = arguments.UUID(description="The influencer ID")
        username = arguments.String(description="The influencer username")
        email = arguments.String(
            required=True, description="The new email to set for the influencer"
        )

    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, email, id=None, username=None):
        if not any([username, id]):
            raise MutationException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        influencer = get_influencer_or_404(id or username)

        with InfluencerService(influencer) as service:
            service.update_email(email)

        return SetInfluencerEmail(ok=True, influencer=influencer)


class InfluencerMutation:
    audience_insight_toggle = AudienceInsightToggleForInfluencer.Field()
    cancel_influencer_cooldown = CancelInfluencerCooldown.Field()
    cancel_schedule_influencer_deletion = CancelScheduledInfluencerDeletion.Field()
    comment_on_influencer = CommentOnInfluencer.Field()
    confirm_social_accounts = ConfirmSocialAccounts.Field()
    cooldown_influencer = CooldownInfluencer.Field()
    create_prewarmed_influencer = CreatePrewarmedInfluencer.Field()
    disable_influencer = DisableInfluencer.Field()
    dismiss_influencer_follower_anomalies = DismissInfluencerFollowerAnomalies.Field()
    enable_influencer = EnableInfluencer.Field()
    get_otp_for_influencer = GetOTPForInfluencer.Field()
    influencer_accept_privacy_policy = InfluencerAcceptPrivacyPolicy.Field()
    influencer_accept_terms_of_service = InfluencerAcceptTermsOfService.Field()
    influencer_confirm_address = InfluencerConfirmAddress.Field()
    influencer_remove_address = InfluencerRemoveAddress.Field()
    influencer_set_address = InfluencerSetAddress.Field()
    influencer_signup = InfluencerSignup.Field()
    message_influencer = MessageInfluencer.Field()
    review_influencer = ReviewInfluencer.Field()
    schedule_influencer_deletion = ScheduleInfluencerDeletion.Field()
    set_influencer_email = SetInfluencerEmail.Field()
    unverify_influencer = UnverifyInfluencer.Field()
    update_influencer = UpdateInfluencer.Field()
    update_influencer_profile = UpdateInfluencerProfile.Field()
    update_vat_number = UpdateVatNumber.Field()
    verify_influencer = VerifyInfluencer.Field()
