import mock
from mock import call

from takumi.services.payment.logic import Dwolla, PaymentServiceProviderFactory, Revolut


def test_psp_get_name():
    assert Dwolla().get_name() == "dwolla"


def test_psp_factory_get_from_payment_method():
    psp = PaymentServiceProviderFactory.from_payment_method("dwolla")
    assert psp.get_name() == Dwolla().get_name()
    assert isinstance(psp, Dwolla)

    psp = PaymentServiceProviderFactory.from_payment_method("revolut")
    assert psp.get_name() == Revolut().get_name()
    assert isinstance(psp, Revolut)


def test_psp_factory_get_from_name():
    psp = PaymentServiceProviderFactory.from_name("dwolla")
    assert psp.get_name() == Dwolla().get_name()
    assert isinstance(psp, Dwolla)

    psp = PaymentServiceProviderFactory.from_name("revolut")
    assert psp.get_name() == Revolut().get_name()
    assert isinstance(psp, Revolut)


def test_payout_dwolla_calls_dwolla_payout(monkeypatch, payment):
    mock_payout = mock.Mock()
    monkeypatch.setattr("takumi.services.payment.logic.dwolla.get_customer", lambda x: "customer")
    monkeypatch.setattr("takumi.services.payment.logic.dwolla.payout", mock_payout)

    Dwolla().payout(payment, _get_dwolla_payment_data_skeleton())
    assert mock_payout.call_args == call("customer", "0", {"payment_id": payment.id})


def test_payout_revolut_calls_revolut_payout(monkeypatch, payment):
    mock_payout = mock.Mock()
    monkeypatch.setattr(
        "takumi.services.payment.logic.revolut.get_counterparty", lambda x: "customer"
    )
    monkeypatch.setattr("takumi.services.payment.logic.revolut.create_payment", mock_payout)

    Revolut().payout(payment, _get_revolut_payment_data_skeleton())
    assert mock_payout.call_args == call(
        request_id=payment.id,
        account_id="5bf1f78d-4ad4-4e0e-9e84-e99cc6df2c1c",  # Sandbox GBP account
        counterparty="customer",
        amount=payment.amount / 100,
        currency=payment.currency,
        reference="Stod 2",
        allow_conversion=False,
    )


#############################################
# Utility functions for tests defined below #
#############################################
def _get_dwolla_payment_data_skeleton():
    return {
        "full_name": "test_name",
        "bank_name": "test_bank",
        "country_code": "test_country_code",
        "destination": {"type": "dwolla", "value": "somevalue"},
    }


def _get_revolut_payment_data_skeleton():
    return {
        "full_name": "test_name",
        "bank_name": "test_bank",
        "country_code": "test_country_code",
        "destination": {"type": "revolut", "value": "somevalue"},
    }
