import hashlib
import hmac
import inspect
from functools import wraps

from flask import g, request
from flask_login import current_user
from flask_principal import PermissionDenied

from core.common.exceptions import APIError

from takumi.constants import MINIMUM_CLIENT_VERSION
from takumi.exceptions import ClientUpgradeRequired
from takumi.i18n import gettext as _
from takumi.roles import get_advertiser_access_need, permissions

SIGNATURE_HEADERS = ["X-Request-Signature-Sha-256", "Webhook-Signature"]


def guard(check):
    """:param check:   a function which determines if this request can be fulfilled
    the function gets the current request object as a parameter,
    the function needs to raise an error/exception to prevent the
    request from reaching the wrapped view.
    """

    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            check(request)
            return fn(*args, **kwargs)

        return decorated

    return wrapper


def min_version_required(view, version=MINIMUM_CLIENT_VERSION):
    """Use for views which will not work with clients of lower version than `version`"""

    def check(request):
        ClientUpgradeRequired.raise_for_version(version, request)

    return guard(check)(view)


def influencer_required(view):
    """Guard for only users with influencer-role but also check if the client version
    is recent enough, and for a valid instagram_account (?) and force_logout (?)
    """

    def check(request):
        try:
            permissions.influencer.test()
        except PermissionDenied:
            raise APIError("Invalid credentials, please log in again", 401)

        ClientUpgradeRequired.raise_for_version(MINIMUM_CLIENT_VERSION, request)

        if current_user.influencer.force_logout():
            raise APIError(_("Please log in again"), 401)

    return guard(check)(view)


def advertiser_auth(key, permission):
    """
    A decorator that checks for user permission for a certain advertiser.
    The decorator requires the function it decorates to have advertiser id as one of its arguments.

    :param key: The name of the argument that contains the advertiser id
    :param permission: The permission required to pass this check
    """

    def get_arg_value_by_name(func, arg_name, args):
        index_of_arg = inspect.getargspec(func).args.index(arg_name)
        return args[index_of_arg]

    def wrapper(view):
        @wraps(view)
        def decorated_function(*args, **kwargs):
            # Lets check to see if the view was called with key as an arg or kwarg
            if key in kwargs:
                advertiser_id = kwargs[key]
            else:
                advertiser_id = get_arg_value_by_name(view, key, args)

            access_level = current_user.advertiser_access.get(advertiser_id)
            if access_level is not None:
                g.identity.provides.add(get_advertiser_access_need(access_level))

            permission.test()
            return view(*args, **kwargs)

        return decorated_function

    return wrapper


def _get_signature(secret, body):
    if not isinstance(secret, bytes):
        secret = bytes(secret, "ascii")
    if not isinstance(body, bytes):
        body = bytes(body, "ascii")

    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def task(view):
    """This protects a task view.  Task endpoints are intended for outside
    calls to trigger internal takumi-server processes.
    """

    def _get_signature_from_headers(headers):
        SIGNATURE_HEADERS = ["X-Request-Signature-Sha-256", "Webhook-Signature"]
        for header in SIGNATURE_HEADERS:
            if header in headers:
                return headers[header]

    def check(request):
        if not hasattr(g, "task"):
            raise Exception("@task endpoint on a non-task blueprint route!")
        if not g.task:
            raise APIError("Access denied (view not allowed)", 403)
        if request.url_rule.endpoint not in g.task.allowed_views:
            raise APIError("Access denied (view not allowed)", 403)
        if g.task.secret:
            signature = _get_signature_from_headers(request.headers)
            if not signature or signature != _get_signature(g.task.secret, request.data):
                raise APIError("Access denied (secret incorrect or missing)", 403)

    return guard(check)(view)
