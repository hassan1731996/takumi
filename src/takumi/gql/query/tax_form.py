from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.roles import permissions
from takumi.services import TaxFormService


class TaxFormQuery:
    tax_form = fields.Field("TaxForm", tax_form_id=arguments.UUID(required=True))

    @permissions.influencer.require()
    def resolve_tax_form(self, info, tax_form_id: str):
        tax_form = TaxFormService.get_by_id(tax_form_id)
        if tax_form is None:
            raise QueryException("Tax form not found")
        if permissions.developer.can():
            return tax_form
        if current_user.influencer != tax_form.influencer:
            raise QueryException("Tax form not found")
        return tax_form
