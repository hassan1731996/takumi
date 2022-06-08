import datetime as dt

import pytest

from takumi.models import PaymentAuthorization
from takumi.payments.authorization_checkers import (
    PaymentAuthorizationChecker,
    PaymentAuthorizationCheckerException,
)


######################################
# Test utilities for interface tests #
######################################
class PaymentAuthorizationCheckerTester(PaymentAuthorizationChecker):
    slug = "some-test-slug"

    def _valid(self, offer):
        return offer == "valid_offer_arg"


def test_payment_authorization_checker_raises_exception_for_incompatible_slugs():
    payment_authorization = PaymentAuthorization(slug="incorrect-slug")

    with pytest.raises(PaymentAuthorizationCheckerException) as exc:
        PaymentAuthorizationCheckerTester(payment_authorization).valid("valid_offer_arg")

    assert (
        "Payment authorization slug mismatch. Checking for some-test-slug, but got incorrect-slug"
        in exc.exconly()
    )


def test_payment_authorization_checker_does_not_pass_for_expired_authorization():
    payment_authorization = PaymentAuthorization(
        slug="some-test-slug", expires=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    )

    assert (
        PaymentAuthorizationCheckerTester(payment_authorization).valid("valid_offer_arg") is False
    )


def test_payment_authorization_checker_does_not_pass_for_custom_validation_check():
    payment_authorization = PaymentAuthorization(slug="some-test-slug")

    assert (
        PaymentAuthorizationCheckerTester(payment_authorization).valid("not_valid_offer_arg")
        is False
    )


def test_payment_authorization_checker_validates_payment_authorization():
    payment_authorization = PaymentAuthorization(slug="some-test-slug")

    assert PaymentAuthorizationCheckerTester(payment_authorization).valid("valid_offer_arg") is True
