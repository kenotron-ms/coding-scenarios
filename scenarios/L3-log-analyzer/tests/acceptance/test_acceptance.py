"""Acceptance tier (HELD OUT). Denominator = 36 (see rubric.yaml). Defines "working".

Every tier runs the REAL path -- the built CLI as a subprocess -- and every
expected value is recomputed by the independent oracle (REQUIREMENTS.md §6.3).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from _harness import (
    SOLUTION_DIR,
    BASE_DT,
    load_declared_schema,
    make_line,
    oracle,
    parse_json,
    run_cli,
    run_cli_peak_rss,
    validate_schema,
    write_log,
    as_stdin,
)

_JSON_KEY_ORDER = [
    "schema_version", "window", "totals",
    "top_paths", "status_counts", "status_classes", "error_rate",
]


def _assert_report_equal(got: dict, expected: dict) -> None:
    """Field-for-field equality, treating error_rate as a float within tolerance."""
    exp = {k: v for k, v in expected.items() if not k.startswith("_")}
    assert got["error_rate"] == pytest.approx(exp["error_rate"], abs=1e-9)
    got2 = {k: v for k, v in got.items() if k != "error_rate"}
    exp2 = {k: v for k, v in exp.items() if k != "error_rate"}
    assert got2 == exp2


def _standard_lines() -> list[str]:
    """15 entries, five paths with unambiguous descending frequency, mixed statuses."""
    specs = [("/a", 5), ("/b", 4), ("/c", 3), ("/d", 2), ("/e", 1)]
    statuses = [200, 200, 301, 404, 500]
    lines: list[str] = []
    t = 0
    for path, count in specs:
        for _ in range(count):
            lines.append(make_line(BASE_DT + timedelta(seconds=t * 5), path, statuses[t % 5]))
            t += 1
    return lines


# --------------------------------------------------------------------------- #
# AC-1 -- input sources (FR-1, FR-2)                                          #
# --------------------------------------------------------------------------- #

def test_ac01_input_sources_equivalent_text(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    a = run_cli([str(log)])
    b = run_cli(["-"], stdin=as_stdin(lines))
    c = run_cli([], stdin=as_stdin(lines))
    assert a.rc == b.rc == c.rc == 0
    assert a.out == b.out == c.out


def test_ac01b_input_sources_equivalent_json(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    a = run_cli(["--format", "json", str(log)])
    b = run_cli(["--format", "json", "-"], stdin=as_stdin(lines))
    c = run_cli(["--format", "json"], stdin=as_stdin(lines))
    assert a.out == b.out == c.out
    _assert_report_equal(parse_json(a), oracle(lines))


# --------------------------------------------------------------------------- #
# AC-2 -- malformed & degenerate inputs (FR-3, FR-13, NFR-2)                  #
# --------------------------------------------------------------------------- #

def test_ac02_mixed_malformed_counted_on_stderr(tmp_path):
    lines = _standard_lines() + ["garbage one", "also not valid", "10/oct/2023 bad"]
    log = write_log(tmp_path, lines)
    r = run_cli(["--format", "json", str(log)])
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["malformed"] == 3
    assert r.err == "loganalyze: warning: 3 malformed line(s) skipped\n"
    # lines_read invariant: parsed + malformed + blank == lines_read
    t = got["totals"]
    assert t["entries_parsed"] + t["malformed"] + oracle(lines)["_blank"] == t["lines_read"]


def test_ac02b_all_malformed_zero_report(tmp_path):
    lines = ["nope", "still nope", "definitely not a log line"]
    log = write_log(tmp_path, lines)
    r = run_cli(["--format", "json", str(log)])
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["entries_parsed"] == 0
    assert got["totals"]["entries_in_window"] == 0
    assert got["top_paths"] == []
    assert got["status_counts"] == {}
    assert got["status_classes"] == {"1xx": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
    assert got["error_rate"] == 0.0
    assert r.err == "loganalyze: warning: 3 malformed line(s) skipped\n"


def test_ac02c_empty_input_zero_report():
    r = run_cli(["--format", "json"], stdin="")
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["lines_read"] == 0
    assert got["top_paths"] == []
    assert r.err == ""


def test_ac02d_blank_only_input_not_malformed():
    r = run_cli(["--format", "json"], stdin="\n   \n\t\n\n")
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["malformed"] == 0
    assert got["totals"]["entries_parsed"] == 0
    assert got["totals"]["lines_read"] == 4
    assert r.err == ""


def test_ac02e_stderr_clean_when_no_malformed(tmp_path):
    log = write_log(tmp_path, _standard_lines())
    r = run_cli([str(log)])
    assert r.rc == 0
    assert r.err == ""


# --------------------------------------------------------------------------- #
# AC-3 -- top-N paths (FR-4, FR-8)                                            #
# --------------------------------------------------------------------------- #

def test_ac03_top_default_10(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    assert got["top_paths"] == oracle(lines, top=10)["top_paths"]


def test_ac03b_top_1(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", "--top", "1", str(log)]))
    assert got["top_paths"] == oracle(lines, top=1)["top_paths"]
    assert len(got["top_paths"]) == 1


def test_ac03c_top_3(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", "--top", "3", str(log)]))
    assert got["top_paths"] == oracle(lines, top=3)["top_paths"]
    assert len(got["top_paths"]) == 3


def test_ac03d_top_more_than_distinct(tmp_path):
    lines = _standard_lines()  # 5 distinct paths
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", "--top", "25", str(log)]))
    assert got["top_paths"] == oracle(lines, top=25)["top_paths"]
    assert len(got["top_paths"]) == 5


def test_ac03e_tiebreak_ascending_codepoint(tmp_path):
    # /mid appears 3x; /alpha and /zeta each 2x -> ties break ascending.
    lines = (
        [make_line(BASE_DT + timedelta(seconds=i), "/mid", 200) for i in range(3)]
        + [make_line(BASE_DT + timedelta(seconds=10 + i), "/zeta", 200) for i in range(2)]
        + [make_line(BASE_DT + timedelta(seconds=20 + i), "/alpha", 200) for i in range(2)]
    )
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    assert got["top_paths"] == oracle(lines)["top_paths"]
    paths = [p["path"] for p in got["top_paths"]]
    assert paths == ["/mid", "/alpha", "/zeta"]


# --------------------------------------------------------------------------- #
# AC-4 -- status breakdown & error rate (FR-5, FR-6)                          #
# --------------------------------------------------------------------------- #

def test_ac04_status_counts_and_classes(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    exp = oracle(lines)
    assert got["status_counts"] == exp["status_counts"]
    assert got["status_classes"] == exp["status_classes"]


def test_ac04b_status_flag_controls_text_only(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    with_flag = run_cli(["--status", str(log)])
    without = run_cli([str(log)])
    assert "Status codes" in with_flag.out
    assert "Status codes" not in without.out
    # JSON always carries both regardless of --status.
    j_no = parse_json(run_cli(["--format", "json", str(log)]))
    j_yes = parse_json(run_cli(["--format", "json", "--status", str(log)]))
    assert j_no["status_counts"] == j_yes["status_counts"] != {}


def test_ac04c_error_rate_matches_oracle(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    exp = oracle(lines)
    assert got["error_rate"] == pytest.approx(exp["error_rate"], abs=1e-9)
    # text renders the same rate as a percentage with num/den.
    text = run_cli([str(log)]).out
    assert f"({exp['_error_num']}/{exp['_error_den']})" in text


def test_ac04d_error_rate_zero_denominator(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    # Window in the far future -> zero entries -> error_rate 0.0, exit 0.
    r = run_cli(["--format", "json", "--since", "2099-01-01T00:00:00+00:00", str(log)])
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["entries_in_window"] == 0
    assert got["error_rate"] == 0.0


# --------------------------------------------------------------------------- #
# AC-5 -- time-window filtering (FR-7)                                        #
# --------------------------------------------------------------------------- #

def _window_lines() -> tuple[list[str], list[datetime]]:
    times = [BASE_DT + timedelta(seconds=10 * i) for i in range(5)]
    paths = ["/a", "/a", "/b", "/c", "/a"]
    statuses = [200, 200, 500, 404, 200]
    lines = [make_line(t, p, s) for t, p, s in zip(times, paths, statuses)]
    return lines, times


def test_ac05_since_only(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    since_iso = times[2].isoformat()
    r = run_cli(["--format", "json", "--since", since_iso, str(log)])
    got = parse_json(r)
    exp = oracle(lines, since=times[2], since_iso=since_iso)
    assert got["totals"]["entries_in_window"] == exp["totals"]["entries_in_window"] == 3
    assert got["window"] == {"since": since_iso, "until": None}


def test_ac05b_until_only(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    until_iso = times[2].isoformat()
    r = run_cli(["--format", "json", "--until", until_iso, str(log)])
    got = parse_json(r)
    exp = oracle(lines, until=times[2], until_iso=until_iso)
    assert got["totals"]["entries_in_window"] == exp["totals"]["entries_in_window"] == 3
    assert got["window"] == {"since": None, "until": until_iso}


def test_ac05c_both_inclusive_boundaries(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    since_iso, until_iso = times[1].isoformat(), times[3].isoformat()
    r = run_cli(["--format", "json", "--since", since_iso, "--until", until_iso, str(log)])
    got = parse_json(r)
    exp = oracle(lines, since=times[1], until=times[3], since_iso=since_iso, until_iso=until_iso)
    # inclusive at both ends: entries at index 1,2,3 -> 3
    assert got["totals"]["entries_in_window"] == exp["totals"]["entries_in_window"] == 3
    _assert_report_equal(got, exp)


def test_ac05d_inverted_window_zero_entries(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    since_iso, until_iso = times[3].isoformat(), times[1].isoformat()
    r = run_cli(["--format", "json", "--since", since_iso, "--until", until_iso, str(log)])
    assert r.rc == 0
    got = parse_json(r)
    assert got["totals"]["entries_in_window"] == 0
    assert got["top_paths"] == []


def test_ac05e_offset_bearing_absolute_instant(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    # Same instant as times[1] (UTC) expressed in a -07:00 offset.
    shifted = times[1].astimezone(timezone(timedelta(hours=-7)))
    since_iso = shifted.isoformat()
    r = run_cli(["--format", "json", "--since", since_iso, str(log)])
    got = parse_json(r)
    exp = oracle(lines, since=times[1], since_iso=since_iso)
    assert got["totals"]["entries_in_window"] == exp["totals"]["entries_in_window"]
    assert got["window"]["since"] == since_iso  # normalized, offset preserved


def test_ac05f_naive_since_is_utc(tmp_path):
    lines, times = _window_lines()
    log = write_log(tmp_path, lines)
    naive = "2023-10-10T12:00:20"  # == times[2] as UTC
    r = run_cli(["--format", "json", "--since", naive, str(log)])
    got = parse_json(r)
    utc_dt = datetime.fromisoformat(naive).replace(tzinfo=timezone.utc)
    exp = oracle(lines, since=utc_dt, since_iso=utc_dt.isoformat())
    assert got["totals"]["entries_in_window"] == exp["totals"]["entries_in_window"] == 3
    assert got["window"]["since"] == "2023-10-10T12:00:20+00:00"


# --------------------------------------------------------------------------- #
# AC-6 -- JSON schema (FR-9, §2.1)                                            #
# --------------------------------------------------------------------------- #

def test_ac06_json_matches_pinned_fields(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", str(log)]))
    _assert_report_equal(got, oracle(lines))


def test_ac06b_json_key_order_exact(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    out = run_cli(["--format", "json", str(log)]).out
    obj = json.loads(out)
    assert list(obj.keys()) == _JSON_KEY_ORDER
    assert list(obj["window"].keys()) == ["since", "until"]
    assert list(obj["totals"].keys()) == [
        "lines_read", "entries_parsed", "malformed", "entries_in_window"
    ]
    assert list(obj["status_classes"].keys()) == ["1xx", "2xx", "3xx", "4xx", "5xx"]
    assert out.endswith("}\n")  # indent=2 with trailing newline


def test_ac06c_json_validates_declared_schema(tmp_path):
    lines = _standard_lines() + ["a malformed line"]
    log = write_log(tmp_path, lines)
    got = parse_json(run_cli(["--format", "json", "--status", str(log)]))
    errors = validate_schema(got, load_declared_schema())
    assert errors == []


# --------------------------------------------------------------------------- #
# AC-7 -- exit codes & stream purity (FR-10, FR-12)                           #
# --------------------------------------------------------------------------- #

def test_ac07_exit_codes(tmp_path):
    log = write_log(tmp_path, _standard_lines())
    assert run_cli([str(log)]).rc == 0
    assert run_cli(["--bogus", str(log)]).rc == 2
    assert run_cli(["/no/such/file.log"]).rc == 1


def test_ac07b_stdout_purity_json_pipeable(tmp_path):
    lines = _standard_lines() + ["garbage", "more garbage"]
    log = write_log(tmp_path, lines)
    r = run_cli(["--format", "json", str(log)])
    # stdout is valid JSON even though a malformed warning was emitted...
    json.loads(r.out)
    assert "warning" in r.err and "warning" not in r.out


def test_ac07c_stdout_purity_text(tmp_path):
    lines = _standard_lines() + ["garbage"]
    log = write_log(tmp_path, lines)
    r = run_cli([str(log)])
    assert "warning:" not in r.out
    assert "error:" not in r.out
    assert "warning:" in r.err


# --------------------------------------------------------------------------- #
# AC-8 -- help & version (FR-11, NFR-6)                                       #
# --------------------------------------------------------------------------- #

def test_ac08_help_contains_exit_table_and_resolutions():
    r = run_cli(["--help"])
    assert r.rc == 0
    low = r.out.lower()
    assert "exit codes" in low
    assert "0" in r.out and "1" in r.out and "2" in r.out
    assert "utc" in low  # A-1 resolution
    assert "ascending" in low  # A-2 resolution
    assert "--top 0" in r.out  # A-3 resolution


def test_ac08b_version_exit0():
    r = run_cli(["--version"])
    assert r.rc == 0
    assert r.out.startswith("loganalyze ")
    assert any(ch.isdigit() for ch in r.out)


# --------------------------------------------------------------------------- #
# AC-9 -- bounded memory (NFR-1)                                              #
# --------------------------------------------------------------------------- #

def test_ac09_bounded_memory_streaming():
    from _harness import synth_chunks

    rc_s, out_s, _e, peak_s = run_cli_peak_rss(["--format", "json"], synth_chunks(120_000))
    rc_l, out_l, _e2, peak_l = run_cli_peak_rss(["--format", "json"], synth_chunks(600_000))
    assert rc_s == 0 and rc_l == 0
    small = json.loads(out_s.decode())
    large = json.loads(out_l.decode())
    assert small["totals"]["entries_parsed"] == 120_000
    assert large["totals"]["entries_parsed"] == 600_000
    # 5x more input must not blow up memory: ratio bounded, absolute < 200 MiB.
    assert peak_s > 0 and peak_l > 0
    assert peak_l < peak_s * 1.5, f"peak RSS grew with input: {peak_s} -> {peak_l} KiB"
    assert peak_l < 200 * 1024, f"peak RSS {peak_l} KiB exceeds 200 MiB"


# --------------------------------------------------------------------------- #
# AC-10 -- determinism across PYTHONHASHSEED (FR-8)                           #
# --------------------------------------------------------------------------- #

def test_ac10_determinism_json_hashseed(tmp_path):
    lines = _standard_lines()
    log = write_log(tmp_path, lines)
    outs = {run_cli(["--format", "json", str(log)], seed=s).out_bytes for s in (0, 1, 2, 12345)}
    assert len(outs) == 1


def test_ac10b_determinism_text_tieheavy_hashseed(tmp_path):
    # Many equal-count paths stress ordering stability under hash randomization.
    lines = [make_line(BASE_DT + timedelta(seconds=i), f"/p{i % 20:02d}", 200) for i in range(200)]
    log = write_log(tmp_path, lines)
    outs = {run_cli(["--status", str(log)], seed=s).out_bytes for s in (0, 1, 7, 99, 424242)}
    assert len(outs) == 1


# --------------------------------------------------------------------------- #
# AC-11 -- design artifacts & self-golden text (NFR-4, §5.4)                  #
# --------------------------------------------------------------------------- #

def test_ac11_design_artifacts_present():
    design = SOLUTION_DIR / "design"
    assert (design / "CLI_UX.md").is_file()
    assert (design / "report.schema.json").is_file()
    assert (design / "USER_STORIES.md").is_file()


def test_ac11b_text_matches_cli_ux_sample(tmp_path):
    # The exact 7-line sample documented in design/CLI_UX.md §5.
    sample = [
        make_line(BASE_DT, "/index.html", 200, host="10.0.0.1"),
        make_line(BASE_DT + timedelta(seconds=4), "/index.html", 200, host="10.0.0.2"),
        make_line(BASE_DT + timedelta(seconds=25), "/index.html", 200, host="10.0.0.3"),
        make_line(BASE_DT + timedelta(seconds=36), "/api/v1/items", 200, host="10.0.0.4"),
        make_line(BASE_DT + timedelta(seconds=44), "/api/v1/items", 500, host="10.0.0.5", method="POST"),
        make_line(BASE_DT + timedelta(seconds=55), "/static/app.js", 404, host="10.0.0.6"),
        make_line(BASE_DT + timedelta(seconds=84), "/static/app.js", 200, host="10.0.0.7"),
    ]
    log = write_log(tmp_path, sample)
    out = run_cli(["--top", "3", "--status", str(log)]).out
    cli_ux = (SOLUTION_DIR / "design" / "CLI_UX.md").read_text(encoding="utf-8")
    assert out.strip() in cli_ux, "text output does not match the committed CLI_UX.md sample"


def test_ac11c_user_stories_traceability():
    text = (SOLUTION_DIR / "design" / "USER_STORIES.md").read_text(encoding="utf-8")
    for n in range(1, 9):
        assert f"US-{n}" in text
    assert "FR-1" in text and "FR-7" in text
