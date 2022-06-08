from sqlalchemy import func
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db


class EmailLead(db.Model):
    """Collections of emails gathered from takumi.com/brands"""

    __tablename__ = "email_leads"

    id = db.Column(UUIDString, primary_key=True)
    created = db.Column(UtcDateTime, server_default=func.now())
    email = db.Column(db.String, nullable=False)
    company = db.Column(db.String)
    name = db.Column(db.String)
    job_title = db.Column(db.String)
    phone_number = db.Column(db.String)
    campaign_ref = db.Column(db.String)
