"""csvparse -- a dependency-free RFC 4180-subset CSV parser.

Implementation for scenario L1-csv-parser. Must pass all smoke and acceptance
tests and must NOT import the csv standard-library module or any third-party
CSV library.
"""

from __future__ import annotations


def _position(text: str, offset: int) -> tuple[int, int]:
    """Return 1-based (line, column) of `offset` into `text`, for error messages.

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
    r"""Parse RFC 4180-subset CSV text into rows of string fields.

    Parameters
    ----------
    text : str
        The CSV input. Parsed as a sequence of Unicode code points.
    delimiter : str
        Field separator; exactly one character. Default: ','.
    quotechar : str
        Quote character; exactly one character, must differ from delimiter.
        Default: '"'.

    Returns
    -------
    list[list[str]]
        Outer list is records; inner list is fields. Empty input returns [].

    Raises
    ------
    ValueError
        If delimiter or quotechar is not exactly one character, or they are equal.
        Malformed input (unterminated quoted field, or characters after a closing
        quote such as "ab"cd) also raises ValueError with the absolute character
        offset of the offending quotechar.

    Ambiguity resolutions (REQUIREMENTS §1.6)
    ------------------------------------------
    (a) Malformed input: raises ValueError naming the absolute offset of the
        offending quote. Applied consistently to both unterminated quoted fields
        and post-closing-quote garbage characters.
    (b) Whitespace: preserved verbatim in unquoted fields (no stripping).
        Whitespace inside quoted fields is always preserved.
    (c) BOM: a single leading U+FEFF BOM is stripped before parsing. It never
        affects field or record counts and only touches the first field of the
        first record.
    """
    # FR-11: validate parameters
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValueError(f"delimiter must be a single character, got {delimiter!r}")
    if not isinstance(quotechar, str) or len(quotechar) != 1:
        raise ValueError(f"quotechar must be a single character, got {quotechar!r}")
    if delimiter == quotechar:
        raise ValueError(f"delimiter and quotechar must differ, both are {delimiter!r}")

    # Resolution (c1): strip a single leading BOM before parsing
    text = text.removeprefix("\ufeff")

    # FR-1: empty input returns []
    if not text:
        return []

    n = len(text)
    rows: list[list[str]] = []
    row: list[str] = []
    field_buf: list[str] = []
    i = 0
    in_quotes = False
    quote_start = 0
    # after_close: just closed a quoted field; only delimiter/terminator/EOF
    # may legally follow (FR-2, and the §1.6(a) "chars after closing quote"
    # sibling of the unterminated-quote malformed construct).
    after_close = False
    last_was_terminator = False

    while i < n:
        ch = text[i]
        last_was_terminator = False

        # --- IN_QUOTED state ---
        if in_quotes:
            if ch == quotechar:
                if i + 1 < n and text[i + 1] == quotechar:
                    field_buf.append(quotechar)  # FR-2/3: doubled quote -> literal
                    i += 2
                else:
                    # Closing quote: transition to AFTER_QUOTE state
                    in_quotes = False
                    after_close = True
                    i += 1
            else:
                field_buf.append(ch)  # FR-4/FR-5: delimiter/newline is data here
                i += 1
            continue

        # --- AFTER_QUOTE state ---
        if after_close:
            if ch == delimiter:
                row.append("".join(field_buf))
                field_buf.clear()
                after_close = False
                i += 1
            elif ch == "\n":
                row.append("".join(field_buf))
                field_buf.clear()
                rows.append(row)
                row = []
                after_close = False
                last_was_terminator = True
                i += 1
            elif ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                row.append("".join(field_buf))
                field_buf.clear()
                rows.append(row)
                row = []
                after_close = False
                last_was_terminator = True
                i += 2
            else:
                # Resolution (a1): raise ValueError for chars after closing quote
                line, col = _position(text, i)
                raise ValueError(
                    f"unexpected character {ch!r} after closing quote at "
                    f"line {line}, column {col} (absolute offset {i})"
                )
            continue

        # --- IN_FIELD state ---
        if not field_buf and ch == quotechar:
            # FR-2: quotechar as first char of a field opens a quoted field
            in_quotes = True
            quote_start = i
            i += 1
        elif ch == delimiter:
            # FR-6: delimiter splits fields
            row.append("".join(field_buf))
            field_buf.clear()
            i += 1
        elif ch == "\n":
            # FR-9: bare LF terminates a record
            row.append("".join(field_buf))
            field_buf.clear()
            rows.append(row)
            row = []
            last_was_terminator = True
            i += 1
        elif ch == "\r" and i + 1 < n and text[i + 1] == "\n":
            # FR-9: CRLF counts as one record terminator
            row.append("".join(field_buf))
            field_buf.clear()
            rows.append(row)
            row = []
            last_was_terminator = True
            i += 2
        else:
            # Ordinary data: includes a lone `\r` not followed by `\n`
            # (FR-9) and a quotechar inside an already-started, unquoted
            # field (FR-12).
            field_buf.append(ch)
            i += 1

    # Check for unterminated quoted field (Resolution a1: raise ValueError)
    if in_quotes:
        line, col = _position(text, quote_start)
        raise ValueError(
            f"unterminated quoted field starting at line {line}, column {col} "
            f"(absolute offset {quote_start})"
        )

    # FR-8: Trailing-separator logic.
    # If the last character was a record terminator that already flushed a row,
    # do not add an extra empty row. Otherwise flush the current field and row.
    if not last_was_terminator:
        if row or field_buf or after_close:
            row.append("".join(field_buf))
            rows.append(row)

    return rows
