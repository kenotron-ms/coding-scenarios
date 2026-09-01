# L3 — Log Analyzer — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> artifact obligations per `framework/ARTIFACT_GRADIENT.md` row **L3**.

## 0. Scenario Summary
- **Level:** L3
- **Codename / dir:** `L3-log-analyzer`
- **One-liner:** A command-line tool that parses a web access-log format and emits
  aggregate reports (top paths, status-code breakdown, error rate, time-window
  filtering) as human-readable text or JSON.
- **New difficulty introduced:** **The first CLI surface.** Everything below L3
  was verified by calling a function or a class. Here the *real path* is a
  process: argv parsing, file **or** stdin input, exit codes, selectable output
  formats, help/usage text, and diagnostics on stderr. The agent must design a
  user-facing contract (grammar + output shapes) before it can implement one, and
  the harness judges it by running the built CLI as a subprocess.
- **Estimated reference solution size:** 250–400 LoC across 5–6 files (CLI,
  parse, aggregate, render, `__main__`), plus ~100 lines of design artifacts.
- **Time budget:** 30 minutes wall-clock.
- **Iteration budget:** soft 10, hard 25 edit→verify cycles.
- **Intervention budget:** 0.

## 1. Product Requirements

- **1.1 Problem statement** — An operator with shell access to a web server needs
  fast, dependency-free answers about traffic and errors *without* shipping logs
  to a log platform: which paths are hot, how status codes are distributed, what
  fraction of requests failed, and how those answers change inside a specific time
  window. The deliverable is a single-purpose CLI that streams an access log
  (from a file or a pipe) and prints an aggregate report as human text or as JSON
  for downstream tooling.

- **1.2 Target users / personas** — Two lightweight **operator profiles**. These
  are usage contexts, not formal persona artifacts; personas are `N/A` at this
  rung (`ARTIFACT_GRADIENT.md` L3: Personas = `—`).

  | Profile | Context | What they need from the tool |
  |---------|---------|------------------------------|
  | **On-call SRE (triage)** | Paged at 02:00; needs to know what broke and when. | Error rate + status breakdown narrowed to the incident window; must work on a piped `zcat`/`tail` stream; must not choke on a truncated or corrupt tail. |
  | **Capacity reviewer (weekly)** | Reviewing traffic shape for a service. | Top-N paths over a whole day/week; JSON output to feed a spreadsheet or dashboard job; stable output so week-over-week diffs are meaningful. |

- **1.3 User stories** — Required deliverable at this rung (see §5.2). The
  following are the *baseline* stories the solution must satisfy; the agent
  restates and extends them in `design/USER_STORIES.md` with traceability to
  `FR-n`.
  - **US-1** As an on-call SRE, I want to pipe a log slice into the tool, so that
    I can triage without copying files around. *(FR-1)*
  - **US-2** As an on-call SRE, I want the error rate and status breakdown for a
    specific time window, so that I can confirm when the incident started and
    stopped. *(FR-5, FR-6, FR-7)*
  - **US-3** As an on-call SRE, I want a corrupt or truncated line to be skipped
    and *counted*, not to abort the run, so that a bad tail never costs me the
    whole report. *(FR-3)*
  - **US-4** As a capacity reviewer, I want the top N requested paths, so that I
    can see where load concentrates. *(FR-4)*
  - **US-5** As a capacity reviewer, I want machine-readable JSON with a stable,
    documented schema, so that I can script against it without re-writing my
    parser every release. *(FR-9)*
  - **US-6** As any operator, I want `--help` to tell me the grammar, the exit
    codes, and the tool's ordering/timezone rules, so that I do not have to read
    the source. *(FR-11)*
  - **US-7** As a script author, I want exit codes that distinguish "worked",
    "runtime failure", and "you called me wrong", so that my wrapper script can
    branch correctly. *(FR-10)*
  - **US-8** As a capacity reviewer, I want to run this against a multi-gigabyte
    log on a small box, so that I do not need a machine with more RAM than the
    log has bytes. *(NFR-1)*

