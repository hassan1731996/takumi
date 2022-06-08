from flask_principal import ActionNeed, RoleNeed

from takumi.models import User
from takumi.roles.needs import bypass_instagram_profile_validation
from takumi.roles.roles import Role


class FooRole(Role):
    name = "foo"
    needs = [RoleNeed("foo"), ActionNeed("a")]


class BarRole(FooRole):
    name = "bar"
    needs = [RoleNeed("bar"), ActionNeed("b")]


def test_role_needs_subclassing():
    bar = BarRole()
    assert bar.needs == {RoleNeed("bar"), RoleNeed("foo"), ActionNeed("a"), ActionNeed("b")}
    assert bar.has_role("foo")
    assert bar.has_role("bar")


def test_role_get_needs_does_not_includes_special_need():
    user = User(role_name="influencer", needs=[])
    assert bypass_instagram_profile_validation not in user.get_needs()


def test_role_get_needs_includes_special_need():
    user = User(role_name="influencer", needs=["bypass_instagram_profile_validation"])
    assert bypass_instagram_profile_validation in user.get_needs()
