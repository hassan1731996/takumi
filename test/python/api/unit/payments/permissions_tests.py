import datetime as dt

import mock
import pytest

from takumi.payments.permissions import (
    PaymentPermission,
    PaymentPermissionChecker,
    PaymentPermissionException,
    USATaxInfoPermission,
)


class PaymentPermissionTester(PaymentPermission):
    fail_message = "Test fail message"
    authorizations_needs = ["test-authorization-slug"]

    def handle_failure(self, payment):
        return False


def test_payment_permission_gets_required_authorization_from_influencer(payment):
    required_authorization = mock.Mock(valid=lambda *args: True)
    with mock.patch(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs",
        return_value=[required_authorization],
    ) as m_get_authorizations:
        PaymentPermissionTester().pass_permission(payment)

    assert m_get_authorizations.called
    m_get_authorizations.assert_called_with(PaymentPermissionTester.authorizations_needs)


def test_payment_permission_fails_if_influencer_has_no_required_authorizations(
    monkeypatch, payment
):
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs", lambda *args: []
    )

    with pytest.raises(PaymentPermissionException) as exc:
        PaymentPermissionTester().pass_permission(payment)

    assert PaymentPermissionTester().fail_message in exc.exconly()


def test_payment_permission_checker_passes_if_able_to_handle_failure(monkeypatch, payment):
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs", lambda *args: []
    )

    class PaymentPermissionThatHandlesFailureTester(PaymentPermission):
        fail_message = "Test fail message"
        authorizations_needs = ["test-authorization-slug"]

        def handle_failure(self, payment):
            return True

    PaymentPermissionThatHandlesFailureTester().pass_permission(payment)


def test_payment_permission_fails_if_influencer_has_invalid_authorization(monkeypatch, payment):
    required_authorization = mock.Mock(valid=lambda *args: False)
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs",
        lambda *args: [required_authorization],
    )

    with pytest.raises(PaymentPermissionException) as exc:
        PaymentPermissionTester().pass_permission(payment)

    assert PaymentPermissionTester().fail_message in exc.exconly()


def test_payment_permission_passes_if_influencer_has_one_or_more_valid_required_authorizations(
    monkeypatch, payment
):
    valid_authorization = mock.Mock(valid=lambda *args: True)
    invalid_authorization = mock.Mock(valid=lambda *args: False)
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs",
        lambda *args: [valid_authorization, invalid_authorization],
    )

    PaymentPermissionTester().pass_permission(payment)


def test_payment_permission_checker_fails_if_influencer_does_not_pass_all_permissions(
    monkeypatch, payment
):
    # Arrange
    valid_authorization = mock.Mock(valid=lambda *args: True)
    invalid_authorization = mock.Mock(valid=lambda *args: False)

    permission1 = PaymentPermissionTester()
    permission2 = PaymentPermissionTester()
    permission2.fail_message = "Correct failed permission test"

    permission_checker = PaymentPermissionChecker(payment)
    permission_checker.required_permissions = [permission1, permission2]

    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs",
        mock.Mock(side_effect=[[valid_authorization], [invalid_authorization]]),
    )

    # Act
    with pytest.raises(PaymentPermissionException) as exc:
        permission_checker.check()

    # Assert
    assert permission1.fail_message not in exc.exconly()
    assert permission2.fail_message in exc.exconly()


def test_payment_permission_checker_succeeds_if_influencer_passes_all_permissions(
    monkeypatch, payment
):
    # Arrange
    valid_authorization = mock.Mock(valid=lambda *args: True)

    permission1 = PaymentPermissionTester()
    permission2 = PaymentPermissionTester()

    permission_checker = PaymentPermissionChecker(payment)
    permission_checker.required_permissions = [permission1, permission2]

    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs",
        mock.Mock(side_effect=[[valid_authorization], [valid_authorization]]),
    )
    # Act & Assert
    permission_checker.check()


##############################
# Implementation tests below #
##############################
def test_usa_tax_info_permission_handle_failure_for_w9_non_customer_by_raising_exception(
    monkeypatch, payment
):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.get_payment_authorizations_for_slugs", lambda *args: []
    )

    payment.offer.influencer.w9_tax_years_submitted = []

    with pytest.raises(
        PaymentPermissionException,
        match=r"In order to claim this payment you need to fill out your W9",
    ):
        USATaxInfoPermission().pass_permission(payment)

    payment.offer.influencer.w9_tax_years_submitted = [dt.datetime.now().year]

    # Shouldn't raise
    USATaxInfoPermission().pass_permission(payment)
