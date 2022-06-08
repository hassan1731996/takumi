import datetime as dt

from core.workingday import WorkingDay


class Period:
    def after(self, start):
        """
        Returns a datetime that represents a period after the start time
        """
        raise NotImplementedError()

    def before(self, start):
        """
        Returns a datetime that represents a period before the start time
        """
        raise NotImplementedError()


class DateTimePeriod(Period):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def after(self, start: dt.datetime) -> dt.datetime:
        return start + dt.timedelta(**self.kwargs)

    def before(self, start: dt.datetime) -> dt.datetime:
        return start - dt.timedelta(**self.kwargs)


class WorkingTimePeriod(Period):
    def __init__(self, locale: str, days: int) -> None:
        self.locale = locale
        self.hours = days * 24

    def after(self, start: dt.datetime) -> dt.datetime:
        return WorkingDay(self.locale).add_working_hours(start, self.hours)

    def before(self, start: dt.datetime) -> dt.datetime:
        return WorkingDay(self.locale).subtract_working_hours(start, self.hours)
