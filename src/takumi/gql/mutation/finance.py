from flask_login import current_user

from takumi import slack
from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_payment_or_404
from takumi.models.config import Config
from takumi.roles import permissions
from takumi.services import PaymentService


class PaymentProvider(arguments.Enum):
    dwolla = "dwolla"
    revolut = "revolut"


class TogglePaymentProcessing(Mutation):
    class Arguments:
        payment_provider = PaymentProvider(required=True)
        processing = fields.Boolean(
            required=True, description="Whether to process payments for this provider"
        )

    payment_processing_status = fields.Field("PaymentProcessingStatus")

    @permissions.manage_payments.require()
    def mutate(
        root, info, payment_provider: PaymentProvider, processing: bool
    ) -> "TogglePaymentProcessing":
        if payment_provider == PaymentProvider.dwolla:
            key = "PROCESS_DWOLLA_PAYMENTS"
        elif payment_provider == PaymentProvider.revolut:
            key = "PROCESS_REVOLUT_PAYMENTS"
        else:
            raise MutationException("Unknown payment provider")

        slack.payment_provider_toggle(
            provider=payment_provider, processing=processing, name=current_user.full_name
        )

        config = Config.get(key)
        config.value = processing
        db.session.commit()

        configs = Config.query.filter(
            Config.key.in_(["PROCESS_DWOLLA_PAYMENTS", "PROCESS_REVOLUT_PAYMENTS"])
        ).all()

        return TogglePaymentProcessing(
            payment_processing_status={
                "revolut": next(c for c in configs if "REVOLUT" in c.key).value,
                "dwolla": next(c for c in configs if "DWOLLA" in c.key).value,
            },
            ok=True,
        )


class ApprovePayment(Mutation):
    class Arguments:
        payment_id = arguments.UUID(
            required=True, description="The ID of the payment will be approved"
        )

    payment = fields.Field("Payment")

    @permissions.manage_payments.require()
    def mutate(root, info, payment_id):
        payment = get_payment_or_404(payment_id)

        with PaymentService(payment) as service:
            service.approve()

        return ApprovePayment(payment=payment, ok=True)


class FinanceMutation:
    toggle_payment_processing = TogglePaymentProcessing.Field()
    approve_payment = ApprovePayment.Field()
