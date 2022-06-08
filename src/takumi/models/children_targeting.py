from sqlalchemy import and_, func, or_
from sqlalchemy.dialects.postgresql import ARRAY, ENUM
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .helpers import hybrid_method_expression


class ChildrenTargeting(db.Model):
    """A database entry representing the campaign's children targeting, a 1:1 map to targeting"""

    __tablename__ = "children_targeting"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())

    min_children_count = db.Column(db.Integer)
    max_children_count = db.Column(db.Integer)

    ages = db.Column(MutableList.as_mutable(ARRAY(db.Integer)))

    child_gender = db.Column(ENUM("female", "male", name="gender", create_type=False))

    has_unborn_child = db.Column(db.Boolean, nullable=True)

    has_born_child = db.Column(db.Boolean, nullable=True)

    @hybrid_method_expression
    def targets_children_count(self, child_count):
        return and_(
            child_count >= func.coalesce(self.min_children_count, 0),
            or_(self.max_children_count == None, self.max_children_count >= child_count),
        )

    @hybrid_method_expression
    def targets_any_of_children_ages(self, children_ages):
        return or_(self.ages == [], self.ages == None, self.ages.overlap(children_ages))

    @hybrid_method_expression
    def targets_any_of_children_genders(self, children_genders):
        return or_(self.child_gender == None, self.child_gender.in_(children_genders))

    @hybrid_method_expression
    def targets_unborn_child(self, has_unborn_child):
        return or_(self.has_unborn_child == None, self.has_unborn_child == has_unborn_child)

    @hybrid_method_expression
    def targets_born_child(self, has_born_child):
        return or_(self.has_born_child == None, self.has_born_child == has_born_child)
