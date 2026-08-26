"""Roman numeral conversion module.

Provides two pure functions for converting between integers and Roman numeral strings.
Both functions use only the Python standard library and target Python >= 3.11.
"""
from __future__ import annotations

_VALUES: list[tuple[int, str]] = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]

_SYM: dict[str, int] = {
    "I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000
}


def to_roman(n: int) -> str:
    """Convert an integer to its standard Roman numeral string.

    Converts integers in the range [1, 3999] to Roman numerals using subtractive
    notation (e.g. 4 -> 'IV', 9 -> 'IX', 40 -> 'XL', 90 -> 'XC', 400 -> 'CD',
    900 -> 'CM').

    Args:
        n: An integer in the range [1, 3999].

    Returns:
        The Roman numeral string representation of n.

    Raises:
        ValueError: If n is not an integer (or is a bool), or if n is outside
                    the range [1, 3999].
    """
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 3999:
        raise ValueError(f"to_roman: expected int in [1, 3999], got {n!r}")
    out: list[str] = []
    for val, sym in _VALUES:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def from_roman(s: str) -> int:
    """Convert a standard Roman numeral string to its integer value.

    Parses standard Roman numeral strings using the subtractive rule. Only
    uppercase Roman numerals are accepted; lowercase characters will raise
    ValueError (uppercase-only policy).

    Policy: This function accepts UPPERCASE only. Lowercase characters,
    empty strings, malformed numerals, or non-standard forms (e.g. 'IIII',
    'IC', 'VV', 'XM') all raise ValueError.

    Args:
        s: A non-empty string containing an uppercase standard Roman numeral.

    Returns:
        The integer value of the Roman numeral.

    Raises:
        ValueError: If s is not a string, is empty, contains lowercase or
                    invalid characters, or is a non-standard numeral form.
    """
    if not isinstance(s, str) or not s:
        raise ValueError(f"from_roman: expected non-empty str, got {s!r}")
    if any(c not in _SYM for c in s):
        raise ValueError(f"from_roman: invalid characters in {s!r}")
    values = [_SYM[c] for c in s]
    total = 0
    for i, v in enumerate(values):
        if i + 1 < len(values) and v < values[i + 1]:
            total -= v
        else:
            total += v
    if not 1 <= total <= 3999:
        raise ValueError(f"from_roman: value out of range for {s!r}")
    # Canonicity check: only the standard spelling is accepted.
    if to_roman(total) != s:
        raise ValueError(f"from_roman: non-standard numeral {s!r}")
    return total
