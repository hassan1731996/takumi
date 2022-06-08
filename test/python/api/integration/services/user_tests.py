import mock
import pytest

from takumi.services.exceptions import (
    EmailNotFoundException,
    EnrollException,
    InvalidPasswordException,
    InvalidRoleException,
    PasswordTooShortException,
    UserAlreadyExists,
    UserInactiveException,
)
from takumi.services.user import UserService


def test_user_service_invite_user_success(db_developer_user, monkeypatch):
    # Arrange

    # Act
    with mock.patch("takumi.services.user.AdminUserCreatedEmail.send") as mock_email:
        user = UserService.create_user("email@email.email", db_developer_user, "name", "advertiser")

    # Assert
    assert mock_email.called
    assert mock_email.call_args[0][0] == "email@email.email"
    assert user.email == "email@email.email"


def test_user_service_invite_user_fails_for_invalid_role():
    with pytest.raises(InvalidRoleException) as exc:
        UserService.create_user("email", "created_by", "name", "invalid_role!!")

    assert "{} is not a valid role name".format("invalid_role!!") in exc.exconly()


def test_user_service_invite_user_fails_for_existing_email(
    db_session, db_developer_user, email_login
):
    # Arrange
    db_session.add(email_login)
    db_session.commit()

    # Act
    with pytest.raises(UserAlreadyExists) as exc:
        UserService.create_user(email_login.email, db_developer_user, "name", "advertiser")

    # Assert
    assert "User already exists" in exc.exconly()


def test_user_service_enroll_to_advertiser_success(db_advertiser, db_developer_user, monkeypatch):
    # Arrange
    assert db_advertiser.users == []

    # Act
    with mock.patch(
        "takumi.services.user.AdvertiserUserEnrollmentVerificationEmail.send"
    ) as mock_email:
        user, invite_url = UserService.enroll_to_advertiser(
            "email@email.email", db_advertiser, db_developer_user
        )

    # Assert
    assert mock_email.called
    assert mock_email.call_args[0][0] == "email@email.email"
    assert invite_url is not None
    assert user in db_advertiser.users
    assert db_advertiser in user.advertisers
    assert user.advertiser_access == {db_advertiser.id: "member"}


def test_user_service_enroll_to_advertiser_resend_email_if_user_already_enrolled(
    db_advertiser, db_developer_user, monkeypatch
):
    with mock.patch("takumi.services.user.AdvertiserUserEnrollmentVerificationEmail.send"):
        UserService.enroll_to_advertiser("email@email.email", db_advertiser, db_developer_user)

    with mock.patch(
        "takumi.services.user.AdvertiserUserEnrollmentVerificationEmail.send"
    ) as mock_email:
        user, invite_url = UserService.enroll_to_advertiser(
            "email@email.email", db_advertiser, db_developer_user
        )

    assert mock_email.called
    assert mock_email.call_args[0][0] == "email@email.email"
    assert invite_url is not None


def test_user_service_enroll_brand_profile_to_advertiser_success(
    db_advertiser, db_developer_user, monkeypatch
):
    # Arrange
    assert db_advertiser.users == []

    # Act
    user = UserService.enroll_brand_profile_to_advertiser("email@email.email", db_advertiser)

    # Assert
    assert user in db_advertiser.users
    assert db_advertiser in user.advertisers
    assert user.advertiser_access == {db_advertiser.id: "brand_profile"}


def test_user_service_enroll_brand_profile_to_advertiser_fail_if_email_already_in_db(
    db_session, email_login, db_advertiser
):

    # Arrange
    db_session.add(email_login)
    db_session.commit()

    # Act
    with pytest.raises(EnrollException) as exc:
        UserService.enroll_brand_profile_to_advertiser(email_login.email, db_advertiser)

    # Assert
    assert "User with this Email already exists in the system or was archived." in exc.exconly()


def test_send_brand_profile_invitation_success(
    db_session, email_login, db_advertiser, db_developer_user
):
    email_login.invitation_sent = False
    db_session.add(email_login)
    db_session.commit()

    with mock.patch(
        "takumi.services.user.send_advertiser_invite", return_value="http://some.url"
    ) as mock_send_invite:
        result = UserService.send_brand_profile_invitation(
            email_login.email, db_advertiser, db_developer_user
        )
    mock_send_invite.assert_called_once()
    assert result is True
    assert email_login.invitation_sent is True


