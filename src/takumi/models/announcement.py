from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .helpers import hybrid_method_subquery

influencers_seen_announcements = db.Table(
    "influencers_seen_announcements",
    db.Model.metadata,
    db.Column("influencer_id", UUIDString, db.ForeignKey("influencer.id"), primary_key=True),
    db.Column("announcement_id", UUIDString, db.ForeignKey("announcement.id"), primary_key=True),
)


class Announcement(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    active = db.Column(db.Boolean, default=False)

    title = db.Column(db.String, nullable=False)
    message = db.Column(db.String, nullable=False)

    button_action = db.Column(db.String, nullable=True)
    button_action_props = db.Column(
        MutableDict.as_mutable(JSONB), nullable=False, server_default="{}"
    )

    translations = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    influencers_seen = db.relationship(
        "Influencer", secondary=influencers_seen_announcements, lazy="select"
    )

    def see_announcement(self, influencer):
        if self.seen_by_influencer(influencer):
            return
        db.session.execute(
            influencers_seen_announcements.insert(),
            dict(influencer_id=influencer.id, announcement_id=self.id),
        )
        db.session.commit()

    @hybrid_method_subquery
    def seen_by_influencer(cls, influencer):
        AliasedAnnouncement = aliased(cls)
        return (
            db.session.query(func.count(AliasedAnnouncement.id) > 0)
            .join(influencers_seen_announcements)
            .filter(
                influencers_seen_announcements.c.influencer_id == influencer.id,
                AliasedAnnouncement.id == cls.id,
            )
        )
