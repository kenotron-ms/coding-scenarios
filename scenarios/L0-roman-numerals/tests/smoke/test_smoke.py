"""Smoke tier (VISIBLE to the strategy). Not weight-bearing; a fast self-check."""
import pytest

import roman


def test_smoke_to_roman_4():
    assert roman.to_roman(4) == "IV"


def test_smoke_to_roman_1994():
    assert roman.to_roman(1994) == "MCMXCIV"


def test_smoke_from_roman_xlii():
    assert roman.from_roman("XLII") == 42


def test_smoke_round_trip():
    assert roman.from_roman(roman.to_roman(2024)) == 2024


def test_smoke_invalid_raises():
    with pytest.raises(ValueError):
        roman.to_roman(0)
