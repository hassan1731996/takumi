import datetime as dt
import json

import mock
import pytest
from dateutil.parser import parse as dateutil_parse
from flask import g, url_for
from freezegun import freeze_time

from takumi.models import ApiTask
from takumi.utils import uuid4_str
from takumi.views.task import _upload_to_s3


@pytest.fixture()
def mock_signature(monkeypatch):
    signature = "a" * 64
    monkeypatch.setattr("core.taxid.TaxID.calculate_signature", lambda *args, **kwargs: signature)
    yield signature


@pytest.fixture(autouse=True)
def mock_get_pdf_link(monkeypatch):
    monkeypatch.setattr(
        "core.taxid.TaxID.get_pdf_link", lambda *args, **kwargs: {"pdf": "https://example.com/pdf"}
    )


@pytest.fixture(autouse=True)
def mock_request_get(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock.Mock())


@pytest.fixture()
def url():
    task = ApiTask(allowed_views=["tasks.taxid_callback"])
    setattr(g, "task", task)
    yield url_for("tasks.taxid_callback", task_id=uuid4_str())


def _get_data_skeleton(
    form_number: str, reference: str, signature_date: str = "2021-03-18T00:00:00.000Z"
):
    return {
        "type": f"form.{form_number}.created",
        "attempt": 1,
        "form": {
            "formNumber": form_number,
            "senderEmail": "user@example.com",
            "token": "callback_t0k3n",
            "name": "John Doe",
            "businessName": "Corporation, Inc.",
            "reference": reference,
            form_number: {"line1Name": "John Doe", "signatureDate": signature_date},
        },
    }


@freeze_time(dt.datetime(2021, 1, 1, 0, 0))
def test_taxid_callback(client, mock_signature, url, db_tax_form):
    headers = {"Webhook-Signature": mock_signature}
    signature_date = "2021-03-18T00:00:00.000Z"

    data = _get_data_skeleton("w9", db_tax_form.id, signature_date)

    assert db_tax_form.signature_date != dateutil_parse(signature_date)

    response = client.post(url, json=data, headers=headers)

    assert response.status_code == 200
    assert db_tax_form.signature_date == dateutil_parse(signature_date)


def test_taxid_callback_sets_tax_form_id_in_callback(client, mock_signature, url, db_tax_form):
    headers = {"Webhook-Signature": mock_signature}
    data = _get_data_skeleton("w8ben", db_tax_form.id)

    assert db_tax_form.number == "w9"

    response = client.post(url, json=data, headers=headers)

    assert response.status_code == 200
    assert db_tax_form.number == "w8ben"


def test_taxid_callback_appends_w9_tax_years_submitted_year(
    client, mock_signature, url, db_tax_form
):
    headers = {"Webhook-Signature": mock_signature}
    signature_date = "2019-03-18T00:00:00.000Z"

    data = _get_data_skeleton("w8ben", db_tax_form.id, signature_date)

    assert db_tax_form.influencer.w9_tax_years_submitted == []

    response = client.post(url, json=data, headers=headers)

    assert response.status_code == 200
    signature_year = dateutil_parse(signature_date).year
    assert db_tax_form.influencer.w9_tax_years_submitted == [signature_year]


def test_taxid_upload_to_s3(db_tax_form, mock_s3):
    data = {"form": {"token": "callback_t0k3n"}}

    _upload_to_s3(influencer=db_tax_form.influencer, data=data)

    mock_s3.put_object.assert_called_once()
    put_call = mock_s3.put_object.call_args_list[0]
    assert json.loads(put_call.kwargs["Body"]) == data

    mock_s3.upload_fileobj.assert_called_once()


def test_taxid_callback_test_notifies_slack(client, mock_signature, url):
    headers = {"Webhook-Signature": mock_signature}
    callback_test_reference = "abc123"
    data = _get_data_skeleton("w8ben", callback_test_reference)

    with mock.patch("takumi.views.task.slack.notify_debug") as mock_slack:
        client.post(url, json=data, headers=headers)

    mock_slack.assert_called_once()
