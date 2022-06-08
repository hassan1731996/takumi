import pytest

from takumi.models import Currency


def test_currency_formatted_value_with_precision(app):
    round_down_currency = Currency(amount=12345, currency="GBP", currency_digits=False)
    round_up_currency = Currency(amount=12355, currency="GBP", currency_digits=False)
    precision_currency = Currency(amount=12345, currency="GBP", currency_digits=True)

    assert round_down_currency.formatted_value == "£123"
    assert round_up_currency.formatted_value == "£124"
    assert precision_currency.formatted_value == "£123.45"


@pytest.mark.parametrize(
    "currency,formatted",
    [
        ("GBP", "£12,345.67"),
        ("USD", "$12,345.67"),
        ("EUR", "12.345,67\xa0€"),
        ("ZAR", "R\xa012\xa0345,67"),
    ],
)
def test_currency_formatted_value(app, currency, formatted):
    obj = Currency(amount=1234567, currency=currency, currency_digits=True)

    assert obj.formatted_value == formatted
