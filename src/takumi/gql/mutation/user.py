from flask_login import current_user

from takumi.auth import advertiser_auth
from takumi.constants import EMAIL_ENROLLMENT_SIGNER_NAMESPACE
from takumi.emails import AdminUserCreatedEmail
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_advertiser_or_404, get_user_or_404
from takumi.roles import permissions
from takumi.roles.roles import InfluencerRole, roles
from takumi.services import UserService
from takumi.services.exceptions import EnrollException
from takumi.signers import url_signer


def _can_set_role(role_name):
    if role_name not in roles:
        raise MutationException(f"{role_name} is not a valid role name")
    if not permissions.set_user_role(role_name).can():
        raise MutationException(
            f"You do not have sufficient permission to set users role to {role_name}"
        )


class InviteUser(Mutation):
    """Invite a user to our backoffice without enrolling them to a brand"""

    class Arguments:
        email = arguments.String(required=True, description="Email of the user to invite")
        name = arguments.String(required=True, description="Name of the user to invite")
        role = arguments.String(required=True, description="Role of the user to invite")

    user = fields.Field("User")

    @permissions.developer.require()
    def mutate(root, info, email, name, role):
        _can_set_role(role)

        user = UserService.create_user(email, current_user, name, role)
        return InviteUser(user=user, ok=True)


class EnrollUser(Mutation):
    """Enroll a user to an advertiser"""

    class Arguments:
        email = arguments.String(required=True, description="Email of the user to invite")
        advertiser_id = arguments.UUID(
            required=True, description="ID of the advertiser to invite to"
        )
        access_level = arguments.String(
            description="The access level assigned to the enrolled user"
        )

    user = fields.Field("User")
    invite_url = fields.String()

    @advertiser_auth(key="advertiser_id", permission=permissions.advertiser_admin)
    def mutate(root, info, email, advertiser_id, access_level="admin"):
        advertiser = get_advertiser_or_404(advertiser_id)

        if not permissions.advertiser_owner.can():
            # Owner access_level is required in order to set access_level other than member on a user
            # XXX: set default access level to admin to allow everyone to invite people
            access_level = "admin"

        user, invite_url = UserService.enroll_to_advertiser(
            email, advertiser, current_user, access_level=access_level
        )
        if invite_url is not None and not permissions.get_enrollment_url.can():
            # Empty out the invite_url if user doesn't have permission to see it
            invite_url = None

        return EnrollUser(user=user, invite_url=invite_url, ok=True)


class EnrollBrandProfileUser(Mutation):
    """Enroll a brand profile user to an advertiser"""

    class Arguments:
        email = arguments.String(
            required=True, description="Email of the brand profile user to invite"
        )
        advertiser_id = arguments.UUID(
            required=True, description="ID of the advertiser to invite to"
        )

    # FIXME: error_message is a temporary solution to help with frontend error handling
    error_message = fields.String()
    user = fields.Field("User")

    @permissions.account_manager.require()
    def mutate(root, info, email, advertiser_id):
        advertiser = get_advertiser_or_404(advertiser_id)

        try:
            user = UserService.enroll_brand_profile_to_advertiser(email, advertiser)
            error_message = None
            ok = True
        except EnrollException as ex:  # FIXME: temporary solution to help with frontend error handling
            user = None
            error_message = ex.message
            ok = False

        return EnrollBrandProfileUser(user=user, error_message=error_message, ok=ok)


class RemoveBrandProfileUser(Mutation):
    class Arguments:
        user_id = arguments.UUID(
            required=True, description="ID of the advertiser where brand user to remove"
        )

    @permissions.account_manager.require()
    def mutate(root, info, user_id=None):
        if not user_id:
            return None
        brand_profile_user = UserService.get_by_id(user_id)
        if not brand_profile_user:
            return None
        UserService.delete_user(brand_profile_user)
        return RemoveBrandProfileUser(ok=True)


class SendBrandProfileInvitation(Mutation):
    class Arguments:
        advertiser_id = arguments.UUID(
            required=True, description="ID of the advertiser to invite to"
        )
        user_id = arguments.UUID(
            required=True, description="ID of the advertiser where brand user to remove"
        )

    @permissions.account_manager.require()
    def mutate(root, info, *args, advertiser_id, user_id):
        advertiser = get_advertiser_or_404(advertiser_id)
        user = get_user_or_404(user_id)
        has_sent = UserService.send_brand_profile_invitation(user.email, advertiser, current_user)
        return SendBrandProfileInvitation(ok=has_sent)


class ResendInvite(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="ID of the user to update")

    user = fields.Field("User")

    @permissions.developer.require()
    def mutate(root, info, id):
        user = get_user_or_404(id)

        if user.email_login.verified:
            raise MutationException("User already verified")
        if type(user.role) == InfluencerRole:
            raise MutationException("Cannot resend invitation to an influencer")

        with UserService(user) as service:
            service.reset_email_invite()

        # Send email
        AdminUserCreatedEmail(
            {
                "enlisting_user_email": current_user.email,
                "token": url_signer.dumps(
                    dict(email=user.email), salt=EMAIL_ENROLLMENT_SIGNER_NAMESPACE
                ),
            }
        ).send(user.email)

        return ResendInvite(user=user, ok=True)


class RevokeInvite(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="ID of the user to update")

    @permissions.developer.require()
    def mutate(root, info, id):
        user = get_user_or_404(id)

        if user.email_login.verified:
            raise MutationException("User already verified")
        if type(user.role) == InfluencerRole:
            raise MutationException("Cannot revoke invitation to an influencer")

        UserService.delete_user(user)

        return RevokeInvite(ok=True)


class UpdateUser(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="ID of the user to update")
        role = arguments.String(description="Role to assign to the user")

    user = fields.Field("User")

    @permissions.developer.require()
    def mutate(root, info, id, role=None):
        user = get_user_or_404(id)

        with UserService(user) as service:
            if role is not None:
                _can_set_role(role)
                service.update_role(role)

        return UpdateUser(user=user, ok=True)


class EmailNotificationPreferences(arguments.Enum):
    hourly = "hourly"
    daily = "daily"
    off = "off"


class UpdateCurrentUser(Mutation):
    class Arguments:
        full_name = arguments.String(description="Full name of current user")
        password = arguments.String(description="New password for the user")
        profile_picture = arguments.String(description="Url to the new profile picture")
        email_notification_preference = EmailNotificationPreferences(
            description="Email notification preference to control when/if you receive emails"
        )

    user = fields.Field("User")

    @permissions.public.require()
    def mutate(
        root,
        info,
        full_name=None,
        password=None,
        profile_picture=None,
        email_notification_preference=None,
    ):
        user = current_user._get_current_object()

        with UserService(user) as service:
            if full_name is not None:
                service.update_full_name(full_name)
            if password is not None:
                service.update_password(password)
            if profile_picture is not None:
                service.update_profile_picture(profile_picture)
            if email_notification_preference is not None:
                service.update_email_notification_preference(email_notification_preference)

        return UpdateCurrentUser(user=user, ok=True)


class UserMutation:
    enroll_user = EnrollUser.Field()
    enroll_brand_profile_user = EnrollBrandProfileUser.Field()
    invite_user = InviteUser.Field()
    update_user = UpdateUser.Field()
    update_current_user = UpdateCurrentUser.Field()
    resend_user_invite = ResendInvite.Field()
    send_brand_profile_invitation = SendBrandProfileInvitation.Field()
    revoke_user_invite = RevokeInvite.Field()
    remove_brand_profile_user = RemoveBrandProfileUser.Field()
