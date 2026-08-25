"""Acceptance tier (HELD OUT). Denominator = 6 (see rubric.yaml). Defines "working"."""
import pytest

import roman


def test_round_trip_sweep():  # L0-AC01
    for n in range(1, 4000):
        assert roman.from_roman(roman.to_roman(n)) == n


def test_subtractive_forms():  # L0-AC02
    for n, exp in {4: "IV", 9: "IX", 40: "XL", 90: "XC", 400: "CD", 900: "CM"}.items():
        assert roman.to_roman(n) == exp


def test_known_values():  # L0-AC03
    assert roman.to_roman(1994) == "MCMXCIV"
    assert roman.to_roman(3999) == "MMMCMXCIX"
    assert roman.from_roman("XLII") == 42
    assert roman.from_roman("MCMLIV") == 1954


def test_to_roman_invalid_raises():  # L0-AC04
    for bad in (0, 4000, -1, 3.5, "x"):
        with pytest.raises(ValueError):
            roman.to_roman(bad)


def test_from_roman_invalid_raises():  # L0-AC05
    for bad in ("", "IIII", "IC", "VV", "ABC", "XM"):
        with pytest.raises(ValueError):
            roman.from_roman(bad)


def test_case_policy_consistent():  # L0-AC06
    # §1.6: policy may accept lowercase (== uppercase) or reject it, but must be consistent.
    try:
        value = roman.from_roman("iv")
    except ValueError:
        return  # reject-lowercase policy: consistent
    assert value == roman.from_roman("IV")  # accept-lowercase policy: must match
