from unittest import TestCase

import mock
import pytest

from takumi.events import (
    ColumnLog,
    EventApplicationException,
    InvalidLogSubject,
    InvalidStartStateException,
    TableLog,
    UnsupportedEventException,
)

from . import FailEvent, PassEvent, StateEvent


class _TestColumnLog(ColumnLog):
    type_map = {"failing": FailEvent, "passing": PassEvent, "state": StateEvent}


class _TestTableLog(TableLog):
    event_model = mock.MagicMock()
    relation = "influencer"
    type_map = {"failing": FailEvent, "passing": PassEvent, "state": StateEvent}


class InvalidFakeSubject:
    pass


class FakeSubject:
    def __init__(self, events=None):
        self.events = events
        self.state = "start"


class ColumnLogTests(TestCase):
    def setUp(self):
        self.subject = FakeSubject()
        self.log = _TestColumnLog(self.subject)

    def test_add_event_raises_unsupportedeventexception_on_invalid_event_type(self):
        with pytest.raises(UnsupportedEventException):
            self.log.add_event("this is not a valid event type", {})

    def test_log_initializes_with_empty_errors(self):
        b = _TestColumnLog(self.subject)
        assert b.errors == []

    def test_log_initializes_post_events_to_array_if_necessary(self):
        self.subject.events = None
        _TestColumnLog(self.subject)
        assert self.subject.events == []

    def test_log_raises_eventapplicationexception_if_apply_fails(self):
        with pytest.raises(EventApplicationException) as error:
            self.log.add_event("failing")
        assert str(error.value) == "I am a dummy"

    def test_log_raises_invalidlogsubject_if_subject_has_no_events_member(self):
        with pytest.raises(InvalidLogSubject):
            _TestColumnLog(InvalidFakeSubject())

    def test_log_raises_invalidlogsubject_if_subject_has_invalid_event_type(self):
        subject = InvalidFakeSubject()
        subject.events = "invalid_type"
        with pytest.raises(InvalidLogSubject):
            _TestColumnLog(subject)

    def test_log_ensure_start_state_throws_on_invalid_start_state(self):
        log = _TestColumnLog(self.subject)
        self.subject.state = "invalid_state"
        with pytest.raises(InvalidStartStateException):
            log.add_event("state", {})

    def test_log_ensure_end_state_sets_end_state(self):
        log = _TestColumnLog(self.subject)
        self.subject.state = "start"
        log.add_event("state", {})
        assert self.subject.state == "end"


class TableLogTests(TestCase):
    def setUp(self):
        self.subject = FakeSubject()
        self.log = _TestTableLog(self.subject)

    def test_add_event_creates_db_event(self):
        self.log.add_event("passing", {"extra_data": "data"})
        call_args = self.log.event_model.call_args_list[0][1]

        assert "type" in call_args
        assert "event" in call_args
        assert "extra_data" in call_args["event"]

    def test_add_event_raises_on_invalid_event(self):
        with pytest.raises(UnsupportedEventException):
            self.log.add_event("unknown", {})


class EventTests(TestCase):
    def test_logevent_repr_contains_properties(self):
        event = PassEvent({"this": "is a property"})
        assert "is a property" in str(event)


def test_log_discards_if_none_default_values(advertiser_user, client):
    subject = FakeSubject()
    log = _TestColumnLog(subject)
    with client.use(advertiser_user):
        log.add_event("passing", {})
    assert len(subject.events) == 1


def test_log_allows_force_to_ignore_start_state(app):
    obj = FakeSubject()

    log = _TestColumnLog(obj)
    log.add_event("state")
    assert obj.state == "end"
    assert obj.events[0]["_forced"] == False

    obj.state = "invalid"
    log = _TestColumnLog(obj)
    with pytest.raises(InvalidStartStateException):
        log.add_event("state")

    assert obj.state == "invalid"

    log.add_event("state", force=True)

    assert obj.state == "end"
    assert obj.events[1]["_forced"] == True
