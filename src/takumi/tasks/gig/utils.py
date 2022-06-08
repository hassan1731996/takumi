from takumi import slack
from takumi.models import Gig


def report_gig(gig: Gig, reason: str) -> None:
    from takumi.services import GigService
    from takumi.services.exceptions import ServiceException

    if gig.state == Gig.STATES.REPORTED:
        return  # do not re-report

    if not gig.autoreport:
        # Forced through
        return

    # Check if there is a prior report for the same reason
    for event in gig.events:
        if event.type != "report":
            continue
        if event.event["reason"] == reason and event.creator_user is None:
            # exit early
            return

    try:
        with GigService(gig) as service:
            service.report_gig(reason=reason)
    except ServiceException as e:
        slack.gig_log_exception(gig, e)
