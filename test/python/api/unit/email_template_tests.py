import mock
import pytest

from takumi.emails import (
    AdminUserCreatedEmail,
    AdvertiserSignupVerificationEmail,
    AdvertiserUserEnrollmentVerificationEmail,
    CandidatesReadyForReviewEmail,
    EndOfCampaignEmail,
    OTPLinkEmail,
    PasswordRecoveryEmail,
    VerificationEmail,
    WelcomeEmail,
)
from takumi.exceptions import APIError


def test_release_stage_in_production_sends_email(monkeypatch, app, influencer_user):
    monkeypatch.setattr("takumi.models.user.User.by_email", lambda *args, **kwargs: influencer_user)
    email = WelcomeEmail()
    email._client = mock.Mock()

    with mock.patch.dict("takumi.emails.email.current_app.config", {"RELEASE_STAGE": "production"}):
        email.send("darri@takumi.com")
    assert email._client.send_email.called


def test_release_stage_in_development_sends_email_if_all_takumi_recipients(app):
    email = WelcomeEmail()
    email._client = mock.Mock()

    with mock.patch.dict(
        "takumi.emails.email.current_app.config", {"RELEASE_STAGE": "development"}
    ):
        email.send_many(["darri@takumi.com", "david@takumi.com"])
    assert email._client.send_email.called


def test_release_stage_in_development_raises_api_error_if_not_takumi_recipient(app):
    email = WelcomeEmail()
    email._client = mock.Mock()

    with mock.patch.dict(
        "takumi.emails.email.current_app.config", {"RELEASE_STAGE": "development"}
    ):
        with pytest.raises(APIError):
            email.send_many(["darri@takumi.com", "darri@example.com"])
    assert not email._client.send_email.called


def test_admin_user_created_email(app):
    email = AdminUserCreatedEmail({"enlisting_user_email": "Rick", "token": "ouuuuuueeeeeee"})
    url_end = "/enroll/verify/ouuuuuueeeeeee"

    # text rendering test
    text = email._render_text()

    assert url_end in text
    assert "Rick" in text

    # email rendering test
    html = email._render_html()

    expected_text = 'Hey, Rick added you to the "Takumi" team.'
    assert expected_text in html
    assert url_end in html


def test_password_recovery_email(app):
    email = PasswordRecoveryEmail({"recipient": "Rick", "token": "ouuuuuueeeeeee"})
    url_end = "/password-recovery/ouuuuuueeeeeee"

    # text rendering test
    text = email._render_text()

    assert url_end in text
    assert "Rick" in text

    # email rendering test
    html = email._render_html()

    expected_text = "Someone requested a password recovery for Rick."
    assert expected_text in html
    assert url_end in html


def test_verification_email(app):
    old_email = "twopunchhermaphrodite@example.com"
    new_email = "onepunchman@example.com"

    email = VerificationEmail({"old_email": old_email, "new_email": new_email, "token": "Saitama"})
    url_end = "/email/verify/Saitama"

    # text rendering test
    text = email._render_text()

    assert url_end in text
    assert old_email in text
    assert new_email in text

    # email rendering test
    html = email._render_html()

    expected_text = 'You\'ve requested to change your contact email from {} to "{}".'.format(
        old_email, new_email
    )

    assert expected_text in html
    assert url_end in html


def test_otp_link_email(app):
    login_code = "SOMELOGINCODEABC"
    email = OTPLinkEmail(token="Aang", login_code=login_code)

    # text rendering test
    text = email._render_text()

    assert login_code in text

    # email rendering test
    html = email._render_html()

    assert login_code in html


def test_advertiser_user_enrollment_verification_email(app):
    email = AdvertiserUserEnrollmentVerificationEmail(
        {"enlisting_user_email": "Soos", "advertiser_name": "Mabel", "token": "Stan"}
    )
    url_end = "/enroll/verify/Stan"

    # text rendering test
    text = email._render_text()

    assert url_end in text

    # email rendering test
    html = email._render_html()

    expected_text = 'Hey, Soos invited you to join the "Mabel" team on Takumi'

    assert expected_text in html
    assert url_end in html


def test_advertiser_signup_verification_email(app):
    email = AdvertiserSignupVerificationEmail({"email": "Giant", "token": "Person"})
    url_end = "/signup/verify/Person"

    # text rendering test
    text = email._render_text()

    assert url_end in text

    # email rendering test
    html = email._render_html()

    expected_text = (
        'Hey, we want to verify that you are indeed "Giant". '
        "Verifying this address will let you receive notifications and password resets from Takumi"
    )

    assert expected_text in html
    assert url_end in html


def test_end_of_campaign_email(app):
    email = EndOfCampaignEmail({"advertiser_domain": "Super", "campaign_id": "Human"})
    url_end = "/brands/Super/Human/progress"

    # text rendering test
    text = email._render_text()

    assert url_end in text

    # email rendering test
    html = email._render_html()

    assert url_end in html


def test_candidates_ready_for_review(app):
    email = CandidatesReadyForReviewEmail(
        {
            "advertiser_domain": "Super",
            "campaign_id": "Human",
            "campaign_name": "Bitten by a Radioactive Spider",
        }
    )

    assert (
        'New influencers are waiting for approval in "Bitten by a Radioactive Spider"'
        in email._render_html()
    )
