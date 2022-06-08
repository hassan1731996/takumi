import mock
import pytest

from takumi.bank.exceptions import BankException
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.bank import (
    REQUIRES_ADDRESS,
    RegisterGbAccount,
    RegisterIban,
    RegisterUsAccount,
    RegisterZaAccount,
)


def test_register_iban_mutation_raises_on_bank_exception(app, influencer_user, client) -> None:
    full_name = "John Doe"
    country_code = "de"
    iban = "de123123123"
    bic = "foobarxxx"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_iban", side_effect=BankException("Invalid details")
        ):
            with pytest.raises(
                MutationException, match=r"Unexpected error while adding payment details.*"
            ):
                RegisterIban().mutate(
                    "info", full_name=full_name, country_code=country_code, iban=iban, bic=bic
                )


def test_register_iban_mutation_raises_if_missing_address_when_required(
    app, client, influencer_user, influencer
) -> None:
    full_name = "John Doe"
    country_code = "de"
    iban = "de123123123"
    bic = "foobarxxx"

    influencer_user.influencer = influencer

    assert influencer.address is None

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_iban", side_effect=BankException("Inbalid details")
        ):
            with pytest.raises(
                MutationException, match=r"Unexpected error while adding payment details.*"
            ):
                RegisterIban().mutate(
                    "info", full_name=full_name, country_code=country_code, iban=iban, bic=bic
                )


def test_register_iban_mutation_calls_register(app, influencer_user, client) -> None:
    full_name = "John Doe"
    country_code = "de"
    iban = "de123 123 123"
    bic = "foobarxxx"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_iban",
            return_value={"destination": {"type": "revolut", "value": "xxx"}},
        ) as mock_register:
            response = RegisterIban().mutate(
                "info", full_name=full_name, country_code=country_code, iban=iban, bic=bic
            )

    assert response.destination_type == "revolut"
    assert response.destination_value == "xxx"

    mock_register.assert_called_with(
        full_name="John Doe", country_code="DE", iban="DE123123123", bic="FOOBARXXX"
    )


def test_register_iban_mutation_calls_register_with_address_if_required(
    app, client, influencer_user, influencer, address
) -> None:
    full_name = "John Doe"
    country_code = "ch"
    iban = "ch123123123"
    bic = "foobarxxx"

    influencer_user.influencer = influencer

    assert country_code.upper() in REQUIRES_ADDRESS
    assert influencer.address == address

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_iban",
            return_value={"destination": {"type": "revolut", "value": "xxx"}},
        ) as mock_register:
            response = RegisterIban().mutate(
                "info", full_name=full_name, country_code=country_code, iban=iban, bic=bic
            )

    assert response.destination_type == "revolut"
    assert response.destination_value == "xxx"

    mock_register.assert_called_with(
        full_name=full_name,
        country_code=country_code.upper(),
        iban="CH123123123",
        bic="FOOBARXXX",
        address=address,
    )


def test_register_gb_account_mutation_raises_on_bank_exception(
    app, influencer_user, client
) -> None:
    full_name = "John Doe"
    account_number = "12341234"
    sort_code = "010203"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_uk_account",
            side_effect=BankException("Inbalid details"),
        ):
            with pytest.raises(
                MutationException, match=r"Unexpected error while adding payment details.*"
            ):
                RegisterGbAccount().mutate(
                    "info", full_name=full_name, account_number=account_number, sort_code=sort_code
                )


def test_register_gb_account_mutation_calls_register(app, influencer_user, client) -> None:
    full_name = "John Doe"
    account_number = "12341234"
    sort_code = "010203"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_uk_account",
            return_value={"destination": {"type": "revolut", "value": "xxx"}},
        ) as mock_register:
            response = RegisterGbAccount().mutate(
                "info", full_name=full_name, account_number=account_number, sort_code=sort_code
            )

    assert response.destination_type == "revolut"
    assert response.destination_value == "xxx"

    mock_register.assert_called_with(
        full_name=full_name,
        country_code="GB",
        account_number=account_number,
        sort_code=sort_code,
    )


def test_register_us_account_mutation_raises_on_bank_exception(
    app, influencer_user, client
) -> None:
    full_name = "John Doe"
    bank_name = "The Bank"
    account_number = "12341234"
    routing_number = "54321"
    account_type = "savings"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_us_account",
            side_effect=BankException("Inbalid details"),
        ):
            with pytest.raises(
                MutationException, match=r"Unexpected error while adding payment details.*"
            ):
                RegisterUsAccount().mutate(
                    "info",
                    full_name=full_name,
                    bank_name=bank_name,
                    account_number=account_number,
                    routing_number=routing_number,
                    account_type=account_type,
                )


def test_register_us_account_mutation_calls_register(app, influencer_user, client) -> None:
    full_name = "John Doe"
    bank_name = "The Bank"
    account_number = "12341234"
    routing_number = "54321"
    account_type = "savings"

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_us_account",
            return_value={"destination": {"type": "dwolla", "value": "xxx"}},
        ) as mock_register:
            response = RegisterUsAccount().mutate(
                "info",
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
            )

    assert response.destination_type == "dwolla"
    assert response.destination_value == "xxx"

    mock_register.assert_called_with(
        full_name=full_name,
        bank_name=bank_name,
        account_number=account_number,
        routing_number=routing_number,
        account_type=account_type,
    )


def test_register_za_account_mutation_raises_on_bank_exception(
    app, client, influencer_user, influencer, address
) -> None:
    full_name = "John Doe"
    account_number = "12341234"
    bic = "foobarxxx"

    influencer_user.influencer = influencer
    influencer.address = address

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_za_account",
            side_effect=BankException("Inbalid details"),
        ):
            with pytest.raises(
                MutationException, match=r"Unexpected error while adding payment details.*"
            ):
                RegisterZaAccount().mutate(
                    "info", full_name=full_name, account_number=account_number, bic=bic
                )


def test_register_za_account_mutation_raises_if_no_address(
    app, client, influencer_user, influencer
) -> None:
    full_name = "John Doe"
    account_number = "12341234"
    bic = "foobarxxx"
    influencer_user.influencer = influencer

    assert influencer.address is None

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_iban", side_effect=BankException("Inbalid details")
        ):
            with pytest.raises(
                MutationException, match=r"Address is required for South African accounts.*"
            ):
                RegisterZaAccount().mutate(
                    "info", full_name=full_name, account_number=account_number, bic=bic
                )


def test_register_za_account_mutation_calls_register(
    app, client, influencer_user, influencer, address
) -> None:
    full_name = "John Doe"
    account_number = "12341234"
    bic = "foobarxxx"
    influencer_user.influencer = influencer
    influencer.address = address

    with client.user_request_context(influencer_user):
        with mock.patch(
            "takumi.gql.mutation.bank.register_za_account",
            return_value={"destination": {"type": "revolut", "value": "xxx"}},
        ) as mock_register:
            response = RegisterZaAccount().mutate(
                "info", full_name=full_name, account_number=account_number, bic=bic
            )

    assert response.destination_type == "revolut"
    assert response.destination_value == "xxx"

    mock_register.assert_called_with(
        full_name=full_name,
        account_number=account_number,
        bic=bic,
        address=address,
    )
