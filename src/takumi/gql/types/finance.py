from typing import Dict

from graphene import NonNull, ObjectType

from takumi.gql import fields
from takumi.models import Currency


class PaymentProcessingStatus(ObjectType):
    id = fields.String()
    dwolla = fields.Boolean()
    revolut = fields.Boolean()

    def resolve_id(root, info):
        return "payment-processing-status"


class PaymentBalance(ObjectType):
    id = fields.String()
    provider = fields.String()
    amount = fields.Field("Currency")

    def resolve_id(root: Dict, info) -> str:
        return f"payment-balance-{root['provider']}-{root['amount'].currency}"


class PayableAmount(ObjectType):
    gbp = fields.Field("Currency", required=True)
    eur = fields.Field("Currency", required=True)
    usd = fields.Field("Currency", required=True)

    def resolve_gbp(root, info) -> Currency:
        return Currency(root.get("GBP", 0), currency="GBP", currency_digits=False)

    def resolve_eur(root, info) -> Currency:
        return Currency(root.get("EUR", 0), currency="EUR", currency_digits=False)

    def resolve_usd(root, info) -> Currency:
        return Currency(root.get("USD", 0), currency="USD", currency_digits=False)


class PayableItem(ObjectType):
    description = fields.String(required=True)
    amounts = fields.Field(PayableAmount, required=True)


class PayableStats(ObjectType):
    claimable = fields.List(NonNull(PayableItem), required=True)
    upcoming = fields.List(NonNull(PayableItem), required=True)
