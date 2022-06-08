import mock
import pytest

from takumi.audit import AuditClient
from takumi.constants import MAX_AUDIT_AGE


@pytest.fixture(scope="function")
def audit_client():
    yield AuditClient()


def test_audit_client_uses_local_example_if_token_is_local(app, influencer, monkeypatch):
    monkeypatch.setattr("takumi.audit.AuditService", mock.Mock())

    app.config["HYPEAUDITOR_AUTH_TOKEN"] = "local"

    with mock.patch.object(AuditClient, "_get_example_audit") as mock_example:
        with mock.patch.object(AuditClient, "_fetch_audit_by_username") as mock_real:
            client = AuditClient()

            client.create_influencer_audit(influencer)

    assert client.local == True
    assert mock_example.called
    assert not mock_real.called


def test_audit_client_uses_hypeaudit_api_if_token_given(app, influencer, monkeypatch):
    monkeypatch.setattr("takumi.audit.AuditService", mock.Mock())

    app.config["HYPEAUDITOR_AUTH_TOKEN"] = "a_different_token_thats_not_local"

    with mock.patch.object(AuditClient, "_get_example_audit") as mock_example:
        with mock.patch.object(AuditClient, "_fetch_audit_by_username") as mock_real:
            client = AuditClient()

            client.create_influencer_audit(influencer)

    assert client.local == False
    assert not mock_example.called
    assert mock_real.called


def test_audit_client_get_example_audit(app, influencer, monkeypatch):
    client = AuditClient()

    raw_audit = client._get_example_audit()

    assert raw_audit is not None
    assert raw_audit["followers_count"] == 25_436_910


def test_audit_client_creating_new_audit(app, influencer, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    app.config["HYPEAUDITOR_AUTH_TOKEN"] = "local"

    client = AuditClient()

    audit = client.create_influencer_audit(influencer)

    assert audit is not None
    demo = audit.followers_demography

    assert next(d["value"] for d in demo if d["name"] == "female") == pytest.approx(0.5964)
    assert next(d["value"] for d in demo if d["name"] == "male") == pytest.approx(0.4035)

    assert audit.engagement_rate == pytest.approx(0.0463)
    assert audit.audience_quality_score == 92

    reach = audit.followers_reach

    real = next(r["value"] for r in reach if r["name"] == "real")
    influencers = next(r["value"] for r in reach if r["name"] == "influencers")
    suspicious = next(r["value"] for r in reach if r["name"] == "suspicious_accounts")
    mass = next(r["value"] for r in reach if r["name"] == "mass_followers")

    assert real == pytest.approx(0.8037)
    assert suspicious == pytest.approx(0.0944)
    assert influencers == pytest.approx(0.0173)
    assert mass == pytest.approx(0.0847)


def test_get_fresh_audit_returns_latest_if_less_than_max_audit_age(client, audit_client):
    mock_influencer = mock.Mock()
    mock_influencer.latest_audit.age = MAX_AUDIT_AGE - 1

    audit = audit_client.get_fresh_influencer_audit(mock_influencer)

    assert audit == mock_influencer.latest_audit


def test_get_fresh_audit_creates_a_new_one_if_at_least_max_audit_age(client, audit_client):
    mock_influencer = mock.Mock()
    mock_influencer.latest_audit.age = MAX_AUDIT_AGE

    with mock.patch.object(audit_client, "create_influencer_audit") as mock_create:
        audit = audit_client.get_fresh_influencer_audit(mock_influencer)

    assert mock_create.called
    assert audit == mock_create.return_value


def test_transform_result_dividing_whole_numbers(client, audit_client):
    result = audit_client._get_example_audit()

    reach = result["followers_reach"]

    real = next(r["value"] for r in reach if r["name"] == "real")
    suspicious = next(r["value"] for r in reach if r["name"] == "suspicious_accounts")

    assert real == pytest.approx(0.8037)
    assert suspicious == pytest.approx(0.0944)
