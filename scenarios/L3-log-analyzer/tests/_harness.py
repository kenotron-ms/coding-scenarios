"""Shared, harness-owned helpers for the L3 log-analyzer suites.

Never shipped to the strategy under test. Everything here runs the **real
path** -- the built CLI as a subprocess (`python -m loganalyze`) -- and computes
every expected value with an INDEPENDENT implementation (the oracle), so a
solution cannot pass by hardcoding the smoke outputs (REQUIREMENTS.md §6.3/§6.4).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
SOLUTION_DIR = Path(
    os.environ.get("SOLUTION_DIR") or (_TESTS.parent / "reference" / "solution")
).resolve()

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MON_INDEX = {m: i for i, m in enumerate(_MON, start=1)}

# A fixed base instant (UTC) used to build synthetic logs deterministically.
BASE_DT = datetime(2023, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Subprocess runner (the real path)                                           #
# --------------------------------------------------------------------------- #

@dataclass
class Result:
    rc: int
    out: str
    err: str
    out_bytes: bytes
    err_bytes: bytes


def run_cli(
    args: list[str],
    *,
    stdin: str | bytes | None = None,
    seed: int | None = None,
    env_extra: dict[str, str] | None = None,
) -> Result:
    """Run ``python -m loganalyze ARGS`` in SOLUTION_DIR; capture rc/out/err."""
    data = stdin.encode("utf-8") if isinstance(stdin, str) else stdin
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-m", "loganalyze", *args],
        cwd=str(SOLUTION_DIR),
        input=data,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return Result(
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
        proc.stdout,
        proc.stderr,
    )


def run_cli_peak_rss(
    args: list[str], chunk_iter: Iterable[bytes]
) -> tuple[int, bytes, bytes, int]:
    """Run the CLI while streaming ``chunk_iter`` to stdin; sample peak RSS (KiB).

    Reads stdout/stderr in reader threads to avoid pipe deadlock, feeds stdin in
    a writer thread (so the input is never materialized in the test process
    either), and polls ``/proc/<pid>/status`` ``VmHWM`` -- the kernel's
    high-water mark -- for the child's peak resident memory.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "loganalyze", *args],
        cwd=str(SOLUTION_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    peak = {"kb": 0}
    stop = threading.Event()

    def poll() -> None:
        status = f"/proc/{proc.pid}/status"
        while not stop.is_set():
            try:
                with open(status) as fh:
                    for line in fh:
                        if line.startswith("VmHWM:"):
                            kb = int(line.split()[1])
                            peak["kb"] = max(peak["kb"], kb)
                            break
            except OSError:
                pass
            time.sleep(0.02)

    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []

    def reader(pipe, sink: list[bytes]) -> None:
        assert pipe is not None
        for chunk in iter(lambda: pipe.read(65536), b""):
            sink.append(chunk)
        pipe.close()

    def feed() -> None:
        assert proc.stdin is not None
        try:
            for chunk in chunk_iter:
                proc.stdin.write(chunk)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [
        threading.Thread(target=poll, daemon=True),
        threading.Thread(target=reader, args=(proc.stdout, out_chunks), daemon=True),
        threading.Thread(target=reader, args=(proc.stderr, err_chunks), daemon=True),
        threading.Thread(target=feed, daemon=True),
    ]
    for t in threads:
        t.start()
    proc.wait()
    stop.set()
    for t in threads:
        t.join(timeout=2)
    return proc.returncode, b"".join(out_chunks), b"".join(err_chunks), peak["kb"]


# --------------------------------------------------------------------------- #
# Log construction                                                            #
# --------------------------------------------------------------------------- #

def fmt_ts(dt: datetime) -> str:
    """Format ``dt`` as ``DD/Mon/YYYY:HH:MM:SS +ZZZZ`` (locale-independent)."""
    offset = dt.strftime("%z") or "+0000"
    return (
        f"{dt.day:02d}/{_MON[dt.month - 1]}/{dt.year:04d}:"
        f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} {offset}"
    )


def make_line(
    dt: datetime,
    path: str,
    status: int,
    *,
    host: str = "10.0.0.1",
    method: str = "GET",
    nbytes: str = "0",
) -> str:
    """Build one valid CLF-subset line."""
    return f'{host} - - [{fmt_ts(dt)}] "{method} {path} HTTP/1.1" {status} {nbytes}'


