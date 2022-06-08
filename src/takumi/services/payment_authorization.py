import datetime as dt

from sqlalchemy import or_

from takumi.events.payment_authorization import PaymentAuthorizationLog
from takumi.extensions import db
from takumi.models import PaymentAuthorization
from takumi.payments.authorization_checkers import CHECKERS
from takumi.services import Service
from takumi.services.exceptions import (
    InfluencerNotFound,
    PaymentAuthorizationSlugNotFoundException,
    ValidPaymentAuthorizationAlreadyExists,
)
from takumi.services.influencer import InfluencerService


class PaymentAuthorizationService(Service):
    """
    Represents the business model for PaymentAuthorizations. This isolates the database
    from the application.
    """

    SUBJECT = PaymentAuthorization

    @property
    def payment_authorization(self):
        return self.subject

    @staticmethod
    def create(influencer_id, slug, expires=None):
        influencer = InfluencerService.get_by_id(influencer_id)

        if influencer is None:
            raise InfluencerNotFound(f"Influencer {influencer_id} not found")

        if slug not in CHECKERS:
            raise PaymentAuthorizationSlugNotFoundException(
                f"Payment authorization {slug} not found"
            )

        now = dt.datetime.now(dt.timezone.utc)

        existing_payment_authorization = PaymentAuthorization.query.filter(
            PaymentAuthorization.influencer_id == influencer_id,
            PaymentAuthorization.slug == slug,
            or_(
                PaymentAuthorization.expires > now, PaymentAuthorization.expires == None
            ),  # noqa: E711
        ).first()

        if existing_payment_authorization is not None:
            # Maybe just update the expiration time if they don't match?
            raise ValidPaymentAuthorizationAlreadyExists(
                "A {} payment authorization already exists for influencer {}. Expiration date: {}".format(
                    slug, influencer_id, existing_payment_authorization.expires
                )
            )

        payment_authorization = PaymentAuthorization()
        log = PaymentAuthorizationLog(payment_authorization)
        log.add_event("create", {"influencer_id": influencer.id, "slug": slug, "expires": expires})

        db.session.add(payment_authorization)
        db.session.commit()

        return payment_authorization
