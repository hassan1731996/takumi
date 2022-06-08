from flask import current_app, jsonify
from redis.exceptions import RedisError
from sentry_sdk import capture_message, push_scope
from sqlalchemy.engine import create_engine

from core.common.exceptions import APIError

import takumi.alembic.utils as alembic_utils
from takumi.extensions import elasticsearch, instascrape, redis, tiger
from takumi.ig.instascrape import InstascrapeError

from .blueprint import api


def db_status():
    status = {"healthy": True}
    try:
        engine = create_engine(
            current_app.config["SQLALCHEMY_DATABASE_URI"], connect_args={"connect_timeout": 1}
        )
        connection = engine.connect()
        connection.close()
        engine.dispose()
    except Exception as e:
        status["healthy"] = False
        status["msg"] = str(e)  # This is a little leaky but ok for now

    return status


def redis_status():
    status = {"healthy": True}
    try:
        redis.get_connection().ping()
    except RedisError as e:
        status["healthy"] = False
        status["error"] = str(e)
    return status


def alembic_status():
    status = {"healthy": True}
    try:
        status["current_head"] = alembic_utils.get_heads()
    except Exception as e:
        status["current_head"] = None
        status["msg"] = str(e)
    try:
        status["deployed_head"] = alembic_utils.get_stored_heads()
    except Exception as e:
        status["deployed_head"] = None
        status["msg"] = str(e)
    return status


def tiger_status():
    status = {"healthy": True}
    try:
        tiger.get_queue_stats(report_statsd=True)
    except Exception as e:
        status["healthy"] = False
        status["error"] = str(e)
    return status


def instascrape_status():
    status = {"healthy": True}
    return status  # TODO enable this check
    if current_app.config.get("RELEASE_STAGE") == "local":
        return status
    try:
        status["details"] = instascrape.status()
    except InstascrapeError as e:
        status["healthy"] = False
        status["error"] = str(e)
    return status


def elasticsearch_status():
    status = {"healthy": True}
    try:
        status["healthy"] = elasticsearch.ping()
    except Exception as e:
        status["healthy"] = False
        status["error"] = str(e)
    return status


@api.route("/status")
def server_status():
    status = {
        "services": {
            "db": db_status(),
            "alembic": alembic_status(),
            "redis": redis_status(),
            "tiger": tiger_status(),
            "instascrape": instascrape_status(),
            "elasticsearch": elasticsearch_status(),
        },
        "api": {
            "git_hash": current_app.config["GITHASH"],
            "version": current_app.config["VERSION"],
        },
    }

    all_healthy = all([service.get("healthy", False) for service in status["services"].values()])

    if not all_healthy:
        with push_scope() as scope:
            scope.set_extra("status", status)
            capture_message("API /status check failed")

    return jsonify(status), all_healthy and 200 or 500


@api.route("/_raise", methods=["GET", "POST"])
def _raise():
    raise APIError("_raise!", 500)


@api.route("/_crash", methods=["GET", "POST"])
def _crash():
    return str(1 / 0)
