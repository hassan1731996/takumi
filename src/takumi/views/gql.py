import traceback

from flask import current_app, request
from flask_graphql import GraphQLView as FlaskGraphQLView
from flask_login import current_user
from flask_principal import PermissionDenied
from graphql import Source, parse, validate
from sentry_sdk import capture_exception, start_transaction

from core.common.exceptions import APIError
from core.common.monitoring import TimingStats
from core.common.sqla import CountSQLExecutions

from takumi import slack
from takumi.gql.exceptions import GraphQLException
from takumi.gql.middlewares import (
    AuthorizationMiddleware,
    DebugTimingMiddleware,
    DisableIntrospectionMiddleware,
    StatsdTimingMiddleware,
)
from takumi.gql.schema import public_schema, schema
from takumi.roles import permissions
from takumi.services.exceptions import ServiceException
from takumi.utils import record_cost
from takumi.views.blueprint import api
from takumi.vsapi import get_request_version

# These exceptions, and all subclasses of them, are passed
# through to the client and not reported to sentry
ALLOWED_EXCEPTIONS = (GraphQLException, ServiceException, PermissionDenied)


class GraphQLView(FlaskGraphQLView):
    @property
    def schema(self):
        from flask_login import current_user

        if current_user.is_authenticated:
            return schema
        return public_schema

    @staticmethod
    def _notify_permission_error(error):
        """Notify slack on permission raised permission error"""
        permission = error.original_error.args[0]
        needs = [need.value for need in permission.needs]
        path = ".".join(str(node.name.value) for node in error.nodes)

        slack.report_permission_error(current_user, path, needs)

    @staticmethod
    def _format_permission_error(error):
        """Write a pretty message and list needs required for the action"""
        permission = error.original_error.args[0]
        needs = [n.value for n in permission.needs]
        formatted_error = {
            "message": (
                "You do not have permission to do that ({})".format(
                    ", ".join(n for n in needs if n != "developer")
                )
            )
        }
        if error.locations is not None:
            formatted_error["locations"] = [
                {"line": loc.line, "column": loc.column} for loc in error.locations
            ]
        return formatted_error

    def _handle_exceptions(self, result):
        """Iterate and report unexpected exceptions

        Exceptions of the type `ServiceException` and `GraphQLException` are
        allowed and will simply bubble up to be errors in the graphql response. We
        can decide to have a singular exception, similar to `APIError` that we used
        to have, that is the only allowed exception to bubble up.
        """
        response_errors = []
        for e in result.errors:
            if not hasattr(e, "original_error"):
                formatted_error = super().format_error(e)
                response_errors.append(formatted_error)
            else:
                error_type = type(e.original_error)
                error = e.original_error
                stack = e.stack or e.original_error.__traceback__

                formatted_error = self.format_error(e)

                if isinstance(error, ALLOWED_EXCEPTIONS):
                    formatted_error["type"] = type(error).__name__
                    formatted_error["errorCode"] = getattr(error, "error_code", None)
                else:
                    if permissions.developer.can():
                        # Give developers the traceback
                        formatted_error["traceback"] = "".join(traceback.format_tb(stack)).split(
                            "\n"
                        )
                    else:
                        # Mask the error message for general users
                        formatted_error["message"] = "An unexpected exception has occurred"

                    node_names = [node.name.value for node in e.nodes]
                    culprit = "GraphQL: {}".format(", ".join(node_names))

                    path = ".".join([str(p) for p in formatted_error.get("path", [])])

                    capture_exception(
                        (error_type, error, stack),
                        data={"culprit": culprit, "extra": {"path": path}},
                    )

                if "traceback" in formatted_error:
                    # Print out the traceback to console
                    output = ""
                    if "message" in formatted_error:
                        output += f"\n# Message\n{formatted_error['message']}\n"
                    if "path" in formatted_error:
                        path = ".".join([str(p) for p in formatted_error.get("path", [])])
                        output += f"\n# Path\n{path}\n"
                    if "traceback" in formatted_error:
                        tb = "\n".join(formatted_error["traceback"])
                        output += f"\n# Traceback\n{tb})\n"

                    current_app.logger.error(output)
                response_errors.append(formatted_error)
        return response_errors

    def _metric_name(self, operation_name, suffix=None):
        metric_name = f"takumi.api.graphql.query.{operation_name}"
        if suffix is not None:
            return f"{metric_name}.{suffix}"
        return metric_name

    def format_error(self, error):
        """Custom format error handler to pretty format permission exception"""
        if isinstance(getattr(error, "original_error", None), PermissionDenied):
            formatted_error = self._format_permission_error(error)
            self._notify_permission_error(error)
        else:
            formatted_error = super().format_error(error)
            original_error = getattr(error, "original_error", None)
            if original_error is not None and getattr(original_error, "errors", None) is not None:
                formatted_error["errors"] = [str(e) for e in error.original_error.errors]
        return formatted_error

    def validate_query_authentication(self, query):
        """Validate the query when logged out

        If the user is not authenticted and makes an invalid query to the
        public schema, we will check if the query was intended for the private
        schema. If the query is valid for the private schema, raise 401
        unauthorized for the client.
        """
        if current_user.is_authenticated or query is None:
            return

        source = Source(query, name="GraphQL request")
        ast = parse(source)
        try:
            public_validation_errors = validate(public_schema, ast)
        except Exception as e:
            public_validation_errors = [e]

        if not public_validation_errors:
            return

        # Check if the query is valid on the private schema
        try:
            private_validation_errors = validate(schema, ast)
        except Exception as e:
            private_validation_errors = [e]

        if not private_validation_errors:
            # Private query was valid, but user not logged in
            raise APIError("Unauthorized", 401)

    def get_response(self, request, data, show_graphiql=False):
        """Custom implementation of the get_response to handle errors differently"""
        if current_app.config["RELEASE_STAGE"] != "local":
            statsd = current_app.config["statsd"]
        else:
            statsd = None

        with TimingStats(statsd) as total_metric:
            with TimingStats(statsd) as parse_metric:
                query, variables, operation_name, id = self.get_graphql_params(request, data)
                parse_metric.name = self._metric_name(operation_name, "parse")
            total_metric.name = self._metric_name(operation_name, "total")

            self.validate_query_authentication(query)

            response = {}

            with start_transaction(op="graphql", name=operation_name):
                with TimingStats(statsd, self._metric_name(operation_name, "execute")) as metric:
                    with CountSQLExecutions() as sql_executions:
                        execution_result = self.execute_graphql_request(
                            data, query, variables, operation_name, show_graphiql
                        )
                        status_code = 200
                    if statsd:
                        statsd.histogram(
                            self._metric_name(operation_name, "sql_queries"), sql_executions.count()
                        )
                    if execution_result:
                        if execution_result.errors:
                            metric.tags.append("errored")
                            response["errors"] = self._handle_exceptions(execution_result)

                        if execution_result.invalid:
                            metric.tags.append("invalid")
                            response["invalid"] = True
                        else:
                            response["data"] = execution_result.data

                        if self.batch:
                            metric.tags.append("batch")
                            response = {"id": id, "payload": response, "status": status_code}

                        cost = {"sql_queries": sql_executions.count()}
                        record_cost(f"GraphQL-{operation_name}-SQL-Queries", cost["sql_queries"])
                        if request.args.get("cost") is not None:
                            response["cost"] = cost

            if response != {}:
                with TimingStats(statsd, self._metric_name(operation_name, "encode")):
                    result = self.json_encode(request, response, show_graphiql)
            else:
                result = None

            if statsd:
                aggregate_tags = metric.tags + [f"operation:{operation_name}"]
                total_metric.tags.append(f"operation:{operation_name}")
                statsd.timing("takumi.gql.request", metric.time, tags=aggregate_tags)
                statsd.timing("takumi.gql.request.cpu", metric.cpu_time, tags=aggregate_tags)

        return result, status_code


@api.route("/graphql", methods=["POST"])
@api.route("/graphql/<operationName>", methods=["POST"])
def graphql(*args, **kwargs):
    kwargs.pop("operationName", None)
    return GraphQLView.as_view(
        "graphql",
        get_context=lambda self: {"client_version": get_request_version(request.headers)},
        middleware=[
            DisableIntrospectionMiddleware(),
            AuthorizationMiddleware(),
            StatsdTimingMiddleware(),
            DebugTimingMiddleware(),
        ],
    )(*args, **kwargs)


# TODO: Remove when clients have stopped using the public endpoint
api.add_url_rule(
    "/public/graphql",
    view_func=GraphQLView.as_view(
        "public_graphql",
        context={},
        middleware=[DisableIntrospectionMiddleware(), AuthorizationMiddleware()],
    ),
)
