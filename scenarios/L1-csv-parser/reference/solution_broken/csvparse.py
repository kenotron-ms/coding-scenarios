"""L1 broken mutant — deliberately WRONG. Used to prove the grader discriminates.

Naive `text.splitlines()` + `line.split(delimiter)`: ignores all quoting, so
delimiters/newlines embedded in quoted fields are not handled, escaped quotes
are not unescaped, and malformed input is never detected. It must FAIL the
gate (acceptance_pass < 1.0) and score 0 / Failed.
"""

from __future__ import annotations


def parse_csv(
    text: str,
    *,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[list[str]]:
    _ = quotechar  # unused: this mutant ignores quoting entirely
    if not text:
        return []
    return [line.split(delimiter) for line in text.splitlines()]