- **1.4 Functional requirements**
  - **FR-1 Input sources.** Read the log from the positional `FILE` argument. If
    `FILE` is omitted **or** is exactly `-`, read from stdin. No TTY detection is
    required: with `FILE` omitted the tool reads stdin unconditionally.
  - **FR-2 Line parsing.** Parse each input line against the log grammar fixed in
    §2.3 into an entry of `(host, timestamp, method, path, status, bytes)`.
    Timestamps parse to timezone-aware instants using the line's numeric offset.
  - **FR-3 Malformed-line handling.** A line that does not match the grammar is
    **skipped and counted**; it never aborts the run and never changes the exit
    code. Blank/whitespace-only lines are skipped and are **not** counted as
    malformed. When the malformed count is > 0, the tool emits exactly one
    summary line on **stderr** (never stdout) — see §2.1. Malformed lines are
    counted regardless of `--since`/`--until` (they have no usable timestamp).
  - **FR-4 Top-N paths.** Report the most-requested paths with their request
    counts, descending by count, limited to `--top N` (default `10`). The list is
    computed over the **in-window** entries. If fewer distinct paths exist than
    `N`, report all of them. `--top 0` semantics are an open resolution (§1.6);
    a negative `N` is a usage error (exit 2).
  - **FR-5 Status-code breakdown.** Report a histogram of exact status codes
    present in the window (codes with zero occurrences are omitted) **and** the
    five-bucket class rollup `1xx/2xx/3xx/4xx/5xx` (all five keys always present,
    zeros included). `--status` controls only whether the **text** rendering
    includes the exact-code section; JSON always contains both (§2.1).
  - **FR-6 Error rate.** `error_rate = (entries in window with status ≥ 400) /
    (entries in window)`. When the denominator is `0`, the error rate is `0.0`.
    JSON emits a float rounded to 6 decimal places; text renders a percentage
    with 2 decimal places alongside the raw numerator/denominator.
  - **FR-7 Time-window filtering.** `--since ISO` and `--until ISO` restrict the
    aggregations (FR-4, FR-5, FR-6) to entries whose timestamp falls inside the
    window, **inclusive at both ends** (`since ≤ ts ≤ until`). Either may be
    given alone. A window in which `since > until` is legal and yields a
    well-formed zero-entry report with exit 0. An unparseable ISO value is a
    usage error (exit 2). Timezone semantics for naive values are an open
    resolution (§1.6).
  - **FR-8 Deterministic, stable ordering.** For identical input and identical
    arguments the tool produces **byte-identical** stdout across repeated
    invocations, including under differing `PYTHONHASHSEED`. Primary sort of
    `top_paths` is count descending; ties are broken by a documented,
    deterministic rule (§1.6). Status codes are emitted in ascending numeric
    order. No output ordering may depend on `dict`/`set` iteration by accident.
  - **FR-9 Output formats.** `--format text` (default) renders the human report;
    `--format json` emits the **stable schema** fixed in §2.1 and nothing else on
    stdout. Any other value is a usage error (exit 2).
  - **FR-10 Exit codes.** `0` success (including "zero entries" and "everything
    was malformed"); `1` runtime error (file not found, unreadable, is a
    directory, I/O failure); `2` usage error (unknown flag, bad `--format` value,
    unparseable `--since`/`--until`, negative `--top`, extra positional
    arguments). See the table in §2.1.
  - **FR-11 `--help` and `--version`.** Both write to stdout and exit `0`.
    `--help` must show the usage line, every option with a description, **the
    exit-code table**, and the tool's resolutions of the three §1.6 ambiguities.
    `--version` prints the program name and a semantic version.
  - **FR-12 Stream discipline.** stdout carries **only** the report (or help /
    version). Every diagnostic, warning, and error goes to stderr. This must hold
    for both formats, so `loganalyze --format json app.log | jq .` is always
    valid JSON.
  - **FR-13 Degenerate inputs.** Empty input, all-blank input, and
    all-malformed input each produce a well-formed zero-entry report on stdout
    (empty `top_paths`, empty `status_counts`, all-zero `status_classes`,
    `error_rate` `0.0`) and exit `0`.

- **1.5 Out of scope** — Combined Log Format (referrer + user-agent fields) and
  any format other than the §2.3 subset; compressed input (`.gz`); multiple input
  files; `tail -f`/follow mode; unique-visitor, per-host, or bytes-transferred
  reports; path normalization or grouping (query-string stripping, regex
  bucketing); output-to-file (`-o`); colorized or TTY-adaptive output; config
  files or environment-variable configuration; named IANA timezones (numeric
  offsets only); non-English month abbreviations; incremental/streaming output
  (the report is emitted once, at end of input); a Python API contract — the CLI
  *is* the contract.

- **1.6 Ambiguities the agent must resolve** — Three. Each must be resolved
  **consistently**, documented in the `--help` epilogue *and* in
  `design/CLI_UX.md`, and implemented identically in both output formats.

  | # | Ambiguity | Acceptable resolutions | How acceptance tests it |
  |---|-----------|------------------------|-------------------------|
  | A-1 | **Naive `--since`/`--until` vs. log offsets.** Log timestamps always carry a numeric offset; an ISO argument may not (`2023-10-10T13:00:00`). | (a) treat a naive value as **UTC**; (b) treat a naive value as **wall-clock in the entry's own offset**. An *offset-bearing* argument (`…-07:00`, `…Z`) is **always** compared as an absolute instant — this part is not open. | Offset-bearing windows are asserted exactly. Naive windows are asserted to match *one* of (a)/(b) and to match the declared policy; mixing the two across `--since`/`--until` or across formats fails. |
  | A-2 | **Tie-breaking for equal path counts.** | Any deterministic total order, documented. Recommended: ascending lexicographic (Unicode code-point) by path. | Exact-order golden cases are built tie-free. Tie cases assert: byte-identical output over 3 runs with different `PYTHONHASHSEED`, the same `(path, count)` multiset as the reference, and an ordering consistent with the declared rule. |
  | A-3 | **`--top 0`.** | (a) "none" → empty `top_paths` / no top-paths rows; (b) "all" → every distinct path, fully ordered. | `--top 0` must exit `0` and produce a well-formed report whose `top_paths` is either `[]` or the complete ordered path list, and the text and JSON renderings of the same invocation must agree. Crash, traceback, or exit ≠ 0 fails. |

