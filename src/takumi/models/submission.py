from typing import TYPE_CHECKING

from sqlalchemy import DDL, event, func
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Gig, Media  # noqa


class Submission(db.Model):
    __tablename__ = "submission"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    transcoded = db.Column(db.Boolean, default=False)

    caption = db.Column(db.String, nullable=False)

    media = relationship(
        "Media",
        primaryjoin="and_(Submission.id == foreign(Media.owner_id), Media.owner_type == 'submission')",
        order_by="Media.order",
        backref="submission",
    )

    gig_id = db.Column(UUIDString, db.ForeignKey("gig.id", ondelete="restrict"), nullable=False)
    gig = relationship("Gig", back_populates="submissions")

    def __repr__(self):
        return f"<Submission: {self.id} ({self.gig})>"


# fmt: off
submission_triggers = DDL("""
CREATE TRIGGER cascade_submission_delete_media
AFTER DELETE ON submission
FOR EACH ROW EXECUTE PROCEDURE delete_related_media('submission');

CREATE TRIGGER cascade_submission_update_media
AFTER UPDATE ON submission
FOR EACH ROW EXECUTE PROCEDURE update_related_media('submission');
""")
# fmt: on
event.listen(
    Submission.__table__, "after_create", submission_triggers.execute_if(dialect="postgresql")  # type: ignore
)
