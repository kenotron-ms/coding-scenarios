# loganalyze -- CLI UX Specification

The user-facing contract for `loganalyze`, designed before implementation and
committed as the artifact the running binary is diffed against (REQUIREMENTS.md
§5.4, scored under `FID`). If the sample output below does not match what the
binary prints, that is a documented lie and caps `FID` at 1 -- so this file is
kept byte-faithful to the implementation.

## 1. Grammar

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

## 2. Verbatim `--help`

`--help` and `--version` both write to stdout and exit `0`. `--help` reproduces
the exit-code table and the three ambiguity resolutions so the tool is usable
without reading the source (NFR-6):

```text
usage: loganalyze [-h] [--version] [--top N] [--status] [--since ISO]
                  [--until ISO] [--format {text,json}]
                  [FILE]

Summarize a web access log (Common Log Format subset).

positional arguments:
  FILE                  access log to read; omit or use '-' to read stdin

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --top N               number of top paths to report (default: 10)
  --status              include the exact status-code breakdown in text output
  --since ISO           only count entries at or after this ISO-8601 instant
  --until ISO           only count entries at or before this ISO-8601 instant
  --format {text,json}  output format (default: text)

exit codes:
  0  success   report emitted (including empty, all-malformed, and empty-window
               inputs); also --help and --version
  1  runtime   FILE missing, a directory, or unreadable; an I/O error
  2  usage     unknown/invalid flag, bad --format, unparseable --since/--until,
               negative or non-integer --top, or more than one FILE

ambiguity resolutions (fixed, identical in text and json):
  * a naive --since/--until value (no timezone offset) is read as UTC; an
    offset-bearing value (...+/-HH:MM or ...Z) is an absolute instant
  * paths with equal counts are ordered by ascending Unicode code point
  * --top 0 means "none": top_paths is empty
```

## 3. Exit codes

| Code | Name | Triggers |
|------|------|----------|
| `0` | success | Report emitted -- including empty input, all-malformed input, and empty time windows. Also `--help` and `--version`. |
| `1` | runtime error | `FILE` does not exist, is a directory, or is unreadable; I/O error while reading. |
| `2` | usage error | Unknown/invalid flag, unknown `--format` value, unparseable `--since`/`--until`, non-integer or negative `--top`, more than one positional argument. |

## 4. stderr diagnostics (pinned)

All diagnostics go to stderr; stdout carries only the report (or help/version),
so `loganalyze --format json app.log | jq .` is always valid JSON (FR-12).

```text
loganalyze: warning: <N> malformed line(s) skipped
loganalyze: error: <message>
```

The warning is emitted **once**, at most, and only when `N > 0` -- never one
line per bad line. Usage errors additionally print the standard argparse
`usage:` line before `loganalyze: error: ...`.

## 5. Rendered text-output sample (self-golden)

The following is the exact output of:

```text
loganalyze --top 3 --status <7-line sample log>
```

where the sample log has three requests to `/index.html`, two each to
`/api/v1/items` and `/static/app.js`, one `500`, one `404`, and five `200`s.
The implementation must reproduce this byte-for-byte (this block is asserted as
a substring of this file by the acceptance suite):

```text
Entries:    7 parsed  (0 malformed line(s) skipped)
Window:     (none) .. (none)
Error rate: 28.57%  (2/7)

Top 3 paths
       3  /index.html
       2  /api/v1/items
       2  /static/app.js

Status codes
  200       5
  404       1
  500       1

Status classes
  1xx      0   2xx      5   3xx      0   4xx      1   5xx      1
```

Layout rules:

- **Header block** (always): `Entries:` (parsed count + malformed count),
  `Window:` (effective window or `(none) .. (none)`), `Error rate:` (percentage
  to 2 decimals with raw numerator/denominator).
- **`Top K paths`** where `K` is the number of rows actually shown (`<= --top`),
  each row `count` right-justified in a 6-wide column, then two spaces, then the
  verbatim path. Ordered by count descending, ties by ascending code point.
- **`Status codes`** appears only with `--status`: each in-window exact code
  (ascending, zero-count codes omitted).
- **`Status classes`** (always): the five buckets `1xx..5xx` in fixed order,
  zeros included.

## 6. Ambiguity resolutions (REQUIREMENTS.md §1.6) with rationale

- **A-1 -- naive `--since`/`--until` => UTC.** An ISO argument without an offset
  is interpreted as UTC; an offset-bearing (`...+/-HH:MM`) or `Z`-suffixed value
  is an absolute instant. Rationale: operators piping logs from mixed hosts want
  a single, unsurprising reference frame, and UTC is the log-analysis default.
  Applied identically to `--since`, `--until`, and to both output formats.
- **A-2 -- tie-break by ascending Unicode code point of the path.** Rationale: a
  total, content-derived order makes week-over-week diffs stable and is trivial
  to reproduce in a downstream consumer; it never depends on hash/iteration
  order (FR-8).
- **A-3 -- `--top 0` means "none".** `--top 0` exits `0` with an empty
  `top_paths` (JSON) / a `Top 0 paths` header with no rows (text). Rationale:
  "zero of something" is naturally the empty set; a caller wanting everything
  uses a large `--top`. A negative `--top` is a usage error (exit 2).
