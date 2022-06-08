# encoding=utf-8
import mock
from flask import json, url_for

from takumi.models import EmailLead
from takumi.utils import uuid4_str


def test_email_leads_get(client):
    with mock.patch("flask_sqlalchemy.BaseQuery.get_or_404") as m:
        m.return_value = EmailLead()
        response = client.get(url_for("api.inbound", id=uuid4_str()))
    assert response.status_code == 200
    assert "id" in response.json


def test_email_leads(client, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        mock_first.return_value = None
        with mock.patch("sqlalchemy.orm.session.Session.add") as mock_add:
            response = client.post(
                url_for("api.submit_email_lead"),
                data=json.dumps(
                    {
                        "first_name": "What",
                        "last_name": "A. Name",
                        "job_title": "Test extraordinaire",
                        "company": "Test ehf",
                        "industry": "Food",
                        "email": "tester@test.is",
                        "phone_number": "5671234",
                        "country": "America land",
                    }
                ),
                headers={"content-type": "application/json"},
            )
    assert response.status_code == 200
    assert mock_add.called
    email_lead = mock_add.call_args[0][0]
    assert email_lead.email == "tester@test.is"
    assert email_lead.company == "Test ehf"
    assert response.json["valued"]


def test_email_leads_returns_error_if_email_exists(client, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    existing_lead = EmailLead(id=uuid4_str(), email="tester@test.is")
    with mock.patch("sqlalchemy.orm.session.Session.add"):
        with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
            mock_first.return_value = existing_lead
            response = client.post(
                url_for("api.submit_email_lead"),
                data=json.dumps(
                    {
                        "first_name": "What",
                        "last_name": "A. Name",
                        "job_title": "Test extraordinaire",
                        "company": "Test ehf",
                        "industry": "Food",
                        "email": "tester@test.is",
                        "phone_number": "5671234",
                        "country": "America land",
                    }
                ),
                headers={"content-type": "application/json"},
            )
    assert response.status_code == 200
    # assert not response.json["valued"]
