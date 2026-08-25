"""loganalyze -- stream a Common Log Format subset and emit aggregate reports.

Reference solution for scenario ``L3-log-analyzer``. Single-file, standard
library only. The harness runs it as a **subprocess** (``python -m loganalyze``),
never by import (REQUIREMENTS.md 2.5). It MUST pass the acceptance gate
(>= 0.95) and score well; its sibling ``reference/solution_broken/loganalyze.py``
MUST fail it, proving the grader discriminates (HARNESS.md 5).

Internal separation of concerns (the 2.2 module boundaries, expressed here as
clearly-scoped functions in a single file):

* ``parse_line``  -- one raw line -> ``Entry`` or ``None`` (pure).
* ``aggregate``   -- iterable of ``Entry`` -> filled ``Report`` (pure, streaming).
* ``render_text`` / ``render_json`` -- ``Report`` -> ``str`` (pure).
* ``main`` / ``_run`` / ``_iter_entries`` -- the ONLY code that touches argv,
  the standard streams, ``sys.exit``, or the filesystem.

The three 1.6 ambiguities are resolved here, once, and identically in both
output formats:

* **A-1** A *naive* ``--since``/``--until`` value (no offset) is interpreted as
  **UTC**. An offset-bearing value (``...+/-HH:MM`` or ``...Z``) is compared as
  an absolute instant.
* **A-2** Ties in path count break by **ascending Unicode code point** of the
  path.
* **A-3** ``--top 0`` means **none** -- an empty ``top_paths`` list.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

__version__ = "1.0.0"

PROG = "loganalyze"

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}

# Backtracking-safe: every quantifier is a bounded or linear scan, no nested
# unbounded quantifiers (NFR-3 -- a hostile line cannot cause catastrophic
# backtracking).
_LINE_RE = re.compile(r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "([^"]*)" (\d{3}) (-|\d+)$')
_TS_RE = re.compile(r"^(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-]\d{4})$")
_METHOD_RE = re.compile(r"^[A-Z]+$")
_HTTP_RE = re.compile(r"^HTTP/\d\.\d$")

_HELP_EPILOG = """\
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
"""


class Entry(NamedTuple):
    """One successfully-parsed log line. Only reported fields are retained."""

    ts: datetime
    path: str
    status: int


@dataclass
class Report:
    """The aggregate report -- the sole input to rendering.

    ``lines_read``/``blank_lines``/``malformed`` are owned by the line reader
    (``_iter_entries``); every other field is filled by ``aggregate``.
    """

    lines_read: int = 0
    entries_parsed: int = 0
    malformed: int = 0
    blank_lines: int = 0
    entries_in_window: int = 0
    since_iso: str | None = None
    until_iso: str | None = None
    top_paths: list[tuple[str, int]] = field(default_factory=list)
    status_counts: dict[str, int] = field(default_factory=dict)
    status_classes: dict[str, int] = field(default_factory=dict)
    error_num: int = 0
    error_den: int = 0
    error_rate: float = 0.0


def _parse_ts(s: str) -> datetime | None:
    """Parse a ``DD/Mon/YYYY:HH:MM:SS +ZZZZ`` bracket body to an aware instant.

    Month is matched case-sensitively against English abbreviations (so
    ``oct`` is malformed); an out-of-range day/time yields ``None`` too. Never
    depends on the process locale.
    """
    m = _TS_RE.fullmatch(s)
    if m is None:
        return None
    dd, mon, yyyy, hh, mm, ss, off = m.groups()
    month = _MONTHS.get(mon)
    if month is None:
        return None
    oh, om = int(off[1:3]), int(off[3:5])
    if oh > 23 or om > 59:
        return None
    delta = timedelta(hours=oh, minutes=om)
    tz = timezone(delta if off[0] == "+" else -delta)
    try:
        return datetime(int(yyyy), month, int(dd), int(hh), int(mm), int(ss), tzinfo=tz)
    except ValueError:
        return None


def parse_line(line: str) -> Entry | None:
    """Parse one CLF-subset line into an ``Entry``, or ``None`` if malformed.

    Pure: no I/O, no printing, no process state. The request field must hold
    exactly three space-separated tokens (``METHOD PATH HTTP/x.y``); a path
    containing a space or a quote therefore makes the line malformed rather
    than crashing.
    """
    m = _LINE_RE.fullmatch(line)
    if m is None:
        return None
    _host, _ident, _auth, ts_str, request, status_str, _bytes = m.groups()
    ts = _parse_ts(ts_str)
    if ts is None:
        return None
    parts = request.split(" ")
    if len(parts) != 3:
        return None
    method, path, http = parts
    if not _METHOD_RE.fullmatch(method):
        return None
    if not path.startswith("/"):
        return None
    if not _HTTP_RE.fullmatch(http):
        return None
    status = int(status_str)
    if not (100 <= status <= 599):
        return None
    return Entry(ts=ts, path=path, status=status)


def aggregate(
    entries: Iterable[Entry],
    report: Report,
    *,
    top: int,
    since: datetime | None,
    until: datetime | None,
) -> Report:
    """Consume ``entries`` once, accumulating only bounded counters into ``report``.

    Peak memory scales with the number of *distinct* paths and status codes,
    never with the number of entries or bytes read (NFR-1): the input iterable
    is never materialized.
    """
    paths: Counter[str] = Counter()
    statuses: Counter[int] = Counter()
    in_window = 0
    errors = 0
    for e in entries:
        report.entries_parsed += 1
        if since is not None and e.ts < since:
            continue
        if until is not None and e.ts > until:
            continue
        in_window += 1
        paths[e.path] += 1
        statuses[e.status] += 1
        if e.status >= 400:
            errors += 1
    report.entries_in_window = in_window
    # A-2: primary count descending, ties broken by ascending code-point path.
    ordered = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))
    report.top_paths = ordered[:top] if top > 0 else []
    # status_counts: ascending numeric key order, zero-count codes omitted.
    report.status_counts = {f"{code:03d}": statuses[code] for code in sorted(statuses)}
    classes = {f"{k}xx": 0 for k in range(1, 6)}
    for code, n in statuses.items():
        classes[f"{code // 100}xx"] += n
    report.status_classes = classes
    report.error_num = errors
    report.error_den = in_window
    report.error_rate = round(errors / in_window, 6) if in_window else 0.0
    return report


def render_json(report: Report) -> str:
    """Serialize ``report`` to the pinned, versioned 2.1 JSON schema.

    Keys are emitted in the fixed order, ``indent=2``, with a trailing newline;
    the output carries no path, hostname, or run timestamp, so it is
    byte-reproducible and path-independent.
    """
    obj: dict[str, object] = {
        "schema_version": 1,
        "window": {"since": report.since_iso, "until": report.until_iso},
        "totals": {
            "lines_read": report.lines_read,
            "entries_parsed": report.entries_parsed,
            "malformed": report.malformed,
            "entries_in_window": report.entries_in_window,
        },
        "top_paths": [{"path": p, "count": c} for p, c in report.top_paths],
        "status_counts": dict(report.status_counts),
        "status_classes": dict(report.status_classes),
        "error_rate": report.error_rate,
    }
    return json.dumps(obj, indent=2) + "\n"


def render_text(report: Report, *, show_status: bool) -> str:
    """Render ``report`` as the human-readable text layout (design/CLI_UX.md)."""
    since = report.since_iso or "(none)"
    until = report.until_iso or "(none)"
    pct = (report.error_num / report.error_den * 100) if report.error_den else 0.0
    entries_line = (
        f"Entries:    {report.entries_parsed:,} parsed  "
        f"({report.malformed} malformed line(s) skipped)"
    )
    lines: list[str] = [
        entries_line,
        f"Window:     {since} .. {until}",
        f"Error rate: {pct:.2f}%  ({report.error_num}/{report.error_den})",
        "",
        f"Top {len(report.top_paths)} paths",
    ]
    lines.extend(f"  {count:>6}  {path}" for path, count in report.top_paths)
    if show_status:
        lines.append("")
        lines.append("Status codes")
        lines.extend(f"  {code}  {n:>6}" for code, n in report.status_counts.items())
    lines.append("")
    lines.append("Status classes")
    cls = report.status_classes
    lines.append(
        "  " + "   ".join(f"{k} {cls[k]:>6}" for k in ("1xx", "2xx", "3xx", "4xx", "5xx"))
    )
    return "\n".join(lines) + "\n"


def _iter_entries(stream: Iterable[str], report: Report) -> Iterator[Entry]:
    """Yield parsed entries from ``stream`` while accounting for every line.

    The single place that reads the raw stream: it counts every physical line,
    skips (and does not count) blank/whitespace-only lines, and counts -- but
    never yields -- malformed lines. Streaming; never materializes the input.
    """
    for raw in stream:
        report.lines_read += 1
        if raw.strip() == "":
            report.blank_lines += 1
            continue
        entry = parse_line(raw.rstrip("\r\n"))
        if entry is None:
            report.malformed += 1
            continue
        yield entry


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 instant; a naive value is normalized to UTC (A-1)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Summarize a web access log (Common Log Format subset).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_HELP_EPILOG,
    )
    parser.add_argument(
        "--version", action="version", version=f"{PROG} {__version__}"
    )
    parser.add_argument(
        "--top", metavar="N", type=int, default=10,
        help="number of top paths to report (default: 10)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="include the exact status-code breakdown in text output",
    )
    parser.add_argument(
        "--since", metavar="ISO",
        help="only count entries at or after this ISO-8601 instant",
    )
    parser.add_argument(
        "--until", metavar="ISO",
        help="only count entries at or before this ISO-8601 instant",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "file", metavar="FILE", nargs="?",
        help="access log to read; omit or use '-' to read stdin",
    )
    return parser


def _open_stream(path: str | None) -> tuple[io.TextIOBase, bool]:
    """Return ``(text_stream, should_close)`` for ``path`` (``None``/``-`` => stdin).

    Raises ``OSError`` subclasses (caught by the caller) when a named file
    cannot be opened.
    """
    if path is None or path == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"), False
    return open(path, "r", encoding="utf-8", errors="replace"), True


def _run(
    args: argparse.Namespace,
    since: datetime | None,
    until: datetime | None,
    since_iso: str | None,
    until_iso: str | None,
) -> int:
    """Do the work: open input, aggregate, render, write. Returns the exit code."""
    try:
        stream, should_close = _open_stream(args.file)
    except IsADirectoryError:
        print(f"{PROG}: error: {args.file!r} is a directory", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"{PROG}: error: no such file: {args.file!r}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"{PROG}: error: cannot read {args.file!r}: {exc.strerror or exc}", file=sys.stderr)
        return 1

    report = Report(since_iso=since_iso, until_iso=until_iso)
    try:
        aggregate(_iter_entries(stream, report), report, top=args.top, since=since, until=until)
    except OSError as exc:
        print(f"{PROG}: error: I/O error while reading input: {exc}", file=sys.stderr)
        return 1
    finally:
        if should_close:
            stream.close()

    if report.malformed > 0:
        print(
            f"{PROG}: warning: {report.malformed} malformed line(s) skipped",
            file=sys.stderr,
        )

    out = render_json(report) if args.format == "json" else render_text(report, show_status=args.status)
    try:
        sys.stdout.write(out)
        sys.stdout.flush()
    except BrokenPipeError:
        _silence_broken_pipe()
        return 0
    return 0


def _silence_broken_pipe() -> None:
    """Redirect stdout to /dev/null so interpreter shutdown does not traceback."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code (0/1/2)."""
    parser = _build_parser()
    args = parser.parse_args(argv)  # argparse exits 2 on usage errors

    if args.top < 0:
        parser.error(f"--top must be non-negative, got {args.top}")  # exits 2

    try:
        since = _parse_iso(args.since) if args.since is not None else None
    except ValueError:
        parser.error(f"unparseable --since value: {args.since!r}")  # exits 2
    try:
        until = _parse_iso(args.until) if args.until is not None else None
    except ValueError:
        parser.error(f"unparseable --until value: {args.until!r}")  # exits 2

    since_iso = since.isoformat() if since is not None else None
    until_iso = until.isoformat() if until is not None else None

    try:
        return _run(args, since, until, since_iso, until_iso)
    except BrokenPipeError:
        _silence_broken_pipe()
        return 0
    except Exception as exc:  # noqa: BLE001 -- NFR-2: never leak a traceback
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
