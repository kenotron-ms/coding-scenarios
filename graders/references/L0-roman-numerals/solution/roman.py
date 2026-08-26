"""Roman numeral conversion — L0 reference solution (a correct, passing solution).

Used to sanity-check the grader: it MUST pass the gate and score high.
"""
from __future__ import annotations

_VALUES: list[tuple[int, str]] = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]
_SYM: dict[str, int] = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def to_roman(n: int) -> str:
    """Return the standard Roman numeral for 1 <= n <= 3999; else raise ValueError."""
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 3999:
        raise ValueError(f"to_roman: expected int in [1, 3999], got {n!r}")
    out: list[str] = []
    for val, sym in _VALUES:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def from_roman(s: str) -> int:
    """Return the integer for a standard Roman numeral.

    Policy (resolves REQUIREMENTS §1.6): UPPERCASE only. Lowercase, empty,
    malformed, or non-standard numerals (e.g. ``IIII``, ``IC``) raise ValueError.
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
