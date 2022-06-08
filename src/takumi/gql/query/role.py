from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.roles import get_need_from_name, permissions, roles


class RoleQuery:
    has_role = fields.Boolean(role_name=arguments.String(required=True))
    has_permission = fields.Boolean(
        permission_name=arguments.String(required=True, name="permission")
    )
    roles = fields.List("Role")

    @permissions.public.require()
    def resolve_has_role(root, info, role_name):
        return current_user.role_name == role_name

    @permissions.public.require()
    def resolve_has_permission(root, info, permission_name):
        permission = getattr(permissions, permission_name, None)
        if permission is None or not isinstance(permission, permissions.Permission):
            # dynamically create need and permission -- used for UI-only needs/permissions/featureflags
            return permissions.Permission(get_need_from_name(permission_name)).can()
        return permission.can()

    @permissions.developer.require()
    def resolve_roles(root, info):
        return roles.values()
