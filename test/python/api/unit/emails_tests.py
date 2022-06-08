import mock
import pytest

from core.common.exceptions import APIError

from takumi.constants import TAKUMI_DOMAINS
from takumi.emails.email import Email


def test_send_email_in_non_prod_allows_only_takumi_domains(app):
    assert app.config["RELEASE_STAGE"] != "production"

    email = Email(template="welcome_email.html", text_template="", subject="Test Subject")

    with pytest.raises(APIError, match=r"Can only email takumi domains when not in production"):
        email._send_email(["foo@example.com"])


def test_send_email_in_non_prod_allows_handles_multiple_emails_only_takumi(app):
    assert app.config["RELEASE_STAGE"] != "production"

    email = Email(template="welcome_email.html", text_template="", subject="Test Subject")

    with pytest.raises(APIError, match=r"Can only email takumi domains when not in production"):
        email._send_email(["user@takumi.com", "admin@takumi.com", "other@example.com"])


def test_send_email_in_non_prod_allows_all_takumi_domains(app):
    assert app.config["RELEASE_STAGE"] != "production"

    email = Email(
        template="welcome_email.html",
        text_template="",
        subject="Test Subject",
        ses_client=mock.Mock(),
    )

    addresses = [f"user@{domain}" for domain in TAKUMI_DOMAINS]

    email._send_email(addresses)

    assert email._client.send_email.call_count == 1

    kwargs = email._client.send_email.call_args[1]

    assert kwargs["Destination"]["BccAddresses"] == addresses


def test_send_email_in_prod_allows_any_domain(app):
    app.config["RELEASE_STAGE"] = "production"

    email = Email(
        template="welcome_email.html",
        text_template="",
        subject="Test Subject",
        ses_client=mock.Mock(),
    )

    addresses = ["foo@takumi.com", "foo@example.com"]

    email._send_email(addresses)

    assert email._client.send_email.call_count == 1

    kwargs = email._client.send_email.call_args[1]

    assert kwargs["Destination"]["BccAddresses"] == addresses
