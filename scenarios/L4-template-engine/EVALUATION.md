# L4 — Template Engine — EVALUATION (human-readable grader)

The machine-readable grader is `rubric.yaml`; this is its readable companion.
See `framework/GRADING.md` for the contract and `framework/HARNESS.md` for how to
run it. The grader passes on `graders/references/L4-template-engine/solution/` (gate PASS: 100% acceptance)
and fails on `graders/references/L4-template-engine/solution_broken/` (an interpolation-only mutant whose
acceptance falls far below the 0.95 floor) — proving it discriminates on the
dimension the scenario cares about: a real tokenizer→parser→renderer engine, not
a regex substituter (HARNESS.md §5).

## How to run it

```
python framework/harness/run_scenario.py \
    --scenario scenarios/L4-template-engine \
    --solution graders/references/L4-template-engine/solution \
    [--telemetry telemetry.json] --strategy <name> \
    --out runs/<datetime>/L4/
```

`COR/ROB` come from the tiers below; `EFF/AUT` from `--telemetry`; `QUA` from the
static floor (`ruff`+`pyright`, provisional) + grader agent (final); `REG` from
the `per-group-diff` strategy; `FID` from the `design/` artifacts (grader agent).
The gate is `acceptance_pass >= 0.95` (GRADING.md §4, L3–L4).

## Check registry (denominators: acceptance = 47, adversarial = 26)

Each id maps 1:1 to a test function (weight 1), so the per-tier denominator is
the row count. `smoke` (7 examples in `tests/smoke/`, visible) is **not**
weight-bearing.

### Acceptance (held out) — 47 checks

