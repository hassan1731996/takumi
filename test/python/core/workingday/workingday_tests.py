# encoding=utf-8

import datetime as dt

from core.workingday import WorkingDay


def test_payable_date_class_rollforward_at_1330_on_saturday_works():
    submitted = dt.datetime(2015, 11, 28, 13, 30, 0)
    expected_result = dt.datetime(2015, 12, 2, 0, 0, 0)
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result


def test_payable_date_class_rollforward_at_1330_on_christmas_day_works():
    submitted = dt.datetime(2015, 12, 25, 13, 30, 00)
    # 25. is christmas day, 26. is the second day of christmas, 27. is a sunday
    # and 28. is "boxing day shift"
    expected_result = dt.datetime(2015, 12, 31, 0, 0, 0)
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result


def test_payable_date_class_rollforward_at_1330_on_a_normal_monday():
    submitted = dt.datetime(2015, 11, 30, 13, 30, 00)  # monday afternoon
    expected_result = dt.datetime(2015, 12, 2, 13, 30, 00)  # wednesday afternoon
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result


def test_payable_date_class_rollforward_at_1530_on_sunday_works():
    submitted = dt.datetime(2015, 11, 29, 15, 30, 00)  # sunday afternoon
    expected_result = dt.datetime(2015, 12, 2, 0, 0, 0)  # wednesday morning
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result


def test_payable_date_class_rollforward_at_1430_on_friday_works():
    submitted = dt.datetime(2015, 11, 27, 14, 30, 00)  # friday afternoon
    expected_result = dt.datetime(2015, 12, 1, 14, 30, 00)  # tuesday afternoon
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result


def test_payable_date_class_rollforward_with_one_holiday_working_day_and_weekend_between():
    submitted = dt.datetime(2014, 12, 31, 13, 30, 00)
    expected_result = dt.datetime(2015, 1, 5, 13, 30, 00)
    pd = WorkingDay("en_GB")
    result = pd.add_working_hours(submitted, delta=48)
    assert result == expected_result
