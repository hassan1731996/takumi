from contextlib import contextmanager

import pytest
from flask import g, request

from core.common.exceptions import APIError

from takumi.auth import SIGNATURE_HEADERS, _get_signature, task
from takumi.models import ApiTask


class UrlRule:
    def __init__(self, endpoint):
        self.endpoint = endpoint


def test_task_decorator_raises_exception_if_no_g_task():
    with pytest.raises(Exception) as exc:
        wrapped = task(lambda: None)
        wrapped()
    assert "non-task blueprint" in exc.exconly()


@pytest.fixture(autouse=True, scope="module")
def app_context(app):
    pass


@contextmanager
def api_task_request(allowed_views, secret=None, **request_attrs):
    old_request_attrs = {}
    for attr, value in request_attrs.items():
        old_request_attrs[attr] = getattr(request, attr)
        setattr(request, attr, value)

    setattr(g, "task", ApiTask(allowed_views=allowed_views, secret=secret))
    wrapped = task(lambda: None)
    yield wrapped

    delattr(g, "task")
    for attr, value in old_request_attrs.items():
        setattr(request, attr, value)


def test_task_decorator_raises_exception_if_endpoint_not_in_allowed_views():
    with api_task_request([], url_rule=UrlRule("test.something")) as view:
        with pytest.raises(APIError) as exc:
            view()
        assert "Access denied" in exc.exconly()


def test_task_decorator_does_not_raise_exception_if_endpoint_in_allowed_views():
    route = "test.something"
    with api_task_request([route], url_rule=UrlRule(route)) as view:
        view()


def test_task_decorator_raises_exception_if_secret_missing():
    route = "test.something"
    with api_task_request([route], "test secret", url_rule=UrlRule(route)) as view:
        with pytest.raises(APIError) as exc:
            view()
        assert "Access denied" in exc.exconly()


def test_task_decorator_raises_exception_if_signature_mismatch():
    route = "test.something"
    headers = {key: "wrong signature" for key in SIGNATURE_HEADERS}
    with api_task_request(
        [route], secret="test secret", url_rule=UrlRule(route), headers=headers
    ) as view:
        with pytest.raises(APIError) as exc:
            view()
        assert "Access denied" in exc.exconly()


def test_task_decorator_does_not_raise_exception_if_signature_found_in_any_valid_header():
    route = "test.something"
    correct_signature = _get_signature("test secret", "test string")
    request_attrs = dict(url_rule=UrlRule(route), data="test string")

    for header in SIGNATURE_HEADERS:
        request_attrs["headers"] = {header: correct_signature}
        with api_task_request([route], "test secret", **request_attrs) as view:
            try:
                view()
            except Exception as exception:
                assert False, "Failed for header: {} (exception: {})".format(header, exception)


def test_get_signature_handles_unicode():
    expected = "d44616514169dc4e793d99ffd02152ef8fd91f0db313eb3fc1844f49f18d083a"
    assert _get_signature("test secret", "test string") == expected
    assert _get_signature("test secret", "test string") == expected
    assert _get_signature("test secret", "test string") == expected
    assert _get_signature("test secret", "test string") == expected
