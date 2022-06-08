from flask import current_app
from graphene import ObjectType

from core.payments import dwolla, revolut

from takumi.gql import fields
from takumi.models import Currency
from takumi.models import Payment as PaymentModel


class Payment(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()
    modified = fields.DateTime()
    successful = fields.Boolean()
    type = fields.String()
    dashboard_link = fields.String()
    amount = fields.Field("Currency")

    def resolve_dashboard_link(payment: PaymentModel, info):
        if payment.type == "dwolla":
            return dwolla.get_web_dashboard_link(payment, current_app.config["RELEASE_STAGE"])
        elif payment.type == "revolut":
            return revolut.get_web_dashboard_link(payment, current_app.config["RELEASE_STAGE"])
        return None

    def resolve_amount(payment: PaymentModel, info):
        return Currency(amount=payment.amount, currency=payment.currency)
