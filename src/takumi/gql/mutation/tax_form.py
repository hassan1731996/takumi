import datetime as dt

from flask_login import current_user
from sentry_sdk import capture_message

from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.models import TaxForm
from takumi.roles import permissions
from takumi.services import FormNumber, TaxFormService


class TaxFormNumber(arguments.Enum):
    w8ben = "w8ben"
    w9 = "w9"


class RequestTaxForm(Mutation):
    """Request tax form"""

    class Arguments:
        form_number = TaxFormNumber(required=True, description="Type of the tax form")
        influencer_id = arguments.UUID(
            required=False, description="Id of the influencer the tax form belongs to"
        )

    tax_form = fields.Field("TaxForm")

    @permissions.influencer.require()
    def mutate(self, info, form_number: FormNumber, influencer_id: str = None):
        if influencer_id is not None and permissions.developer.can():
            influencer = get_influencer_or_404(influencer_id)
        else:
            influencer = current_user.influencer
        if influencer is None:
            raise MutationException("Influencer not found")
        previous_tax_forms = TaxFormService.get(
            influencer=influencer,
            year=dt.datetime.now(dt.timezone.utc).year,
            number=form_number,
            state=TaxForm.STATES.PENDING,
        )
        if len(previous_tax_forms) != 0:
            if len(previous_tax_forms) == 1:
                return RequestTaxForm(tax_form=previous_tax_forms[0], ok=True)
            else:
                capture_message(f"Multiple pending tax forms found for influencer: {influencer.id}")
                raise MutationException("Multiple pending tax forms found")
        tax_form = TaxFormService.create(form_number=form_number, influencer=influencer)
        return RequestTaxForm(tax_form=tax_form, ok=True)


class TaxFormMutation:
    request_tax_form = RequestTaxForm.Field()
