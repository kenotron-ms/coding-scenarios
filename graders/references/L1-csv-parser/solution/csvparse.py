"""csvparse — a dependency-free RFC 4180-subset CSV parser.

Reference solution for scenario L1-csv-parser. Used to sanity-check the
grader: it MUST pass the acceptance gate and the "no stdlib csv" probe, and
score high (REQUIREMENTS.md §7, `HARNESS.md` §5).
"""

from __future__ import annotations


def _position(text: str, offset: int) -> tuple[int, int]:
    """1-based (line, column) of `offset` into `text`, for error messages.

    Only ever called on the (rare) malformed-input path, so it does not cost
    anything in the hot loop of the success path (NFR-1).
    """
    prefix = text[:offset]
    last_nl = prefix.rfind("\n")
    line = prefix.count("\n") + 1
    col = offset - last_nl if last_nl != -1 else offset + 1
    return line, col


def parse_csv(
    text: str,
    *,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[list[str]]:
    r"""Parse RFC 4180-subset CSV `text` into a list of rows of string fields.

    Single-pass character scanner over `text`: the only state is an
    in-quotes flag, the current field buffer, the current row buffer, and a
    one-character lookahead (used solely to recognize ``\r\n`` and doubled
    quotes). No regex, no split-then-repair, no I/O, no globals, no mutation
    of arguments — equal inputs always return equal outputs.

    This resolves the three ambiguities left open by REQUIREMENTS.md §1.6:

    (a) **Malformed input** (an unterminated quoted field, or stray
        characters immediately following a closing quote, e.g. ``"ab"cd``)
        raises ``ValueError`` naming the 1-based ``line``/``column`` of the
        fault. Both sibling malformed constructs use this same raise policy
        (never silent recovery), and no field already accumulated is ever
        silently dropped before the error is raised.
    (b) **Whitespace around unquoted fields** is preserved **verbatim** —
        never stripped. Whitespace inside quoted fields is always preserved
        regardless of this choice.
    (c) A single leading UTF-8 **BOM** (``U+FEFF``) is stripped before
        parsing; it never affects field or row counts and never touches any
        field other than the first field of the first record.

    Args:
        text: the CSV document to parse.
        delimiter: single-character field separator (default ``,``).
        quotechar: single-character quote character (default ``"``).

    Returns:
        A list of rows, each a list of string fields. Empty `text` (after
        BOM-stripping) returns ``[]``. A blank line (interior or as the
        whole input) yields a record of one empty field, ``[""]`` — it is
        not skipped. A single trailing record separator terminates the
        final record without creating an extra empty row.

    Raises:
        ValueError: if `delimiter`/`quotechar` are not single, distinct
            characters, or if `text` contains a malformed quoted field.
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

    n = len(text)
    rows: list[list[str]] = []
    row: list[str] = []
    field: list[str] = []
    i = 0
    in_quotes = False
    quote_start = 0
    # after_close: just closed a quoted field; only delimiter/terminator/EOF
    # may legally follow (FR-2, and the §1.6(a) "chars after closing quote"
    # sibling of the unterminated-quote malformed construct).
    after_close = False

    while i < n:
        ch = text[i]

        if in_quotes:
            if ch == quotechar:
                if i + 1 < n and text[i + 1] == quotechar:
                    field.append(quotechar)  # FR-3: doubled quote -> literal
                    i += 2
                else:
                    in_quotes = False
                    after_close = True
                    i += 1
            else:
                field.append(ch)  # FR-4/FR-5: delimiter/newline is data here
                i += 1
            continue

        if after_close:
            if ch == delimiter:
                row.append("".join(field))
                field.clear()
                after_close = False
                i += 1
            elif ch == "\n":
                row.append("".join(field))
                field.clear()
                rows.append(row)
                row = []
                after_close = False
                i += 1
            elif ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                row.append("".join(field))
                field.clear()
                rows.append(row)
                row = []
                after_close = False
                i += 2
            else:
                line, col = _position(text, i)
                raise ValueError(
                    f"unexpected character {ch!r} after closing quote at "
                    f"line {line}, column {col}"
                )
            continue

        if not field and ch == quotechar:  # FR-2: quote as first char opens
            in_quotes = True
            quote_start = i
            i += 1
        elif ch == delimiter:
            row.append("".join(field))
            field.clear()
            i += 1
        elif ch == "\n":  # FR-9: bare LF terminates a record
            row.append("".join(field))
            field.clear()
            rows.append(row)
            row = []
            i += 1
        elif ch == "\r" and i + 1 < n and text[i + 1] == "\n":  # FR-9: CRLF as one
            row.append("".join(field))
            field.clear()
            rows.append(row)
            row = []
            i += 2
        else:
            # Ordinary data: includes a lone `\r` not followed by `\n`
            # (FR-9) and a quotechar inside an already-started, unquoted
            # field (FR-12).
            field.append(ch)
            i += 1

    if in_quotes:
        line, col = _position(text, quote_start)
        raise ValueError(
            f"unterminated quoted field starting at line {line}, column {col}"
        )

    if row or field or after_close:
        row.append("".join(field))
        rows.append(row)

    return rows
