from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db

if TYPE_CHECKING:
    from takumi.models import Advertiser, User  # noqa


class UserAdvertiserAssociation(db.Model):
    __tablename__ = "user_advertiser_association"

    user_id = db.Column(
        "user_id", UUIDString, db.ForeignKey("user.id", ondelete="cascade"), primary_key=True
    )
    advertiser_id = db.Column(
        "advertiser_id",
        UUIDString,
        db.ForeignKey("advertiser.id", ondelete="cascade"),
        primary_key=True,
    )
    created = db.Column(UtcDateTime, server_default=func.now())
    access_level = db.Column("access_level", db.String, nullable=False)

    user = relationship("User", back_populates="advertisers_association")
    advertiser = relationship("Advertiser", back_populates="users_association")


def create_user_advertiser_association(user, advertiser, access_level):
    association = UserAdvertiserAssociation(
        user_id=user.id, advertiser_id=advertiser.id, access_level=access_level
    )
    association.user = user
    advertiser.users_association.append(association)
