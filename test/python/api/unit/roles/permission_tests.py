from flask_principal import Need

from takumi.roles.needs import developer_role
from takumi.roles.permissions import Permission, set_user_role


def test_all_permissions_include_developer_role_need():
    permission = Permission()
    assert developer_role in permission.needs


def test_set_user_role():
    expected_need = Need("set_user_role", "some_role")
    permission = set_user_role("some_role")
    assert expected_need in permission.needs
