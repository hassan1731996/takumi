# encoding=utf-8

from takumi.i18n import format_currency


def test_format_currency_eur():
    assert format_currency(200_000, "EUR") == "2.000 €"


def test_format_currency_gbp():
    assert format_currency(200_000, "GBP") == "£2,000"


def test_format_currency_usd():
    assert format_currency(200_000, "USD") == "$2,000"


def test_format_currency_removes_fractions_by_default():
    assert format_currency(123, "GBP") == "£1"


def test_format_currency_keeps_fractions_if_currency_digits_true():
    assert format_currency(123, "GBP", True) == "£1.23"


def test_format_currency_defaults_to_gbp_but_zeroes_amount():
    assert format_currency(100, "ISK") == "£0"


def test_format_currency_empty_string_currency():
    assert format_currency(123, "") == "£0"
