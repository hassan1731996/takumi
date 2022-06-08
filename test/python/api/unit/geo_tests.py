import mock
from flask import Flask

from core.geo.geo import GeoRequest


def test_request_country_code():
    with mock.patch("core.geo.geo.GeoRequest.geo_ip") as MockGeoIP:
        MockGeoIP.city.return_value.country.iso_code = "GB"

        app = Flask(__name__)
        geo_request = GeoRequest(app)
        for ip in ("1.1.1.1", "1.1.1.1,", "1.1.1.1,1.1.1.1"):
            with app.test_request_context(headers={"X-Forwarded-For": ip}):
                assert geo_request.country_code() == "GB"
        with app.test_request_context():
            assert geo_request.country_code() is None
        with app.test_request_context(headers={"X-Forwarded-For": ""}):
            assert geo_request.country_code() is None


def test_request_city():
    app = Flask(__name__)
    geo_request = GeoRequest(app)
    with mock.patch("core.geo.geo.GeoRequest.geo_ip") as MockGeoIP:
        MockGeoIP.city.return_value.city.names = {"en": "London"}

        with app.test_request_context(headers={"X-Forwarded-For": "1.2.3.4"}):
            assert geo_request.city() == "London"
        with app.test_request_context():
            assert geo_request.city() is None