## 2. Technical Requirements

- **2.1 Interface / API contract**

  **CLI grammar** (the normative surface):

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

  **Exit codes** (must be reproduced in the `--help` epilogue):

  | Code | Name | Triggers |
  |------|------|----------|
  | `0` | success | Report emitted — including empty input, all-malformed input, and empty time windows. Also `--help` and `--version`. |
  | `1` | runtime error | `FILE` does not exist, is a directory, or is unreadable; I/O error while reading. |
  | `2` | usage error | Unknown/duplicate-incompatible flag, unknown `--format` value, unparseable `--since`/`--until`, non-integer or negative `--top`, more than one positional argument. |

  **Diagnostic lines** (stderr, pinned — acceptance matches these exactly):

  ```text
  loganalyze: warning: <N> malformed line(s) skipped
  loganalyze: error: <message>
  ```

  The warning is emitted **once**, at most, and only when `N > 0`. Per-line
  warnings are forbidden (a 2 GB corrupt log must not produce 2 GB of stderr).
  Usage errors (exit 2) additionally print the standard `usage: …` line, which is
  what `argparse` does natively — use it rather than reimplementing it.

  **JSON output schema** (`--format json`) — **stable and versioned**. All keys
  are always present. Serialization is `indent=2` with a trailing newline, keys
  in exactly the order shown:

  ```json
  {
    "schema_version": 1,
    "window": {
      "since": "2023-10-10T00:00:00+00:00",
      "until": null
    },
    "totals": {
      "lines_read": 1203,
      "entries_parsed": 1200,
      "malformed": 3,
      "entries_in_window": 1150
    },
    "top_paths": [
      {"path": "/index.html", "count": 842},
      {"path": "/api/v1/items", "count": 201}
    ],
    "status_counts": {"200": 1100, "404": 45, "500": 5},
    "status_classes": {"1xx": 0, "2xx": 1100, "3xx": 0, "4xx": 45, "5xx": 5},
    "error_rate": 0.043478
  }
  ```

  Schema rules:

  | Field | Rule |
  |-------|------|
  | `schema_version` | Integer literal `1`. |
  | `window.since` / `window.until` | `null` when the flag was not given, otherwise the **normalized** ISO-8601 form of the parsed value. |
  | `totals.lines_read` | Every physical line read from input, including blank and malformed lines. |
  | `totals.entries_parsed` | Lines that matched the §2.3 grammar, **before** window filtering. |
  | `totals.malformed` | Non-blank lines that failed the grammar. Invariant: `entries_parsed + malformed + blank_lines == lines_read`. |
  | `totals.entries_in_window` | Parsed entries surviving `--since`/`--until`. Equals `entries_parsed` when no window is given. |
  | `top_paths` | Array of objects, length `≤ --top`, ordered per FR-8. Computed over in-window entries. |
  | `status_counts` | Object keyed by 3-character status string, ascending numeric key order, in-window entries only, zero-count codes omitted. |
  | `status_classes` | All five keys always present, zeros included, in the fixed order `1xx,2xx,3xx,4xx,5xx`. |
  | `error_rate` | Float, `round(x, 6)`; `0.0` when `entries_in_window == 0`. |

  The schema deliberately contains **no input path, hostname, or run timestamp**,
  so JSON output is byte-reproducible and path-independent.

  **Text output** — the agent owns the exact layout (this is the CLI UX design
  deliverable, §5.4, scored under `FID`). The layout must be committed as a
  rendered sample in `design/CLI_UX.md`, and the implementation must match that
  sample. Required *content*, whatever the layout:

  - total entries parsed and the malformed count;
  - the effective window (or an explicit indication that none was applied);
  - the error rate as a percentage plus its numerator/denominator;
  - the top-N paths with counts, in FR-8 order;
  - the exact status-code breakdown **when `--status` is given**; the `1xx…5xx`
    class rollup always.

  Illustrative only — not normative, do not treat as a golden file:

  ```text
  Entries:    1,200 parsed  (3 malformed lines skipped)
  Window:     2023-10-10T00:00:00+00:00 .. (none)
  Error rate: 4.35%  (50/1150)

  Top 3 paths
    842  /index.html
    201  /api/v1/items
     97  /static/app.js

  Status classes
    2xx  1100    3xx     0    4xx    45    5xx     5
  ```

- **2.2 Architecture constraints** — A package with enforced module boundaries;
  this separation is a scored `QUA` requirement, not a suggestion.

  | Module | Responsibility | May do | Must not do |
  |--------|----------------|--------|-------------|
  | `cli.py` | argv parsing, I/O wiring, exit codes | touch `sys.argv`, `sys.stdin/stdout/stderr`, `sys.exit`, open files | contain parsing or aggregation logic |
  | `parse.py` | one line → entry or `None` | pure string/datetime work | print, exit, read files |
  | `aggregate.py` | iterable of entries → report object | accumulate counters | print, exit, read files, materialize the input |
  | `render.py` | report object → `str` (text or JSON) | format | print, exit, compute aggregates |
  | `__main__.py` | `python -m loganalyze` shim | call `cli.main()` | anything else |

  `cli.py` is the **only** module permitted to call `print`, `sys.exit`, or touch
  the standard streams. Forbidden everywhere: third-party imports, network
  access, writing to the filesystem, `eval`/`exec`, shelling out, and reading the
  input more than once.

