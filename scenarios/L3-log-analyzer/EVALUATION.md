# L3 -- Log Analyzer -- EVALUATION (human-readable grader)

The machine-readable grader is `rubric.yaml`; this is its readable companion.
See `framework/GRADING.md` for the contract and `framework/HARNESS.md` for how
to run it. Its grader **passes on `reference/solution/`** (gate PASS, high score)
and **fails on `reference/solution_broken/`** (acceptance < 0.95, gate FAIL) --
proving the grader discriminates a correct CLI from one that emits wrong
aggregates.

Unlike L0-L2 (`kind: python-module`), L3 is the first `kind: cli` rung: every
tier runs the **built CLI as a subprocess** (`python -m loganalyze`) located via
`SOLUTION_DIR`, and asserts on exit codes, stdout, and stderr separately. No
tier imports the solution (REQUIREMENTS.md §6.3).

## How to run it

```
python framework/harness/run_scenario.py \
    --scenario scenarios/L3-log-analyzer \
    --solution scenarios/L3-log-analyzer/reference/solution \
    [--telemetry telemetry.json] --strategy <name> \
    --out runs/<datetime>/L3/
```

`COR/ROB` come from the tiers below; `EFF/AUT` from `--telemetry`; `QUA` from the
static floor (provisional) + grader agent (final); `FID` from the grader agent
over `design/`. The gate is `acceptance_pass >= 0.95` (REQUIREMENTS.md §7.3):
the acceptance matrix is large, so a single cosmetic assertion is not fatal, but
the reference clears it fully (36/36).

## Denominators

- **acceptance = 36** (weight-bearing; the gate is computed over these)
- **adversarial = 22** (feeds `COR`/`ROB`; never the gate)
- **smoke = 6** (visible, not weight-bearing)

These equal the real test-function counts, so the runner emits **no denominator
drift warning**. Each registry id maps 1:1 to a test function (see `rubric.yaml`
`checks:` and the tables below).

## Acceptance registry (denominator = 36)