def write_log(tmp_path: Path, lines: list[str], name: str = "access.log") -> Path:
    """Write ``lines`` (each newline-terminated) to a file, return its path."""
    p = tmp_path / name
    p.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return p


def as_stdin(lines: list[str]) -> str:
    """Join ``lines`` into newline-terminated stdin text (matches ``write_log``)."""
    return "".join(line + "\n" for line in lines)


def gen_entries(
    seed: int, n: int, *, distinct_paths: int = 12
) -> list[tuple[datetime, str, int]]:
    """Deterministic pseudo-random (ts, path, status) triples for a run.

    Uses a fixed seed so the grader itself is deterministic, but a different
    distribution from the smoke sample (anti-gaming, §6.4). Distinct paths are
    given deliberately unequal frequencies so ordering is unambiguous.
    """
    import random

    rng = random.Random(seed)
    statuses = [200, 200, 200, 200, 301, 404, 404, 500, 200, 403]
    triples: list[tuple[datetime, str, int]] = []
    for i in range(n):
        # skew path frequency: lower-index paths are hotter
        idx = min(int(abs(rng.gauss(0, distinct_paths / 3))), distinct_paths - 1)
        path = f"/p/{idx:02d}"
        status = rng.choice(statuses)
        dt = BASE_DT + timedelta(seconds=i * 7)
        triples.append((dt, path, status))
    return triples


def synth_chunks(
    n_lines: int, *, distinct_paths: int = 40, per_chunk: int = 4000
) -> Iterator[bytes]:
    """Yield a bounded-distinct-path synthetic log as byte chunks (never whole)."""
    buf: list[str] = []
    for i in range(n_lines):
        path = f"/p/{i % distinct_paths}"
        status = 500 if i % 10 == 0 else 200
        buf.append(make_line(BASE_DT, path, status) + "\n")
        if len(buf) >= per_chunk:
            yield "".join(buf).encode("utf-8")
            buf = []
    if buf:
        yield "".join(buf).encode("utf-8")


# --------------------------------------------------------------------------- #
# Independent oracle (never imports the solution)                             #
# --------------------------------------------------------------------------- #

_OL = re.compile(r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "([^"]*)" (\d{3}) (-|\d+)$')
_OTS = re.compile(r"^(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-]\d{4})$")
_OMETHOD = re.compile(r"^[A-Z]+$")
_OHTTP = re.compile(r"^HTTP/\d\.\d$")


def _oracle_parse(line: str) -> tuple[datetime, str, int] | None:
    m = _OL.fullmatch(line)
    if m is None:
        return None
    _host, _ident, _auth, ts_str, request, status_str, _bytes = m.groups()
    tm = _OTS.fullmatch(ts_str)
    if tm is None:
        return None
    dd, mon, yyyy, hh, mm, ss, off = tm.groups()
    if mon not in _MON_INDEX:
        return None
    oh, om = int(off[1:3]), int(off[3:5])
    if oh > 23 or om > 59:
        return None
    delta = timedelta(hours=oh, minutes=om)
    tz = timezone(delta if off[0] == "+" else -delta)
    try:
        dt = datetime(int(yyyy), _MON_INDEX[mon], int(dd), int(hh), int(mm), int(ss), tzinfo=tz)
    except ValueError:
        return None
    parts = request.split(" ")
    if len(parts) != 3:
        return None
    method, path, http = parts
    if not _OMETHOD.fullmatch(method) or not path.startswith("/") or not _OHTTP.fullmatch(http):
        return None
    status = int(status_str)
    if not (100 <= status <= 599):
        return None
    return dt, path, status


