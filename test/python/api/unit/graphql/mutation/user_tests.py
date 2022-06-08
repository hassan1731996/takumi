import mock
import pytest
from mock import call

from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.user import (
    EnrollBrandProfileUser,
    EnrollUser,
    InviteUser,
    ResendInvite,
    RevokeInvite,
    SendBrandProfileInvitation,
    UpdateCurrentUser,
    UpdateUser,
)
from takumi.roles.roles import AdvertiserRole
from takumi.utils import uuid4_str


# prevent role-permissions from affecting the tests in this module
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        with mock.patch("takumi.roles.permissions.Permission.can", return_value=True):
            yield


def test_invite_user_success(monkeypatch, client, developer_user):
    # Arrange
    create_user = _get_create_user_skeleton()

    # Act
    with mock.patch("takumi.gql.mutation.user.UserService.create_user") as mock_user_service:
        with client.user_request_context(developer_user):
            InviteUser().mutate(**create_user)

    # Assert
    assert mock_user_service.call_args == call(
        create_user["email"], developer_user, create_user["name"], create_user["role"]
    )


def test_enroll_user_with_admin_access_level_defaults_to_admin_access_level_if_current_user_does_not_have_permission(
    monkeypatch, advertiser
):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_advertiser_owner_permission(monkeypatch, False)

    enroll_user = _get_enroll_user_skeleton()
    enroll_user["access_level"] = "owner"

    # Act
    with mock.patch(
        "takumi.gql.mutation.user.UserService.enroll_to_advertiser",
        return_value=("some user", "some link"),
    ) as mock_user_service:
        EnrollUser().mutate(**enroll_user)

    # Assert
    assert mock_user_service.call_args == call(
        enroll_user["email"], advertiser, None, access_level="admin"
    )


def test_enroll_user_with_admin_access_level_succeeds_if_current_user_has_owner_permission(
    monkeypatch, advertiser
):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_advertiser_owner_permission(monkeypatch, True)

    enroll_user = _get_enroll_user_skeleton()
    enroll_user["access_level"] = "admin"

    # Act
    with mock.patch(
        "takumi.gql.mutation.user.UserService.enroll_to_advertiser",
        return_value=("some user", "some link"),
    ) as mock_user_service:
        EnrollUser().mutate(**enroll_user)

    # Assert
    assert mock_user_service.call_args == call(
        enroll_user["email"], advertiser, None, access_level="admin"
    )


def test_enroll_user_returns_invite_url_as_none_if_current_user_does_not_have_permission_to_view_it(
    monkeypatch, advertiser
):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_advertiser_owner_permission(monkeypatch, False)
    _stub_get_enrollment_url(monkeypatch, False)
    _stub_enroll_to_advertiser(monkeypatch, "some user", "some url")
    enroll_user = _get_enroll_user_skeleton()

    # Act
    with mock.patch("takumi.gql.mutation.user.EnrollUser") as mock_enroll_user:
        EnrollUser().mutate(**enroll_user)

    # Assert
    assert mock_enroll_user.call_args == call(user="some user", invite_url=None, ok=True)


def test_enroll_user_returns_invite_url_if_current_user_does_not_have_permission_to_view_it(
    monkeypatch, advertiser
):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_advertiser_owner_permission(monkeypatch, False)
    _stub_get_enrollment_url(monkeypatch, True)
    _stub_enroll_to_advertiser(monkeypatch, "some user", "some url")
    enroll_user = _get_enroll_user_skeleton()

    # Act
    with mock.patch("takumi.gql.mutation.user.EnrollUser") as mock_enroll_user:
        EnrollUser().mutate(**enroll_user)

    # Assert
    assert mock_enroll_user.call_args == call(user="some user", invite_url="some url", ok=True)


def test_resend_invite_raises_if_user_is_already_verified(
    monkeypatch, advertiser_user, email_login
):
    advertiser_user.email_login.verified = True

    _stub_get_user(monkeypatch, advertiser_user)

    with pytest.raises(MutationException) as exc:
        ResendInvite().mutate(info=None, id=advertiser_user.id)

    assert "User already verified" in exc.exconly()


def test_resend_invite_raises_if_influencer(monkeypatch, influencer_user, email_login):
    _stub_get_user(monkeypatch, influencer_user)
    influencer_user.email_login.verified = False

    with pytest.raises(MutationException) as exc:
        ResendInvite().mutate(info=None, id=influencer_user.id)

    assert "Cannot resend invitation to an influencer" in exc.exconly()


def test_revoke_invite_raises_if_user_is_already_verified(
    monkeypatch, advertiser_user, email_login
):
    advertiser_user.email_login.verified = True

    _stub_get_user(monkeypatch, advertiser_user)

    with pytest.raises(MutationException) as exc:
        RevokeInvite().mutate(info=None, id=advertiser_user.id)

    assert "User already verified" in exc.exconly()