| id | criterion | axis | proves | test |
|----|-----------|------|--------|------|
| L3-AC01 | AC-1 | COR | `FILE` / `-` / stdin give identical text | `test_ac01_input_sources_equivalent_text` |
| L3-AC02 | AC-1 | COR | same three sources give identical json | `test_ac01b_input_sources_equivalent_json` |
| L3-AC03 | AC-2 | COR,ROB | malformed counted once on stderr; lines_read invariant | `test_ac02_mixed_malformed_counted_on_stderr` |
| L3-AC04 | AC-2 | ROB | all-malformed -> zero report, exit 0 | `test_ac02b_all_malformed_zero_report` |
| L3-AC05 | AC-2 | ROB | empty input -> zero report, clean stderr | `test_ac02c_empty_input_zero_report` |
| L3-AC06 | AC-2 | ROB | blank-only input not counted malformed | `test_ac02d_blank_only_input_not_malformed` |
| L3-AC07 | AC-2 | COR | stderr empty when nothing is wrong | `test_ac02e_stderr_clean_when_no_malformed` |
| L3-AC08 | AC-3 | COR | default top-10 matches oracle | `test_ac03_top_default_10` |
| L3-AC09 | AC-3 | COR | `--top 1` truncates correctly | `test_ac03b_top_1` |
| L3-AC10 | AC-3 | COR | `--top 3` truncates correctly | `test_ac03c_top_3` |
| L3-AC11 | AC-3 | COR | `--top 25` > distinct -> all paths | `test_ac03d_top_more_than_distinct` |
| L3-AC12 | AC-3 | COR | ties break ascending code point | `test_ac03e_tiebreak_ascending_codepoint` |
| L3-AC13 | AC-4 | COR | status histogram + class rollup correct | `test_ac04_status_counts_and_classes` |
| L3-AC14 | AC-4 | COR,FID | `--status` affects text only; json always both | `test_ac04b_status_flag_controls_text_only` |
| L3-AC15 | AC-4 | COR | error rate matches oracle; text shows num/den | `test_ac04c_error_rate_matches_oracle` |
| L3-AC16 | AC-4 | ROB | zero-denominator error rate is 0.0 | `test_ac04d_error_rate_zero_denominator` |
| L3-AC17 | AC-5 | COR | `--since` only | `test_ac05_since_only` |
| L3-AC18 | AC-5 | COR | `--until` only | `test_ac05b_until_only` |
| L3-AC19 | AC-5 | COR | both bounds inclusive | `test_ac05c_both_inclusive_boundaries` |
| L3-AC20 | AC-5 | ROB | inverted window -> zero entries, exit 0 | `test_ac05d_inverted_window_zero_entries` |
| L3-AC21 | AC-5 | COR | offset-bearing arg compared as absolute instant | `test_ac05e_offset_bearing_absolute_instant` |
| L3-AC22 | AC-5 | COR | naive arg read as UTC, normalized in json | `test_ac05f_naive_since_is_utc` |
| L3-AC23 | AC-6 | COR,FID | json matches pinned fields | `test_ac06_json_matches_pinned_fields` |
| L3-AC24 | AC-6 | COR,FID | json key order + trailing newline | `test_ac06b_json_key_order_exact` |
| L3-AC25 | AC-6 | FID | json validates against declared schema | `test_ac06c_json_validates_declared_schema` |
| L3-AC26 | AC-7 | COR,ROB | exit codes 0/1/2 per table | `test_ac07_exit_codes` |
| L3-AC27 | AC-7 | COR | json stdout stays pure with a warning | `test_ac07b_stdout_purity_json_pipeable` |
| L3-AC28 | AC-7 | COR | text diagnostics on stderr only | `test_ac07c_stdout_purity_text` |
| L3-AC29 | AC-8 | FID | `--help` carries exit table + resolutions | `test_ac08_help_contains_exit_table_and_resolutions` |
| L3-AC30 | AC-8 | FID | `--version` exits 0 | `test_ac08b_version_exit0` |
| L3-AC31 | AC-9 | EFF | bounded memory: 5x input, RSS ratio < 1.5 | `test_ac09_bounded_memory_streaming` |
| L3-AC32 | AC-10 | REG | json byte-identical across hash seeds | `test_ac10_determinism_json_hashseed` |
| L3-AC33 | AC-10 | REG | tie-heavy text byte-identical across hash seeds | `test_ac10b_determinism_text_tieheavy_hashseed` |
| L3-AC34 | AC-11 | FID | design artifacts present | `test_ac11_design_artifacts_present` |
| L3-AC35 | AC-11 | FID | text matches committed CLI_UX.md sample | `test_ac11b_text_matches_cli_ux_sample` |
| L3-AC36 | AC-11 | FID | USER_STORIES US-1..US-8 traced to FR-n | `test_ac11c_user_stories_traceability` |

## Adversarial registry (denominator = 22; feeds COR/ROB, never the gate)

Empty / all-malformed inputs; `--top 0` (none) and `--top -1` (exit 2); unknown
flag and `--format xml` (exit 2); missing file and directory (exit 1); window
boundary inclusion and one-second exclusion; unparseable `--since` (exit 2); a
huge streamed input (memory + no timeout); CRLF endings; invalid-UTF-8 bytes; a
1 MB single line; a path with a space or quote (malformed, not a crash); status
`100`/`599`; `BYTES` of `-`; a lowercase month (malformed); `--top 3 --top 5`
(last wins); a large distinct-path set; and `| head -1` (no traceback). See
`rubric.yaml` `checks:` ids `L3-ADV01..L3-ADV22`.

## Gate & discrimination

`gate: "acceptance_pass >= 0.95"`. The broken mutant
(`reference/solution_broken/`) is byte-for-byte the reference except it orders
`top_paths` **ascending** and counts `status > 400` for the error rate. It still
runs and prints a plausible report, but fails every ordering/JSON-golden/error-
rate assertion -- driving `acceptance_pass` well below 0.95 and the gate to
FAIL. This is the sanity check `HARNESS.md` §5 requires.

## Judge (QUA, FID)

Static floor: `ruff` + `pyright` clean (floor failure => QUA <= 1; `ruff` may be
absent on the host, in which case the floor is `pyright` alone). QUA graded 0-4
by the grader agent (maintainability/clarity/separation of parse/aggregate/
render/CLI concerns). FID graded 0-4 over `design/` (CLI_UX design-diff, help
completeness, JSON schema fidelity, user-story traceability).
