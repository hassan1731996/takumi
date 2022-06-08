# encoding=utf-8
import mock
from flask import url_for


def raiser(cls):
    def _raise(*args, **kwargs):
        raise cls(error_details="test details")

    return _raise


def test_iban_calculate_returns_form_error_for_invalid_input(influencer_client, influencer):
    resp = influencer_client.post(url_for("api.calculate_iban"), data={})
    assert resp.status_code == 422


def test_register_bank_details_fails_if_iban_country_code_is_not_the_given_country_code(
    influencer_client, influencer
):
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={
            "bank_name": "Mocker",
            "iban": "GB1234",
            "full_name": "James Mock",
            "country_code": "US",
        },
    )
    assert resp.status_code == 422


def test_register_bank_details_calls_register_dwolla_if_given_ach_numbers(
    influencer_client, influencer
):
    with mock.patch("takumi.bank.register_dwolla_details") as mock_register_dwolla:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "full_name": "James Mock",
                "country_code": "us",
                "account_number": "1",
                "routing_number": "2",
                "account_type": "savings",
            },
        )
    assert resp.status_code == 200
    assert mock_register_dwolla.called


def test_register_bank_details_raises_form_error_if_neither_iban_nor_ach_numbers(
    influencer_client, influencer
):
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={"bank_name": "Mocker", "full_name": "James Mock", "country_code": "us"},
    )
    assert resp.status_code == 422


def test_register_bank_details_raises_form_error_if_both_iban_and_ach_numbers(
    influencer_client, influencer
):
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={
            "bank_name": "Mocker",
            "full_name": "James Mock",
            "country_code": "GB",
            "iban": "GB1233",
            "account_number": "1",
            "routing_number": "2",
        },
    )
    assert resp.status_code == 422


def test_register_bank_details_raises_form_error_if_full_name_cant_be_split(
    influencer_client, influencer
):
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={
            "bank_name": "Mocker",
            "full_name": "JamesMock",
            "country_code": "GB",
            "iban": "GB1233",
        },
    )
    assert resp.status_code == 422


def test_register_bank_details_only_accepts_account_number_and_sort_code(
    influencer_client, influencer
):
    with mock.patch("takumi.bank.register_revolut_account_number") as mock_register_revolut:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "full_name": "John Doe",
                "country_code": "GB",
                "account_number": "12341234",
                "sort_code": "040004",
            },
        )
    assert resp.status_code == 200
    assert mock_register_revolut.called


def test_register_bank_details_sanitises_name(influencer_client, influencer):
    with mock.patch("takumi.bank.register_revolut_account_number") as mock_register_revolut:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "full_name": "MR  JOHN   dOE  ",
                "country_code": "GB",
                "account_number": "12341234",
                "sort_code": "040004",
            },
        )
    assert resp.status_code == 200
    assert mock_register_revolut.called
    assert mock_register_revolut.call_args.kwargs["full_name"] == "Mr John Doe"


def test_register_bank_details_registers_revolut_with_iban_and_bic(
    influencer_client, influencer, monkeypatch
):
    monkeypatch.setattr("takumi.bank.validate_iban", lambda iban: True)

    with mock.patch("takumi.bank.register_revolut_iban") as mock_register_revolut_iban:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "iban": "DE1234",
                "bic": "foobar",
                "full_name": "James Mock",
                "country_code": "de",
            },
        )

    assert resp.status_code == 200
    assert mock_register_revolut_iban.called


def test_register_bank_details_with_south_african_details_requires_address(
    influencer_client, influencer
):
    assert influencer.address is None
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={
            "bank_name": "Mocker",
            "account_number": "12341234",
            "bic": "foobar",
            "full_name": "James Mock",
            "country_code": "za",
        },
    )

    assert resp.status_code == 400
    assert "Address is required for South African accounts" in resp.json["error"]["message"]


def test_register_bank_details_registers_revolut_with_south_african_details(
    influencer_client, influencer, address
):
    assert influencer.address is not None
    with mock.patch(
        "takumi.bank.register_revolut_south_africa"
    ) as mock_register_revolut_south_africa:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "account_number": "12341234",
                "bic": "foobar",
                "full_name": "James Mock",
                "country_code": "za",
            },
        )

    assert resp.status_code == 200
    assert mock_register_revolut_south_africa.called

    submitted_address = mock_register_revolut_south_africa.call_args_list[0].kwargs["address"]
    assert submitted_address["street_line1"] == address.address1
    assert submitted_address["city"] == address.city
    assert submitted_address["country"] == address.country


def test_register_bank_details_with_swiss_details_requires_address(influencer_client, influencer):
    assert influencer.address is None
    resp = influencer_client.post(
        url_for("api.register_bank_details"),
        data={
            "bank_name": "Mocker",
            "iban": "CH0123456789012345678",
            "bic": "foobar",
            "full_name": "James Mock",
            "country_code": "CH",
        },
    )

    assert resp.status_code == 400
    assert "Address is required for bank accounts in your country." in resp.json["error"]["message"]


def test_register_bank_details_registers_revolut_with_swiss_details(
    influencer_client, influencer, address, monkeypatch
):
    monkeypatch.setattr("takumi.bank.validate_iban", lambda iban: True)

    assert influencer.address is not None
    with mock.patch("takumi.bank.register_revolut_iban") as mock_register_revolut_iban:
        resp = influencer_client.post(
            url_for("api.register_bank_details"),
            data={
                "bank_name": "Mocker",
                "iban": "CH0123456789012345678",
                "bic": "foobar",
                "full_name": "James Mock",
                "country_code": "CH",
            },
        )

    assert resp.status_code == 200
    assert mock_register_revolut_iban.called

    submitted_address = mock_register_revolut_iban.call_args_list[0].kwargs["address"]
    assert submitted_address["street_line1"] == address.address1
    assert submitted_address["city"] == address.city
    assert submitted_address["country"] == address.country
