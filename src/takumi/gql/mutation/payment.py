from typing import Optional

from flask_login import current_user
from sentry_sdk import capture_message

from takumi.feature_flags import BypassPaymentRestrictionFlag
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.models import Campaign, Config, Offer
from takumi.roles import permissions
from takumi.services import OfferService, ServiceException
from takumi.services.payment import PaymentService, PendingPaymentExistsException
from takumi.services.payment.types import PaymentDataDict


class RequestPayment(Mutation):
    class Arguments:
        offer_id = arguments.UUID(required=True)
        destination_type = arguments.String(required=True)
        destination_value = arguments.String(required=True)

        full_name = arguments.String(required=False, description="Deprecated")
        bank_name = arguments.String(required=False, description="Deprecated")
        country_code = arguments.String(required=False, description="Deprecated")

    campaign = fields.Field("Campaign")

    @permissions.influencer.require()
    def mutate(
        root,
        info,
        offer_id: str,
        destination_type: str,
        destination_value: str,
        full_name: Optional[str] = None,
        bank_name: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> "RequestPayment":
        offer: Optional[Offer] = OfferService.get_by_id(offer_id)

        if not offer or offer.influencer != current_user.influencer:
            raise MutationException("Unable to claim offer. Please contact hello@takumi.com")

        campaign: Campaign = offer.campaign
        if campaign.pro_bono:
            # Guard just in case, if payment is requested in pro bono campaign,
            # it should go to takumi
            destination_type = "takumi"

        if not BypassPaymentRestrictionFlag(current_user).enabled:
            if permissions.use_takumi_payment.can():
                # Use takumi payment service provider (never goes outside of our system)
                destination_type = "takumi"
            elif (
                current_user.influencer.instagram_account
                and current_user.influencer.instagram_account.boosted
            ):
                # The current user has fake boosted numbers from instascrape, raise an
                # exception and force this to go support
                raise MutationException("Unable to claim offer. Please contact hello@takumi.com")

        data: PaymentDataDict = {
            "destination": {"type": destination_type, "value": destination_value}
        }

        try:
            payment = PaymentService.create(offer.id, data=data)
        except PendingPaymentExistsException:
            # Pending payment already exists, just return normally
            return RequestPayment(ok=True, campaign=campaign)

        process_payment = (
            (payment.type == "dwolla" and Config.get("PROCESS_DWOLLA_PAYMENTS").value is True)
            or (payment.type == "revolut" and Config.get("PROCESS_REVOLUT_PAYMENTS").value is True)
            or payment.type == "takumi"
        )

        # For debugging
        block_payment = False
        if (
            destination_type == "revolut"
            and destination_value != current_user.revolut_counterparty_id
        ):
            block_payment = True
            capture_message(f"Revolut destination value mismatch. Offer: {offer.id}")

        if process_payment and not block_payment:
            try:
                with PaymentService(payment) as service:
                    if service.check_for_approval():
                        service.request(data)
            except ServiceException as exc:
                with PaymentService(payment) as service:
                    service.request_failed(exc.message)
                raise MutationException(exc.message)

        return RequestPayment(ok=True, campaign=campaign)


class PaymentMutation:
    request_payment = RequestPayment.Field()
