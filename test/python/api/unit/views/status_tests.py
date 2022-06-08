import mock
import psycopg2
import sqlalchemy
from flask import url_for


def _fake_execute_raises_exception(*args, **kwargs):
    raise psycopg2.OperationalError("test")


def test_status_db_not_accessible(monkeypatch, client):
    monkeypatch.setattr(
        sqlalchemy.engine.base.Connection, "execute", _fake_execute_raises_exception
    )
    monkeypatch.setattr("takumi.views.status.tiger_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.redis_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.instascrape_status", lambda: {"healthy": True})

    response = client.get(url_for("api.server_status"))
    assert response.status_code == 500
    assert response.json["services"]["db"]["healthy"] is False


def test_status_one_unhealthy_status_causes_500(monkeypatch, client):
    monkeypatch.setattr("takumi.views.status.db_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.tiger_status", lambda: {"healthy": False})
    monkeypatch.setattr("takumi.views.status.redis_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.instascrape_status", lambda: {"healthy": True})

    response = client.get(url_for("api.server_status"))
    assert response.status_code == 500
    assert response.json["services"]["db"]["healthy"] is True
    assert response.json["services"]["tiger"]["healthy"] is False


def test_status_sends_status_to_sentry_if_not_all_healthy(monkeypatch, client):
    monkeypatch.setattr("takumi.views.status.db_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.tiger_status", lambda: {"healthy": False})
    monkeypatch.setattr("takumi.views.status.redis_status", lambda: {"healthy": True})
    monkeypatch.setattr("takumi.views.status.instascrape_status", lambda: {"healthy": True})

    with mock.patch("takumi.views.status.capture_message") as mock_sentry_msg:
        response = client.get(url_for("api.server_status"))
    assert response.status_code == 500
    assert mock_sentry_msg.called
