import pytest

from takumi.gql.resolver import default_resolver


class Object:
    key = "value"


obj = Object()
dic = {"key": "value"}


def test_default_resolver_with_an_object():
    result = default_resolver("key", None, obj, None)

    assert result == "value"


def test_default_resolver_with_a_dict():
    result = default_resolver("key", None, dic, None)

    assert result == "value"


def test_default_resolver_doesnt_swallow_attribute_error_coming_from_deep_in_the_object():
    class Err:
        @property
        def prop(self):
            raise AttributeError("Deep attribute error")

    err = Err()

    with pytest.raises(AttributeError):
        default_resolver("prop", None, err, None)


def test_default_resolver_returns_default_value_with_key_not_in_object():
    result = default_resolver("not_in_obj", "default_value", obj, None)

    assert result == "default_value"


def test_default_resolver_returns_default_value_with_key_not_in_dict():
    result = default_resolver("not_in_dict", "default_value", dic, None)

    assert result == "default_value"