| id | group | axis | criterion | proves | test |
|----|-------|------|-----------|--------|------|
| L4-AC01 | G1 | COR | AC-1 | interpolation, quotes/text verbatim | `test_interpolation_simple` |
| L4-AC02 | G1 | COR | AC-1 | dotted attribute/key chain | `test_interpolation_dotted` |
| L4-AC03 | G1 | COR | AC-1 | `[i]` / `['k']` index access | `test_interpolation_index_access` |
| L4-AC04 | G1 | COR | AC-1 | deep mixed `a.b[1].c` chain | `test_interpolation_deep_chain` |
| L4-AC05 | G1 | COR | AC-1 | mapping key resolved before attribute | `test_mapping_before_attribute` |
| L4-AC06 | G1 | COR | AC-1 | non-string values `str()`-ified | `test_non_string_values_stringified` |
| L4-AC07 | G1 | COR | AC-1 | text-only and empty templates | `test_text_only_and_empty_template` |
| L4-AC08 | G2 | COR | AC-2 | all six comparison operators | `test_if_comparison_operators` |
| L4-AC09 | G2 | COR | AC-2 | `and`/`or`/`not` precedence | `test_if_boolean_ops_and_precedence` |
| L4-AC10 | G2 | COR | AC-2 | `if`/`elif`/`elif`/`else` selection | `test_if_elif_else_chain` |
| L4-AC11 | G2 | COR | AC-2 | nested conditionals | `test_if_nested` |
| L4-AC12 | G2 | COR | AC-2 | truthiness, no-`else` fallthrough | `test_if_truthiness_and_no_else` |
| L4-AC13 | G3 | COR | AC-3 | all five `loop` fields | `test_for_basic_and_all_loop_fields` |
| L4-AC14 | G3 | COR | AC-3 | nested loops shadow correctly | `test_for_nested_shadowing` |
| L4-AC15 | G3 | COR | AC-3 | outer binding restored at `endfor` | `test_for_scope_restore` |
| L4-AC16 | G3 | COR, ROB | AC-3 | empty iterable is not an error | `test_for_empty_iterable` |
| L4-AC17 | G3 | COR | AC-3 | iterate dicts (keys) and strings | `test_for_over_dict_and_string` |
| L4-AC18 | G4 | COR | AC-4 | mapping loader include | `test_include_mapping_loader` |
| L4-AC19 | G4 | COR | AC-4 | callable loader include | `test_include_callable_loader` |
| L4-AC20 | G4 | COR | AC-4 | include inside a loop sees loop vars | `test_include_inside_loop_sees_loop_vars` |
| L4-AC21 | G4 | ROB | AC-4 | missing name / no loader → runtime error | `test_include_missing_and_no_loader` |
| L4-AC22 | G5 | COR | AC-5 | `upper`/`lower`/`length` built-ins | `test_builtin_filters` |
| L4-AC23 | G5 | COR | AC-5 | `default` incl. falsy passthrough | `test_default_filter_semantics` |
| L4-AC24 | G5 | COR | AC-5 | filter chaining + literal args | `test_filter_chaining_and_literal_args` |
| L4-AC25 | G5 | COR | AC-5 | user filter + shadow a built-in | `test_user_filter_and_shadowing` |
| L4-AC26 | G5 | ROB | AC-5 | unknown/raising filter → runtime error | `test_unknown_and_raising_filter` |
| L4-AC27 | G6 | COR, ROB | AC-6 | autoescape escapes all five chars | `test_autoescape_on_escapes_all_five` |
| L4-AC28 | G6 | COR | AC-6 | off doesn't escape; literal never escaped | `test_autoescape_off_and_literal_never_escaped` |
| L4-AC29 | G6 | COR | AC-6 | explicit-over-inherited + env inheritance | `test_autoescape_precedence_and_env_inheritance` |
| L4-AC30 | G7 | ROB | AC-7 | strict raises, names the path | `test_strict_undefined_raises_named_path` |
| L4-AC31 | G7 | COR | AC-7 | lenient no-raise; `default` intercepts | `test_lenient_undefined_and_default_intercepts` |
| L4-AC32 | G8 | ROB | AC-9 | unterminated tag position | `test_position_unterminated_tag` |
| L4-AC33 | G8 | ROB | AC-9 | unclosed block points at opener | `test_position_unclosed_block_points_opener` |
| L4-AC34 | G8 | ROB | AC-9 | mismatched/stray closer position | `test_position_mismatched_and_stray_closer` |
| L4-AC35 | G8 | ROB | AC-9 | multi-line + tab column counting | `test_position_multiline_and_tabs` |
| L4-AC36 | G9 | COR | AC-10 | `__all__` + exception hierarchy | `test_public_names_and_exception_hierarchy` |
| L4-AC37 | G9 | COR | AC-10 | keyword-only params + pinned defaults | `test_signatures_keyword_only` |
| L4-AC38 | G9 | COR, ROB | AC-10 | `render(None)==render({})`; no mutation | `test_render_none_equiv_and_context_not_mutated` |
| L4-AC39 | G10 | COR | AC-8 | render independence across calls | `test_render_independence_across_calls` |
| L4-AC40 | G10 | COR | AC-8 | environment compiles once per name | `test_environment_caches_compiled_template` |
| L4-AC41 | G10 | EFF | AC-8 | linear output under time budget | `test_linear_output_under_budget` |
| L4-AC42 | G11 | COR, ROB | AC-7 | A-1 lenient uniform across positions | `test_a1_lenient_uniform_across_positions` |
| L4-AC43 | G11 | COR | AC-6 | A-3 explicit + inherited autoescape | `test_a3_autoescape_explicit_and_inherited` |
| L4-AC44 | Gsec | QUA | AC-11 | no `eval`/`exec`/`compile`/`__import__` | `test_no_eval_exec_in_source` |
| L4-AC45 | Gsec | ROB | AC-11 | sandbox refuses `_`/dunder access | `test_sandbox_refuses_underscore_access` |
| L4-AC46 | G1 | COR | AC-1 | plain text round-trips (hypothesis) | `test_plaintext_roundtrips_unchanged` |
| L4-AC47 | G8 | ROB | AC-9 | only `TemplateError` crosses the API | `test_error_taxonomy_no_foreign_exception` |

### Adversarial (hidden, run once) — 26 checks

