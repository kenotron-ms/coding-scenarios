# Lane implement_loganalyze

## Outcome

Create the complete `loganalyze` Python package under
`scenarios/L3-log-analyzer/solution/loganalyze/` and the design artifacts under
`scenarios/L3-log-analyzer/solution/design/`, so that `python -m loganalyze`
works as a fully-featured CLI from the `solution/` directory.

Concrete files to create (all repo-relative paths):

- `scenarios/L3-log-analyzer/solution/loganalyze/__init__.py` — package marker + `__version__`
- `scenarios/L3-log-analyzer/solution/loganalyze/__main__.py` — `python -m loganalyze` shim calling `cli.main()`
- `scenarios/L3-log-analyzer/solution/loganalyze/parse.py` — CLF-subset grammar → `(datetime, path, status)` or `None`; pure, no I/O
- `scenarios/L3-log-analyzer/solution/loganalyze/aggregate.py` — streaming iterable of entries → report dict; no I/O
- `scenarios/L3-log-analyzer/solution/loganalyze/cli.py` — `argparse`-based argv parsing, file/stdin wiring, exit codes 0/1/2, stderr diagnostics
- `scenarios/L3-log-analyzer/solution/loganalyze/render.py` — report dict → text or JSON string; no I/O
- `scenarios/L3-log-analyzer/solution/design/CLI_UX.md` — grammar, verbatim `--help`, exit-code table, rendered text sample, three ambiguity resolutions
- `scenarios/L3-log-analyzer/solution/design/report.schema.json` — JSON Schema draft 2020-12 for the JSON output
- `scenarios/L3-log-analyzer/solution/design/USER_STORIES.md` — US-1..US-8 traced to FR-n

## Steps

### 1. Read the authoritative requirements first

Read `scenarios/L3-log-analyzer/REQUIREMENTS.md`, `scenarios/L3-log-analyzer/SPEC.md`,
`scenarios/L3-log-analyzer/manifest.yaml`, and `scenarios/L3-log-analyzer/tests/_harness.py`
before writing any code. The harness `_harness.py` contains the independent oracle — match it.

### 2. Create the design artifacts first (design-before-implement)

Write `design/CLI_UX.md` capturing:
- The exact CLI grammar (usage line + every option)
- The verbatim `--help` output the binary will produce
- The exit-code table (0 = success, 1 = runtime error, 2 = usage error)
- A rendered text-output sample the binary must match
- Resolutions for the three §1.6 ambiguities:
  - **A-1 (naive --since/--until):** treat naive ISO values as UTC
  - **A-2 (tie-breaking):** ascending lexicographic (Unicode code-point) by path
  - **A-3 (--top 0):** "none" → empty `top_paths` list

Write `design/report.schema.json` (JSON Schema draft 2020-12) matching the §2.1 schema exactly.

Write `design/USER_STORIES.md` with US-1..US-8 each traced to FR-n.

### 3. Implement `parse.py`

Parse one CLF-subset line:
```
HOST IDENT AUTHUSER [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD PATH HTTP/x.y" STATUS BYTES
```
Use a single compiled regex (no nested unbounded quantifiers). Return `(datetime, path, status)`
or `None` for malformed lines. Blank/whitespace lines are handled by the caller (not counted
as malformed). Strip trailing `\r\n`. Parse the timestamp to a timezone-aware `datetime`.
STATUS must be 3 digits in [100, 599]. PATH begins with `/`. METHOD is uppercase ASCII only.
HTTP/x.y must be `HTTP/` + one digit + `.` + one digit. English month abbreviations only,
case-sensitive.

### 4. Implement `aggregate.py`

Accept an iterator of `(datetime, path, status)` triples plus optional `since`/`until`
`datetime` bounds. Stream line by line — never materialize the input. Accumulate:
- `paths: dict[str, int]` (path → count, in-window only)
- `statuses: dict[int, int]` (status code → count, in-window only)
- `errors` (status >= 400, in-window)
- `in_window`, `parsed`, `malformed`, `blank`, `lines_read` counters

