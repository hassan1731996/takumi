from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.audit import (
    AuditClient,
    AuditException,
    AuditInfluencerNotFound,
    AuditPrivateUser,
    AuditTryLater,
)
from takumi.constants import MAX_AUDIT_AGE
from takumi.extensions import db, tiger
from takumi.models import Audit
from takumi.services import InfluencerService

AUDIT_QUEUE = f"{MAIN_QUEUE_NAME}.audit"


@tiger.task(unique=True, queue=AUDIT_QUEUE)
def create_audit(influencer_id, force=False):
    """Create audit for influencer

    This task in run on the shared queue to accommodate for the potential 10-30
    minute retry timer.

    An audit is only created if they don't have one within the last
    MAX_AUDIT_AGE days
    """
    influencer = InfluencerService.get_by_id(influencer_id)

    if not force and influencer.latest_audit and influencer.latest_audit.age < MAX_AUDIT_AGE:
        return

    client = AuditClient()

    try:
        audit = client.create_influencer_audit(influencer)
    except AuditTryLater as exc:
        # Audit isn't ready, retry in the reported TTL time
        raise RetryException(method=fixed(delay=exc.ttl, max_retries=10), log_error=False)
    except (AuditInfluencerNotFound, AuditPrivateUser, AuditException):
        return

    # Run PDF generation
    create_audit_pdf(audit.id)


@tiger.task(unique=True)
def create_audit_pdf(audit_id):
    """Get a PDF for an audit and update the audit to include the link"""

    client = AuditClient()
    audit = Audit.query.get_or_404(audit_id)

    audit.pdf = client.fetch_audit_pdf(audit.influencer)

    db.session.commit()