- **2.3 Data model** — Log entries are transient records; there is no
  persistence. The input grammar is **exactly** this Common Log Format subset,
  one entry per line:

  ```text
  HOST IDENT AUTHUSER [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD PATH HTTP/x.y" STATUS BYTES
  ```

  ```text
  127.0.0.1 - - [10/Oct/2023:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326
  ```

  | Field | Rule | Reported? |
  |-------|------|-----------|
  | `HOST` | One non-whitespace token (IPv4, IPv6, or hostname). Not otherwise validated. | No (validation only) |
  | `IDENT`, `AUTHUSER` | Two single non-whitespace tokens, conventionally `-`. Must be **present**; value ignored. | No (validation only) |
  | timestamp | `[` + `%d/%b/%Y:%H:%M:%S %z` + `]`. Zero-padded 2-digit day; English 3-letter month (`Jan`…`Dec`, case-sensitive); 4-digit year; 24-hour zero-padded time; offset `+HHMM`/`-HHMM`. Parsed to a timezone-aware instant. | Yes (FR-7) |
  | `METHOD` | 1+ uppercase ASCII letters. | No (validation only) |
  | `PATH` | A run of non-space characters beginning with `/`. Taken **verbatim**, including any query string or fragment: no decoding, no normalization, no trailing-slash collapsing, no query stripping. | Yes (FR-4) |
  | `HTTP/x.y` | Literal `HTTP/`, one digit, `.`, one digit. | No (validation only) |
  | `STATUS` | Exactly 3 digits, in `[100, 599]`. | Yes (FR-5, FR-6) |
  | `BYTES` | A non-negative integer, or `-` meaning unknown. | No — byte-volume reporting is out of scope (§1.5); the field is validated, not reported. |

  Structural rules: fields are separated by a single space; the request is a
  double-quoted string containing **exactly three** space-separated tokens (so a
  path containing a space or a quote makes the line malformed); trailing `\r`
  and `\n` are tolerated and stripped; a blank or whitespace-only line is skipped
  silently. **Anything else is malformed** — including a bad month abbreviation,
  a 2-digit status, a missing bracket or quote, a missing field, or an extra
  trailing field.

  Input is decoded as UTF-8 with `errors="replace"`; a `UnicodeDecodeError` must
  never escape. A line that survives replacement but fails the grammar is
  malformed like any other.

- **2.4 Technology constraints** — Python ≥ 3.11. **Standard library only**;
  `argparse` is the expected argv parser (it supplies exit code 2 and the
  `usage:` line for free). No `requirements.txt` dependencies. `ruff` and
  `pyright` are the static gates and are provided by the harness, not vendored.

- **2.5 Entrypoint contract** — `kind: cli`. The harness invokes the built CLI as
  a **subprocess** — never by importing it:

  ```yaml
  entrypoint:
    kind: cli
    command: ["python", "-m", "loganalyze"]
    cwd: solution/
  ```

  The harness supplies argv, optionally pipes stdin, and captures stdout, stderr,
  and the return code separately. It may vary `PYTHONHASHSEED` between
  invocations (FR-8). A `loganalyze` console script via `pyproject.toml` is
  **Optional/Stretch**; `python -m loganalyze` is the normative entrypoint and is
  what every acceptance assertion uses.

## 3. Non-Functional Requirements

- **NFR-1 Performance (streaming, bounded memory)** — The tool must consume input
  **line by line** and hold only aggregations in memory. Peak RSS must be
  independent of input size: it may scale with the number of *distinct paths and
  status codes*, never with the number of lines or bytes read. Concretely: a
  multi-gigabyte log with a bounded distinct-path set must complete without
  loading the file, and peak RSS at ~2 GB of input must be within **1.2×** of
  peak RSS at ~200 MB of the same distribution, and under **200 MB** absolute.
  Reading the whole file (`read()`, `readlines()`, `list(...)`, `sys.stdin.read()`)
  fails this NFR by construction. Throughput target ≥ 50,000 lines/s on the
  reference runner — informative, not gated.
- **NFR-2 Reliability & error handling** — A single malformed line never crashes
  the run (FR-3). No traceback may ever reach stderr: unexpected exceptions are
  caught at the `cli.py` boundary and rendered as
  `loganalyze: error: <message>` with exit 1. Undecodable bytes, CRLF endings,
  and pathologically long lines are survivable. Writing to a closed stdout (e.g.
  `| head -1`) must not produce a traceback.
- **NFR-3 Security** — The log is **untrusted input**. No `eval`, `exec`,
  `pickle`, or dynamic import of anything derived from input. Log content is
  never interpreted as a path, format string, or shell fragment. Any regex used
  for parsing must be linear-scan safe — no nested unbounded quantifiers that
  permit catastrophic backtracking on a hostile line. The tool reads exactly the
  one file it was given and writes nothing to the filesystem.
