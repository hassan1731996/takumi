import pytest

from core.common.instagram import InvalidShortCode, shortcode_to_id, shorten_ig_id


def test_shorten_ig_id_handles_str_with_user_part():
    assert shorten_ig_id("1202077265624618258_362197100") == "BCuoud6INUS"


def test_shorten_ig_id_handles_str_without_user_part():
    assert shorten_ig_id("1202077265624618258") == "BCuoud6INUS"


def test_shorten_ig_id_handles_long():
    assert shorten_ig_id(1_202_077_265_624_618_258) == "BCuoud6INUS"


def test_shorten_ig_id_handles_unicode():
    assert shorten_ig_id("1202077265624618258") == "BCuoud6INUS"


def test_shorten_ig_id_returns_non_digit_string():
    assert shorten_ig_id("BCuoud6INUS") == "BCuoud6INUS"


def test_shortcode_to_id_converts_to_id():
    assert shortcode_to_id("BCuoud6INUS") == "1202077265624618258"


def test_shortcode_to_id_invalid_code_raises():
    with pytest.raises(InvalidShortCode):
        shortcode_to_id("sadlfjo34f2034fj20f923joks90df9s09fsd")


def test_shortcode_to_id_doesnt_convert_integer_id():
    assert shortcode_to_id("12020772656246182528") == "12020772656246182528"
