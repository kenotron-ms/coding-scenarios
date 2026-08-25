"""Adversarial tier (HIDDEN). Denominator = 8. Feeds COR/ROB; never the gate."""
import pytest

import roman


def test_adv_IIII_invalid():
    with pytest.raises(ValueError):
        roman.from_roman("IIII")


def test_adv_IC_invalid():
    with pytest.raises(ValueError):
        roman.from_roman("IC")


def test_adv_XM_invalid():
    with pytest.raises(ValueError):
        roman.from_roman("XM")


def test_adv_VX_invalid():
    with pytest.raises(ValueError):
        roman.from_roman("VX")


def test_adv_MMMM_out_of_range():
    with pytest.raises(ValueError):
        roman.from_roman("MMMM")


def test_adv_empty_whitespace_invalid():
    for bad in ("", " ", "\t", "  IV "):
        with pytest.raises(ValueError):
            roman.from_roman(bad)


def test_adv_boundary_1():
    assert roman.to_roman(1) == "I"
    assert roman.from_roman("I") == 1


def test_adv_boundary_3999():
    assert roman.to_roman(3999) == "MMMCMXCIX"
    assert roman.from_roman("MMMCMXCIX") == 3999
