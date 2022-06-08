import json
import os

from core.testing.flask_client import TestClient as _TestClient

from takumi.app import create_app
from takumi.error_codes import MAINTENANCE_MODE


def test_maintenance_mode_for_nonexistent_path():
    os.environ["MAINTENANCE_MESSAGE"] = "Takumi is down for maintenance"
    app = create_app(testing=True)
    with app.test_request_context():
        app.test_client_class = _TestClient
        client = app.test_client()
        resp = client.get("/anything")
        assert resp.status_code == 503
        assert json.loads(resp.data)["error"]["message"] == "Takumi is down for maintenance"


def test_maintenance_mode_for_existing_path():
    os.environ["MAINTENANCE_MESSAGE"] = "System of a down is Takumi"
    app = create_app(testing=True)
    with app.test_request_context():
        app.test_client_class = _TestClient
        client = app.test_client()
        resp = client.get("/posts")
        assert resp.status_code == 503
        assert json.loads(resp.data)["error"]["message"] == "System of a down is Takumi"


def test_maintenance_mode_includes_error_code():
    os.environ["MAINTENANCE_MESSAGE"] = "Takumi is down for maintenance"
    app = create_app(testing=True)
    with app.test_request_context():
        app.test_client_class = _TestClient
        client = app.test_client()
        resp = client.get("/something")
        assert resp.status_code == 503
        assert json.loads(resp.data)["error"]["code"] == MAINTENANCE_MODE


def test_maintenance_mode_for_exempt_path():
    os.environ["MAINTENANCE_MESSAGE"] = "Takumi is down for maintenance"
    app = create_app(testing=True)
    with app.test_request_context():
        app.test_client_class = _TestClient
        client = app.test_client()
        resp = client.get("/status")
        assert resp.status_code == 200
