import datetime as dt
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Any, Dict, Sequence, Union

from flask_login import current_user


class EventException(Exception):
    pass


class UnsupportedEventException(EventException):
    pass


class EventApplicationException(EventException):
    pass


class InvalidStartStateException(EventApplicationException):
    pass


class InvalidStateException(EventApplicationException):
    pass


EventState = Union[str, None]


class Event(metaclass=ABCMeta):
    properties: Dict[str, Any]
    start_state: Union[EventState, Sequence[EventState]] = None
    end_state: EventState = None

    def __init__(self, properties: Dict):
        self.properties = properties

    @abstractmethod
    def apply(self, subject):
        """Apply an event to a subject.

        :param subject:  The subject on which to apply the event
        :raises EventApplicationException:
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}:\n{self.properties}>"


class LogException(Exception):
    pass


class InvalidLogSubject(LogException):
    pass


class Log(metaclass=ABCMeta):
    """A Log applies events to its subject, this is the "abstract" parent class, which can't be
    used directly.

    Classes implementing a Log need to implement `make_event` and `log_event`, and optionally `apply_event`.
    When a log adds an event, the general flow is:
        * make_event(..)   - creates the Event object and adds any extra metadata to the event data
        * apply_event(..)  - calls event.apply() and ensures states.  The parent implementation is fine here.
        * log_event(..)    - logs the event on the subject.

    This abstract class is not opinionated on how the events get created or logged, as those are
    details which should be taken care of by the implementation.
    """

    def __init__(self, subject):
        if "events" not in dir(subject):
            raise InvalidLogSubject(f"Log ({self}) got invalid subject: `{subject}` (no events)")
        self.subject = subject
        self.errors = []

    def _ensure_start_state(self, event):
        if event.start_state is not None:
            if isinstance(event.start_state, str):
                start_states = [event.start_state]
            else:
                start_states = event.start_state
            if self.subject.state not in start_states:
                raise InvalidStartStateException(
                    "Unable to apply `{}` to `{}`, start state `{}` is not in {}".format(
                        event, self.subject, self.subject.state, start_states
                    )
                )

    def _ensure_end_state(self, event):
        if event.end_state is not None:
            self.subject.state = event.end_state

    def apply_event(self, event, *, ignore_start_state=False):
        if not ignore_start_state:
            self._ensure_start_state(event)
        event.apply(self.subject)
        self._ensure_end_state(event)
        self.subject.modified = dt.datetime.now(dt.timezone.utc)

    def add_event(self, event_type, event_data=None, *, force=False):
        """Adds an event to the subject

        :param event_type:  type of event (string)
        :param event_data:  the event properties (dict)
        :param ignore_start_state: force the state change (bool)
        :returns:  boolean indicating whether there was an error encountered or not
        """

        if event_data is None:
            event_data = {}
        else:
            event_data = deepcopy(event_data)  # avoid leaking any mutations

        event = self.make_event(event_type, event_data, force=force)

        from_state = getattr(self.subject, "state", None)
        self.apply_event(event, ignore_start_state=force)
        to_state = getattr(self.subject, "state", None)

        if from_state != to_state:
            event_data["_from_state"] = from_state
            event_data["_to_state"] = to_state

        self.log_event(event_type, event_data)

    @property
    def errored(self):
        """:returns:  boolean indicating whether this builder has encountered errors"""
        return len(self.errors) > 0


class ColumnLog(Log):
    """A log that applies events and logs them to an `events` column"""

    def __init__(self, subject, *args, **kwargs):
        super().__init__(subject, *args, **kwargs)
        if not isinstance(subject.events, list) and subject.events is not None:
            raise InvalidLogSubject(
                "Log ({}) got invalid subject: `{}`.events=`{}`".format(
                    self, subject, type(subject.events)
                )
            )

        if self.subject.events is None:
            self.subject.events = []

    def make_event(self, event_type, event_data, force):
        if current_user and hasattr(current_user, "id"):
            event_data["_user_id"] = current_user.id

        event_data["_type"] = event_type
        event_data["_created"] = dt.datetime.now(dt.timezone.utc).isoformat()
        event_data["_forced"] = force
        try:
            return self.type_map[event_type](event_data)
        except KeyError as exc:
            raise UnsupportedEventException(f"{exc} is not a supported event type")

    def log_event(self, event_type, event_data):
        self.subject.events.append(event_data)


class TableLog(Log):
    """A log that that persists events in a event table"""

    def make_event(self, event_type, event_data, force):
        event_data["_type"] = event_type
        event_data["_created"] = dt.datetime.now(dt.timezone.utc).isoformat()
        event_data["_forced"] = force
        try:
            return self.type_map[event_type](event_data)
        except KeyError as exc:
            raise UnsupportedEventException(f"{exc} is not a supported event type")

    def log_event(self, event_type, event_data):
        args = dict(type=event_type, event=event_data)
        args[self.relation] = self.subject
        db_event_obj = self.event_model(**args)

        if current_user and hasattr(current_user, "id"):
            db_event_obj.creator_user = current_user
