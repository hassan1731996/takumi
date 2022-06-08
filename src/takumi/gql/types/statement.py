from graphene import ObjectType

from takumi import models
from takumi.gql import fields


class Statement(ObjectType):
    year = fields.Int()
    balance = fields.Field("Currency")
    url = fields.String()

    def resolve_balance(root, info):
        balance = root["balance"]
        return models.Currency(amount=balance["amount"], currency=balance["currency"])
