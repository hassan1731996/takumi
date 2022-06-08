import datetime as dt
from typing import Optional, TypedDict

from babel import Locale, UnknownLocaleError
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import aliased
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString

from takumi.extensions import db
from takumi.taxes import TaxFactory

from .helpers import hybrid_method_subquery


class VatPercentage(TypedDict):
    start_date: Optional[str]
    end_date: Optional[str]
    value: float


class Region(db.Model):
    """There are three or four ways to do hierarchy data structures in SQL.
    Most obvious is adjacency list, next is nested sets, one is a special
    contrib Postgres type ltree. We are using a version of the easiest one:
    adjacency list with a denormalized path for the list position, beginning
    with the root, ending with the parent.

         id | name           | path
        ----+----------------+-----------
          2 | UK             | {1,2}
          3 |   London       | {1,2,3}
          4 |     Shoreditch | {1,2,3,4}
          5 |   Manchester   | {1,2,5}

    """

    __tablename__ = "region"

    id = db.Column(UUIDString, primary_key=True)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    locale_code = db.Column(db.String)  # example en_GB
    osm_id = db.Column(db.String)

    name = db.Column(db.String, nullable=False)
    path = db.Column(MutableList.as_mutable(ARRAY(UUIDString)), index=True)

    # can influencers see posts
    supported = db.Column(db.Boolean, nullable=False, server_default="f")
    # can advertisers see region in takumi-web
    hidden = db.Column(db.Boolean, nullable=False, server_default="f")

    polygons = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    info = db.Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    coming_soon = db.Column(db.Boolean, nullable=False, server_default="f")

    market_slug = db.Column(db.String, index=True)
    _vat_percentage = db.Column("vat_percentage", db.Float, default=0)  # XXX: Deprecated
    _vat_percentages = db.Column(
        "vat_percentages", MutableList.as_mutable(JSONB), nullable=False, server_default="[]"
    )

    @property
    def vat_percentage(self) -> Optional[float]:
        if self._vat_percentage:
            return self._vat_percentage
        if not self.parent:
            return None
        return self.parent.vat_percentage

    def get_vat_percentage(self, date: dt.date) -> Optional[float]:
        """Get the VAT percentage for a certain date in the region

        Each range with have a start and end date, that is *inclusive* for the range.
        If a range is from June 10 - June 20, then it inclused June 10 and June 20
        """
        if self.parent:
            return self.parent.get_vat_percentage(date)

        percentage: VatPercentage
        for percentage in self._vat_percentages:
            if (
                percentage["start_date"] is not None
                and dt.date.fromisoformat(percentage["start_date"]) > date
            ):
                # Before start date
                continue
            if (
                percentage["end_date"] is not None
                and dt.date.fromisoformat(percentage["end_date"]) < date
            ):
                # After or on end date
                continue
            return percentage["value"]

        return None

    @classmethod
    def by_name(cls, name):
        return cls.query.filter(func.lower(cls.name) == func.lower(name)).first()

    @property
    def market(self):
        from takumi.models.market import Market

        return Market.get_market(self.market_slug)

    @property
    def locale(self):
        if self.locale_code:
            try:
                return Locale.parse(self.locale_code)
            except UnknownLocaleError:
                return None
        if self.path:
            parent = (
                self.get_parents_query()
                .filter(Region.locale_code != None)  # noqa: E711
                .order_by(func.array_length(Region.path, 1).desc())
            ).first()
            if parent:
                try:
                    return Locale.parse(parent.locale)
                except UnknownLocaleError:
                    return None
        return None

    @property
    def country_code(self):
        """Returns the country code, eg. IS for Iceland"""
        if self.locale is None:
            return None
        return self.locale.territory

    @property
    def country(self):
        """Returns the english name of the country, eg. Iceland instead of Ísland"""
        if self.locale is None:
            return None
        return Locale("en").territories[self.locale.territory]

    def tax_year(self, date):
        tax_logic = TaxFactory.get_tax_logic(self.country_code)
        return tax_logic.get_tax_year_from_date(date)

    def get_tax_year_range(self, year):
        tax_logic = TaxFactory.get_tax_logic(self.country_code)
        return tax_logic.get_tax_year_range(year)

    def get_parents_query(self):
        return Region.query.filter(Region.id.in_(self.path))

    def get_children_query(self, include_self=False):
        filter_query = Region.path.any(self.id)
        if include_self:
            filter_query = or_(filter_query, Region.id == self.id)
        return Region.query.filter(filter_query)

    def has_parent(self):
        return self.path is not None

    @property
    def parent(self) -> Optional["Region"]:
        return Region.query.get(self.path[-1]) if self.has_parent() else None

    @property
    def supported_ancestor(self):
        if self.parent:
            if self.parent.supported:
                return self.parent
            return self.parent.supported_ancestor

        return None

    @property
    def target(self):
        """Find the most suitable region for targeting. Either it self or a more suitable ancestor"""
        if self.supported:
            return self
        if self.supported_ancestor:
            return self.supported_ancestor
        return self  # return ourselves, even if not supported

    @property
    def targetable(self):
        return self.target.supported

    @property
    def is_leaf(self):
        """If a region has no subregions within it, it's considered a leaf"""
        region_level = len(self.path or []) + 1
        return Region.query.filter(Region.path[region_level] == self.id).count() == 0

    @classmethod
    def get_by_locale(cls, locale_code):
        """Returns the top level region with the locale code"""
        return (cls.query.filter(cls.locale_code == locale_code, cls.path == None)).one_or_none()

    @classmethod
    def get_by_territory(cls, territory):
        """Returns the top level region with the territory in the locale code"""
        return (
            cls.query.filter(cls.locale_code.ilike(f"%_{territory}"), cls.path == None)
        ).one_or_none()

    @classmethod
    def get_by_locale_list(cls, locale_codes):
        """Returns the top level regions with the locale codes"""
        return (cls.query.filter(cls.locale_code.in_(locale_codes), cls.path == None)).all()

    @classmethod
    def get_by_territory_list(cls, territories):
        """Returns the top level regions with the territories in the locale code"""
        return (
            cls.query.filter(
                cls.path == None,
                or_(*[Region.locale_code.ilike(f"%_{territory}") for territory in territories]),
            )
        ).all()

    @classmethod
    def get_by_name(cls, name, parent=None):
        query = cls.query.filter(cls.name == name)

        if parent is not None:
            level = len(parent.path or []) + 1
            query = query.filter(cls.path[level] == parent.id)

        return query.first()

    @classmethod
    def get_supported_regions(cls):
        return cls.query.filter(cls.path == None, cls.supported == True)  # noqa: E711

    @classmethod
    def get_most_accurate(cls, country_code, names):
        """Try and find the most accurate match for the given location
        names within the given country code. `names` parameter is a list
        of location names in order of increasing granularity.  Example:

        Region.get_most_accurate('GB', ('England', 'London', 'Hoxton', ))
            -> returns Region for "London"
        """
        region = (
            Region.query.filter(
                Region.path == None,  # noqa: E711
                # Only top level, which are countries
                # Local code of some countries differ in length. i.e. en_GB and fil_PH
                func.substring(Region.locale_code, func.char_length(Region.locale_code) - 1, 2)
                == country_code.upper(),
            )
        ).first()
        if region is None:
            return None  # XXX: raise something so we can create top-level country region?

        for name in names:
            subregion = cls.get_by_name(name, parent=region)
            if subregion is not None:
                region = subregion
            # if subregion is None we still continue iterating through names.
            # if we do support direct targeting to a more accurate region, but
            # not an intermediate area in the "names" list
        return region

    @hybrid_method_subquery
    def is_under_or_equals(cls, region):
        AliasedRegion = aliased(cls)

        if isinstance(region, str):
            region = cls.by_name(region)

        subregion_ids = [
            r_id[0]
            for r_id in db.session.query(AliasedRegion.id)
            .filter(AliasedRegion.path.contains("{" + region.id + "}"))
            .all()
        ]
        region_ids = [region.id] + (region.path if region.path else []) + subregion_ids
        return (
            db.session.query(func.count(AliasedRegion.id) > 0)
            .filter(or_(*[AliasedRegion.id == region_id for region_id in region_ids]))
            .filter(cls.id == AliasedRegion.id)
        )

    def __repr__(self):
        return f"<Region: ({self.id}, {self.name})>"
