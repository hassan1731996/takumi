import datetime as dt

from takumi.schedule import DateTimePeriod, WorkingTimePeriod


def test_date_time_period_after():
    start = dt.datetime(2018, 1, 1, 0, 0)
    assert DateTimePeriod(hours=24).after(start) == dt.datetime(2018, 1, 2, 0, 0)


def test_working_date_time_period_after():
    """January 1st is a bank holiday in the UK"""
    start = dt.datetime(2018, 1, 1, 0, 0)
    assert WorkingTimePeriod(locale="en_GB", days=1).after(start) == dt.datetime(2018, 1, 3, 0, 0)


def test_working_date_time_period_before_is_at_least_period():
    for day in range(1, 7):
        start = dt.datetime(2018, 1, day, 23, 59)
        period = WorkingTimePeriod(locale="en_GB", days=7)
        assert start - period.before(start) >= dt.timedelta(hours=24 * 7)


def test_working_date_time_period_after_is_at_least_period():
    for day in range(1, 7):
        start = dt.datetime(2018, 1, day, 23, 59)
        period = WorkingTimePeriod(locale="en_GB", days=7)
        assert period.after(start) - start >= dt.timedelta(hours=24 * 7)
