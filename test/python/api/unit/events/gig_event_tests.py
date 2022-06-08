# encoding=utf-8

import pytest

from takumi.events import EventApplicationException
from takumi.events.gig import GigLog
from takumi.models.gig import STATES as GIG_STATES


def test_report_gig_reports_a_gig(app, gig):
    # Arrange
    gig.state = GIG_STATES.REVIEWED
    log = GigLog(gig)

    # Act
    log.add_event("report", {"reason": "Doesn't watch Rick and Morty"})

    # Assert
    assert gig.state == GIG_STATES.REPORTED
    assert gig.report_reason == "Doesn't watch Rick and Morty"


def test_report_gig_raises_exception_if_start_state_is_invalid(gig):
    # Arrange
    gig.state = GIG_STATES.REJECTED
    log = GigLog(gig)

    # Act
    with pytest.raises(EventApplicationException):
        log.add_event("report")

    # Assert
    assert gig.state == GIG_STATES.REJECTED


def test_reject_gig_rejects_a_gig(gig):
    # Arrange
    gig.state = GIG_STATES.REPORTED
    log = GigLog(gig)

    # Act
    log.add_event("reject", {"reason": "Doesn't watch TV"})

    # Assert
    assert gig.state == GIG_STATES.REJECTED
    assert gig.reject_reason == "Doesn't watch TV"
