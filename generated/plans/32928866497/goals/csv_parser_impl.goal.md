# Lane csv_parser_impl

## Outcome

Create `scenarios/L1-csv-parser/solution/csvparse.py` implementing a pure RFC 4180-subset CSV parser that passes all smoke and acceptance tests.

The module must export `parse_csv(text, *, delimiter=",", quotechar='"') -> list[list[str]]` and must NOT import the `csv` standard-library module or any third-party CSV library.

## Steps

### 1. Create the solution directory and module

Create `scenarios/L1-csv-parser/solution/csvparse.py` (the harness imports `csvparse` from this directory via `SOLUTION_DIR`).

### 2. Implement `parse_csv` as a single-pass character-level state machine

The function signature must be exactly:

```python
def parse_csv(
    text: str,
    *,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[list[str]]:
```

**Parameter validation (FR-11):** raise `ValueError` if `delimiter` or `quotechar` is not exactly one character, or if they are equal, or if either is `None`.

**State machine logic (single pass, O(n)):**

Use a character index `i` over `text` with the following states:
- `IN_FIELD` (unquoted field accumulation)
- `IN_QUOTED` (inside a quoted field)
- `AFTER_QUOTE` (just saw a closing quote, deciding between doubled-quote escape or end-of-field)

Maintain:
- `field_buf: list[str]` — character accumulator for the current field (join at field-end, never concatenate in inner loop)
- `row: list[str]` — fields accumulated for the current record
- `rows: list[list[str]]` — completed records

**Key rules to implement:**

- **FR-1:** Empty input (`text == ""`) returns `[]`.
- **FR-2/3:** A field starting with `quotechar` is quoted; `""` inside a quoted field is an escaped literal quote.
- **FR-4:** `delimiter` inside a quoted field is ordinary data.
- **FR-5:** `\n` and `\r\n` inside a quoted field are ordinary data, preserved verbatim.
- **FR-6:** `n` top-level delimiters → `n+1` fields.
- **FR-7:** A blank interior line yields `[""]` (one empty-field record); blank lines are NOT skipped.
- **FR-8:** A single trailing record separator does NOT create an extra empty row. Input without a trailing separator still yields its final record.
- **FR-9:** At top level, both `\r\n` and `\n` terminate a record; `\r\n` is one separator; a lone `\r` not followed by `\n` is ordinary data.
- **FR-10:** Unicode-safe; no normalization.
- **FR-12:** `quotechar` is significant only at the start of a field; inside an unquoted field it is ordinary data.
- **FR-13:** Pure function.

**Trailing-separator logic:** After the main loop, if `rows` is non-empty OR `field_buf` is non-empty OR `row` is non-empty, flush the current field and row. But if the very last character was a record terminator that already flushed a row, do not add an extra empty row. Track this with a `last_was_terminator` flag.

### 3. Resolve the three §1.6 ambiguities — choose, apply consistently, document

Choose these resolutions (all are acceptable per REQUIREMENTS.md §1.6):

**(a) Malformed input** (unterminated quoted field, or characters after a closing quote like `"ab"cd`):
→ **Resolution (a1): raise `ValueError`** naming the absolute character offset of the offending quote. Apply the same policy to `"ab"cd` (characters after a closing quote): raise `ValueError`.

**(b) Whitespace around unquoted fields:**
→ **Resolution (b1): preserve whitespace verbatim.** Do not strip leading/trailing whitespace from unquoted fields. Whitespace inside quoted fields is always preserved (required regardless).

**(c) Leading UTF-8 BOM (`U+FEFF`):**
→ **Resolution (c1): strip a single leading BOM** before parsing. This never affects field/record counts and only touches the first field of the first record.

### 4. Write the docstring

The `parse_csv` docstring must mention:
- `malformed` / `unterminated` / `ValueError` (for acceptance test L1-AC18 check on malformed policy)
- `whitespace` (for acceptance test L1-AC18 check on whitespace policy)
- `bom` (for acceptance test L1-AC18 check on BOM policy)

Example docstring content:

```
Parse RFC 4180-subset CSV text into rows of string fields.

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
```

### 5. Ensure the module is importable as `csvparse`

The file must be at `scenarios/L1-csv-parser/solution/csvparse.py`. The conftest sets `SOLUTION_DIR` to point to `scenarios/L1-csv-parser/solution/` so `import csvparse` resolves to this file.

### 6. Run the verifier to confirm

```
SOLUTION_DIR=scenarios/L1-csv-parser/solution \
  pytest scenarios/L1-csv-parser/tests/smoke scenarios/L1-csv-parser/tests/acceptance -q --tb=short
```

All 19 acceptance tests and 5 smoke tests must pass. Fix any failures before writing the marker.

Also confirm no `csv` import exists:
```
grep -r "import csv" scenarios/L1-csv-parser/solution/
```
This must return no output.

## Done when

The following command exits 0 with all tests passing:

```
pytest scenarios/L1-csv-parser/tests/smoke scenarios/L1-csv-parser/tests/acceptance -q --tb=short
```

(The test harness sets `SOLUTION_DIR` automatically; when running manually, set `SOLUTION_DIR=scenarios/L1-csv-parser/solution`.)

## Final step (REQUIRED)

After all tests pass, write the file `artifacts/csv_parser_impl.done` containing exactly the text `csv_parser_impl:ok` and nothing else (no trailing newline beyond what the orchestrator expects — write exactly that string).

This marker file is how the batch orchestrator confirms this lane finished. It MUST be the last action taken.
