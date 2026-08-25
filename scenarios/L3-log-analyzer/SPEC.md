# L3 -- Log Analyzer -- SPEC (prompt handed to the strategy under test)

Build a command-line tool `loganalyze` that streams a web access log (a Common
Log Format subset) and prints an aggregate report -- top paths, status
breakdown, error rate, with time-window filtering -- as human text or JSON.

The **real path is a process**: the harness runs your built CLI as a subprocess
(`python -m loganalyze`), supplies argv, optionally pipes stdin, and inspects the
exit code, stdout, and stderr separately. It never imports your functions.

## CLI grammar

```text
usage: loganalyze [-h] [--version] [--top N] [--status] [--since ISO]
                  [--until ISO] [--format {text,json}] [FILE]

positional arguments:
  FILE                  access log to read; omit or use '-' to read stdin

options:
  -h, --help            show this help message and exit
  --version             show program version and exit
  --top N               number of top paths to report (default: 10)
  --status              include the exact status-code breakdown in text output
  --since ISO           only count entries at or after this ISO-8601 instant
  --until ISO           only count entries at or before this ISO-8601 instant
  --format {text,json}  output format (default: text)
```

## Requirements

- **Input.** Read from the positional `FILE`, or from stdin when `FILE` is
  omitted or is `-`. Decode UTF-8 with `errors="replace"`.
- **Grammar.** Each line is one Common Log Format subset entry:

  ```text
  HOST IDENT AUTHUSER [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD PATH HTTP/x.y" STATUS BYTES
  ```

  `STATUS` is exactly three digits in `[100,599]`; `PATH` is a non-space run
  beginning with `/`, taken verbatim; `METHOD` is uppercase ASCII; `BYTES` is a
  non-negative integer or `-`; the month is an English 3-letter abbreviation,
  case-sensitive. A blank/whitespace-only line is skipped silently; **anything
  else is malformed** -- skipped, **counted**, and reported once on stderr
  (`loganalyze: warning: <N> malformed line(s) skipped`), never aborting the run.
- **Reports** (over the in-window entries): the top-N most-requested paths
  (count descending); the exact status-code histogram plus the `1xx..5xx` class
  rollup; and the error rate `(status >= 400) / (entries in window)`.
- **`--since`/`--until`** restrict aggregations to `since <= ts <= until`
  (inclusive both ends). Either may be given alone; an inverted window yields a
  zero-entry report; an unparseable value is a usage error.
- **`--format json`** emits a stable, versioned schema on stdout and nothing
  else; declare it in `design/report.schema.json`. `--format text` renders a
  human report you design. Diagnostics go **only** to stderr, so
  `loganalyze --format json app.log | jq .` is always valid JSON.
- **Exit codes:** `0` success (including empty, all-malformed, and empty-window
  inputs, and `--help`/`--version`); `1` runtime error (missing file, a
  directory, unreadable, I/O error); `2` usage error (unknown/invalid flag, bad
  `--format`, unparseable `--since`/`--until`, negative/non-integer `--top`,
  more than one positional).
- **Determinism.** For identical input and arguments the tool produces
  byte-identical stdout across repeated invocations, including under differing
  `PYTHONHASHSEED`.
- **Streaming, bounded memory.** Consume input line by line; peak memory must
  scale with the number of *distinct* paths/status codes, never with the number
  of lines. Reading the whole file (`read()`/`readlines()`/`list(...)`) fails.
- **`--help`** must be sufficient to use the tool without reading the source:
  the usage line, every option, the exit-code table, and your resolutions of the
  three ambiguities below.
- Standard library only, Python >= 3.11 (`argparse` is expected). No third-party
  imports, no network, no filesystem writes, no `eval`/`exec`.

## Ambiguities you must resolve

Pick one resolution for each, apply it **consistently** in both output formats,
and document it in the `--help` epilogue **and** in `design/CLI_UX.md`:

1. **Naive `--since`/`--until`** (no offset, e.g. `2023-10-10T13:00:00`): treat
   it as UTC, or as wall-clock in the entry's own offset. (An offset-bearing or
   `Z`-suffixed argument is always an absolute instant -- not open.)
2. **Tie-breaking** for equal path counts: any documented, deterministic total
   order (recommended: ascending Unicode code point).
3. **`--top 0`**: "none" (empty top list) or "all" (every distinct path). A
   negative `--top` is a usage error.

## Deliverables

Your workspace root (the harness's `SOLUTION_DIR`) must contain the runnable CLI
(`python -m loganalyze`) and a `design/` directory with `CLI_UX.md` (grammar,
verbatim `--help`, exit-code table, a rendered text-output sample the binary
matches, and the three resolutions), `report.schema.json` (JSON Schema draft
2020-12 for your JSON output), and `USER_STORIES.md` (US-1..US-8 traced to the
functional requirements).

You are given `tests/smoke/` to check your work. Held-out `acceptance` and
`adversarial` suites grade you (see `EVALUATION.md` for what they measure).

**Entrypoint:** the harness runs `python -m loganalyze` from your workspace (see
`manifest.yaml`).