Return a plain dict with the §2.1 JSON schema shape. Tie-break: sort by `(-count, path)`.
`top_paths` is `ordered[:top]` when `top > 0`, else `[]` when `top == 0`.
`error_rate = round(errors / in_window, 6)` or `0.0` when `in_window == 0`.
`status_counts` keys are 3-char strings in ascending numeric order; zero-count codes omitted.
`status_classes` always has all five keys `1xx..5xx`, zeros included.

### 5. Implement `render.py`

Two functions:
- `render_json(report: dict) -> str` — `json.dumps(report, indent=2)` with a trailing newline.
  Key order must match §2.1 exactly. Use `json.dumps` with `sort_keys=False`.
- `render_text(report: dict, *, show_status: bool) -> str` — human layout matching `design/CLI_UX.md`.
  Required content: total entries parsed + malformed count; effective window; error rate as
  percentage + numerator/denominator; top-N paths with counts; class rollup always; exact
  status-code breakdown only when `show_status=True`.

No `print`, no `sys.exit`, no stream access in this module.

### 6. Implement `cli.py`

Use `argparse.ArgumentParser`. Configure:
- Positional `FILE` (nargs="?") — omit or `-` → stdin
- `--version` action (exit 0, stdout)
- `--top N` (type=int, default=10); validate: negative → exit 2
- `--status` (store_true)
- `--since ISO` / `--until ISO` — parse with `datetime.fromisoformat`; unparseable → exit 2
- `--format {text,json}` (choices, default="text"); invalid → exit 2 (argparse handles this)

Help epilogue must include the exit-code table and the three §1.6 resolutions.

`main()` function:
1. Parse args (argparse handles exit 2 for unknown flags / invalid choices).
2. Open the file (or stdin). Missing file / directory / unreadable → print
   `loganalyze: error: <message>` to stderr, exit 1.
3. Stream lines (iterate line by line, `errors="replace"`).
4. Call `parse.parse_line()` for each non-blank line; count malformed.
5. Call `aggregate.aggregate()` with the entry stream and window bounds.
6. If malformed > 0, print `loganalyze: warning: <N> malformed line(s) skipped` to stderr.
7. Call `render.render_json()` or `render.render_text()`.
8. Print result to stdout. Handle `BrokenPipeError` on stdout write gracefully (exit 0).
9. Exit 0.

Wrap the entire `main()` body in a try/except to catch unexpected exceptions; print
`loganalyze: error: <message>` to stderr and exit 1. Never let a traceback reach stderr.

Only `cli.py` may call `print`, `sys.exit`, or touch `sys.stdin/stdout/stderr`.

### 7. Implement `__init__.py` and `__main__.py`

`__init__.py`: set `__version__ = "1.0.0"`.
`__main__.py`: import and call `cli.main()`.

### 8. Self-verify with the smoke suite

Run the smoke tests as a subprocess check:
```bash
cd scenarios/L3-log-analyzer
SOLUTION_DIR=$(pwd)/solution pytest tests/smoke -q
```
All 6 smoke tests must pass before the lane is complete.

Key things to verify manually:
- `python -m loganalyze --help` exits 0, writes to stdout, includes exit-code table
- `python -m loganalyze --bogus` exits 2, writes `usage:` to stderr
- `python -m loganalyze /no/such/file` exits 1, writes `loganalyze: error:` to stderr
- `python -m loganalyze --format json sample.log | python -m json.tool` parses cleanly
- `python -m loganalyze --top -1 sample.log` exits 2
- `python -m loganalyze --since bad-date sample.log` exits 2
- `PYTHONHASHSEED=0 python -m loganalyze sample.log` and `PYTHONHASHSEED=999 ...` produce identical stdout

## Done when

```bash
pytest scenarios/L3-log-analyzer/tests/smoke -q --tb=short
```
exits 0 (all smoke tests pass) from the repository root.

## Final step (REQUIRED)

After the work is done and the smoke tests pass (exit 0), write the file
`artifacts/implement_loganalyze.done` containing exactly:

```
implement_loganalyze:ok
```

and nothing else (no trailing newline beyond what is shown — the content must be
exactly the string `implement_loganalyze:ok`). This marker is how the batch
orchestrator confirms the lane finished; it must be the LAST action taken.
