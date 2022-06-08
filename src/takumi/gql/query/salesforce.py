from core.salesforce.exceptions import InvalidProductIdException, NotFoundException

from takumi.extensions import salesforce
from takumi.gql import arguments, fields
from takumi.roles import permissions


class AccountQuery:
    account = fields.Field("Account", id=arguments.String(required=True))
    accounts_search = fields.ConnectionField(
        "AccountConnection", name=arguments.String(required=True)
    )

    @permissions.access_sales_force.require()
    def resolve_account(root, info, id):
        try:
            return salesforce.get_account(id)
        except NotFoundException:
            return None

    @permissions.access_sales_force.require()
    def resolve_accounts_search(root, info, name):
        try:
            return salesforce.search_accounts_by_name(name)
        except NotFoundException:
            return None


class OpportunityQuery:
    opportunity = fields.Field("Opportunity", id=arguments.String(required=True))

    @permissions.access_sales_force.require()
    def resolve_opportunity(root, info, id):
        try:
            return salesforce.get_opportunity(id)
        except NotFoundException:
            return None


class OpportunityProductQuery:
    opportunity_product = fields.Field("OpportunityProduct", id=arguments.String(required=True))

    @permissions.access_sales_force.require()
    def resolve_opportunity_product(root, info, id):
        try:
            return salesforce.get_opportunity_product_and_opportunity(id)
        except (NotFoundException, InvalidProductIdException):
            return None