def oracle(
    lines: list[str],
    *,
    top: int = 10,
    since: datetime | None = None,
    until: datetime | None = None,
    since_iso: str | None = None,
    until_iso: str | None = None,
) -> dict:
    """Independently recompute the expected report (JSON shape + text extras)."""
    lines_read = blank = malformed = parsed = in_window = errors = 0
    paths: dict[str, int] = {}
    statuses: dict[int, int] = {}
    for raw in lines:
        lines_read += 1
        if raw.strip() == "":
            blank += 1
            continue
        entry = _oracle_parse(raw.rstrip("\r\n"))
        if entry is None:
            malformed += 1
            continue
        parsed += 1
        ts, path, status = entry
        if since is not None and ts < since:
            continue
        if until is not None and ts > until:
            continue
        in_window += 1
        paths[path] = paths.get(path, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1
        if status >= 400:
            errors += 1
    ordered = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))
    top_paths = ordered[:top] if top > 0 else []
    status_counts = {f"{code:03d}": statuses[code] for code in sorted(statuses)}
    classes = {f"{k}xx": 0 for k in range(1, 6)}
    for code, n in statuses.items():
        classes[f"{code // 100}xx"] += n
    error_rate = round(errors / in_window, 6) if in_window else 0.0
    return {
        "schema_version": 1,
        "window": {"since": since_iso, "until": until_iso},
        "totals": {
            "lines_read": lines_read,
            "entries_parsed": parsed,
            "malformed": malformed,
            "entries_in_window": in_window,
        },
        "top_paths": [{"path": p, "count": c} for p, c in top_paths],
        "status_counts": status_counts,
        "status_classes": classes,
        "error_rate": error_rate,
        "_error_num": errors,
        "_error_den": in_window,
        "_blank": blank,
    }


def parse_json(result: Result) -> dict:
    """Parse the CLI's stdout as JSON (fails loudly on non-JSON)."""
    return json.loads(result.out)


# --------------------------------------------------------------------------- #
# Minimal JSON-Schema (draft 2020-12 subset) validator -- dependency-free     #
# --------------------------------------------------------------------------- #

def _type_ok(inst: object, types: list[str]) -> bool:
    for t in types:
        if t == "object" and isinstance(inst, dict):
            return True
        if t == "array" and isinstance(inst, list):
            return True
        if t == "string" and isinstance(inst, str):
            return True
        if t == "integer" and isinstance(inst, int) and not isinstance(inst, bool):
            return True
        if t == "number" and isinstance(inst, (int, float)) and not isinstance(inst, bool):
            return True
        if t == "null" and inst is None:
            return True
        if t == "boolean" and isinstance(inst, bool):
            return True
    return False


def validate_schema(instance: object, schema: dict, path: str = "$") -> list[str]:
    """Validate ``instance`` against ``schema`` (supports the keywords we use)."""
    errors: list[str] = []

    def check(inst: object, sch: dict, loc: str) -> None:
        if "const" in sch and inst != sch["const"]:
            errors.append(f"{loc}: expected const {sch['const']!r}, got {inst!r}")
        if "enum" in sch and inst not in sch["enum"]:
            errors.append(f"{loc}: {inst!r} not in enum {sch['enum']!r}")
        if "type" in sch:
            types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
            if not _type_ok(inst, types):
                errors.append(f"{loc}: expected type {sch['type']!r}, got {type(inst).__name__}")
                return
        if isinstance(inst, dict):
            props = sch.get("properties", {})
            for req in sch.get("required", []):
                if req not in inst:
                    errors.append(f"{loc}: missing required property {req!r}")
            additional = sch.get("additionalProperties", True)
            patterns = sch.get("patternProperties", {})
            for key, val in inst.items():
                if key in props:
                    check(val, props[key], f"{loc}.{key}")
                    continue
                matched = False
                for pat, subschema in patterns.items():
                    if re.fullmatch(pat, key):
                        check(val, subschema, f"{loc}.{key}")
                        matched = True
                        break
                if not matched and additional is False:
                    errors.append(f"{loc}: additional property {key!r} not allowed")
        if isinstance(inst, list) and "items" in sch:
            for idx, item in enumerate(inst):
                check(item, sch["items"], f"{loc}[{idx}]")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool):
            if "minimum" in sch and inst < sch["minimum"]:
                errors.append(f"{loc}: {inst} < minimum {sch['minimum']}")
            if "maximum" in sch and inst > sch["maximum"]:
                errors.append(f"{loc}: {inst} > maximum {sch['maximum']}")

    check(instance, schema, path)
    return errors


def load_declared_schema() -> dict:
    """Load the solution's own declared JSON Schema (design/report.schema.json)."""
    return json.loads((SOLUTION_DIR / "design" / "report.schema.json").read_text())
