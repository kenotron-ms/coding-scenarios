# Lane csv_parser_impl

## Outcome

Create `scenarios/L1-csv-parser/solution/csvparse.py` implementing a pure RFC 4180-subset CSV parser. The module must export `parse_csv` (and optionally `parse_line`) satisfying all functional requirements (FR-1..FR-13) and non-functional requirements (NFR-1..NFR-4) defined in `scenarios/L1-csv-parser/REQUIREMENTS.md`.

The file to create: `scenarios/L1-csv-parser/solution/csvparse.py`

## Steps

1. **Read the authoritative requirements** before writing code:
   - `scenarios/L1-csv-parser/REQUIREMENTS.md` — full FR/NFR list
   - `scenarios/L1-csv-parser/SPEC.md` — the prompt handed to the strategy
   - `scenarios/L1-csv-parser/manifest.yaml` — entrypoint is `csvparse` module inside `solution/`
   - `scenarios/L1-csv-parser/tests/smoke/test_smoke.py` — 5 visible smoke examples
   - `scenarios/L1-csv-parser/tests/acceptance/test_acceptance.py` — 19 acceptance tests (the gate)

2. **Create `scenarios/L1-csv-parser/solution/` directory** if it does not exist.

3. **Implement `scenarios/L1-csv-parser/solution/csvparse.py`** as a single-pass character-level state machine. Key requirements:
   - **No `import csv`** (or any third-party CSV library) — this is a hard gate failure.
   - **Standard library only** (Python ≥ 3.11).
   - **Interface** (keyword-only params with defaults):
     ```python
     def parse_csv(text: str, *, delimiter: str = ",", quotechar: str = '"') -> list[list[str]]: ...
     ```
   - **FR-1**: Empty input → `[]`. Non-empty input → `list[list[str]]`.
   - **FR-2/3/4/5**: Quoted fields: content up to matching close quote; `""` inside → literal `"`; delimiter inside quoted field → data; `\n`/`\r\n` inside quoted field → data, preserved verbatim.
   - **FR-6**: `n` top-level delimiters → `n+1` fields. `a,,b` → 3 fields. `z,,` → `["z","",""]`.
   - **FR-7**: Blank interior line → `[""]` (NOT skipped, NOT `[]`).
   - **FR-8**: Single trailing separator does NOT create an extra empty row.
   - **FR-9**: `\r\n` and `\n` both terminate records at top level; `\r\n` counts as one separator. A lone `\r` not followed by `\n` is ordinary data.
   - **FR-10**: Unicode-safe; return fields unchanged.
   - **FR-11**: `delimiter` and `quotechar` are each exactly one character; `delimiter == quotechar` raises `ValueError`; non-single-char or `None` raises `ValueError`.
   - **FR-12**: `quotechar` is significant only at the *start* of a field; inside an unquoted field it is ordinary data (`a"b` → `a"b`).
   - **FR-13**: Pure function — no I/O, no globals, no mutation of arguments.
   - **NFR-1**: Single linear pass, O(n). Accumulate field content in a list and `"".join(...)`, never concatenate inside the inner loop.
   - **NFR-3**: `parse_csv` docstring must document all three §1.6 ambiguity resolutions (see below).

4. **Resolve the three §1.6 ambiguities** — choose one option for each, apply consistently, and document in the `parse_csv` docstring:

   - **(a) Malformed input** (unterminated quoted field, or characters after closing quote like `"ab"cd`):
     Choose **(a1) raise `ValueError`** naming the position (line/column or absolute offset) of the fault. Both unterminated quotes AND characters-after-closing-quote must follow the same policy (both raise). The docstring must say "malformed" or "unterminated" or "ValueError".

   - **(b) Whitespace around unquoted fields**:
     Choose **(b1) preserve surrounding whitespace verbatim** (simplest, no trimming). Whitespace inside quoted fields is always preserved regardless. Document "whitespace" in the docstring.

   - **(c) Leading UTF-8 BOM (`U+FEFF`)**:
     Choose **(c1) strip a single leading BOM before parsing** (so BOM never affects field counts or any field other than possibly the first). Document "BOM" in the docstring.

   The acceptance test `test_ambiguity_consistency_matrix` (L1-AC15) observes the policy dynamically and checks consistency. The test `test_docstring_documents_ambiguities` (L1-AC18) checks the docstring for the keywords "malformed"/"unterminated"/"valueerror", "whitespace", and "bom".

5. **Implement the state machine** with these states:
   - `START_FIELD`: beginning of a new field — if next char is `quotechar`, enter `IN_QUOTED`; else enter `IN_UNQUOTED`.
   - `IN_UNQUOTED`: collect chars until delimiter (end field), `\n` (end record), `\r` (peek for `\n`), or end-of-input.
   - `IN_QUOTED`: collect chars until `quotechar`; on `quotechar`, peek: if next is also `quotechar`, emit one `quotechar` and continue; if next is delimiter/newline/end-of-input, close the field; otherwise raise `ValueError` (characters after closing quote).
   - Handle `\r\n` as a single record separator at top level (peek one ahead when `\r` is seen outside a quoted field).
   - A lone `\r` not followed by `\n` is ordinary data in unquoted fields.

6. **Trailing separator rule**: after the main loop, if the last character consumed was a record separator (not a delimiter), do NOT append an extra empty row. The implementation naturally handles this if you emit a row only when a record separator is encountered and there is buffered content, and also emit the final partial row after the loop only if the current field buffer or row is non-empty.

   Specifically: emit the final row after the loop ends only if the accumulated row is non-empty OR the current field buffer is non-empty OR a delimiter was the last character seen (trailing empty field case). A clean trailing `\n` or `\r\n` with nothing after it should not add a row.

7. **Verify with the smoke tests** first:
   ```
   SOLUTION_DIR=scenarios/L1-csv-parser/solution pytest scenarios/L1-csv-parser/tests/smoke -q
   ```
   Then verify with the acceptance suite:
   ```
   SOLUTION_DIR=scenarios/L1-csv-parser/solution pytest scenarios/L1-csv-parser/tests/acceptance -q
   ```

8. **Check for `csv` import** (must not exist):
   ```
   grep -r "import csv" scenarios/L1-csv-parser/solution/
   ```
   This must return no matches.

9. **Run static checks** (ruff and pyright if available):
   ```
   ruff check scenarios/L1-csv-parser/solution/csvparse.py
   ```

## Done when

The following command exits 0 (all 19 acceptance tests + 5 smoke tests pass, with `SOLUTION_DIR` pointing at the solution):

```
SOLUTION_DIR=scenarios/L1-csv-parser/solution pytest scenarios/L1-csv-parser/tests/acceptance scenarios/L1-csv-parser/tests/smoke -q --tb=short
```

Additionally:
- `grep -r "import csv" scenarios/L1-csv-parser/solution/` returns no matches (no csv module used).
- The `parse_csv` docstring contains the words "malformed" (or "unterminated" or "ValueError"), "whitespace", and "BOM".

The verifier command the orchestrator runs is:
```
pytest scenarios/L1-csv-parser/tests/acceptance scenarios/L1-csv-parser/tests/smoke -q --tb=short
```
(The harness sets `SOLUTION_DIR` automatically via `conftest.py` fallback or environment.)

## Final step (REQUIRED)

After all work is done and the acceptance + smoke tests pass, write the file `artifacts/csv_parser_impl.done` containing exactly the text `csv_parser_impl:ok` and nothing else (no trailing newline, no extra whitespace). This marker file is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
