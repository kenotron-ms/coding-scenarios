# L0 — Roman Numerals — EVALUATION (human-readable grader)

The machine-readable grader is `rubric.yaml`; this is its readable companion.
See `framework/GRADING.md` for the contract and `framework/HARNESS.md` for how to
run it. **This scenario is the proven reference** — its grader passes on
`graders/references/L0-roman-numerals/solution/` (score 99, Converged-Clean) and fails on
`graders/references/L0-roman-numerals/solution_broken/` (gate FAIL, score 0).

## How to run it

```
python framework/harness/run_scenario.py \
    --scenario scenarios/L0-roman-numerals \
    --solution <produced-solution-dir> \
    [--telemetry telemetry.json] --strategy <name> \
    --out runs/<datetime>/L0/
```

`COR/ROB` come from the tiers below; `EFF/AUT` from `--telemetry`; `QUA` from the
static floor (provisional) + grader agent (final); the gate is
`acceptance_pass == 1.0`.

## Check registry (denominators: acceptance = 6, adversarial = 8)

| id | tier | axis | criterion | proves | test |
|----|------|------|-----------|--------|------|
| L0-AC01 | acceptance | COR | AC-1 | round-trip identity over `[1,3999]` | `test_round_trip_sweep` |
| L0-AC02 | acceptance | COR | AC-1 | subtractive forms (IV/IX/XL/XC/CD/CM) | `test_subtractive_forms` |
| L0-AC03 | acceptance | COR | AC-1 | known values both directions | `test_known_values` |
| L0-AC04 | acceptance | ROB | AC-2 | `to_roman` rejects out-of-range / non-int | `test_to_roman_invalid_raises` |
| L0-AC05 | acceptance | ROB | AC-2 | `from_roman` rejects malformed/non-standard | `test_from_roman_invalid_raises` |
| L0-AC06 | acceptance | COR | AC-3 | §1.6 case policy is internally consistent | `test_case_policy_consistent` |
| L0-ADV01 | adversarial | ROB | — | `IIII` rejected | `test_adv_IIII_invalid` |
| L0-ADV02 | adversarial | ROB | — | `IC` rejected | `test_adv_IC_invalid` |
| L0-ADV03 | adversarial | ROB | — | `XM` rejected | `test_adv_XM_invalid` |
| L0-ADV04 | adversarial | ROB | — | `VX` rejected | `test_adv_VX_invalid` |
| L0-ADV05 | adversarial | ROB | — | `MMMM` out of range | `test_adv_MMMM_out_of_range` |
| L0-ADV06 | adversarial | ROB | — | empty/whitespace rejected | `test_adv_empty_whitespace_invalid` |
| L0-ADV07 | adversarial | COR | — | boundary `1` | `test_adv_boundary_1` |
| L0-ADV08 | adversarial | COR | — | boundary `3999` | `test_adv_boundary_3999` |

`smoke` (visible, not weight-bearing): 5 worked examples in `tests/smoke/`.

## Judge (QUA)

Static floor: `ruff` + `pyright` clean (floor failure ⇒ QUA ≤ 1). Graded 0–4 by
the grader agent using the QUA template in `framework/GRADING.md §6`, judging
maintainability/clarity only (correctness is COR). L0 has no `FID` (no
product/design surface).
