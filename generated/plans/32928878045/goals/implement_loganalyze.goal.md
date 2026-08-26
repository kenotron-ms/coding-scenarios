# Lane implement_loganalyze

## Outcome

Implement the `loganalyze` CLI package under `scenarios/L3-log-analyzer/solution/` so that:

1. `python -m loganalyze` works from `scenarios/L3-log-analyzer/solution/` as the entrypoint.
2. The smoke test suite passes: `pytest scenarios/L3-log-analyzer/tests/smoke -q --tb=short`.
3. The acceptance gate passes: `acceptance_pass >= 0.95` when running `pytest scenarios/L3-log-analyzer/tests/acceptance -q`.

The solution must be placed at these repo-relative paths:

- `scenarios/L3-log-analyzer/solution/loganalyze/__init__.py`
- `scenarios/L3-log-analyzer/solution/loganalyze/__main__.py`
- `scenarios/L3-log-analyzer/solution/loganalyze/cli.py`
- `scenarios/L3-log-analyzer/solution/loganalyze/parse.py`
- `scenarios/L3-log-analyzer/solution/loganalyze/aggregate.py`
- `scenarios/L3-log-analyzer/solution/loganalyze/render.py`
- `scenarios/L3-log-analyzer/solution/design/CLI_UX.md`
- `scenarios/L3-log-analyzer/solution/design/report.schema.json`
- `scenarios/L3-log-analyzer/solution/design/USER_STORIES.md`

## Steps

Read the authoritative requirements before implementing:
- `scenarios/L3-log-analyzer/REQUIREMENTS.md` — full spec
- `scenarios/L3-log-analyzer/SPEC.md` — concise spec handed to the agent
- `scenarios/L3-log-analyzer/manifest.yaml` — entrypoint and verify commands
- `scenarios/L3-log-analyzer/tests/smoke/test_smoke.py` — visible smoke tests
- `scenarios/L3-log-analyzer/tests/smoke/sample.log` — sample log file
- `scenarios/L3-log-analyzer/tests/_harness.py` — oracle and test harness (shows exactly what the acceptance tests check)

### Step 1 — Create the design artifacts FIRST (before implementation)

**`design/CLI_UX.md`** must contain:
- The CLI grammar (usage line + every option with description)
- The verbatim `--help` text the binary will emit
- The exit-code table (0=success, 1=runtime error, 2=usage error)
- A rendered text-output sample that the binary must match exactly (self-golden check)
- The three §1.6 ambiguity resolutions with rationale:
  - A-1: Naive `--since`/`--until` → treat as UTC
  - A-2: Tie-breaking for equal path counts → ascending lexicographic (Unicode code-point)
  - A-3: `--top 0` → "none" (empty top_paths list)

**`design/report.schema.json`** — JSON Schema draft 2020-12 for the `--format json` output. All keys required, `additionalProperties: false`, types and value constraints per §2.1.

**`design/USER_STORIES.md`** — US-1..US-8 restated, each traced to `FR-n`.

### Step 2 — Implement the package modules (strict module boundaries per §2.2)

**`loganalyze/__init__.py`**:
```python
"""loganalyze — web access-log analyzer."""
__version__ = "1.0.0"
```

**`loganalyze/__main__.py`**:
```python
from loganalyze.cli import main
main()
```

**`loganalyze/parse.py`** — Pure string/datetime work only. No print, no exit, no file I/O.
- Use a single compiled regex to parse the CLF subset grammar:
  `HOST IDENT AUTHUSER [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD PATH HTTP/x.y" STATUS BYTES`
