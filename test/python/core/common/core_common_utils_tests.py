from core.common.chunks import chunks
from core.common.utils import States, pairwise, partitioned_key_name


def test_partitioned_key_name():
    assert partitioned_key_name("foobar") == "f/o/o/bar"


def test_pairwise_with_multiple_data_returns_four_tuple_pairs():
    iterable = iter([1, 2, 3, 4, 5])
    data = pairwise(iterable)
    assert next(data) == (1, 2)
    assert next(data) == (2, 3)
    assert next(data) == (3, 4)
    assert next(data) == (4, 5)
    assert sum(1 for _ in data) == 0


def test_pairwise_with_0_data_returns_empty_listiterable():
    iterable = iter([])
    data = pairwise(iterable)
    assert sum(1 for _ in data) == 0


def test_pairwise_with_1_data_returns_empty_listiterable():
    iterable = iter([1])
    data = pairwise(iterable)
    assert sum(1 for _ in data) == 0


def test_pairwise_with_2_data_returns_one_tuple_pair():
    iterable = iter([1, 2])
    data = pairwise(iterable)
    assert next(data) == (1, 2)
    assert sum(1 for _ in data) == 0


def test_chunks_with_even_sized_chunks():
    result = chunks([1, 2, 3, 4], 2)

    assert list(result) == [[1, 2], [3, 4]]


def test_chunks_with_uneven_sized_chunks():
    result = chunks([1, 2, 3], 2)

    assert list(result) == [[1, 2], [3]]


def test_chunks_with_empty_array():
    result = chunks([], 10)

    assert list(result) == []


def test_states_values():
    class STATES(States):
        FOO = "foo"
        BAR = "bar"

        def func(self):
            pass

    assert STATES.values() == ["foo", "bar"]
