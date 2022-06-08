import mock

from takumi.utils.tiktok import parse_username


def test_parse_username_with_different_lengths():
    assert parse_username("a") == None  # At least 2 characters
    assert parse_username("@a") == None  # At least 2 characters
    assert parse_username("a" * 25) == None  # No more than 24 characters
    assert parse_username("aa") == "aa"
    assert parse_username("a" * 24) == "a" * 24
    assert parse_username("@" + "a" * 24) == "a" * 24


def test_parse_username_with_underscores():
    assert parse_username("___") == "___"
    assert parse_username("a_b_c") == "a_b_c"
    assert parse_username("@a_b_c") == "a_b_c"


def test_parse_username_with_periods():
    assert parse_username("a.b") == "a.b"
    assert parse_username(".a.b") == ".a.b"
    assert parse_username("a.b.") == None  # Can't end with period
    assert parse_username("@.a.b") == ".a.b"


def test_parse_username_with_numbers():
    assert parse_username("12") == None  # Can't be only numbers
    assert parse_username("a2") == "a2"
    assert parse_username("1a") == "1a"
    assert parse_username("@1a") == "1a"


def test_parse_username_with_at_symbol():
    assert parse_username("@foo") == "foo"
    assert parse_username("@.bar") == ".bar"


def test_parse_username_with_full_profile_url():
    assert parse_username("https://www.tiktok.com/@takumihq") == "takumihq"
    assert parse_username("https://www.tiktok.com/@takumihq?foo=bar") == "takumihq"
    assert parse_username("tiktok.com/@takumihq") == "takumihq"
    assert parse_username("tiktok.com/@foo_bar.baz") == "foo_bar.baz"


def test_parse_username_with_shortened_url():
    valid_redirected_url = (
        "https://www.tiktok.com/@foo_bar.baz?language=es&sec_uid="
        "MS4wLjABAAAAkbs3MGjYojcni70XmJly2UYW0sge8Ytc5C5no5EsBjg&u_co"
        "de=daa5al9m5fhla2&timestamp=1582267686&utm_source=copy&utm_c"
        "ampaign=client_share&utm_medium=android&share_app_name=music"
        "ally&share_iid=6795762392309860102&source=h5_m"
    )
    with mock.patch("takumi.utils.tiktok.follow_redirects", return_value=valid_redirected_url):
        assert parse_username("https://vm.tiktok.com/foobar") == "foo_bar.baz"
        assert parse_username("vm.tiktok.com/foobar") == "foo_bar.baz"


def test_parse_username_invalid():
    assert parse_username("?A#$?A") == None
    assert parse_username("https://takumi.com/about") == None
    assert parse_username("https://tiktok.com/legal") == None


def test_parse_username_with_url_and_stuff_pulls_url_correctly():
    with mock.patch("takumi.utils.tiktok.follow_redirects") as mock_redirect:
        mock_redirect.return_value = "https://www.tiktok.com/@foo"
        assert parse_username("NAME AND STUFF https://vm.tiktok.com/foo123/")
        assert parse_username("https://vm.tiktok.com/foo123/ NAME AND STUFF")

    assert mock_redirect.call_count == 2
    assert mock_redirect.call_args_list == [
        mock.call("https://vm.tiktok.com/foo123/"),
        mock.call("https://vm.tiktok.com/foo123/"),
    ]
