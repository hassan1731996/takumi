from sqlalchemy import Table

from core.common.sqla import UUIDString

from takumi.extensions import db

# These are many-to-many tables, don't need any methods/logic


advertiser_region_table = Table(
    "advertiser_region",
    db.Model.metadata,
    db.Column(
        "advertiser_id",
        UUIDString,
        db.ForeignKey("advertiser.id", ondelete="cascade"),
        primary_key=True,
    ),
    db.Column(
        "region_id", UUIDString, db.ForeignKey("region.id", ondelete="cascade"), primary_key=True
    ),
)

targeting_region_table = Table(
    "targeting_region",
    db.Model.metadata,
    db.Column(
        "targeting_id",
        UUIDString,
        db.ForeignKey("targeting.id", ondelete="cascade"),
        primary_key=True,
    ),
    db.Column(
        "region_id", UUIDString, db.ForeignKey("region.id", ondelete="cascade"), primary_key=True
    ),
)

advertiser_industries_table = db.Table(
    "advertiser_industries",
    db.Column(
        "advertiser_industry_id",
        UUIDString,
        db.ForeignKey("advertiser_industry.id", ondelete="cascade"),
        primary_key=True,
    ),
    db.Column(
        "advertiser_id",
        UUIDString,
        db.ForeignKey("advertiser.id", ondelete="cascade"),
        primary_key=True,
    ),
)
