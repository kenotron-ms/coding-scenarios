# L1 — CSV Parser — SPEC (prompt handed to the strategy under test)

Implement a single pure function in a module `csvparse.py` in your workspace.

```python
def parse_csv(
    text: str,
    *,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[list[str]]:
    """Parse RFC 4180-subset CSV text into rows of fields."""
```

## Requirements

- **Quoting.** A field whose first character is `quotechar` is a quoted
  field: its content runs to the matching closing `quotechar`, and the
  enclosing quotes are removed from the returned value. Inside a quoted
  field: a doubled quote (`""`) is an escaped literal quote
  (`"say ""hi"""` → `say "hi"`); `delimiter` is ordinary data and does not
  end the field (`a,"b,c",d` → `["a", "b,c", "d"]`); a newline (`\n` or
  `\r\n`) is ordinary data and does not end the record, preserved
  **verbatim** (no `\r\n` → `\n` translation). A `quotechar` is significant
  only at the *start* of a field; inside an unquoted field it is ordinary
  data (`a"b` → `a"b`).
- **Field/row counts.** Empty fields are supported in any position — the
  invariant is positional: a record with `n` top-level delimiters yields
  exactly `n + 1` fields (`a,,b` → 3 fields; `z,,` → `["z", "", ""]`). A
  blank interior line yields a record of one empty field, `[""]` — blank
  lines are **not** skipped. A single record separator at the very end of
  `text` terminates the final record and does **not** create an extra empty
  row; input without a trailing separator still yields its final record.
  Empty input returns `[]`.
- **Line endings.** Both `\r\n` and `\n` terminate a record at top level,
  and `\r\n` counts as one separator, never two. A lone `\r` at top level
  not followed by `\n` is ordinary data. Mixed line endings within one
  document are supported.
- **Unicode.** Parsing operates on `str` code points; any code point
  (non-BMP, combining marks, RTL marks) is returned unchanged.
- **Parameters.** `delimiter` and `quotechar` are keyword-only, each exactly
  one character, and may be any character (e.g. `\t`, `;`, `|`, `'`). A
  value that is not a single character, or `delimiter == quotechar`, raises
  `ValueError`.
- **Purity.** No I/O, no globals, no mutation of arguments. Equal inputs
  always return equal outputs.
- **Architecture.** Single-pass character scanner. Whole-input regex
  matching or split-then-repair strategies are not acceptable structures.
- Standard library only, Python ≥ 3.11. **The `csv` module is FORBIDDEN** —
  `import csv`, `from csv import ...`, `csv.reader`, dynamic equivalents,
  and any third-party CSV library are all disallowed. The task is to
  implement the parsing yourself; a static scan at scoring time fails the
  gate on any such import.

## Ambiguities you must resolve

The spec deliberately leaves these three open. For each, pick **either**
listed resolution, apply it **consistently**, and **document your choice in
the `parse_csv` docstring**:

1. **Malformed input** (e.g. an unterminated quoted field, `a,"bcd` with no
   closing quote): either **(a)** raise `ValueError` naming the position
   (line/column or absolute offset) of the fault, or **(b)** best-effort
   recovery with a documented rule. Whichever you choose, apply the *same*
   choice to the sibling construct of characters following a closing quote
   (e.g. `"ab"cd`) — either both raise or both recover — and never silently
   drop already-accumulated fields.
2. **Whitespace around unquoted fields** — is ` a , b ` trimmed? Either
   preserve it verbatim, or strip leading/trailing whitespace of *unquoted*
   fields only. Whitespace **inside quoted fields is always preserved**
   regardless of your choice (`" a "` → `" a "`).
3. **Leading UTF-8 BOM** (`U+FEFF`). Either strip a single leading BOM
   before parsing, or treat it as ordinary data in the first field. A BOM
   must never affect record or field *counts*, and must never affect any
   field other than the first field of the first record.

Asking a human to resolve these is an intervention and is scored against
the run — these are deliberate ambiguities, not spec defects.

You are given `tests/smoke/` to check your work. Held-out `acceptance` and
`adversarial` suites will grade you (see `EVALUATION.md` for what they
measure).

**Entrypoint:** the harness imports `csvparse` from your workspace (see
`manifest.yaml`).
