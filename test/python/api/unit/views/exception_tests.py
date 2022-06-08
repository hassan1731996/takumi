from flask import url_for


def test_unsupported_content_type(client):
    response = client.post(url_for("api.login"))
    assert response.status_code == 415
    assert response.content_type == "application/json"
