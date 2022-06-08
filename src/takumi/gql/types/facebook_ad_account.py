from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.relay import Connection


class FacebookAdAccount(ObjectType):
    id = fields.String(description="The ID of the account")
    name = fields.String(description="The name of the account")
    takumi_creative = fields.Boolean(description="Does this account include ads from Takumi")
    currency = fields.String(description="Currency of the account")


class FacebookAdAccountConnection(Connection):
    class Meta:
        node = FacebookAdAccount
