import datetime as dt
from typing import List

from sqlalchemy import func
from tasktiger.schedule import periodic

from takumi import slack
from takumi.extensions import db, tiger
from takumi.models import Config, Currency, Payment
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.services import PaymentService
from takumi.services.exceptions import PaymentRequestFailedException
from takumi.utils.payment import get_balances
from takumi.views.task import send_failed_payout_push_notification

PAYMENT_REAP_DELAY = 5  # seconds


@tiger.task(unique=True, retry=False)
def reap_payment(payment_id: str) -> None:
    """Reap an individual payment

    Run as a separate task in case there are any errors for the individual payment
    """
    payment: Payment = Payment.query.get(payment_id)

    # XXX: Temporarily block automatic retry of payments
    offer = payment.offer
    if len(offer.payments) > 1:
        slack.notify_debug(f"Offer ({offer.id}) has multiple payments, not reaping...")
        return

    # Check if payment processing has been stopped by a different task
    process_payment = (
        payment.type == "dwolla" and Config.get("PROCESS_DWOLLA_PAYMENTS").value is True
    ) or (payment.type == "revolut" and Config.get("PROCESS_REVOLUT_PAYMENTS").value is True)

    if process_payment:
        try:
            with PaymentService(payment) as service:
                service.request(payment.details)
        except PaymentRequestFailedException as e:
            # Mark the payment as failed, letting the influencer retry
            with PaymentService(payment) as service:
                service.request_failed(str(e))
            send_failed_payout_push_notification(payment.offer)


@tiger.scheduled(periodic(hours=3))
def payment_reaper():
    """Schedule payments that have not been run for some reason"""
    to_reap: List[str] = []
    if Config.get("PROCESS_DWOLLA_PAYMENTS").value is True:
        to_reap.extend(
            [
                payment.id
                for payment in db.session.query(Payment.id).filter(
                    Payment.type == "dwolla",
                    Payment.state == PAYMENT_STATES.PENDING,
                    Payment.approved,
                )
            ]
        )

    if Config.get("PROCESS_REVOLUT_PAYMENTS").value is True:
        to_reap.extend(
            [
                payment.id
                for payment in db.session.query(Payment.id).filter(
                    Payment.type == "revolut",
                    Payment.state == PAYMENT_STATES.PENDING,
                    Payment.approved,
                )
            ]
        )

    for idx, payment_id in enumerate(to_reap):
        tiger.tiger.delay(
            reap_payment,
            args=[payment_id],
            unique=True,
            retry=False,
            when=dt.timedelta(seconds=idx * PAYMENT_REAP_DELAY),
        )


@tiger.scheduled(periodic(hours=24, start_date=dt.datetime(2000, 1, 1, 8)))
def notify_payment_stats():
    """Send a payment stats notification to slack every morning"""
    currencies = ["GBP", "USD", "EUR", "ZAR"]
    now = dt.datetime.now(dt.timezone.utc)

    # Pending
    pending_q = db.session.query(func.sum(Payment.amount)).filter(
        Payment.state == PAYMENT_STATES.PENDING
    )
    pending = {
        currency: Currency(pending_q.filter(Payment.currency == currency).scalar() or 0, currency)
        for currency in currencies
    }

    # Requested
    requested_q = db.session.query(func.sum(Payment.amount)).filter(
        Payment.requested > now - dt.timedelta(hours=24),
        Payment.state.in_((PAYMENT_STATES.REQUESTED, PAYMENT_STATES.PENDING, PAYMENT_STATES.PAID)),
    )
    requested = {
        currency: Currency(requested_q.filter(Payment.currency == currency).scalar() or 0, currency)
        for currency in currencies
    }

    slack.payment_stats(pending, requested, balances=get_balances())
