from takumi.vsapi import CLIENT_VERSION_HEADER, DEFAULT_CLIENT_VERSION, get_request_version


def test_request_version_returns_default_if_none_found_in_headers():
    assert get_request_version({}) == DEFAULT_CLIENT_VERSION


def test_request_version_returns_none_if_invalid_version_string():
    assert get_request_version({CLIENT_VERSION_HEADER: -1}) == DEFAULT_CLIENT_VERSION


def test_request_version_returns_version_tuple():
    assert get_request_version({CLIENT_VERSION_HEADER: "1.2.3"}) == (1, 2, 3)


def test_request_version_returns_version_tuple_even_with_postfix():
    assert get_request_version({CLIENT_VERSION_HEADER: "1.2.3-beta"}) == (1, 2, 3)


def test_request_version_with_larger_numbers():
    assert get_request_version({CLIENT_VERSION_HEADER: "3.5.10"}) == (3, 5, 10)
    assert get_request_version({CLIENT_VERSION_HEADER: "33.55.11"}) == (33, 55, 11)
