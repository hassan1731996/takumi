from flask import url_for

from takumi.gql.query.country import SUPPORTED_COUNTRIES


def test_supported_countries(client):
    resp = client.get(url_for("api.supported_countries"))

    assert "countries" in resp.json

    sorted_response = list(sorted(resp.json["countries"], key=lambda c: c["country_code"]))
    sorted_expected = list(
        sorted(
            [country.as_dict() for country in SUPPORTED_COUNTRIES], key=lambda c: c["country_code"]
        ),
    )
    assert sorted_response == sorted_expected
