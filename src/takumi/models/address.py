import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import backref, column_property, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class Address(db.Model):
    __tablename__ = "address"
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    name = db.Column(db.String)
    address1 = db.Column(db.String, nullable=False)
    address2 = db.Column(db.String)
    city = db.Column(db.String, nullable=False)
    postal_code = db.Column(db.String, nullable=False)
    phonenumber = db.Column(db.String)
    country = db.Column(db.String(2), nullable=False)  # ISO-3166-2
    state = db.Column(db.String)
    is_commercial = db.Column(db.Boolean, nullable=False, server_default="f")
    is_pobox = db.Column(db.Boolean, nullable=False, server_default="f")
    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="cascade"), nullable=False, index=True
    )
    influencer = relationship(
        "Influencer", backref=backref("address", uselist=False), lazy="joined"
    )
    postal_code_clean = column_property(
        func.replace(func.upper(func.regexp_replace(postal_code, "[^a-zA-Z0-9]+", "g")), " ", "")
    )
    city_clean = column_property(
        func.trim(func.upper(func.regexp_replace(city, r"[^a-zA-Z0-9\s]+", "g")))
    )

    def __repr__(self):
        return f"<Address: {self.id} (Influencer {self.influencer.id})>"

    @classmethod
    def get_default_address_data_for_influencer(cls, influencer):
        """
        This is the initial data for influencer when setting up address for the
        first time. If the influencer region is a leaf (has no subregions) we assume
        that it's a city.
        """

        city = ""
        country_code = ""

        if influencer.target_region is not None:
            country_code = influencer.target_region.country_code
            if influencer.target_region.path is not None and influencer.target_region.is_leaf:
                city = influencer.target_region.name
        return dict(city=city, country=country_code, address1="", postal_code="")

    @classmethod
    def create_for_influencer(cls, influencer):
        """Return a new Address object with the country and city (if available)
        set from the influencer region.

        """
        address_data = cls.get_default_address_data_for_influencer(influencer)

        return cls(influencer=influencer, **address_data)

    @property
    def age_in_seconds(self):
        return int((dt.datetime.now(dt.timezone.utc) - self.modified).total_seconds())
