import datetime as dt
import logging
import os
import sys
from collections import defaultdict

import speaklater
from datadog.dogstatsd.base import DogStatsd
from flask import Flask, _request_ctx_stack, g, json, jsonify, request  # type: ignore
from flask.sessions import SecureCookieSessionInterface
from flask_cors import CORS
from marshmallow import Schema, ValidationError
from sqlalchemy.orm import Query
from werkzeug.routing import UUIDConverter

# from core.common.monitoring import StatsD, StatsdMiddleware
from core.config import MissingEnvironmentVariables

from takumi.error_codes import MAINTENANCE_MODE
from takumi.roles.permissions import see_request_cost
from takumi.tokens import InvalidToken, InvalidTokenHeader, TokenExpired, get_jwt_session
from takumi.utils import get_cost_headers


def unique_join(self, *props, **kwargs):
    if props[0] in [c.entity for c in self._join_entities]:
        return self
    return self.join(*props, **kwargs)


def unique_outerjoin(self, *props, **kwargs):
    if props[0] in [c.entity for c in self._join_entities]:
        return self
    return self.outerjoin(*props, **kwargs)


Query.unique_join = unique_join  # type: ignore
Query.unique_outerjoin = unique_outerjoin  # type: ignore


class UUIDStringConverter(UUIDConverter):
    def to_python(self, *args, **kwargs):
        value = super().to_python(*args, **kwargs)
        return str(value)


class LazyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, dt.date):
            return o.isoformat()
        if speaklater.is_lazy_string(o):
            return str(o)
        return json.JSONEncoder.default(self, o)


class CustomSessionInterface(SecureCookieSessionInterface):
    """Disable cookies because we use JWT"""

    def save_session(self, *args, **kwargs):
        return


def get_maintenance_message():
    return os.environ.get("MAINTENANCE_MESSAGE")


def configure_maintenance(app):
    message = get_maintenance_message()
    status_map = defaultdict(lambda: 503)
    status_map["/status"] = 200  # we need to appear healthy

    if message is None:
        return

    def maintenance():
        req = _request_ctx_stack.top.request
        return (
            jsonify(
                {
                    "error": {"message": message, "code": MAINTENANCE_MODE},
                    "api": {
                        "git_hash": app.config["GITHASH"],
                        "version": app.config["VERSION"],
                    },
                }
            ),
            status_map[req.path],
        )

    app.before_request(maintenance)


def configure_logging(app):
    app.logger.setLevel(logging.INFO)


class MarshmallowFlask(Flask):
    def make_response(self, rv):
        if isinstance(rv, tuple) and len(rv) == 3:
            schema, data, status_code = rv
            assert isinstance(schema, Schema), (
                "Three tuple returns are expected to " "be of form (<Schema()>, data, status_code)"
            )
            data, errors = schema.dump(data)
            if errors:
                raise ValidationError(errors)

            if schema.many:
                rv = jsonify(data=data)
            else:
                rv = jsonify(data)
            rv.status_code = status_code
        response = super().make_response(rv)
        if see_request_cost.can():
            for header in get_cost_headers():
                response.headers.add(*header)
        return response


def create_app(testing=False, tasks_context=False, debug=False):
    app = MarshmallowFlask("takumi")

    app.debug = debug
    configure_logging(app)
    app.testing = testing
    app.tasks_context = tasks_context
    app.json_encoder = LazyJSONEncoder
    app.url_map.converters["uuid"] = UUIDStringConverter
    try:
        cfg = "takumi.config.{}".format(os.environ.get("RELEASE_STAGE", "local"))
        app.logger.info(f"Loading config: {cfg}")
        app.config.from_object(cfg)
    except MissingEnvironmentVariables as e:
        print(f"ERROR: {e}\n", file=sys.stderr)
        sys.exit(1)
        return None

    configure_maintenance(app)

    app.config["statsd"] = StatsD(
        DogStatsd(
            os.environ.get("DATADOG_STATSD_SERVICE_HOST", "localhost"),
            os.environ.get("DATADOG_STATSD_PORT_8125_UDP_PORT", 8125),
        ),
        tags=[
            "app:{}".format(os.environ.get("TAKUMI_SERVER_APP_NAME", app.name)),
            "stage:{}".format(app.config["RELEASE_STAGE"]),
            "git_hash:{}".format(app.config["GITHASH"]),
        ],
    )

    # Max file upload size, 64MB
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

    from .extensions import configure_extensions

    configure_extensions(app)

    from .views.blueprint import api, tasks, webhooks

    cors_options = {"supports_credentials": True, "max_age": 600}

    if app.config["RELEASE_STAGE"] == "production":
        cors_options["origins"] = r".*\.takumi\.(com|team)$"
    if app.config["RELEASE_STAGE"] == "development":
        cors_options["origins"] = r".*\.takumi\.(com|team)|http://localhost(:\d+)?$"

    CORS(api, **cors_options)
    CORS(app, **cors_options)

    app.register_blueprint(api)
    app.register_blueprint(tasks)
    app.register_blueprint(webhooks)

    from .exceptions import register_error_handlers

    register_error_handlers(app)

    if app.config["RELEASE_STAGE"] != "local":
        app.wsgi_app = StatsdMiddleware(app, app.config["statsd"], prefix="takumi")

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app)

    if json.loads(os.environ.get("PROFILE", "false")) is not False:
        from werkzeug.contrib.profiler import ProfilerMiddleware

        app.config["PROFILE"] = True
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, profile_dir="/tmp")

    app.session_interface = CustomSessionInterface()

    @app.before_request
    def before_request():
        try:
            session = get_jwt_session(request)
            if session:
                g.is_developer = session.get("developer") == True
        except (InvalidTokenHeader, TokenExpired, InvalidToken):
            pass

    return app
