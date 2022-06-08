from takumi.extensions import db
from takumi.models import Audit
from takumi.services import Service


class AuditService(Service):
    """
    Represents the business model for Audit. This isolates the database
    from the application.
    """

    SUBJECT = Audit

    @property
    def audit(self):
        return self.subject

    # POST
    @staticmethod
    def create(influencer, raw_audit):
        audit = Audit(influencer=influencer, **raw_audit)

        db.session.add(audit)
        db.session.commit()

        return audit
