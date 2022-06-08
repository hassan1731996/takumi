import re
from typing import Tuple

from flask import _request_ctx_stack, request  # type: ignore

CLIENT_VERSION_HEADER = "Takumi-Client-Version"
CLIENT_PLATFORM_HEADER = "Takumi-Platform-Name"
DEFAULT_CLIENT_VERSION = (0, 0, 0)
VERSION_REGEX = re.compile(r"(\d+\.\d+\.\d+)")


def _get_headers():
    if _request_ctx_stack:  # use flask request headers if available
        return request.headers
    else:
        return {}


def get_request_version(headers=None) -> Tuple[int, ...]:
    if headers is None:
        headers = _get_headers()

    version = headers.get(CLIENT_VERSION_HEADER)
    if version is None:
        return DEFAULT_CLIENT_VERSION

    try:
        version_number = VERSION_REGEX.findall(version)[0]
        return tuple(int(n) for n in version_number.split("."))
    except Exception:
        return DEFAULT_CLIENT_VERSION


def get_request_platform(headers=None):
    if headers is None:
        headers = _get_headers()

    platform = headers.get(CLIENT_PLATFORM_HEADER)
    if platform is None:
        return "web"

    return platform