- **3.4 Accessibility** — **N/A** — no GUI. The closest analogue at this rung —
  output that is plain-ASCII-safe and never conveys meaning by color alone — is
  covered by NFR-6 and by `--format json` for programmatic consumers.
- **NFR-4 Maintainability** — `ruff` and `pyright` clean. The §2.2 module
  boundaries are respected (parse / aggregate / render / CLI separated, and only
  `cli.py` touches process state). Every public function has a docstring stating
  its contract; cyclomatic complexity ≤ 10 per function. The three §1.6
  resolutions are documented in code, not just in the help text.
- **NFR-5 Observability** — Malformed input is *visible*: the single stderr
  summary line (§2.1) plus the `totals.malformed` field make silent data loss
  impossible. Exit codes are meaningful and distinct per FR-10, so a wrapper
  script can distinguish "the log was bad" (exit 0 with a warning) from "you
  called me wrong" (exit 2) from "I could not read it" (exit 1). Diagnostics
  never contaminate stdout (FR-12).
- **NFR-6 Usability** — `--help` is sufficient to use the tool without reading
  the source: usage line, every option described with its default, the exit-code
  table, and the §1.6 resolutions. Error messages name the offending value
  (`loganalyze: error: unparseable --since value: 'yesterday'`), not just the
  failure class. *(The template has no dedicated usability slot; this NFR is
  filed here because at L3 usability is an observability-of-contract property.)*
- **NFR-7 Portability / footprint** — Zero third-party dependencies; runs on any
  CPython ≥ 3.11 on Linux/macOS. No compilation, no install step required for the
  normative `python -m` entrypoint.

## 4. The Ask (Deliverables & Definition of Done)

- **4.1 Required artifacts**

  | Path | Contents |
  |------|----------|
  | `solution/loganalyze/__init__.py` | Package marker + `__version__`. |
  | `solution/loganalyze/__main__.py` | `python -m loganalyze` shim. |
  | `solution/loganalyze/cli.py` | argv parsing, stream wiring, exit codes, diagnostics. |
  | `solution/loganalyze/parse.py` | §2.3 grammar → entry or `None`. |
  | `solution/loganalyze/aggregate.py` | Streaming aggregation → report object. |
  | `solution/loganalyze/render.py` | Report → text or JSON string. |
  | `design/CLI_UX.md` | The CLI UX spec: grammar, the verbatim `--help` text, the exit-code table, the **rendered text-output sample** the implementation must match, and the §1.6 resolutions with rationale. |
  | `design/report.schema.json` | JSON Schema (draft 2020-12) for the §2.1 output, declared by the solution. |
  | `design/USER_STORIES.md` | The §1.3 stories, restated/extended, each traced to `FR-n`. |

  Optional/Stretch: `solution/pyproject.toml` with a `loganalyze` console script;
  a short `README.md`.

- **4.2 Definition of Done**
  - [ ] `smoke` tests pass.
  - [ ] `acceptance` suite passes at **≥ 95%** (hard gate, §7.3).
  - [ ] `ruff` + `pyright` clean; §2.2 module boundaries respected.
  - [ ] All three §1.6 ambiguities resolved, implemented consistently across both
        output formats, and documented in **both** `--help` and `design/CLI_UX.md`.
  - [ ] `--format json` output validates against `design/report.schema.json`
        **and** against the §2.1 schema, with identical key order.
  - [ ] The text output matches the sample committed in `design/CLI_UX.md`.
  - [ ] Exit codes 0/1/2 behave per the §2.1 table.
  - [ ] Bounded-memory probe passes (NFR-1) — input is never materialized.
  - [ ] `design/USER_STORIES.md` covers US-1..US-8 with `FR-n` traceability.

- **4.3 Acceptance criteria**
  - **AC-1** (FR-1, FR-2): identical reports from `loganalyze FILE`,
    `loganalyze - < FILE`, and `loganalyze < FILE`.
  - **AC-2** (FR-3, FR-13, NFR-2): mixed, all-malformed, and empty inputs each
    exit `0`, report the correct malformed count on stderr only, and emit a
    well-formed report on stdout.
  - **AC-3** (FR-4, FR-8): top-N is correct and correctly truncated for
    `--top 1/3/10/25`, ordered count-descending with the declared tie-break.
  - **AC-4** (FR-5, FR-6): status histogram, class rollup, and error rate are
    correct, including the zero-denominator case.
  - **AC-5** (FR-7): window filtering is inclusive at both boundaries; `--since`
    alone, `--until` alone, both, and an inverted window all behave per FR-7.
  - **AC-6** (FR-9, §2.1): JSON matches the pinned schema field-for-field,
    including key order, rounding, and always-present keys.
  - **AC-7** (FR-10, FR-12): the exit-code table holds; stdout is never polluted
    by diagnostics in either format.
  - **AC-8** (FR-11, NFR-6): `--help`/`--version` exit 0 and `--help` contains the
    exit-code table and all three §1.6 resolutions.
  - **AC-9** (NFR-1): the bounded-memory probe holds at multi-GB input.
  - **AC-10** (FR-8): byte-identical stdout across repeated runs and differing
    `PYTHONHASHSEED`.
  - **AC-11** (NFR-4, §5.4): static checks clean, module boundaries intact,
    required `design/` artifacts present and consistent with the implementation.

