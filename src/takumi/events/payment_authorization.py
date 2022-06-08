from takumi.events import Event, TableLog
from takumi.models import PaymentAuthorizationEvent


class CreatePaymentAuthorization(Event):
    def apply(self, payment_authorization):
        payment_authorization.influencer_id = self.properties["influencer_id"]
        payment_authorization.slug = self.properties["slug"]
        payment_authorization.expires = self.properties["expires"]


class PaymentAuthorizationLog(TableLog):
    event_model = PaymentAuthorizationEvent
    relation = "payment_authorization"
    type_map = {"create": CreatePaymentAuthorization}
