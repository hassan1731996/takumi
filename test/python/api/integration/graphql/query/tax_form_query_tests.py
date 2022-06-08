import pytest

from takumi.gql.exceptions import QueryException
from takumi.gql.query import TaxFormQuery


def test_tax_form_query_by_valid_id(monkeypatch, client, db_tax_form):
    monkeypatch.setattr(
        "core.taxid.TaxID.form_request", lambda *args, **kwargs: "https://example.com/tax_form"
    )
    with client.user_request_context(db_tax_form.influencer.user):
        result = TaxFormQuery().resolve_tax_form("info", tax_form_id=db_tax_form.id)
    assert result == db_tax_form


def test_tax_form_access_from_different_user(monkeypatch, client, db_tax_form, influencer_factory):
    monkeypatch.setattr(
        "core.taxid.TaxID.form_request", lambda *args, **kwargs: "https://example.com/tax_form"
    )
    different_influencer = influencer_factory()
    assert different_influencer != db_tax_form.influencer.user
    with pytest.raises(QueryException, match=r"Tax form not found"):
        with client.user_request_context(different_influencer.user):
            TaxFormQuery().resolve_tax_form("info", tax_form_id=db_tax_form.id)
