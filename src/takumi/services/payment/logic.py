from abc import ABCMeta, abstractmethod
from typing import Dict, Tuple

from past.utils import old_div

from takumi.events.payment import DwollaPaymentLog, RevolutPaymentLog
from takumi.extensions import dwolla, revolut
from takumi.models import Payment


class PaymentServiceProviderFactory:
    """
    Currently only gets PSP from payment methods and names
    Later on we could use different PSPs for the same payment method
    """

    @staticmethod
    def from_payment_method(payment_method):
        payment_service_providers = {
            "dwolla": Dwolla(),
            "takumi": Takumi(),
            "revolut": Revolut(),
        }
        return payment_service_providers[payment_method]

    @staticmethod
    def from_name(psp_name):
        payment_service_providers = {
            "dwolla": Dwolla(),
            "takumi": Takumi(),
            "revolut": Revolut(),
        }
        return payment_service_providers[psp_name]


class PaymentServiceProvider:
    """
    Encapsulates PSP specific logic regarding payments and gateways
    """

    __meta__ = ABCMeta

    @abstractmethod
    def get_log(self, payment):
        """Returns a payment event log"""
        raise NotImplementedError()

    @abstractmethod
    def _payout_logic(self, payment, data):
        """Encapsulates all PSP gateway payout logic"""
        raise NotImplementedError()

    """  Instance methods that implement a default behaviour below """

    def payout(self, payment, data):
        return self._payout_logic(payment, data)

    def get_name(self):
        return self.__class__.__name__.lower()


class Dwolla(PaymentServiceProvider):
    def get_log(self, payment):
        return DwollaPaymentLog(payment)

    def _payout_logic(self, payment, data):
        customer_id = payment.destination
        customer = dwolla.get_customer(customer_id)
        transfer = dwolla.payout(
            customer, str(old_div(payment.amount, 100)), {"payment_id": payment.id}
        )

        return transfer.id, transfer.get_raw_doc()


class Revolut(PaymentServiceProvider):
    def get_log(self, payment):
        return RevolutPaymentLog(payment)

    def _payout_logic(self, payment: Payment, data: Dict) -> Tuple[str, Dict]:
        counterparty_id = payment.destination
        counterparty = revolut.get_counterparty(counterparty_id)
        account_id = revolut.get_account_id(payment.currency)
        campaign = payment.offer.campaign
        reference = f"{campaign.advertiser.name}"

        transfer = revolut.create_payment(
            request_id=payment.id,
            account_id=account_id,
            counterparty=counterparty,
            amount=payment.amount / 100,
            currency=payment.currency,
            reference=reference,
            allow_conversion=campaign.allow_currency_conversion,
        )
        return transfer.id, transfer.as_dict()


class Takumi(PaymentServiceProvider):
    """
    Takumi payment service provider is a pass through PSP.
    It allows developers to claim payments without using a real payment service provider
    Making everything in our system coherent payment wise.
    """

    def get_log(self, payment):
        return DwollaPaymentLog(payment)

    def _payout_logic(self, payment, data):
        reference_id = f"takumi_{payment.id}"
        raw_request_response = "This payment never went outside our system"
        return reference_id, raw_request_response
