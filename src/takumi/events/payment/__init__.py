from takumi.events import ColumnLog, Event
from takumi.events.payment.dwolla import (
    DwollaPaymentCreate,
    DwollaPaymentFailed,
    DwollaPaymentRequested,
    DwollaPaymentRequestFailed,
    DwollaPaymentSuccessful,
)
from takumi.events.payment.revolut import (
    RevolutPaymentCreate,
    RevolutPaymentFailed,
    RevolutPaymentRequested,
    RevolutPaymentRequestFailed,
    RevolutPaymentSuccessful,
)
from takumi.models import Payment


class PaymentExpired(Event):
    start_state = None
    end_state = Payment.STATES.EXPIRED

    def apply(self, payment):
        payment.successful = False


class PaymentApprove(Event):
    def apply(self, payment: Payment) -> None:
        payment.approved = True


class DwollaPaymentLog(ColumnLog):
    type_map = {
        "create": DwollaPaymentCreate,
        "request": DwollaPaymentRequested,
        "request_failed": DwollaPaymentRequestFailed,
        "succeed": DwollaPaymentSuccessful,
        "fail": DwollaPaymentFailed,
        "expire": PaymentExpired,
        "approve": PaymentApprove,
    }


class RevolutPaymentLog(ColumnLog):
    type_map = {
        "create": RevolutPaymentCreate,
        "request": RevolutPaymentRequested,
        "request_failed": RevolutPaymentRequestFailed,
        "succeed": RevolutPaymentSuccessful,
        "fail": RevolutPaymentFailed,
        "expire": PaymentExpired,
        "approve": PaymentApprove,
    }
