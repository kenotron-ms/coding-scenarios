"""Adversarial tier (HIDDEN, run once). Denominator = 22. Feeds COR/ROB; never the gate.

Covers REQUIREMENTS.md §6.1 adversarial inputs: degenerate inputs, exit-code
edges, window boundaries, hostile lines, and stream discipline. Every case runs
the real CLI as a subprocess.
"""

import json
import subprocess
import sys
from datetime import timedelta

from _harness import (
    SOLUTION_DIR,
    BASE_DT,
    make_line,
    oracle,
    parse_json,
    run_cli,
    run_cli_peak_rss,
    synth_chunks,
    write_log,
)


def test_adv01_empty_input():
    r = run_cli(["--format", "json"], stdin="")
    assert r.rc == 0
    assert parse_json(r)["totals"]["lines_read"] == 0


def test_adv02_all_malformed_input(tmp_path):
    log = write_log(tmp_path, ["x", "y", "z", "not a line"])
    r = run_cli(["--format", "json", str(log)])
    assert r.rc == 0
    assert parse_json(r)["totals"]["malformed"] == 4


def test_adv03_top_zero_is_none(tmp_path):
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/p{i % 3}", 200) for i in range(9)]
    log = write_log(tmp_path, lines)
    r = run_cli(["--format", "json", "--top", "0", str(log)])
    assert r.rc == 0
    got = parse_json(r)
    assert got["top_paths"] == []
    # text and json of the same invocation must agree (A-3).
    text = run_cli(["--top", "0", str(log)]).out
    assert "Top 0 paths" in text


def test_adv04_top_negative_is_usage_error(tmp_path):
    log = write_log(tmp_path, [make_line(BASE_DT, "/a", 200)])
    r = run_cli(["--top", "-1", str(log)])
    assert r.rc == 2


def test_adv05_unknown_flag_is_usage_error(tmp_path):
    log = write_log(tmp_path, [make_line(BASE_DT, "/a", 200)])
    r = run_cli(["--frobnicate", str(log)])
    assert r.rc == 2
    assert "usage:" in r.err


def test_adv06_format_xml_is_usage_error(tmp_path):
    log = write_log(tmp_path, [make_line(BASE_DT, "/a", 200)])
    r = run_cli(["--format", "xml", str(log)])
    assert r.rc == 2


def test_adv07_missing_file_is_runtime_error():
    r = run_cli(["/does/not/exist.log"])
    assert r.rc == 1
    assert r.err.startswith("loganalyze: error:")


def test_adv08_directory_as_file_is_runtime_error(tmp_path):
    r = run_cli([str(tmp_path)])  # a directory
    assert r.rc == 1
    assert r.err.startswith("loganalyze: error:")


def test_adv09_boundary_timestamps_included(tmp_path):
    times = [BASE_DT + timedelta(seconds=10 * i) for i in range(5)]
    lines = [make_line(t, "/a", 200) for t in times]
    log = write_log(tmp_path, lines)
    since_iso, until_iso = times[1].isoformat(), times[3].isoformat()
    got = parse_json(run_cli(["--format", "json", "--since", since_iso, "--until", until_iso, str(log)]))
    # entries exactly at since and until are inclusive -> indices 1,2,3
    assert got["totals"]["entries_in_window"] == 3


def test_adv10_one_second_outside_excluded(tmp_path):
    times = [BASE_DT + timedelta(seconds=10 * i) for i in range(5)]
    lines = [make_line(t, "/a", 200) for t in times]
    log = write_log(tmp_path, lines)
    since = (times[1] + timedelta(seconds=1)).isoformat()
    until = (times[3] - timedelta(seconds=1)).isoformat()
    got = parse_json(run_cli(["--format", "json", "--since", since, "--until", until, str(log)]))
    # only index 2 survives (indices 1 and 3 are one second outside)
    assert got["totals"]["entries_in_window"] == 1


def test_adv11_unparseable_since_is_usage_error(tmp_path):
    log = write_log(tmp_path, [make_line(BASE_DT, "/a", 200)])
    r = run_cli(["--since", "yesterday", str(log)])
    assert r.rc == 2
    assert "yesterday" in r.err


