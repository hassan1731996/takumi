from sentry_sdk import capture_exception

from core.payments.dwolla.errors import BankAccountMissingException, DwollaAPIError
from core.payments.exceptions import PaymentGatewayException
from core.payments.revolut.exceptions import (
    CounterPartyNotFound,
    InsufficientFundsException,
    InvalidCurrencyException,
    RevolutException,
)

from takumi import slack
from takumi.constants import PAYOUT_LIMITS
from takumi.extensions import db
from takumi.models import Config, Payment
from takumi.payments.payment_method import PaymentMethodException, PaymentMethodService
from takumi.payments.permissions import PaymentPermissionChecker, PaymentPermissionException
from takumi.services import Service
from takumi.services.exceptions import (
    FailedPaymentMethodException,
    FailedPaymentPermissionException,
    OfferAlreadyPaidException,
    OfferNotClaimableException,
    OfferNotFoundException,
    PaymentRequestFailedException,
    PendingPaymentExistsException,
)
from takumi.services.offer import OfferService
from takumi.services.payment.logic import PaymentServiceProviderFactory
from takumi.services.payment.types import PaymentDataDict


def _pause_payments(provider: str):
    config = Config.get(f"PROCESS_{provider.upper()}_PAYMENTS")
    if config:
        config.value = False
        db.session.commit()
        slack.payments_paused(provider.title(), reason="Insufficient funds")


class PaymentService(Service):
    """
    Represents the business model for Payment. This isolates the database
    from the application.
    """

    SUBJECT = Payment

    @property
    def payment(self) -> Payment:
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Payment.query.get(id)

    @classmethod
    def create(cls, offer_id: str, data: PaymentDataDict) -> Payment:
        offer = OfferService.get_by_id(offer_id)
        if offer is None:
            raise OfferNotFoundException(f"<Offer {offer_id}> not found")
        if not offer.is_claimable:
            raise OfferNotClaimableException("Not payable yet")

        # Offer is paid or already has a pending payment
        if offer.payment is not None and offer.payment.is_pending:
            raise PendingPaymentExistsException("A pending payment exists for offer")

        payment = Payment.query.filter(Payment.offer_id == offer_id, Payment.is_successful).first()
        if payment is not None:
            raise OfferAlreadyPaidException("Offer already paid")

        payment_method = data["destination"]["type"]
        destination = data["destination"]["value"]
        payment_service_provider = PaymentServiceProviderFactory.from_payment_method(payment_method)

        payment = Payment()
        log = payment_service_provider.get_log(payment)
        log.add_event(
            "create",
            {
                "type": payment_service_provider.get_name(),
                "amount": offer.reward,
                "currency": offer.campaign.market.currency,
                "destination": destination,
                "offer_id": offer.id,
                "details": data,
            },
        )
        payment.offer = offer

        # If the campaign is pro_bono and payment method is takumi, we will
        # skip the payment validation, as there is not an actual payment being done
        skip_validation = payment_method == "takumi" and offer.campaign.pro_bono

        if not skip_validation:
            # Validate payment permission for influencer if the campaign isn't pro-bono
            try:
                PaymentPermissionChecker(payment).check()
            except PaymentPermissionException as exc:
                raise FailedPaymentPermissionException(exc.message)

            try:
                PaymentMethodService().validate_payment_method(
                    payment_method, destination, payment.currency
                )
            except PaymentMethodException as exc:
                raise FailedPaymentMethodException(exc.message)

        db.session.add(payment)
        db.session.commit()
        return payment

    def check_for_approval(self) -> bool:
        # Check if payment requires approval
        payment_service_provider = PaymentServiceProviderFactory.from_name(self.payment.type)
        log = payment_service_provider.get_log(self.payment)

        if self.payment.approved:
            # Already approved
            return True

        limit = PAYOUT_LIMITS.get(self.payment.currency, 5_000_00)

        if self.payment.amount < limit:
            # Under the limit, automatically approve
            log.add_event("approve")
            return True

        # Notify for approval
        slack.payment_needs_approval(self.payment)
        return False

    def approve(self):
        payment_service_provider = PaymentServiceProviderFactory.from_name(self.payment.type)
        log = payment_service_provider.get_log(self.payment)
        log.add_event("approve")

    def request(self, data):
        if not self.payment.approved:
            return

        payment_service_provider = PaymentServiceProviderFactory.from_name(self.payment.type)
        try:
            reference_id, raw_request_response = payment_service_provider.payout(self.payment, data)
        except BankAccountMissingException as e:
            slack.payout_request_failure(self.payment.offer, e)
            raise PaymentRequestFailedException(
                "Missing bank account information at at payment processor, "
                "please re-enter valid bank information or contact hello@takumi.com"
            )
        except CounterPartyNotFound as e:
            capture_exception()
            slack.payout_request_failure(self.payment.offer, e)
            raise PaymentRequestFailedException(
                "Missing bank account information at at payment processor, "
                "please re-enter valid bank information or contact hello@takumi.com"
            )
        except InvalidCurrencyException as e:
            slack.payout_request_failure(self.payment.offer, e)
            raise PaymentRequestFailedException(
                "Bank account doesn't support the campaign currency, please enter "
                "local bank account information or contact hello@takumi.com"
            )
        except PaymentGatewayException as e:
            slack.payout_request_failure(self.payment.offer, e)
            capture_exception()  # Log them to sentry
            raise PaymentRequestFailedException(
                "Unexpected error while requesting payout, please contact hello@takumi.com"
            )
        except InsufficientFundsException as e:
            _pause_payments("Revolut")
            slack.payout_request_failure(self.payment.offer, e)
            # Payments have been paused and this payment will be retried when payments will resume
            return
        except DwollaAPIError as e:
            if "Insufficient funds" in e.get_message():
                _pause_payments("Dwolla")
                slack.payout_request_failure(self.payment.offer, e)
                # Payments have been paused and this payment will be retried when payments will resume
                return
            raise e
        except RevolutException as e:
            slack.payout_request_failure(self.payment.offer, e)
            capture_exception()  # Log them to sentry
            raise PaymentRequestFailedException(
                "Unexpected error while requesting payout, please contact hello@takumi.com"
            )

        log = payment_service_provider.get_log(self.payment)
        log.add_event(
            "request", {"reference": reference_id, "raw_request_response": raw_request_response}
        )

    def request_failed(self, reason):
        payment_service_provider = PaymentServiceProviderFactory.from_name(self.payment.type)
        log = payment_service_provider.get_log(self.payment)

        log.add_event("request_failed", {"reason": reason})