## 5. Discovery & Design Activities

Consistent with `ARTIFACT_GRADIENT.md` row **L3** — the first rung with a real UX
surface and required user stories, but no personas, backlog, or visual design.

- **5.1 User research**
  - Stakeholder/operator interviews — **Optional/Stretch**. CLI conventions are
    well established (POSIX/GNU flags, `0/1/2` exit codes, stdout-vs-stderr); the
    two operator profiles in §1.2 are sufficient input.
  - Jobs-to-be-done / needs analysis — **Optional/Stretch**. Credit only if it
    demonstrably changes a design decision (e.g. justifying the JSON schema
    shape), not as a written-after-the-fact narrative.
  - Personas — **N/A** — the operator profiles in §1.2 fully cover the two usage
    contexts; formal personas begin at A1 where end-user experience is part of
    "working."
  - Usability testing — **N/A** — no interactive UI to observe.
- **5.2 Product design**
  - Spec / acceptance criteria — **Required.** This document is the spec; §4.3 is
    the criteria set.
  - **User stories — Required deliverable** (`design/USER_STORIES.md`), traced to
    `FR-n`. First rung where they are mandatory.
  - Definition of Done — **Required** (§4.2).
  - PRD (problem, scope, success metrics) — **Optional/Stretch.** Scored under
    `FID` only if present and consistent; its absence costs nothing.
  - Prioritized backlog — **N/A** — single-shot delivery, no sequencing decision
    to make.
- **5.3 Interaction / visual design**
  - Interface/API contract design — **Required.** The CLI grammar and the JSON
    schema are the contract.
  - **CLI UX / output-format design — Required.** The argument grammar, help
    text, diagnostic wording, exit-code semantics, and the text report layout are
    designed *before* implementation and committed as an artifact.
  - Wireframes, hi-fi mockups, design tokens, interaction/state specs, WCAG
    annotations — **N/A** — no graphical surface.
- **5.4 Design artifacts to produce**

  | Artifact | Must contain | Scored under |
  |----------|--------------|--------------|
  | `design/CLI_UX.md` | Grammar (usage line + every option), verbatim `--help` text, exit-code table, rendered text-output sample, wording of stderr diagnostics, and the three §1.6 resolutions with rationale. | `FID` (design-diff: implementation must match), `QUA` |
  | `design/report.schema.json` | JSON Schema draft 2020-12 for §2.1: all keys required, `additionalProperties: false`, types and value constraints. | `FID` (JSON output validated against it), `COR` |
  | `design/USER_STORIES.md` | US-1..US-8 (restated/extended), each mapped to the `FR-n` it justifies. | `FID` (existence + traceability) |

  Design artifacts are judged by **agreement with the implementation**, not by
  volume. A `CLI_UX.md` whose sample output does not match what the binary prints
  is worse than none — it is a documented lie, and caps `FID` at 1.

## 6. Verification Method

- **6.1 Test tiers**
  - **`smoke` (visible)** — `tests/smoke/sample.log`: ~20 lines spanning three
    timestamps, five paths, statuses across `2xx/3xx/4xx/5xx`, plus 2 deliberately
    malformed lines and 1 blank line. Six worked cases with expected output shown:
    (1) default text run; (2) `--format json` full expected document; (3)
    `--top 2`; (4) a `--since`/`--until` window; (5) `--bogus` → exit 2 with a
    `usage:` line on stderr; (6) `missing.log` → exit 1 with
    `loganalyze: error: …` on stderr. Enough to self-check the happy path, far too
    narrow to pass acceptance by hardcoding.
  - **`acceptance` (held-out)** — A broad matrix over the following dimensions,
    combined against several generated logs (clean / mixed-malformed /
    all-malformed / empty / boundary-heavy), each with an independently computed
    reference report:

    | Dimension | Values exercised |
    |-----------|------------------|
    | Input source | `FILE` arg · `-` · omitted (stdin) |
    | `--format` | `text` · `json` |
    | `--top` | default · `1` · `3` · `25` (> distinct count) · `0` |
    | `--status` | present · absent |
    | Window | none · `--since` only · `--until` only · both · exact-boundary · inverted (`since > until`) |
    | Window arg form | offset-bearing · `Z`-suffixed · naive (policy-consistency check per A-1) |
    | Input content | clean · mixed malformed · all malformed · empty · blank-only |
    | Process surface | exit code · stdout bytes · stderr bytes · rerun determinism |

    Plus: JSON validated against the §2.1 schema *and* the solution's declared
    `design/report.schema.json`; the `lines_read` invariant; `--help`/`--version`
    content checks; the FR-12 stdout-purity check under both formats; and the
    NFR-1 bounded-memory probe.
  - **`adversarial` (hidden, run once)** — Empty input; all-malformed input;
    `--top 0`; `--top -1` (expect 2); unknown flag (expect 2); `--format xml`
    (expect 2); missing file (expect 1); a directory as `FILE` (expect 1);
    timestamps exactly equal to `--since` and to `--until` (must be included);
    an entry one second outside each boundary (must be excluded); unparseable
    `--since` (expect 2); a huge input (memory + no-timeout); CRLF line endings;
    invalid UTF-8 bytes in a path; a 1 MB single line; a path containing a space
    or a quote (must be malformed, not a crash); statuses `100` and `599`; `BYTES`
    of `-`; a lowercase month (`10/oct/2023…` → malformed); `--top 3 --top 5`
    (last wins, no crash); a log with a very large distinct-path set;
    `| head -1` (no traceback).
