# L1 — CSV Parser — EVALUATION (human-readable grader)

The machine-readable grader is `rubric.yaml`; this is its readable companion.
See `framework/GRADING.md` for the contract and `framework/HARNESS.md` for how
to run it. Its grader passes on `graders/references/L1-csv-parser/solution/` (gate PASS, high score)
and fails on both `graders/references/L1-csv-parser/solution_broken/` (acceptance < 1.0) and
`graders/references/L1-csv-parser/solution_csvlib/` (acceptance may be 1.0, but the `import csv`
probe fails the gate) — proving the grader discriminates on *both* dimensions
the scenario cares about: correctness and the stdlib-`csv`-forbidden
constraint.

## How to run it

```
python framework/harness/run_scenario.py \
    --scenario scenarios/L1-csv-parser \
    --solution <produced-solution-dir> \
    [--telemetry telemetry.json] --strategy <name> \
    --out runs/<datetime>/L1/
```

`COR/ROB` come from the tiers below; `EFF/AUT` from `--telemetry`; `QUA` from
the static floor (provisional) + grader agent (final); the gate is
`acceptance_pass == 1.0 and check:L1-CSVLIB-none` — 100% acceptance **and**
no import of the stdlib `csv` module anywhere in the solution
(REQUIREMENTS.md §2.4, §7.3).

## Check registry (denominators: acceptance = 19, adversarial = 11)

| id | tier | axis | criterion | proves | test |
|----|------|------|-----------|--------|------|
| L1-AC01 | acceptance | COR | AC-1 | quoted field, quotes stripped | `test_quoted_field_basic` |
| L1-AC02 | acceptance | COR | AC-1 | doubled quote `""` → literal `"` | `test_doubled_quote_escape` |
| L1-AC03 | acceptance | COR | AC-1 | delimiter inside quotes is data | `test_quoted_field_with_delimiter` |
| L1-AC04 | acceptance | COR | AC-1 | newline inside quotes preserved verbatim | `test_quoted_field_with_newline` |
| L1-AC05 | acceptance | COR | AC-1 | quote inside unquoted field is data | `test_quote_inside_unquoted_field` |
| L1-AC06 | acceptance | COR | AC-1 | fully-empty quoted field `""` → `""` | `test_fully_empty_quoted_field` |
| L1-AC07 | acceptance | COR | AC-2 | `n` delimiters → `n+1` fields | `test_field_count_invariant` |
| L1-AC08 | acceptance | COR, ROB | AC-2 | blank interior line → `[""]`, not skipped | `test_blank_line_yields_empty_field` |
| L1-AC09 | acceptance | COR | AC-2 | trailing separator adds no extra row | `test_trailing_separator_no_extra_row` |
| L1-AC10 | acceptance | COR | AC-3 | CRLF/LF/mixed → identical row counts+values | `test_line_endings_crlf_lf_mixed` |
| L1-AC11 | acceptance | COR, ROB | AC-3 | lone `\r` not before `\n` is ordinary data | `test_lone_cr_is_data` |
| L1-AC12 | acceptance | COR | AC-4 | unicode fields round-trip unchanged | `test_unicode_roundtrip` |
| L1-AC13 | acceptance | COR | AC-4 | non-default `delimiter`/`quotechar` behave identically | `test_custom_delimiter_and_quotechar` |
| L1-AC14 | acceptance | ROB | AC-4 | invalid parameters raise `ValueError` | `test_invalid_parameters_raise` |
| L1-AC15 | acceptance | ROB | AC-5 | §1.6 resolutions applied consistently | `test_ambiguity_consistency_matrix` |
| L1-AC16 | acceptance | ROB | AC-5 | malformed input never silently drops fields/rows | `test_no_silent_dataloss_on_malformed` |
| L1-AC17 | acceptance | EFF | AC-6 | large-input scaling sub-quadratic, within budget | `test_performance_scaling` |
| L1-AC18 | acceptance | QUA | AC-7 | docstring documents all three §1.6 resolutions | `test_docstring_documents_ambiguities` |
| L1-AC19 | acceptance | COR | AC-1 | `hypothesis` round-trip property (generated CSV) | `test_round_trip_hypothesis` |
| L1-ADV01 | adversarial | ROB | — | unterminated quote mid-document → `ValueError` | `test_adv_unterminated_quote_mid_document` |
| L1-ADV02 | adversarial | ROB | — | unterminated quote at end of input → `ValueError` | `test_adv_unterminated_quote_at_end` |
| L1-ADV03 | adversarial | ROB | — | chars after closing quote (`"ab"cd`) → `ValueError` (same policy as ADV01/02) | `test_adv_chars_after_closing_quote` |
| L1-ADV04 | adversarial | ROB | — | lone `quotechar` as entire field → `ValueError` | `test_adv_lone_quotechar_field` |
| L1-ADV05 | adversarial | COR, ROB | — | mixed CRLF/LF with embedded newlines of the opposite kind | `test_adv_mixed_crlf_lf_embedded_newlines` |
| L1-ADV06 | adversarial | COR | — | delimiter *and* newline both inside one quoted field | `test_adv_delimiter_and_newline_in_quotes` |
| L1-ADV07 | adversarial | EFF, ROB | — | 1 MB single field parses correctly and fast | `test_adv_large_field_1mb` |
| L1-ADV08 | adversarial | ROB | — | leading BOM combined with a quoted first field | `test_adv_bom_with_quoted_first_field` |
| L1-ADV09 | adversarial | ROB | — | whitespace-padded unquoted fields, policy applied uniformly | `test_adv_whitespace_padded_unquoted_fields` |
| L1-ADV10 | adversarial | ROB | — | `"\r\n"` as the entire input → `[[""]]` | `test_adv_crlf_only_document` |
| L1-ADV11 | adversarial | ROB | — | last line is a single unterminated quote → `ValueError` | `test_adv_last_line_unterminated_quote` |

`smoke` (visible, not weight-bearing): 5 worked examples in `tests/smoke/`,
verbatim from REQUIREMENTS.md §6.1.

## Gate & probe

`gate: "acceptance_pass == 1.0 and check:L1-CSVLIB-none"`. The probe
`L1-CSVLIB-none` (`rubric.yaml` `probes:`, kind `absent_import`, `module:
csv`) statically scans every `*.py` file in the solution for `import csv` /
`from csv import ...`; a hit fails the probe and therefore the gate,
**regardless of acceptance_pass** (REQUIREMENTS.md §2.4, §7.3). This is
proven by `graders/references/L1-csv-parser/solution_csvlib/`: a behaviorally-correct parser built
on `csv.reader` that passes acceptance but still fails the gate.

## Judge (QUA)

Static floor: `ruff` + `pyright` clean (floor failure ⇒ QUA ≤ 1). Graded 0–4
by the grader agent using the QUA template in `framework/GRADING.md` §6,
judging maintainability/clarity/single-coherent-state-machine only
(correctness is COR). L1 has no `FID` (no product/design surface).
