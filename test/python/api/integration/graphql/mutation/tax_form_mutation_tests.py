from uuid import UUID

import pytest
from flask_principal import PermissionDenied

from takumi.gql.mutation.tax_form import RequestTaxForm
from takumi.models import TaxForm


@pytest.mark.parametrize("form_number", ["w8ben", "w9"])
def test_request_tax_form_mutation_creates_valid_form_type(
    app, monkeypatch, client, db_influencer, form_number
):
    test_url = "https://example.com/tax_form"
    monkeypatch.setattr("core.taxid.TaxID.form_request", lambda *args, **kwargs: test_url)
    with client.user_request_context(db_influencer.user):
        tax_form = RequestTaxForm().mutate(
            "info", form_number=form_number, influencer_id=db_influencer.id
        )
    assert isinstance(UUID(tax_form.tax_form.id, version=4), UUID)
    assert tax_form.tax_form.state == TaxForm.STATES.PENDING
    assert tax_form.tax_form.sender_email is None
    assert tax_form.tax_form.name is None
    assert tax_form.tax_form.signature_date is None
    assert tax_form.tax_form.token is None
    assert tax_form.tax_form.url == test_url


def test_tax_form_access(app, monkeypatch, client, db_advertiser_user, request):
    monkeypatch.setattr(
        "core.taxid.TaxID.form_request", lambda *args, **kwargs: "https://example.com/tax_form"
    )
    with pytest.raises(PermissionDenied, match=r"<Permission needs.*"):
        with client.user_request_context(db_advertiser_user):
            RequestTaxForm().mutate("info", form_number="w9", influencer_id=db_advertiser_user.id)


@pytest.mark.parametrize("form_number", ["w8ben", "w9"])
def test_return_existing_pending_tax_form(app, monkeypatch, client, db_influencer, form_number):
    test_url = "https://example.com/tax_form"
    monkeypatch.setattr("core.taxid.TaxID.form_request", lambda *args, **kwargs: test_url)
    with client.user_request_context(db_influencer.user):
        tax_form1 = RequestTaxForm().mutate("info", form_number=form_number)
        tax_form2 = RequestTaxForm().mutate("info", form_number=form_number)
    assert tax_form1.tax_form.state == TaxForm.STATES.PENDING
    assert tax_form2.tax_form.state == TaxForm.STATES.PENDING
    assert tax_form1.tax_form.id == tax_form2.tax_form.id


@pytest.mark.parametrize("form_number", ["w8ben", "w9"])
def test_return_new_tax_form_for_different_numbers_with_pending_opposite_number(
    app, monkeypatch, client, db_influencer, form_number
):
    test_url = "https://example.com/tax_form"
    monkeypatch.setattr("core.taxid.TaxID.form_request", lambda *args, **kwargs: test_url)
    if form_number == "w8ben":
        opposite_form_number = "w9"
    elif form_number == "w9":
        opposite_form_number = "w8ben"
    else:
        raise ValueError("Invalid form number")
    with client.user_request_context(db_influencer.user):
        tax_form1 = RequestTaxForm().mutate("info", form_number=form_number)
        tax_form2 = RequestTaxForm().mutate("info", form_number=opposite_form_number)
    assert tax_form1.tax_form.number != tax_form2.tax_form.number
    assert tax_form1.tax_form.number == form_number
    assert tax_form2.tax_form.number == opposite_form_number
    assert tax_form1.tax_form.id != tax_form2.tax_form.id
    assert tax_form1.tax_form.state == TaxForm.STATES.PENDING
    assert tax_form2.tax_form.state == TaxForm.STATES.PENDING