- **6.2 "Working" definition** — **≥ 95% of acceptance assertions pass.** There is
  no separate must-pass P0 subset at this rung (that carve-out is introduced at
  A1); the 5% headroom exists because the acceptance matrix is large and a single
  cosmetic text-layout assertion should not be fatal. Adversarial results never
  count toward the gate but feed `COR`/`ROB`.
- **6.3 Verification mechanics** — Every tier runs the **real path**: the built
  CLI as a subprocess (`python -m loganalyze`), with argv and optional piped
  stdin, capturing stdout, stderr, and the return code separately. Importing the
  solution's functions is **not** acceptance evidence at L3
  (`VERIFICATION_CONTRACT.md` §3). Assertion styles:

  | Surface | Style |
  |---------|-------|
  | Exit codes | Exact integer match against the §2.1 table. |
  | stderr | Exact match against the pinned diagnostic strings (§2.1); plus "stderr is empty when nothing is wrong". |
  | `--format json` stdout | **Byte-exact golden files** (schema is pinned, so exactness is fair) + JSON Schema validation + independent recomputation of every aggregate. |
  | `--format text` stdout | **Semantic** assertions — required labels present, extracted counts correct, ordering correct — plus a **self-golden** check that the output matches the sample committed in `design/CLI_UX.md`. The exact layout is the agent's design surface; pinning it would delete the `FID` surface. |
  | Determinism (FR-8) | Same invocation run 3× with different `PYTHONHASHSEED`; stdout must be byte-identical. |
  | Bounded memory (NFR-1) | A generator pipes ~200 MB then ~2 GB of synthetic log to stdin; the harness samples peak RSS of the child process and asserts the NFR-1 bounds. Fails immediately for any implementation that materializes the input. |
  | Static quality | `ruff` + `pyright` in CI mode; an import-graph check that `parse/aggregate/render` never reference `sys.exit`, `print`, or the standard streams. |

- **6.4 Anti-gaming measures**
  - Acceptance logs are **generated per run** with different path/status
    distributions and timestamp spreads than the smoke sample; every expected
    value is computed independently, so hardcoding the smoke outputs fails.
  - JSON Schema validation plus independent recomputation defeats "print a
    plausible-looking constant blob."
  - The bounded-memory probe cannot be satisfied by any implementation that reads
    the file whole — it is a structural, not cosmetic, check.
  - Hash-seed-varied reruns catch accidental reliance on `dict`/`set` iteration
    order, which is the classic "passes locally, flaps in the harness" failure.
  - The **design-diff check** (implementation vs. the agent's own `CLI_UX.md`
    sample and `report.schema.json`) catches design artifacts written post-hoc to
    look compliant; artifact mtimes relative to source files are recorded as a
    supporting signal (§8.3).
  - A large gap between `acceptance_pass` and `adversarial_pass` caps `ROB`
    (`CONVERGENCE_METRICS.md` §6).

## 7. Scoring Rubric

- **7.1 Weight profile** (sum 100):
  `COR 35 · ROB 18 · EFF 12 · AUT 10 · QUA 12 · REG 5 · FID 8`.

  Two axes activate at this rung:
  - **`REG` (5)** — first appearance. There is no second feature to break yet, so
    the weight is small, but there *is* prior behavior to protect: the flag matrix.
    `REG` measures whether behavior stayed correct **across the full matrix and
    across repeated invocations** — e.g. adding `--status` breaking `--format
    json`, adding window filtering breaking the no-window path, or a late fix
    re-breaking an earlier-passing assertion.
  - **`FID` (8)** — first appearance. There is now a product/design surface to be
    faithful to: the CLI UX spec, the help text, the exit-code contract, and the
    declared JSON schema.

