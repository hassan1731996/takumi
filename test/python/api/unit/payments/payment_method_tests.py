import pytest

from takumi.payments.payment_method import (
    InvalidIbanException,
    PaymentMethod,
    PaymentMethodException,
    PaymentMethodService,
    UnsupportedPaymentMethodException,
)


######################################
# Test utilities for interface tests #
######################################
class PaymentMethodTesterException(PaymentMethodException):
    pass


class PaymentMethodTester(PaymentMethod):
    _supported_currencies = ["supported_currency_1", "supported_currency_2"]

    def _validate(self, destination, currency):
        if destination != "supported_destination_arg":
            raise PaymentMethodTesterException("Test exception raised")


###################
# Interface tests #
###################
def test_payment_method_service_throws_unsupported_payment_method_exception_for_unknown_payment_method():
    with pytest.raises(UnsupportedPaymentMethodException) as exc:
        PaymentMethodService.validate_payment_method("FUBAR", "destination", "currency")

    assert "Payment method FUBAR not supported" in exc.exconly()


def test_payment_method_validation_for_supported_currencies():
    PaymentMethodTester().validate("supported_destination_arg", "supported_currency_1")
    PaymentMethodTester().validate("supported_destination_arg", "supported_currency_2")

    with pytest.raises(UnsupportedPaymentMethodException) as exc:
        PaymentMethodTester().validate("supported_destination_arg", "not_supported_currency")

    assert (
        "Currency not_supported_currency not supported for payment method paymentmethodtester"
        in exc.exconly()
    )


def test_payment_method_validation_for_custom_validation_check():
    PaymentMethodTester().validate("supported_destination_arg", "supported_currency_1")

    with pytest.raises(PaymentMethodTesterException) as exc:
        PaymentMethodTester().validate("not_supported_destination", "supported_currency_1")

    assert "Test exception raised" in exc.exconly()


#########################
# Implementations tests #
#########################
def test_payment_method_iban_does_not_validate_for_gbp_transactions_into_non_gb_account():
    with pytest.raises(InvalidIbanException) as exc:
        PaymentMethodService.validate_payment_method("iban", "DExxxxxx", "GBP")

    assert "Cannot transfer GBP into a non GB bank account" in exc.exconly()

    PaymentMethodService.validate_payment_method("iban", "GBxxxxxx", "GBP")


def test_payment_method_iban_does_not_validate_for_eur_transactions_into_gb_account():
    with pytest.raises(InvalidIbanException) as exc:
        PaymentMethodService.validate_payment_method("iban", "GBxxxxxx", "EUR")

    assert "Cannot transfer EUR into a GB bank account" in exc.exconly()

    PaymentMethodService.validate_payment_method("iban", "DExxxxxx", "EUR")
