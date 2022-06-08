import time
from typing import Any, Optional

from flask import current_app
from flask_login import current_user
from graphene.utils.str_converters import to_snake_case
from sentry_sdk import capture_message

from core.common.monitoring import TimingStats

from takumi.constants import TAKUMI_DOMAINS
from takumi.gql.exceptions import GraphQLException
from takumi.models import Campaign
from takumi.roles import permissions
from takumi.roles.needs import advertiser_role


class DebugTimingMiddleware:
    """Print out timing information for query parts

    Queries that take less than min_ms are not printed out, if it's more than
    warn_ms, then it will be yellow and above error_ms will be red
    """

    enabled: bool

    def __init__(self, min_ms: int = 50, warn_ms: int = 100, error_ms: int = 300) -> None:
        self.enabled = current_app.config["RELEASE_STAGE"] == "local"
        self.min_ms = min_ms
        self.warn_ms = warn_ms
        self.error_ms = error_ms

    def get_object_name(self, root: Optional[Any], info: Any) -> str:
        if root is None:
            return "None"

        if hasattr(root, "_meta") and root._meta:
            return root._meta.name

        if hasattr(root, "__tablename__"):
            return root.__tablename__

        return "Unknown"

    def get_operation_type(self, info: Any) -> str:
        try:
            return info.operation.operation
        except Exception:
            return "unknown"

    def get_operation_name(self, info: Any) -> str:
        try:
            return info.operation.name.value
        except Exception:
            return "unknown"

    def get_metric_name(self, root: Any, info: Any) -> str:
        parts = [self.get_operation_name(info)]
        if root is not None:
            try:
                object_name = self.get_object_name(root, info)
            except Exception:
                object_name = "unknown"
            if object_name is None:
                return None  # resolving a field on a sub-object, let's not emit a metric
            parts.append(object_name)

        try:
            field_name = info.field_name
        except Exception:
            field_name = "unknown"
        parts.append(field_name)

        path = ".".join(parts)
        op_type = self.get_operation_type(info).capitalize()

        return f"{op_type} {path}"

    def resolve(self, next: Any, root: Any, info: Any, **args) -> Any:
        if not self.enabled:
            return next(root, info, **args)

        metric_name = self.get_metric_name(root, info)

        now = time.time()
        return_value = next(root, info, **args)
        after = (time.time() - now) * 1000
        after_msg = f"{after:.0f}ms"

        message = f"{after_msg:<5} {metric_name}"

        RED = "\x1b[0;31m"
        GREEN = "\x1b[0;32m"
        ORANGE = "\x1b[0;33m"
        NC = "\x1b[0m"

        if after > self.error_ms:
            print(f"{RED}{message}{NC}")
        elif after > self.warn_ms:
            print(f"{ORANGE}{message}{NC}")
        elif after > self.min_ms:
            print(f"{GREEN}{message}{NC}")

        return return_value


class StatsdTimingMiddleware:
    def __init__(self):
        self.statsd = None

    def init(self):
        if self.statsd is None:
            from flask import current_app

            self.statsd = current_app.config["statsd"]

    def get_object_name(self, root, info):
        if root is None:
            return "None"

        if hasattr(root, "_meta") and root._meta:
            return root._meta.name

        if hasattr(root, "__tablename__"):
            return root.__tablename__

        return None

    def get_operation_type(self, info):
        try:
            return info.operation.operation
        except Exception:
            return "unknown"

    def get_operation_name(self, info):
        try:
            return info.operation.name.value
        except Exception:
            return "unknown"

    def get_metric_name(self, root, info):
        parts = [self.get_operation_type(info), self.get_operation_name(info)]
        if root is not None:
            try:
                object_name = self.get_object_name(root, info)
            except Exception:
                object_name = "unknown"
            if object_name is None:
                return None  # resolving a field on a sub-object, let's not emit a metric
            parts.append(object_name)

        try:
            field_name = info.field_name
        except Exception:
            field_name = "unknown"
        parts.append(field_name)
        return "takumi.gql.{}".format(".".join(parts))

    def resolve(self, next, root, info, **args):
        self.init()  # XXX: a bit wasteful perhaps
        if info.field_name.startswith("__"):
            return next(root, info, **args)

        metric_name = self.get_metric_name(root, info)
        if metric_name is None:
            return next(root, info, **args)

        with TimingStats(self.statsd, metric_name):
            return_value = next(root, info, **args)

        return return_value


class AuthorizationMiddleware:
    def _has_campaign_token(self, info, campaign, needs):
        """Allow bypassing the advertiser requirement on fields if campaign token provided"""
        if advertiser_role not in needs:
            return False

        if not isinstance(campaign, Campaign):
            return False

        token = info.context.get("token")
        if not token:
            return False

        return campaign.report_token == token

    def resolve(self, next, root, info, **args):
        field_name = to_snake_case(info.field_name)

        graphene_type = getattr(info.parent_type, "graphene_type", None)
        field = getattr(graphene_type, field_name, None)
        needs = getattr(field, "needs", None)
        if hasattr(field, "bypass_needs"):
            bypass_needs = field.bypass_needs(root)
        else:
            bypass_needs = False

        if (
            (not bypass_needs and needs is not None)
            and not permissions.Permission(*needs).can()
            and not self._has_campaign_token(info, root, needs)
        ):
            # If the user doesn't fulfil any needs required, then mask out the field
            return None

        if (
            info.operation.operation == "mutation"
            and getattr(current_user, "role_name", None) == "read_only_master"
        ):
            from takumi import slack
            from takumi.gql.mutation.user import UpdateCurrentUser

            if field_name != "update_current_user" and graphene_type != UpdateCurrentUser:
                slack.notify_debug(
                    f"{current_user.email}: Read only mutation blocked: {field_name}/{graphene_type}"
                )
                return None
            else:
                slack.notify_debug(
                    f"{current_user.email}: Read only mutation allowed: {field_name}/{graphene_type}"
                )

        return next(root, info, **args)


class DisableIntrospectionMiddleware:
    """Disable introspection fully except for team members"""

    def resolve(self, next, root, info, **kwargs):
        email = current_user.is_authenticated and current_user.email or ""

        if (
            info.field_name.lower() in ["__schema", "__introspection"]
            and not permissions.team_member.can()
            and not current_app.config["ALLOW_INTROSPECTION"]
            and not any(email.endswith(domain) for domain in TAKUMI_DOMAINS)
        ):
            if email:
                capture_message(f"User ({email}) tried to run an introspection query")
            else:
                capture_message("User tried to run an introspection query")

            raise GraphQLException("You need to be logged in")

        return next(root, info, **kwargs)
