from takumi.events import Event, EventApplicationException


class FailEvent(Event):
    def apply(self, subject):
        raise EventApplicationException("I am a dummy")


class PassEvent(Event):
    def apply(self, subject):
        pass


class StateEvent(Event):
    start_state = "start"
    end_state = "end"

    def apply(self, subject):
        pass