def test_send_brand_profile_invitation_failed(
    db_session, email_login, db_advertiser, db_developer_user
):
    email_login.invitation_sent = False
    db_session.add(email_login)
    db_session.commit()

    with mock.patch(
        "takumi.services.user.send_advertiser_invite", return_value=None
    ) as mock_send_invite:
        result = UserService.send_brand_profile_invitation(
            email_login.email, db_advertiser, db_developer_user
        )
    mock_send_invite.assert_called_once()
    assert result is False
    assert email_login.invitation_sent is False


def test_send_brand_profile_invitation_failed_email_verified(
    db_session, email_login, db_advertiser, db_developer_user
):
    email_login.verified = True
    db_session.add(email_login)
    db_session.commit()

    with mock.patch("takumi.services.user.send_advertiser_invite") as mock_send_invite:
        result = UserService.send_brand_profile_invitation(
            email_login.email, db_advertiser, db_developer_user
        )
    mock_send_invite.assert_not_called()
    assert result is False


def test_user_service_create_user_with_no_email(session):
    UserService.create_user_with_no_email("http://", "full", "admin")

    assert session.add.call_count == 1
    new_user = session.add.call_args[0][0]

    assert new_user.full_name == "full"
    assert new_user.profile_picture == "http://"
    assert new_user.role_name == "admin"


def test_user_service_delete_user_that_has_been_enrolled_to_advertiser(
    monkeypatch, db_advertiser, db_developer_user
):
    # Arrange
    assert db_advertiser.users == []
    monkeypatch.setattr(
        "takumi.services.user.AdvertiserUserEnrollmentVerificationEmail.send", lambda *args: None
    )

    # Act
    user, invite_url = UserService.enroll_to_advertiser(
        "email@email.email", db_advertiser, db_developer_user
    )

    assert user in db_advertiser.users
    assert db_advertiser in user.advertisers
    assert user.advertiser_access == {db_advertiser.id: "member"}

    UserService.delete_user(user)

    assert user not in db_advertiser.users


def test_user_service_update_role(db_session, advertiser_user):
    assert advertiser_user.role_name != "developer"

    UserService(advertiser_user).update_role(role="developer")

    assert advertiser_user.role_name == "developer"


def test_user_service_update_role_raises_on_invalid_role_name(db_session, advertiser_user):
    with pytest.raises(InvalidRoleException):
        UserService(advertiser_user).update_role(role="invalid???")


def test_user_service_update_full_name(db_session, advertiser_user):
    UserService(advertiser_user).update_full_name(name="New Name")

    assert advertiser_user.full_name == "New Name"


def test_user_service_update_password(db_session, advertiser_user, email_login):
    old_hash = email_login.password_hash

    UserService(advertiser_user).update_password(password="s3cur3")

    assert email_login.password_hash != old_hash


def test_user_service_update_password_raises_on_too_short_password(db_session, advertiser_user):
    with pytest.raises(PasswordTooShortException):
        UserService(advertiser_user).update_password(password="12345")


def test_user_service_login_raises_on_email_not_found(db_session):
    with pytest.raises(EmailNotFoundException, match=r"Email (.+) not found"):
        UserService.login("invalid_email@something.com", "password")


def test_user_service_login_raises_on_invalid_password(db_advertiser_user, db_session):
    db_advertiser_user.email_login.set_password("12345")

    with pytest.raises(InvalidPasswordException, match="Invalid password"):
        UserService.login(db_advertiser_user.email, "invalid_password")


def test_user_service_login_raises_on_inactive_user(db_advertiser_user, db_session):
    db_advertiser_user.email_login.set_password("12345")
    db_advertiser_user.active = False

    with pytest.raises(UserInactiveException, match=r"User (.+) is inactive"):
        UserService.login(db_advertiser_user.email, "12345")


def test_user_service_login_logs_user_in(db_advertiser_user, db_session):
    db_advertiser_user.email_login.set_password("12345")

    with mock.patch("takumi.services.user.login_user") as mock_login:
        user = UserService.login(db_advertiser_user.email, "12345")

    assert mock_login.called
    assert user == db_advertiser_user