- Return a named tuple or dataclass `(timestamp: datetime, path: str, status: int)` or `None` for malformed.
- Timestamps must be timezone-aware (parse the `+HHMM`/`-HHMM` offset).
- Blank/whitespace-only lines return a sentinel (not None, to distinguish from malformed).
- Regex must be linear-scan safe (no catastrophic backtracking).
- Month abbreviations are case-sensitive English only (Jan..Dec).
- STATUS must be exactly 3 digits in [100, 599].
- BYTES is a non-negative integer or `-` (validate, don't report).
- A path containing a space or quote makes the line malformed (the request field has exactly 3 space-separated tokens).

**`loganalyze/aggregate.py`** — Streaming aggregation. Takes an iterator of lines, yields a report dict. No print, no exit, no file I/O. Must NOT materialize the input (no `list()`, `readlines()`, `read()`).
- Count: lines_read, entries_parsed, malformed, blank, entries_in_window
- Accumulate: path counts (dict), status counts (dict)
- Apply `--since`/`--until` window filtering (inclusive both ends)
- Return a report object/dict with all fields needed for both text and JSON rendering

**`loganalyze/cli.py`** — ONLY module that may call print, sys.exit, open files, touch stdin/stdout/stderr.
- Use `argparse` with `formatter_class=argparse.RawDescriptionHelpFormatter` for the epilogue
- Arguments: `FILE` (positional, optional), `--version`, `--top N` (default 10, must be integer >= 0; negative → exit 2), `--status` (flag), `--since ISO`, `--until ISO`, `--format {text,json}` (default text)
- Parse `--since`/`--until` as ISO-8601; unparseable → print usage + exit 2
- Extra positional arguments → exit 2
- Open `FILE` (or stdin if omitted/`-`) with `open(..., encoding='utf-8', errors='replace')`
- File not found / is directory / unreadable → `loganalyze: error: <message>` on stderr + exit 1
- After aggregation: if malformed > 0, emit `loganalyze: warning: <N> malformed line(s) skipped` on stderr
- Render and print to stdout
- Catch unexpected exceptions: `loganalyze: error: <message>` on stderr + exit 1
- Handle BrokenPipeError (closed stdout like `| head -1`) gracefully — no traceback

**`loganalyze/render.py`** — Report object → str (text or JSON). No print, no exit, no compute aggregates.
- `render_json(report) -> str`: emit the §2.1 JSON schema with `indent=2`, trailing newline, keys in exact order shown, `status_counts` keys in ascending numeric order, `error_rate` rounded to 6 decimal places
- `render_text(report, *, show_status: bool) -> str`: emit human-readable report matching the `design/CLI_UX.md` sample

### Step 3 — Key implementation details to get right

**JSON key order** (must be exact per §2.1):
```
schema_version, window (since, until), totals (lines_read, entries_parsed, malformed, entries_in_window), top_paths, status_counts, status_classes, error_rate
```
Use `json.dumps(..., indent=2)` on an explicitly ordered dict (Python 3.7+ dicts preserve insertion order).

**`status_classes`** — Always emit all five keys in fixed order: `1xx, 2xx, 3xx, 4xx, 5xx`. Zeros included.

**`window.since` / `window.until`** in JSON — `null` when flag not given; otherwise the normalized ISO-8601 form of the parsed datetime (use `datetime.isoformat()`).

**Determinism (FR-8)** — Sort `top_paths` by `(-count, path)` (count descending, then ascending lexicographic on path for ties). Use `sorted()`, never rely on dict/set iteration order. Status codes sorted ascending numerically.

**Streaming (NFR-1)** — Iterate line by line using a `for line in fileobj:` loop. Never call `.read()`, `.readlines()`, or `list(fileobj)`.

**Malformed line handling** — Skip and count. Never abort. Never emit per-line warnings. One summary warning on stderr at the end, only if count > 0.

**`--top 0`** — Resolve as "none": `top_paths` is `[]`.

**Naive `--since`/`--until`** — Treat as UTC: `datetime.fromisoformat(value).replace(tzinfo=timezone.utc)` if the parsed datetime has no tzinfo.

**Exit codes**:
- 0: success (including empty/all-malformed/empty-window, --help, --version)
- 1: runtime error (file not found, is directory, unreadable, I/O error)
- 2: usage error (argparse handles unknown flags; also bad --format, unparseable --since/--until, negative --top, extra positionals)

**`--help` epilogue** must contain (verbatim in the help text):
- Exit code table
- Resolution of A-1 (naive timestamps → UTC)
- Resolution of A-2 (tie-break → ascending lexicographic)
- Resolution of A-3 (--top 0 → empty list)

**Text output required content** (whatever layout you design — it must match `design/CLI_UX.md` sample):
- Total entries parsed + malformed count
- Effective window (or "none")
- Error rate as percentage + numerator/denominator
- Top-N paths with counts, in FR-8 order
- Exact status-code breakdown when `--status` is given; 1xx..5xx class rollup always

**Static quality** — `ruff` and `pyright` clean. Module boundaries strictly respected:
- `parse.py`, `aggregate.py`, `render.py` must NOT import sys, call print, or reference sys.exit
- Only `cli.py` touches process state

### Step 4 — Verify

Run these checks to confirm correctness:

```bash
cd scenarios/L3-log-analyzer/solution
# Basic smoke check
python -m loganalyze tests/../tests/smoke/sample.log
python -m loganalyze --format json ../tests/smoke/sample.log
python -m loganalyze --help
python -m loganalyze --bogus 2>&1; echo "rc=$?"
python -m loganalyze /no/such/file 2>&1; echo "rc=$?"
```

Then run the smoke suite from the repo root:
```bash
pytest scenarios/L3-log-analyzer/tests/smoke -q --tb=short
```

And the acceptance suite:
```bash
pytest scenarios/L3-log-analyzer/tests/acceptance -q --tb=short
```

## Done when

The following command exits 0 from the repository root:

```bash
pytest scenarios/L3-log-analyzer/tests/smoke -q --tb=short
```

This verifies the six smoke cases:
1. Default text run exits 0 and contains "Top ", "Status classes", "Error rate:"
2. `--format json` produces correct JSON matching the oracle
3. `--top 2` correctly limits and orders top paths
4. `--since`/`--until` window filtering works correctly
5. Unknown flag (`--bogus`) exits 2 with `usage:` on stderr
6. Missing file exits 1 with `loganalyze: error:` on stderr

Additionally, the acceptance suite must pass at ≥ 95%:
```bash
pytest scenarios/L3-log-analyzer/tests/acceptance -q --tb=short
```

## Final step (REQUIRED)

After all the work is done and the smoke test command exits 0, write the file `artifacts/implement_loganalyze.done` containing exactly `implement_loganalyze:ok` and nothing else.

This marker file is how the batch orchestrator confirms the lane finished. It must be the LAST action taken.
