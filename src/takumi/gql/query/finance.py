import datetime as dt
from typing import Dict, List

from sqlalchemy import func

from takumi import models
from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.models import Offer, Payment
from takumi.models.config import Config
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.roles import permissions
from takumi.utils.finance import PayableStats, payable_stats
from takumi.utils.payment import BalanceType, get_balances

CURRENCIES = ["GBP", "USD", "EUR"]


class FinanceQuery:
    queued_funds = fields.List("Currency")
    recently_paid = fields.List(
        "Currency",
        hours=arguments.Int(default_value=24, description="Number of hours to look back"),
    )
    payment_processing_status = fields.Field("PaymentProcessingStatus")
    payment_balances = fields.List("PaymentBalance")
    payable_stats = fields.Field("PayableStats")
    unapproved_payments = fields.List("Offer")

    @permissions.manage_payments.require()
    def resolve_queued_funds(root, info) -> List[models.Currency]:
        pending_q = db.session.query(func.sum(models.Payment.amount)).filter(
            models.Payment.state == PAYMENT_STATES.PENDING
        )
        return [
            models.Currency(
                pending_q.filter(models.Payment.currency == currency).scalar() or 0, currency
            )
            for currency in CURRENCIES
        ]

    @permissions.manage_payments.require()
    def resolve_recently_paid(root, info, hours: int) -> List[models.Currency]:
        now = dt.datetime.now(dt.timezone.utc)

        requested_q = db.session.query(func.sum(models.Payment.amount)).filter(
            models.Payment.requested > now - dt.timedelta(hours=hours),
            models.Payment.state.in_([PAYMENT_STATES.REQUESTED, PAYMENT_STATES.PAID]),
        )

        return [
            models.Currency(
                requested_q.filter(models.Payment.currency == currency).scalar() or 0, currency
            )
            for currency in CURRENCIES
        ]

    @permissions.manage_payments.require()
    def resolve_payment_processing_status(root, info) -> Dict[str, bool]:
        configs = Config.query.filter(
            Config.key.in_(["PROCESS_DWOLLA_PAYMENTS", "PROCESS_REVOLUT_PAYMENTS"])
        ).all()

        return {
            "revolut": next(c for c in configs if "REVOLUT" in c.key).value,
            "dwolla": next(c for c in configs if "DWOLLA" in c.key).value,
        }

    @permissions.manage_payments.require()
    def resolve_payment_balances(root, info) -> List[BalanceType]:
        return get_balances()

    @permissions.manage_payments.require()
    def resolve_payable_stats(root, info) -> PayableStats:
        return payable_stats(payable_since_days=14, upcoming_days=[1, 2, 3, 4, 5, 6, 7, 14, 21, 28])

    @permissions.manage_payments.require()
    def resolve_unapproved_payments(root, info) -> List[Offer]:
        return Offer.query.join(Payment).filter(
            ~Payment.approved, Payment.state == Payment.STATES.PENDING
        )
