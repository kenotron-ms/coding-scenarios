"""L0 broken mutant — deliberately WRONG. Used to prove the grader discriminates.

Additive-only (no subtractive notation) and no validation. It must FAIL the gate
(acceptance_pass < 1.0) and score 0 / Failed.
"""
from __future__ import annotations

_TABLE = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]
_SYM = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def to_roman(n: int) -> str:
    out = []
    for val, sym in _TABLE:  # additive only -> 4 becomes "IIII", 1994 wrong
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def from_roman(s: str) -> int:
    return sum(_SYM[c] for c in s)  # no validation, no canonicity check