- **7.2 Per-axis scoring guide**

  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | acceptance < 95% (gate fail) | ≥ 95% acceptance but real gaps — e.g. window boundaries off by one end, or JSON key order/rounding drift | ≥ 99% acceptance **and** ≥ 95% adversarial; every aggregate correct under every flag combination |
  | ROB | a malformed line, empty input, or missing file crashes or emits a traceback | survives malformed lines but mishandles a degenerate case (all-malformed, 1 MB line, invalid UTF-8, closed stdout) | every §6.1 adversarial input handled with the right exit code and a clean diagnostic; nothing ever tracebacks |
  | EFF | > 25 iterations or > 30 min | passed near the hard cap, or high `failed_runs_before_pass` (thrash on argv/exit-code semantics) | passed ≤ 10 iterations, under time budget, ≤ 1 failed run before pass |
  | AUT | any `rescue` | one `clarify` on a §1.6 ambiguity (which the spec explicitly asks the agent to resolve alone) | zero interventions, no dead ends |
  | QUA | lint/type errors, or a single-file blob mixing argv parsing with aggregation | clean, but boundaries leak — e.g. `parse.py` prints warnings, or `render.py` recomputes aggregates | `ruff`+`pyright` clean, §2.2 boundaries strictly held, docstrings present, complexity ≤ 10, resolutions documented in code |
  | REG | a fix for one flag demonstrably broke another (`regressions_introduced` > 0 at final) or output is non-deterministic across runs | one oscillation, or one flag combination regressed and was recovered late | zero regressions, zero oscillations, byte-identical output across all rerun/hash-seed checks |
  | FID | a required `design/` artifact is missing, or `CLI_UX.md` contradicts the binary | artifacts present but thin — help text omits the exit-code table or a §1.6 resolution; schema file drifts from actual output | all three artifacts present, internally consistent, traced to `FR-n`; help text complete; JSON validates against the solution's own declared schema; text output matches the committed sample |

- **7.3 Hard gate** — `acceptance_floor = 0.95`. Below it the run is **Failed (0
  overall)** regardless of other axes. `gaming_events` (reading held-out tests,
  hardcoding expected outputs, escaping the workspace) disqualify the run and
  zero `QUA`/`FID`.
- **7.4 Pass threshold** — **72.** L3 is the first rung with a genuine design
  surface and real process semantics; a "Converged" band result (70–84) is the
  expected outcome for a competent strategy, and 72 requires it to have done more
  than merely clear the gate.

## 8. Convergence Signals

- **8.1 Healthy convergence** — The strategy designs before it types: it writes
  the grammar, help text, exit-code table, and JSON schema into `design/` first,
  then implements against them. It reaches for `argparse` immediately (exit code 2
  and the `usage:` line come free) rather than hand-rolling argv parsing. It
  writes a streaming generator from the first commit, because it read NFR-1 before
  it read FR-4. It runs its **own CLI as a subprocess** during its loop rather
  than only importing functions — the single strongest predictor of passing at
  this rung. Most of its iterations go to §2.3 grammar edge cases, not to
  plumbing. Expect ≤ 10 iterations, zero interventions, and the three §1.6
  resolutions decided once and never revisited.
- **8.2 Pathological patterns**
  - **Function-testing instead of process-testing.** The agent verifies by
    importing `aggregate()` and never runs the CLI; passes its own checks, then
    fails a broad swath of acceptance on exit codes, stream discipline, or help
    text. Surfaces as a very low `failed_runs_before_pass` followed by a large
    acceptance drop — the classic L3 cliff.
  - **stdout/stderr conflation.** Warnings printed to stdout break *every* golden
    assertion at once. Look for a single fix flipping a large block of assertions
    from fail to pass — the fix was cheap, but the diagnosis cost iterations.
  - **Late memory discovery.** The agent uses `readlines()` for convenience,
    passes everything else, then hits the NFR-1 probe at the end and must
    restructure `aggregate.py` under time pressure. Shows up as a `dead_end` plus
    an iteration spike in the last quartile.
  - **Ordering oscillation.** Tie-break rules changed repeatedly (`oscillations`
    > 0), or output that is only *sometimes* stable because a `set` leaked into
    the ordering path — caught by the hash-seed reruns, often after the agent has
    declared done.
  - **Malformed-as-fatal.** Treating a bad line as an error exit, or emitting one
    warning per bad line. Both look "careful" and both fail FR-3/NFR-5.
  - **Post-hoc design artifacts.** `design/` written after `solution/` to satisfy
    the checklist, with a sample output that does not match the binary. Detectable
    by mtime ordering plus the design-diff check; caps `FID`.
  - **Overfitting to the smoke log.** Constants derived from the 20-line sample —
    hardcoded path names, an assumed status set, a fixed top-5. Acceptance's
    generated logs expose it immediately.
- **8.3 Instrumentation notes** — Beyond the shared `CONVERGENCE_METRICS.md` set,
  capture for this rung:
  - **Subprocess self-verification:** did the agent ever invoke its own CLI as a
    process during its loop, and at which iteration? (Binary + first-occurrence
    index.)
  - **Flag-matrix self-coverage:** which flag combinations the agent exercised
    itself, versus the acceptance matrix — the delta predicts the acceptance drop.
  - **Peak RSS** from the NFR-1 probe at both input sizes, plus the ratio.
  - **Design-artifact ordering:** mtimes of `design/*` relative to
    `solution/loganalyze/*` (design-first vs. post-hoc), and the design-diff
    result.
  - **Iteration-phase split:** iterations spent on argv/exit-code plumbing versus
    on §2.3 grammar edge cases. A strategy spending most of its budget on
    plumbing is failing the *new* difficulty this rung introduces, even if it
    ultimately passes.
