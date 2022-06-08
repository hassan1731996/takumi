import copy
from contextlib import contextmanager

import mock
from flask import url_for

from takumi.gql.mutation.public.authentication import CreateOTP
from takumi.instagram_account import create_or_get_instagram_account_by_username
from takumi.models import User
from takumi.services import InfluencerService


@contextmanager
def mock_rate_limit(*args, **kwargs):
    yield


def test_restoring_influencer_after_deleting_them(
    monkeypatch,
    client,
    db_influencer,
    db_address,
    db_interest,
    elasticsearch,
):
    #################################
    # First we delete an influencer #
    #################################

    # Arrange
    original_user = copy.deepcopy(db_influencer.user)
    original_email_login = copy.deepcopy(db_influencer.user.email_login)
    account = db_influencer.instagram_account
    original_token = copy.deepcopy(account.token)
    original_username = copy.deepcopy(db_influencer.username)

    assert db_influencer.instagram_account.info == {}
    assert db_influencer.address is not None
    assert db_influencer.interests is not None
    assert db_influencer.disabled is False
    assert db_influencer.is_signed_up is True
    assert db_influencer.has_interests is True
    assert db_influencer.deletion_date is None

    assert "removed" not in db_influencer.user.full_name
    assert "removed" not in db_influencer.email

    # Act
    with InfluencerService(db_influencer) as s:
        s.delete(force=True)

    # Assert
    assert db_influencer.instagram_account is None
    assert db_influencer.address is None
    assert db_influencer.interests == []
    assert db_influencer.disabled is True
    assert db_influencer.is_signed_up is False
    assert db_influencer.deletion_date is not None

    assert "removed" in db_influencer.user.full_name
    assert "removed" in db_influencer.email

    ######################################################
    # Now that influencer has to go through signup again #
    ######################################################

    # Start verification by creating a token
    monkeypatch.setattr(
        "takumi.views.signup.get_scraped_ig_info",
        lambda x: {"id": account.ig_user_id, "username": account.ig_username},
    )

    with client.use(db_influencer.user):
        response = client.post(
            url_for("api.start_verification"), data={"username": db_influencer.username}
        )
        assert response.status_code == 200
        assert original_token != account.token

    api_uri = "https://example.com"
    email = "new_user_login@takumi.com"
    monkeypatch.setattr(
        "takumi.gql.mutation.public.authentication.check_rate_limit", mock_rate_limit
    )
    with mock.patch("takumi.services.user.send_otp") as mock_send_otp:
        CreateOTP().mutate(
            "info",
            email=email,
            app_uri=api_uri,
            new_signup=True,
        )
    assert mock_send_otp.called
    args = mock_send_otp.call_args.args
    kwargs = mock_send_otp.call_args.kwargs
    assert args[0].email == email
    assert kwargs["app_uri"] == api_uri
    assert kwargs["new_signup"] == True

    user = User.by_email(email)
    user.influencer.instagram_account = create_or_get_instagram_account_by_username(
        original_username
    )

    ###################################################################################################################
    # Verify that only the user and email logins have change but we still have their influencer and instagram account #
    ###################################################################################################################
    assert user != original_user
    assert user.email_login != original_email_login
    assert user.influencer.instagram_account == account
