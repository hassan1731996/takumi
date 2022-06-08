import datetime as dt
from typing import TYPE_CHECKING, Optional

import sqlalchemy
from babel import negotiate_locale
from flask import current_app
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Index
from sqlalchemy.sql.expression import cast
from sqlalchemy_searchable import vectorizer
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableSet, SimpleTSVectorType, SoftEnum, UUIDString

from takumi.extensions import db
from takumi.feature_flags import FLAGS
from takumi.roles import get_need_from_name, get_role_from_name
from takumi.utils import uuid4_str

from .helpers import hybrid_property_expression

if TYPE_CHECKING:
    from takumi.models import (  # noqa
        Device,
        Theme,
        UserAdvertiserAssociation,
        UserCommentAssociation,
    )


class EMAIL_NOTIFICATION_PREFERENCES:
    DAILY = "daily"
    HOURLY = "hourly"
    OFF = "off"

    @staticmethod
    def values():
        return [
            EMAIL_NOTIFICATION_PREFERENCES.DAILY,
            EMAIL_NOTIFICATION_PREFERENCES.HOURLY,
            EMAIL_NOTIFICATION_PREFERENCES.OFF,
        ]


class User(db.Model):
    """Carries authentication and a relation to one or more advertisers or an
    influencer.
    """

    __tablename__ = "user"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    last_login = db.Column(UtcDateTime)
    active = db.Column(db.Boolean, nullable=False, server_default="t")
    last_active = db.Column(UtcDateTime)
    profile_picture = db.Column(db.String)
    full_name = db.Column(db.String)
    settings = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    birthday = db.Column(db.Date)
    gender = db.Column(db.Enum("female", "male", name="gender"))
    locale = db.Column(db.String)
    timezone = db.Column(db.String)
    role_name = db.Column(db.String, nullable=False)
    email_notification_preference = db.Column(
        SoftEnum(*EMAIL_NOTIFICATION_PREFERENCES.values()),
        server_default=EMAIL_NOTIFICATION_PREFERENCES.HOURLY,
        nullable=False,
    )

    device_id = db.Column(UUIDString, db.ForeignKey("device.id", ondelete="cascade"), unique=True)
    device = relationship("Device")

    revolut_counterparty_id = db.Column(UUIDString)

    needs = db.Column(
        MutableSet.as_mutable(ARRAY(db.String)),
        nullable=False,
        server_default=text("ARRAY[]::varchar[]"),
    )

    search_vector = db.Column(SimpleTSVectorType("full_name"), index=True)

    advertisers_association = relationship("UserAdvertiserAssociation", back_populates="user")

    comments_association = relationship("UserCommentAssociation", back_populates="user")

    tiktok_username = db.Column(db.String)
    youtube_channel_url = db.Column(db.String)

    theme = relationship("Theme")
    theme_id = db.Column(UUIDString, db.ForeignKey("theme.id", ondelete="cascade"))

    __table_args__ = (Index("ix_user_device_id", "device_id"),)

    @classmethod
    def by_email(cls, email):
        from takumi.models.email_login import EmailLogin

        user_id = db.session.query(EmailLogin.user_id).filter(EmailLogin.email == email).subquery()
        return cls.query.filter(User.id == user_id).one_or_none()

    def update_last_active(self):

        update_last_active = (
            User.__table__.update()
            .where(User.id == self.id)
            .values(last_active=dt.datetime.now(dt.timezone.utc))
        )
        db.session.execute(update_last_active)

    @property
    def advertisers(self):
        return [association.advertiser for association in self.advertisers_association]

    @property
    def advertiser_access(self):
        return {
            association.advertiser_id: association.access_level
            for association in self.advertisers_association
        }

    def can(self, need):
        return self.role_name == "developer" or need in self.get_needs()

    def get_needs(self):
        user_needs = set().union(self.role.needs)
        for need in self.needs:
            user_needs.add(get_need_from_name(need))
        return user_needs

    @property
    def role(self):
        return get_role_from_name(self.role_name)

    @property
    def has_facebook_account(self):
        return self.facebook_account is not None

    @property
    def has_instagram_account(self):
        if self.influencer is not None:
            return self.influencer.instagram_account is not None
        return False

    @hybrid_property_expression
    def age(cls):
        return cast(func.date_part("year", func.age(cls.birthday)), sqlalchemy.Integer)

    @property
    def is_active(self):
        return self.active

    def get_id(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def email(self) -> Optional[str]:
        if self.email_login is not None:
            return self.email_login.email
        return None

    @property
    def ig_username(self):
        if self.influencer:
            return self.influencer.username
        return None

    @property
    def request_locale(self):
        if self.locale is None:
            return None
        return negotiate_locale([self.locale], current_app.config["AVAILABLE_LOCALES"])

    @property
    def feature_flags(self):
        return {flag.key: flag(self).enabled for flag in FLAGS}

    def __repr__(self):
        return f"<User: {self.id} ({self.full_name}), Role: {self.role_name}>"


@vectorizer(User.full_name)
def full_name_vectorizer(column):
    """Unaccent the full name column when vectorizing, used in searching"""
    return func.unaccent(column)


class TargetingUpdate(db.Model):
    __tablename__ = "targeting_update"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    field_name = db.Column(db.String)
    user_id = db.Column(UUIDString, db.ForeignKey(User.id, ondelete="cascade"))
    user = relationship(User, backref="targeting_updates")


class UserEvent(db.Model):
    """A user event

    The user events are a log of all mutations to the user
    """

    __tablename__ = "user_event"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    type = db.Column(db.String, nullable=False)

    creator_user_id = db.Column(UUIDString, db.ForeignKey(User.id), index=True)
    creator_user = relationship(User, lazy="joined", foreign_keys=[creator_user_id])

    user_id = db.Column(
        UUIDString, db.ForeignKey(User.id, ondelete="restrict"), index=True, nullable=False
    )
    user = relationship(
        User,
        backref=backref("events", uselist=True, order_by="UserEvent.created"),
        lazy="joined",
        foreign_keys=[user_id],
    )

    event = db.Column(JSONB)

    __table_args__ = (Index("ix_user_event_user_type_created", "user_id", "type", "created"),)

    def __repr__(self):
        return "<UserEvent: {} ({} {})>".format(
            self.id, self.created and self.created.strftime("%Y-%m-%d %H:%M:%S"), self.type
        )

    def __str__(self):
        return (
            "UserEvent\n"
            "id: {id}\n"
            "type: {type}\n"
            "creator: {creator}\n"
            "event: {event}\n".format(
                id=self.id, type=self.type, creator=self.creator_user, event=self.event
            )
        )
