from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_offer_or_404
from takumi.models import Payment
from takumi.roles import permissions
from takumi.services.payment import PaymentServiceProviderFactory


class MarkAsPaid(Mutation):
    """Mark gig as paid by creating a Takumi payment"""

    class Arguments:
        offer_id = arguments.UUID(required=True, description="The id of the offer")
        reference = arguments.String(
            required=True,
            description="A reference for the manual payment. Either a explanation or a jira ticket id",
        )

    offer = fields.Field("Offer")

    @permissions.developer.require()
    def mutate(root, info, offer_id: str, reference: str) -> "MarkAsPaid":
        offer = get_offer_or_404(offer_id)

        provider = PaymentServiceProviderFactory.from_payment_method("takumi")
        payment = Payment()
        log = provider.get_log(payment)
        log.add_event(
            "create",
            {
                "type": "takumi",
                "amount": offer.reward,
                "currency": offer.campaign.market.currency,
                "destination": "n/a",
                "offer_id": offer.id,
                "details": {},
            },
        )
        payment.offer = offer
        payment.state = "requested"
        payment.successful = True
        payment.reference = reference

        db.session.add(payment)
        db.session.commit()

        return MarkAsPaid(offer=offer, ok=True)
