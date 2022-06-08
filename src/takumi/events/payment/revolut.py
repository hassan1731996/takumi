import datetime as dt

from takumi.events import Event
from takumi.models.payment import STATES


class RevolutPaymentCreate(Event):
    start_state = None
    end_state = STATES.PENDING

    def apply(self, payment):
        payment.type = self.properties["type"]
        payment.amount = self.properties["amount"]
        payment.currency = self.properties["currency"]
        payment.destination = self.properties["destination"]
        payment.offer_id = self.properties["offer_id"]
        payment.details = self.properties["details"]
        payment.country = self.properties.get("country_code")

        # Clear out sensitive data from the log
        self.properties["details"] = "DETAILS_REMOVED"
        self.properties["destination"] = "DETAILS_REMOVED"


class RevolutPaymentRequested(Event):
    start_state = (None, STATES.PENDING)
    end_state = STATES.REQUESTED

    def apply(self, payment):
        payment.reference = self.properties["reference"]
        payment.requested = dt.datetime.now(dt.timezone.utc)

        # Clear out the details
        payment.details = {}
        payment.destination = None


class RevolutPaymentRequestFailed(Event):
    start_state = (None, STATES.PENDING)
    end_state = STATES.FAILED

    def apply(self, payment):
        payment.successful = False

        # Clear out the details
        payment.details = {}
        payment.destination = None


class RevolutPaymentFailed(Event):
    start_state = (STATES.REQUESTED, STATES.PAID)
    end_state = STATES.FAILED

    def apply(self, payment):
        payment.successful = False


class RevolutPaymentSuccessful(Event):
    start_state = STATES.REQUESTED
    end_state = STATES.PAID

    def apply(self, payment):
        payment.successful = True
