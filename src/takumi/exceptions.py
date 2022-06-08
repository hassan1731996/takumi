from flask import g, jsonify
from flask_principal import PermissionDenied
from sentry_sdk import capture_message

from core.common.exceptions import APIError

from takumi.error_codes import OUTDATED_CLIENT_VERSION
from takumi.events import EventApplicationException
from takumi.extensions import login_manager
from takumi.ig.instascrape import InstascrapeError

from .vsapi import VERSION_REGEX, get_request_platform, get_request_version


class APNSPayloadSizeTooLarge(Exception):
    pass


class AccountsCurrencyMismatch(Exception):
    pass


class BudgetEstimateException(Exception):
    pass


class GigReservationException(Exception):
    pass


class GigExpirationException(Exception):
    pass


class UnknownCallbackLabelException(Exception):
    pass


class PushNotificationError(Exception):
    def __init__(self, message, http_status=500, payload=""):
        self.message = message
        self.http_status = http_status
        self.payload = payload


def _parse_version(version):
    if isinstance(version, str):
        return tuple([int(n) for n in VERSION_REGEX.findall(version)[0].split(".")])
    return version


def client_version_is_lower_than_min_version(client_version, min_version):
    client_version = _parse_version(client_version)
    enforce_version = _parse_version(min_version)
    if client_version == (0, 0, 0):
        return False
    if client_version < enforce_version:
        return True
    return False


class ClientUpgradeRequired(APIError):
    error_message = (
        "Takumi app is out of date. Update to the latest version {store}to continue using Takumi."
    )
    upgrade_urls = {
        "ios": "https://itunes.apple.com/us/app/takumi-connect-with-brands/id1042708237?ls=1",
        "android": "https://play.google.com/store/apps/details?id=com.takumi&hl=en",
    }
    store_strings = {"ios": "in the App Store ", "android": "in the Play Store "}

    MIN_CLIENT_SUPPORTING_FORCE_UPDATE = (3, 1, 1)

    def __init__(self, client_version, min_version, request):
        payload = {"required_version": self.format_version(min_version)}
        platform = self.get_client_platform(request.headers)
        if platform in self.upgrade_urls:
            payload["upgrade_url"] = self.upgrade_urls[platform]

        return super().__init__(
            self.error_message.format(store=self.store_strings.get(platform, "")),
            status_code=415,
            error_code=OUTDATED_CLIENT_VERSION,
            payload=payload,
        )

    def format_version(self, version):
        return ".".join(map(str, version))

    def get_client_platform(self, headers):
        platform_map = {"iPhone OS": "ios", "iOS": "ios", "Android": "android"}
        platform = get_request_platform(headers)
        return platform_map.get(platform)

    @classmethod
    def raise_for_version(cls, min_version, request):
        min_version = _parse_version(min_version)
        client_version = get_request_version(request.headers)
        if client_version_is_lower_than_min_version(client_version, min_version):
            raise cls(client_version, min_version, request)


def handle_api_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def handle_permission_error(error):
    error = dict(message=str(error))
    if hasattr(g, "identity"):
        error["current_needs"] = [need.value for need in g.identity.provides]

    response = jsonify(error=error)
    response.status_code = 403
    return response


def handle_event_application_error(error):
    response = jsonify(error=dict(message=str(error)))
    response.status_code = 422
    return response


def handle_instascrape_error(error):
    """Report instascraper error to sentry, but show graceful error"""
    capture_message(f"Instascrape error: {error}")

    response = jsonify(
        error=dict(message="Instagram is currently unavailable, please try again later")
    )
    response.status_code = 503
    return response


def register_error_handlers(app):
    app.errorhandler(APIError)(handle_api_error)
    app.errorhandler(PermissionDenied)(handle_permission_error)
    app.errorhandler(EventApplicationException)(handle_event_application_error)
    app.errorhandler(InstascrapeError)(handle_instascrape_error)

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        return jsonify(error=dict(message="Unauthorized")), 401

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify(error=dict(message="Not Found")), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        return jsonify(error=dict(message="Method not Allowed")), 405

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify(error=dict(message="Request Entity Too Large")), 413

    @app.errorhandler(415)
    def unsupported_media(error):
        return jsonify(error=dict(message="Only `application/json` is supported")), 415

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify(error=dict(message="Too many requests")), 429

    @app.errorhandler(500)
    def internal_error(error):
        from takumi.extensions import db

        db.session.rollback()
        return jsonify(error=dict(message="Server Error")), 500