| id | axis | proves | test |
|----|------|--------|------|
| L4-ADV01 | ROB | `{{ unclosed` → syntax error | `test_adv_unterminated_interpolation` |
| L4-ADV02 | ROB | `{% if %}` no condition | `test_adv_if_without_condition` |
| L4-ADV03 | ROB | stray `{% endfor %}` | `test_adv_stray_endfor` |
| L4-ADV04 | ROB | `{% if %}…{% endfor %}` mismatch position | `test_adv_if_endfor_mismatch` |
| L4-ADV05 | ROB | unknown tag `{% forr %}` | `test_adv_unknown_tag` |
| L4-ADV06 | ROB | `{% else %}` outside `if` | `test_adv_else_outside_if` |
| L4-ADV07 | ROB | `{{ }}` empty expression | `test_adv_empty_expression` |
| L4-ADV08 | ROB | `{{ | upper }}` leading pipe | `test_adv_leading_pipe` |
| L4-ADV09 | ROB | `{{ x | }}` trailing pipe | `test_adv_trailing_pipe` |
| L4-ADV10 | ROB | unclosed-at-EOF points at opener | `test_adv_unclosed_block_at_eof_points_opener` |
| L4-ADV11 | ROB | CRLF source exact line/col | `test_adv_crlf_positions_exact` |
| L4-ADV12 | ROB | tab-indented exact column | `test_adv_tab_indented_position` |
| L4-ADV13 | ROB | unknown filter → runtime error | `test_adv_unknown_filter` |
| L4-ADV14 | ROB | raising filter → runtime error | `test_adv_filter_that_raises` |
| L4-ADV15 | ROB | `default` missing required arg | `test_adv_default_missing_argument` |
| L4-ADV16 | COR, ROB | `length` on int errors, on `""` is 0 | `test_adv_length_on_non_sized` |
| L4-ADV17 | ROB | non-iterable loop target | `test_adv_for_non_iterable_target` |
| L4-ADV18 | ROB | `a.b.c` with `a.b is None` no bare error | `test_adv_none_in_the_middle_of_chain` |
| L4-ADV19 | COR, ROB | four-deep nested loops shadow | `test_adv_four_deep_nested_loops_with_shadowing` |
| L4-ADV20 | ROB | include of a missing name | `test_adv_include_missing_name` |
| L4-ADV21 | ROB | self-include cycle → runtime error | `test_adv_self_include_cycle` |
| L4-ADV22 | ROB | A→B→A cycle → runtime error | `test_adv_indirect_include_cycle` |
| L4-ADV23 | ROB | `__class__`/`__dict__`/mro sandbox probes | `test_adv_sandbox_dunder_probes` |
| L4-ADV24 | COR, ROB | `<script>` injected, autoescape on/off | `test_adv_injection_autoescape_on_and_off` |
| L4-ADV25 | ROB | undefined in both strictness modes | `test_adv_undefined_in_both_modes` |
| L4-ADV26 | EFF, ROB | 100×100 nested loop stays linear | `test_adv_large_nested_loop_is_linear` |

## Gate

`gate: "acceptance_pass >= 0.95"` (GRADING.md §4, L3–L4). The adversarial tier
feeds `COR`/`ROB` but never the gate. There is no gate-authority probe at this
rung; the `eval`/`exec` prohibition is enforced by acceptance check `L4-AC44`
(a static AST scan of the solution source) and by the `static_floor`.

## Judge (QUA, FID)

Static floor: `ruff` + `pyright` clean (floor failure ⇒ QUA ≤ 1). `QUA` is then
graded 0–4 by the grader agent (GRADING.md §6) on the §2.2 one-way composition,
docstrings, and complexity — not correctness. `FID` (live at L4) grades the
required `design/` artifacts (PRD, USER_STORIES, API_REFERENCE, GRAMMAR,
EXAMPLES) for existence, internal consistency, and agreement with the shipped
code. The reference runner leaves `QUA`/`FID` as `judge_pending`.
