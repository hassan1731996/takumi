from collections import defaultdict

from flask import Flask
from mock import Mock

from core.common.monitoring import StatsD, StatsdMiddleware

from takumi.app import create_app


class FakeStatsD:
    def __init__(self):
        self.calls = []

    def timing(self, *args, **kwargs):
        self.calls.append({"timing": [args, kwargs]})

    def some_non_overloaded_method(self, *args, **kwargs):
        self.calls.append({"some_non_overloaded_method": [args, kwargs]})

    def _timing(self, *args, **kwargs):
        pass


def test_stats_middleware_emits_non_2xx_metrics(influencer_client, app):
    resp = influencer_client.get("/_raise")
    assert resp.status_code != 200
    metric_tags = app.config["statsd"].timing.call_args[1]["tags"]
    assert "http_status_code:{}".format(resp.status_code) in metric_tags


def test_statsd_wrapper_adds_tags_if_tags():
    mock = FakeStatsD()
    statsd = StatsD(mock, tags=["tag1"])
    statsd.timing()
    assert "tags" in mock.calls[0]["timing"][1]


def test_statsd_wrapper_does_not_add_tags_if_no_tags():
    mock = FakeStatsD()
    statsd = StatsD(mock)
    statsd.timing()
    assert "tags" not in mock.calls[0]["timing"][1]


def test_statsd_wrapper_adds_sample_rate_if_none_given():
    mock = FakeStatsD()
    statsd = StatsD(mock)
    statsd.timing()
    assert "sample_rate" in mock.calls[0]["timing"][1]
    assert mock.calls[0]["timing"][1]["sample_rate"] == 1


def test_statsd_wrapper_leaves_sample_rate_untouched_if_given():
    mock = FakeStatsD()
    statsd = StatsD(mock)
    statsd.timing(sample_rate=999)
    assert "sample_rate" in mock.calls[0]["timing"][1]
    assert mock.calls[0]["timing"][1]["sample_rate"] == 999


def test_statsd_wrapper_does_not_wrap_and_add_tags_to_non_overloaded_methods():
    mock = FakeStatsD()
    statsd = StatsD(mock, tags=["tag1"])
    statsd.some_non_overloaded_method()
    assert "tags" not in mock.calls[0]["some_non_overloaded_method"][1]


def test_statsd_middleware_metric_name():
    app = create_app(testing=True)
    mw = StatsdMiddleware(app, Mock())
    path = "/self/terms/accept?here=is&more=data"
    expected = "api.accept_terms"
    assert mw._metric_name(path, method="POST") == expected


def test_statsd_middleware_calls_emit_aggregate_stats():
    app = Flask("test")

    @app.route("/")
    def blah():
        return ""

    mw = StatsdMiddleware(app, Mock())
    mock_emit = Mock()
    setattr(mw, "_emit_aggregate_stats", mock_emit)
    env = defaultdict(str)
    env["PATH_INFO"] = "/"
    mw(env, Mock())
    assert mock_emit.called


def test_statsd_emit_aggregate_stats():
    app = Flask("test")
    mw = StatsdMiddleware(app, Mock(), "prefix")

    class FakeMetric:
        time = 5.0
        cpu_time = 2.5
        tags = ["http_status_code:200"]

    expected_tags = ["http_status_code:200", "view:test_view"]

    mw._emit_aggregate_stats("test_view", FakeMetric())
    assert mw.statsd.timing.called
    assert mw.statsd.timing.call_args_list[0][0] == ("prefix.api.request", 5.0)
    assert mw.statsd.timing.call_args_list[0][1] == {"tags": expected_tags}
    assert mw.statsd.timing.call_args_list[1][0] == ("prefix.api.request.cpu", 2.5)
    assert mw.statsd.timing.call_args_list[1][1] == {"tags": expected_tags}
