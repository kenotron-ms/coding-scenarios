# Lane acceptance_gate

## Outcome

The `loganalyze` CLI under `scenarios/L3-log-analyzer/solution/` passes the
held-out acceptance suite at >= 95% (`acceptance_pass >= 0.95`), and the static
quality gates (`ruff` + `pyright`) are clean.

This lane builds on the work from lane `implement_loganalyze`. It fixes any
remaining issues uncovered by the broader acceptance matrix and ensures the
full quality bar is met.

## Steps

### 1. Run the acceptance suite and identify failures

```bash
cd scenarios/L3-log-analyzer
SOLUTION_DIR=$(pwd)/solution pytest tests/acceptance -q --tb=short 2>&1 | head -100
```

Read the failure output carefully. Common failure categories at this rung:

- **JSON key order drift** — `json.dumps` must emit keys in exactly the §2.1 order:
  `schema_version`, `window`, `totals`, `top_paths`, `status_counts`, `status_classes`, `error_rate`.
  Use an `OrderedDict` or construct the dict in the exact order before serializing.

- **status_counts key format** — keys must be 3-character strings (`"200"`, `"404"`), not integers.
  Sort by numeric value: `sorted(statuses.keys())` where keys are ints, then format as `f"{code:03d}"`.

- **error_rate rounding** — must be `round(errors / in_window, 6)`, not `round(..., 2)` or truncated.

- **window.since / window.until** — must be the normalized ISO-8601 form of the parsed datetime
  (i.e. `dt.isoformat()`), not the raw string the user passed. `null` when not given.

- **Naive --since/--until** — if the user passes `2023-10-10T13:00:00` (no offset), treat as UTC:
  `datetime.fromisoformat(s).replace(tzinfo=timezone.utc)`. This must be consistent in both formats.

- **Determinism under PYTHONHASHSEED** — `top_paths` ordering must never rely on dict/set iteration.
  Sort explicitly: `sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))`.

- **stdout purity** — no warnings or diagnostics on stdout in either format. The warning
  `loganalyze: warning: <N> malformed line(s) skipped` goes only to stderr.

- **Bounded memory** — input must be consumed line by line. Never call `read()`, `readlines()`,
  or `list(f)`. Iterate `for line in f:` directly.

- **--top 0** — must produce empty `top_paths` (resolution A-3: "none"). Exit 0.

- **--top N where N > distinct paths** — report all distinct paths (no error).

- **Inverted window (since > until)** — valid, produces zero-entry report, exit 0.

- **All-malformed / empty input** — exit 0, well-formed zero-entry report on stdout,
  warning on stderr only when malformed > 0.

- **BrokenPipeError** — writing to a closed pipe (e.g. `| head -1`) must not traceback.
  Catch `BrokenPipeError` around the stdout write and exit 0.

- **--help content** — must contain the exit-code table and all three §1.6 resolutions.
  Use `argparse`'s `epilog` parameter with `formatter_class=argparse.RawDescriptionHelpFormatter`.

- **design/report.schema.json** — must exist at `solution/design/report.schema.json` and
  the JSON output must validate against it. The schema must declare `additionalProperties: false`
  and all required keys.

- **design/CLI_UX.md** — must exist and the text output sample must match what the binary actually
  prints (run the binary and capture its output to confirm).

- **design/USER_STORIES.md** — must exist and cover US-1..US-8 with FR-n traceability.

### 2. Run static quality gates

```bash
cd scenarios/L3-log-analyzer/solution
ruff check loganalyze/
pyright loganalyze/
```

Fix any lint or type errors. Common issues:
- Missing return type annotations on public functions
- `Any` types where specific types are needed
- Unused imports
- Lines too long

### 3. Verify module boundary constraints

Confirm that `parse.py`, `aggregate.py`, and `render.py` do NOT import or call:
- `print`
- `sys.exit`
- `sys.stdin`, `sys.stdout`, `sys.stderr`
- Any file I/O

Only `cli.py` may touch process state.

### 4. Verify determinism

```bash
cd scenarios/L3-log-analyzer/solution
PYTHONHASHSEED=0 python -m loganalyze --format json ../tests/smoke/sample.log > /tmp/out0.json
PYTHONHASHSEED=42 python -m loganalyze --format json ../tests/smoke/sample.log > /tmp/out42.json
PYTHONHASHSEED=999 python -m loganalyze --format json ../tests/smoke/sample.log > /tmp/out999.json
diff /tmp/out0.json /tmp/out42.json && diff /tmp/out42.json /tmp/out999.json && echo "DETERMINISTIC"
```

### 5. Verify the design artifacts are consistent with the binary

```bash
cd scenarios/L3-log-analyzer/solution
python -m loganalyze --help
```
Compare the actual `--help` output against what is written in `design/CLI_UX.md`. They must match.

Run the binary on the smoke log and compare the text output against the sample in `design/CLI_UX.md`.

### 6. Re-run the full acceptance suite

```bash
cd scenarios/L3-log-analyzer
SOLUTION_DIR=$(pwd)/solution pytest tests/acceptance -q --tb=short
```

Must pass >= 95% of assertions.

## Done when

```bash
pytest scenarios/L3-log-analyzer/tests/acceptance -q --tb=short
```
exits 0 (or with a pass rate >= 95%) from the repository root.

Additionally, `ruff check scenarios/L3-log-analyzer/solution/loganalyze/` and
`pyright scenarios/L3-log-analyzer/solution/loganalyze/` must both exit 0.

## Final step (REQUIRED)

After the acceptance suite passes (>= 95%) and static checks are clean, write
the file `artifacts/acceptance_gate.done` containing exactly:

```
acceptance_gate:ok
```

and nothing else. This marker is how the batch orchestrator confirms the lane
finished; it must be the LAST action taken.
