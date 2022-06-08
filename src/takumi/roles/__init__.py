from contextlib import contextmanager

from flask import g
from flask_principal import Identity

from . import needs
from .needs import advertiser_admin_access, advertiser_member_access, advertiser_owner_access
from .roles import roles


def get_role_from_name(name):
    return roles.get(name)


def get_need_from_name(name):
    if hasattr(needs, name):
        return getattr(needs, name)
    else:
        return needs.ActionNeed(name)


def get_advertiser_access_need(level):
    levels = dict(
        admin=advertiser_admin_access,
        member=advertiser_member_access,
        owner=advertiser_owner_access,
    )
    return levels[level]


# TODO: Remove when advertiser access level has been revisited
def provide_advertiser_access_need(user, advertiser_id):
    """This is a quick fix.
    When our views were ported to graphql all permission checks for advertiser access level broke.
    In our old views every request was built up in a REST like manner where the request included the
    advertiser_id in the requested url. I.e host/brand/{advertiser_id]/some_advertiser_resources

    We had a @brands.url_value_preprocessor that added current users access level need to him based on his
    relation to the advertiser_id.

    In our current solution we don't have access to the advertiser_id before hand
    when doing mutations to resources that belong to some advertiser.
    """
    access_level = user.advertiser_access.get(advertiser_id)
    if access_level is not None:
        g.identity.provides.add(get_advertiser_access_need(access_level))


@contextmanager
def system_access():
    if not hasattr(g, "identity"):
        g.identity = Identity("system")
    g.identity.provides.add(needs.system_role)
    yield
    g.identity.provides.remove(needs.system_role)
