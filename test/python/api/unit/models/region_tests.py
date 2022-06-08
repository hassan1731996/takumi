# encoding=utf-8
import datetime as dt

from takumi.models import Region


def test_region_with_unknown_locale_returns_none():
    region = Region(name="Unknown Land")
    region.locale_code = "xx_XX"
    assert region.locale is None


def test_region_get_vat_percentage_multiple_values(region: Region) -> None:
    region._vat_percentages = [
        {"start_date": None, "end_date": "2020-06-30", "value": 0.19},
        {"start_date": "2020-07-01", "end_date": "2020-12-31", "value": 0.16},
        {"start_date": "2021-01-01", "end_date": None, "value": 0.19},
    ]

    assert region.get_vat_percentage(dt.date(2020, 6, 29)) == 0.19
    assert region.get_vat_percentage(dt.date(2020, 6, 30)) == 0.19

    assert region.get_vat_percentage(dt.date(2020, 7, 1)) == 0.16
    assert region.get_vat_percentage(dt.date(2020, 7, 2)) == 0.16
    assert region.get_vat_percentage(dt.date(2020, 12, 30)) == 0.16
    assert region.get_vat_percentage(dt.date(2020, 12, 31)) == 0.16

    assert region.get_vat_percentage(dt.date(2021, 1, 1)) == 0.19
    assert region.get_vat_percentage(dt.date(2021, 1, 2)) == 0.19


def test_region_get_vat_percentage_with_single_value(region: Region) -> None:
    region._vat_percentages = [
        {"start_date": None, "end_date": None, "value": 0.21},
    ]

    assert region.get_vat_percentage(dt.date(2020, 6, 29)) == 0.21


def test_region_get_vat_percentage_with_no_value(region: Region) -> None:
    region._vat_percentages = []

    assert region.get_vat_percentage(dt.date(2020, 6, 29)) == None
