import mock
import pytest
from elasticsearch_dsl import Search

from core.elasticsearch import ResultSet


@pytest.yield_fixture(scope="function")
def elasticsearch():
    return mock.MagicMock()


@pytest.yield_fixture(scope="function")
def query():
    return {}


@pytest.yield_fixture(scope="function")
def resultset(query, elasticsearch):
    rs = ResultSet(query, elasticsearch)
    rs.hits = []
    rs.total_hits = None
    yield rs


def test_resultset_with_dsl_search_object_converts_to_dict(elasticsearch):
    rs = ResultSet(Search(), elasticsearch)
    assert type(rs.query) == dict


def test_resultset_with_invalid_query_type_raises_valueerror(elasticsearch):
    with pytest.raises(ValueError):
        ResultSet(1, elasticsearch)


def test_resultset_fetch_when_not_initialized(elasticsearch, resultset):
    resultset.initialied = False
    resultset.fetch()
    assert elasticsearch.search.called


def test_resultset_fetch_when_initialized_but_new_offset_or_limit(elasticsearch, resultset, query):
    assert resultset.initialized is False
    resultset.fetch()
    assert elasticsearch.search.called
    assert elasticsearch.search.call_count == 1

    assert resultset.initialized is True
    resultset.fetch(offset=1, limit=2)
    assert elasticsearch.search.call_count == 2

    assert query["from"] == 1
    assert query["size"] == 2


def test_resultset_fetch_early_return_if_initialized_and_unchanged_offsets(
    elasticsearch, resultset
):
    resultset.initialized = True
    resultset.fetch()
    assert not elasticsearch.search.called

    resultset.fetch(offset=resultset.offset, limit=resultset.limit)
    assert not elasticsearch.search.called


def test_resultset_count_calls_fetch_with_zero_zero_if_not_initialized(resultset):
    mock_fetch = mock.Mock()
    setattr(resultset, "fetch", mock_fetch)
    resultset.count()
    assert mock_fetch.called
    assert mock_fetch.call_args[0] == (0, 0)


def test_resultset_get_item_slice_calls_fetch_with_slice_start_and_size(resultset):
    mock_fetch = mock.Mock()
    setattr(resultset, "fetch", mock_fetch)
    resultset[1:100]  # try to get 99 elements
    assert mock_fetch.called
    assert mock_fetch.call_args[0] == (1, 99)


def test_resultset_first_calls_fetch_with_zero_one_if_not_initialized(resultset):
    mock_fetch = mock.Mock()
    setattr(resultset, "fetch", mock_fetch)

    resultset.first()
    assert mock_fetch.called
    assert mock_fetch.call_args_list[0][0] == (0, 1)


def test_result_set_with_zero_hits_first_returns_none(resultset):
    mock_fetch = mock.Mock(return_value=None)
    setattr(resultset, "fetch", mock_fetch)

    assert resultset.first() is None


def test_result_set_repr_calls_fetch_if_not_initialized(resultset):
    mock_fetch = mock.Mock(return_value=None)
    setattr(resultset, "fetch", mock_fetch)
    repr(resultset)
    assert mock_fetch.called
