"""L1 "csvlib" mutant — behaviorally correct BUT uses the FORBIDDEN stdlib `csv`.

Exists only to prove the grader's `absent_import` probe (`check:L1-CSVLIB-none`
in rubric.yaml) actually fires: this solution is built on `csv.reader` for
real tokenization (not just a decorative unused import), replicates the same
§1.6 resolutions as `reference/solution/csvparse.py` (raise on malformed
input, preserve whitespace verbatim, strip a leading BOM), and is written to
pass the acceptance suite at 100%. It MUST still FAIL the gate, because
`gate: "acceptance_pass == 1.0 and check:L1-CSVLIB-none"` and this module
violates REQUIREMENTS.md §2.4 (`import csv` is a constraint violation, not a
correctness one). Proves the probe discriminates independently of
correctness.
"""

from __future__ import annotations

import csv
import io

# Unicode Private-Use-Area codepoint used only as an internal shield for a
# lone `\r` (FR-9): `io.StringIO`/`csv.reader` always treat a bare `\r` as a
# line terminator during line-splitting, regardless of quoting or the
# `newline=` argument, which is wrong per FR-9 ("a lone \r ... is ordinary
# data"). We swap it out before parsing and restore it in every field
# afterwards -- csv.reader never sees it and can't misinterpret it.
_CR_SENTINEL = "\ue000"


def _shield_lone_cr(text: str) -> str:
    """Replace every `\\r` not immediately followed by `\\n` with a sentinel."""
    n = len(text)
    out: list[str] = []
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\r" and not (i + 1 < n and text[i + 1] == "\n"):
            out.append(_CR_SENTINEL)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def parse_csv(
    text: str,
    *,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[list[str]]:
    """Parse CSV text using the (forbidden) stdlib `csv` module.

    Same three §1.6 resolutions as the reference solution: (a) malformed
    input raises ValueError; (b) whitespace around unquoted fields is
    preserved verbatim; (c) a single leading BOM is stripped.
    """
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValueError(f"delimiter must be a single character, got {delimiter!r}")
    if not isinstance(quotechar, str) or len(quotechar) != 1:
        raise ValueError(f"quotechar must be a single character, got {quotechar!r}")
    if delimiter == quotechar:
        raise ValueError(f"delimiter and quotechar must differ, both are {delimiter!r}")

    text = text.removeprefix("\ufeff")
    if not text:
        return []

    csv.field_size_limit(max(csv.field_size_limit(), len(text) + 1))
    buf = io.StringIO(_shield_lone_cr(text), newline="")
    reader = csv.reader(buf, delimiter=delimiter, quotechar=quotechar, strict=True)
    rows: list[list[str]] = []
    try:
        for raw_row in reader:
            # FR-7: csv.reader yields [] for a blank line; we require [""].
            fields = raw_row if raw_row else [""]
            rows.append([f.replace(_CR_SENTINEL, "\r") for f in fields])
    except csv.Error as exc:
        raise ValueError(f"malformed CSV input: {exc}") from exc
    return rows
