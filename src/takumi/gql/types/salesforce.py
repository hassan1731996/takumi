from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection, Node
from takumi.models import Currency


class Account(ObjectType):
    class Meta:
        interfaces = (Node,)

    name = fields.String()


class AccountConnection(Connection):
    class Meta:
        node = Account

    name = fields.String()


class Opportunity(ObjectType):
    id = fields.String()
    name = fields.String()
    amount = fields.Float()
    stageName = fields.String()


class OpportunityProduct(ObjectType):
    id = fields.String()
    name = fields.String()
    total_amount = fields.Field("Currency")
    launch_date = fields.String()
    link = fields.String()
    opportunity = fields.Field("Opportunity")

    def resolve_total_amount(opportunityProduct, info):
        return Currency(
            amount=opportunityProduct.total_amount * 100, currency=opportunityProduct.currency
        )