def test_revoke_invite_raises_if_influencer(monkeypatch, influencer_user, email_login):
    _stub_get_user(monkeypatch, influencer_user)
    influencer_user.email_login.verified = False

    with pytest.raises(MutationException) as exc:
        RevokeInvite().mutate(info=None, id=influencer_user.id)

    assert "Cannot revoke invitation to an influencer" in exc.exconly()


def test_update_user(monkeypatch, influencer_user):
    # Arrange
    _stub_get_user(monkeypatch, influencer_user)

    # Act
    with mock.patch("takumi.gql.mutation.user.UserService") as mock_update_user:
        UpdateUser().mutate(info=None, id=influencer_user.id, role=AdvertiserRole.name)

    # Assert
    service_calls = mock_update_user.return_value.__enter__.return_value
    assert call(AdvertiserRole.name) in service_calls.update_role.mock_calls


def test_update_current_user(monkeypatch, developer_user):
    # Arrange
    _stub_current_user_object(monkeypatch, developer_user)
    update_current_user = _get_update_current_user_skeleton()

    # Act
    with mock.patch("takumi.gql.mutation.user.UserService") as mock_update_user:
        UpdateCurrentUser().mutate(**update_current_user)

    # Assert
    service_calls = mock_update_user.return_value.__enter__.return_value
    assert call(update_current_user["full_name"]) in service_calls.update_full_name.mock_calls
    assert call(update_current_user["password"]) in service_calls.update_password.mock_calls
    assert (
        call(update_current_user["profile_picture"])
        in service_calls.update_profile_picture.mock_calls
    )


def test_enroll_brand_profile_user_success(monkeypatch, advertiser):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_advertiser_owner_permission(monkeypatch, True)

    enroll_user = _get_enroll_brand_profile_user_skeleton()

    # Act
    with mock.patch(
        "takumi.gql.mutation.user.UserService.enroll_brand_profile_to_advertiser",
        return_value="some user obj",
    ) as mock_user_service:
        EnrollBrandProfileUser().mutate(**enroll_user)

    # Assert
    assert mock_user_service.call_args == call(enroll_user["email"], advertiser)


def test_send_invitation_for_brand_profile_success(monkeypatch, advertiser, advertiser_user):
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_get_user(monkeypatch, advertiser_user)
    invite_args = _get_send_brand_profile_invitation_skeleton()

    with mock.patch(
        "takumi.gql.mutation.user.UserService.send_brand_profile_invitation", return_value=True
    ) as mock_send:
        response = SendBrandProfileInvitation().mutate(**invite_args)
    mock_send.assert_called_once()
    assert response.ok is True


def test_send_invitation_for_brand_profile_failed(monkeypatch, advertiser, advertiser_user):
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_get_user(monkeypatch, advertiser_user)
    invite_args = _get_send_brand_profile_invitation_skeleton()

    with mock.patch(
        "takumi.gql.mutation.user.UserService.send_brand_profile_invitation", return_value=False
    ) as mock_send:
        response = SendBrandProfileInvitation().mutate(**invite_args)
    mock_send.assert_called_once()
    assert response.ok is False


#############################################
# Utility functions for tests defined below #
#############################################


def _stub_get_advertiser(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.user.get_advertiser_or_404", lambda x: value)


def _stub_get_user(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.user.get_user_or_404", lambda x: value)


def _stub_advertiser_owner_permission(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.user.permissions.advertiser_owner.can", lambda: value)


def _stub_get_enrollment_url(monkeypatch, value):
    monkeypatch.setattr(
        "takumi.gql.mutation.user.permissions.get_enrollment_url.can", lambda: value
    )


def _stub_enroll_to_advertiser(monkeypatch, user, invite_url):
    monkeypatch.setattr(
        "takumi.gql.mutation.user.UserService.enroll_to_advertiser",
        mock.Mock(return_value=(user, invite_url)),
    )


def _stub_current_user_object(monkeypatch, value):
    monkeypatch.setattr(
        "takumi.gql.mutation.user.current_user", mock.Mock(_get_current_object=lambda: value)
    )


def _get_create_user_skeleton():
    return {"info": "info", "email": "test@test.test", "name": "test_name", "role": "advertiser"}


def _get_enroll_user_skeleton():
    return {
        "info": "info",
        "email": "test@test.test",
        "advertiser_id": uuid4_str(),
        "access_level": "member",
    }


def _get_enroll_brand_profile_user_skeleton():
    return {
        "info": "info",
        "email": "test@test.test",
        "advertiser_id": uuid4_str(),
    }


def _get_send_brand_profile_invitation_skeleton():
    return {
        "info": "info",
        "user_id": uuid4_str(),
        "advertiser_id": uuid4_str(),
    }


def _get_update_current_user_skeleton():
    return {
        "info": "info",
        "full_name": "full_name",
        "password": "password",
        "profile_picture": "profile_picture",
    }