def test_adv12_huge_input_streams_without_timeout():
    rc, out, _err, peak = run_cli_peak_rss(["--format", "json"], synth_chunks(300_000))
    assert rc == 0
    assert json.loads(out.decode())["totals"]["entries_parsed"] == 300_000
    assert peak < 200 * 1024


def test_adv13_crlf_line_endings(tmp_path):
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/p{i % 2}", 200 if i % 2 else 500) for i in range(6)]
    p = tmp_path / "crlf.log"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    got = parse_json(run_cli(["--format", "json", str(p)]))
    exp = oracle(lines)
    assert got["totals"]["entries_parsed"] == exp["totals"]["entries_parsed"] == 6
    assert got["top_paths"] == exp["top_paths"]


def test_adv14_invalid_utf8_bytes_survivable():
    raw = b'1.1.1.1 - - [10/Oct/2023:12:00:00 +0000] "GET /caf\xe9 HTTP/1.1" 200 5\n'
    r = run_cli(["--format", "json"], stdin=raw)
    assert r.rc == 0
    assert "Traceback" not in r.err
    # the undecodable byte is replaced, not fatal: the line still parses.
    assert parse_json(r)["totals"]["lines_read"] == 1


def test_adv15_one_megabyte_single_line():
    raw = b"x" * (1024 * 1024) + b"\n"
    r = run_cli(["--format", "json"], stdin=raw)
    assert r.rc == 0
    assert "Traceback" not in r.err
    assert parse_json(r)["totals"]["malformed"] == 1


def test_adv16_path_with_space_or_quote_is_malformed(tmp_path):
    space = '1.1.1.1 - - [10/Oct/2023:12:00:00 +0000] "GET /a b HTTP/1.1" 200 5'
    quote = '1.1.1.1 - - [10/Oct/2023:12:00:00 +0000] "GET /a"b HTTP/1.1" 200 5'
    log = write_log(tmp_path, [space, quote])
    r = run_cli(["--format", "json", str(log)])
    assert r.rc == 0
    assert parse_json(r)["totals"]["malformed"] == 2


def test_adv17_status_boundaries_100_and_599(tmp_path):
    lines = [make_line(BASE_DT, "/a", 100), make_line(BASE_DT + timedelta(seconds=1), "/b", 599)]
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    assert got["totals"]["entries_parsed"] == 2
    assert got["status_classes"]["1xx"] == 1
    assert got["status_classes"]["5xx"] == 1


def test_adv18_bytes_dash_is_valid(tmp_path):
    log = write_log(tmp_path, [make_line(BASE_DT, "/a", 200, nbytes="-")])
    got = parse_json(run_cli(["--format", "json", str(log)]))
    assert got["totals"]["entries_parsed"] == 1


def test_adv19_lowercase_month_is_malformed(tmp_path):
    line = '1.1.1.1 - - [10/oct/2023:12:00:00 +0000] "GET /a HTTP/1.1" 200 5'
    log = write_log(tmp_path, [line])
    got = parse_json(run_cli(["--format", "json", str(log)]))
    assert got["totals"]["malformed"] == 1
    assert got["totals"]["entries_parsed"] == 0


def test_adv20_repeated_top_last_wins(tmp_path):
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/p{i % 6}", 200) for i in range(18)]
    log = write_log(tmp_path, lines)
    r = run_cli(["--format", "json", "--top", "3", "--top", "5", str(log)])
    assert r.rc == 0
    assert len(parse_json(r)["top_paths"]) == 5


def test_adv21_large_distinct_path_set(tmp_path):
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/u/{i}", 200) for i in range(3000)]
    lines += [make_line(BASE_DT + timedelta(seconds=4000 + i), "/hot", 200) for i in range(50)]
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    exp = oracle(lines, top=10)
    assert got["top_paths"] == exp["top_paths"]
    assert got["top_paths"][0] == {"path": "/hot", "count": 50}


def test_adv22_broken_pipe_no_traceback(tmp_path):
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/p{i % 4}", 200) for i in range(40)]
    log = write_log(tmp_path, lines)
    proc = subprocess.Popen(
        [sys.executable, "-m", "loganalyze", "--status", str(log)],
        cwd=str(SOLUTION_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    proc.stdout.readline()      # consume one line, like `| head -1`
    proc.stdout.close()         # close the read end -> child sees a broken pipe
    _out, err = proc.communicate()
    assert b"Traceback" not in err
    assert proc.returncode in (0, 1)
