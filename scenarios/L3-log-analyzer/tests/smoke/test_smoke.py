"""Smoke tier (VISIBLE to the strategy). Not weight-bearing; a fast self-check.

Six worked cases from REQUIREMENTS.md §6.1, run against the real CLI as a
subprocess. Expected aggregates are recomputed by the independent oracle over
the same `sample.log`, so these demonstrate the happy path without revealing
the held-out acceptance matrix.
"""

from pathlib import Path

from _harness import oracle, parse_json, run_cli

_SAMPLE = Path(__file__).resolve().parent / "sample.log"
_LINES = _SAMPLE.read_text(encoding="utf-8").splitlines()


def test_smoke_default_text_run():
    r = run_cli([str(_SAMPLE)])
    assert r.rc == 0
    assert "Top " in r.out and "Status classes" in r.out and "Error rate:" in r.out


def test_smoke_json_full_document():
    r = run_cli(["--format", "json", str(_SAMPLE)])
    assert r.rc == 0
    got = parse_json(r)
    expected = {k: v for k, v in oracle(_LINES).items() if not k.startswith("_")}
    assert got == expected


def test_smoke_top_2():
    r = run_cli(["--format", "json", "--top", "2", str(_SAMPLE)])
    assert r.rc == 0
    got = parse_json(r)
    expected = oracle(_LINES, top=2)
    assert got["top_paths"] == expected["top_paths"]
    assert len(got["top_paths"]) == 2


def test_smoke_time_window():
    # Window covering only the 12:00 group.
    since = "2023-10-10T12:00:00+00:00"
    until = "2023-10-10T12:59:59+00:00"
    r = run_cli(["--format", "json", "--since", since, "--until", until, str(_SAMPLE)])
    assert r.rc == 0
    got = parse_json(r)
    from datetime import datetime

    expected = oracle(
        _LINES,
        since=datetime.fromisoformat(since),
        until=datetime.fromisoformat(until),
        since_iso=since,
        until_iso=until,
    )
    assert got["totals"]["entries_in_window"] == expected["totals"]["entries_in_window"]


def test_smoke_unknown_flag_is_usage_error():
    r = run_cli(["--bogus", str(_SAMPLE)])
    assert r.rc == 2
    assert "usage:" in r.err


def test_smoke_missing_file_is_runtime_error():
    r = run_cli(["/no/such/file.log"])
    assert r.rc == 1
    assert r.err.startswith("loganalyze: error:")
