import mock
import pytest

from takumi.bank.dwolla import register_dwolla_details
from takumi.bank.exceptions import InvalidDetailsException
from takumi.bank.revolut import register_revolut_account_number


def test_register_dwolla_routing_number(client, influencer_user, monkeypatch):
    monkeypatch.setattr(
        "takumi.bank.dwolla.dwolla.get_customer_by_email",
        lambda email: mock.Mock(bank_account=None),
    )
    monkeypatch.setattr(
        "takumi.bank.dwolla.register_hashed_bank_destination", lambda *args, **kwargs: None
    )
    full_name = "John Doe"
    bank_name = "Test Bank"
    account_number = "000000000"
    account_type = "Test Account"

    # Too short
    routing_number = "12345678"
    with pytest.raises(InvalidDetailsException, match="Routing number has to be exactly 9 digits"):
        with client.user_request_context(influencer_user):
            register_dwolla_details(
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
                influencer=influencer_user,
            )

    # Too long
    routing_number = "1234567890"
    with pytest.raises(InvalidDetailsException, match="Routing number has to be exactly 9 digits"):
        with client.user_request_context(influencer_user):
            register_dwolla_details(
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
                influencer=influencer_user,
            )

    # Letters
    routing_number = "12E456789"
    with pytest.raises(InvalidDetailsException, match="Routing number has to be exactly 9 digits"):
        with client.user_request_context(influencer_user):
            register_dwolla_details(
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
                influencer=influencer_user,
            )

    # Valid
    routing_number = "123456789"
    with mock.patch("takumi.bank.dwolla.dwolla.create_customer_bank_account") as mock_add:
        with client.user_request_context(influencer_user):
            register_dwolla_details(
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
                influencer=influencer_user,
            )
    assert mock_add.called


def test_register_revolut_details_rejects_invalid_account_number(
    client, influencer_user, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr(
        "takumi.bank.revolut.revolut.add_counterparty", lambda *args, **kwargs: mock.Mock()
    )
    form = {"full_name": "John Doe", "country_code": "GB", "sort_code": "04-00-04"}

    # Too short
    form["account_number"] = "1234"
    with pytest.raises(InvalidDetailsException, match="Account number has to be exactly 8 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Too long
    form["account_number"] = "123412341234"
    with pytest.raises(InvalidDetailsException, match="Account number has to be exactly 8 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Letters
    form["account_number"] = "12E4I234"
    with pytest.raises(InvalidDetailsException, match="Account number has to be exactly 8 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Valid
    form["account_number"] = " 12341234 "
    with mock.patch("takumi.bank.revolut.revolut.add_counterparty") as mock_add:
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    assert mock_add.called


def test_register_revolut_details_rejects_invalid_sort_code(client, influencer_user, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr(
        "takumi.bank.revolut.revolut.add_counterparty", lambda *args, **kwargs: mock.Mock()
    )
    form = {"full_name": "John Doe", "country_code": "GB", "account_number": "12341234"}

    # Too short
    form["sort_code"] = "12345"
    with pytest.raises(InvalidDetailsException, match="Sort code has to be exactly 6 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Too long
    form["sort_code"] = "1234567"
    with pytest.raises(InvalidDetailsException, match="Sort code has to be exactly 6 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Letters
    form["sort_code"] = "I2E456"
    with pytest.raises(InvalidDetailsException, match="Sort code has to be exactly 6 digits"):
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)

    # Valid
    influencer_user.revolut_counterparty_id = None
    form["sort_code"] = " 123456 "
    with mock.patch("takumi.bank.revolut.revolut.add_counterparty") as mock_add:
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)
    assert mock_add.called

    # Valid with dashes
    influencer_user.revolut_counterparty_id = None
    form["sort_code"] = " 12-34-56 "
    with mock.patch("takumi.bank.revolut.revolut.add_counterparty") as mock_add:
        with client.user_request_context(influencer_user):
            register_revolut_account_number(**form)
    assert mock_add.called
