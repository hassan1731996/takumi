import datetime as dt

from takumi.taxes.util.tax_years import get_tax_year_range_for_country_code


def test_get_tax_year_range_for_country_code_returns_default_for_missing_country_code():
    start = dt.date(2000, 1, 1)
    end = dt.date(2000, 12, 31)
    assert (start, end) == get_tax_year_range_for_country_code(None, 2000)


def test_get_tax_year_range_for_country_code_returns_default_for_a_unknown_country_code():
    start = dt.date(2000, 1, 1)
    end = dt.date(2000, 12, 31)
    assert (start, end) == get_tax_year_range_for_country_code("LALA-land", 2000)


def test_get_tax_year_range_for_country_code_returns_6th_of_april_as_tax_year_for_gb():
    start = dt.date(2000, 4, 6)
    end = dt.date(2001, 4, 5)
    assert (start, end) == get_tax_year_range_for_country_code("GB", 2000)
