from core.math.math import round_fractional


def test_round_fractional_default_significand():
    assert round_fractional(123) == (100, 23)


def test_round_fractional_no_significand():
    assert round_fractional(123, 0) == (123, 0)


def test_round_fractional_zero():
    assert round_fractional(0) == (0, 0)


def test_round_fractional_larger_number():
    assert round_fractional(12_897_183_481_741) == (12_897_183_481_700, 41)
    assert round_fractional(12_897_183_481_741, 3) == (12_897_183_481_000, 741)
