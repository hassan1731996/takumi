from typing import Dict, List, Literal, Optional, Union

from dateutil.parser import parse as dateutil_parse
from sqlalchemy import extract

from takumi.extensions import db, taxid
from takumi.models import Influencer, TaxForm
from takumi.services import Service
from takumi.services.exceptions import ServiceException
from takumi.slack.channels.tax import tax_form_submitted
from takumi.utils import uuid4_str

FormNumber = Union[Literal["w9"], Literal["w8ben"]]
FormState = Union[Literal["completed"], Literal["pending"], Literal["invalid"]]


class TaxFormService(Service):
    SUBJECT = TaxForm

    @property
    def tax_form(self) -> TaxForm:
        return self.subject

    @staticmethod
    def get_by_id(id: str) -> Optional[TaxForm]:
        return TaxForm.query.get(id)

    @staticmethod
    def get(
        influencer: Influencer,
        year: Optional[int] = None,
        number: Optional[FormNumber] = None,
        state: Optional[FormState] = None,
    ) -> List[TaxForm]:
        q = TaxForm.query.filter(TaxForm.influencer == influencer)
        if year is not None:
            q = q.filter(extract("year", TaxForm.created) == year)
        if number is not None:
            q = q.filter(TaxForm.number == number)
        if state is not None:
            q = q.filter(TaxForm.state == state)
        return q.all()

    @staticmethod
    def create(form_number: FormNumber, influencer: Influencer) -> TaxForm:
        form_id = uuid4_str()
        form_url = taxid.form_request(form_number=form_number, reference=form_id)
        tax_form = TaxForm(
            id=form_id,
            state=TaxForm.STATES.PENDING,
            url=form_url,
            influencer=influencer,
            number=form_number,
        )

        db.session.add(tax_form)
        db.session.commit()

        return tax_form

    def callback_update(self, payload: Dict) -> None:
        """Update form from a callback"""
        if "w9" in payload:
            self.tax_form.signature_date = dateutil_parse(payload["w9"]["signatureDate"])
            self.tax_form.number = "w9"
        elif "w8ben" in payload:
            self.tax_form.signature_date = dateutil_parse(payload["w8ben"]["signatureDate"])
            self.tax_form.number = "w8ben"
        else:
            raise ServiceException("Invalid callback")

        self.tax_form.token = payload["token"]
        self.tax_form.sender_email = payload["senderEmail"]
        self.tax_form.name = payload["name"]
        self.tax_form.state = TaxForm.STATES.COMPLETED
        tax_form_submitted(self.tax_form)
