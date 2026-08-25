# Goal — lane `l4-grader`: build and PROVE the L4 template-engine runnable grader

## Outcome
A fully-runnable, PROVEN grader for scenario **L4 (template-engine, a multi-module
library)**, mirroring the L0/L1/L2 pattern, such that `framework/harness/run_scenario.py`
gives **gate PASS** on the correct reference and **gate FAIL** on a broken mutant.

## Exit
Complete when **either** every item below reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items
ending FAIL or BLOCKED are residuals, not failures of the goal.
Terminal states: `PASS` / `FAIL-<reason>` / `BLOCKED-<reason>` / `PENDING-HUMAN-<reason>`.

## Items
1. **Read (read-only)**: `scenarios/L1-csv-parser/` (all), `scenarios/L0-roman-numerals/`
   (all), `framework/GRADING.md`, `framework/HARNESS.md`, `framework/harness/run_scenario.py`,
   and `scenarios/L4-template-engine/REQUIREMENTS.md` (§4.3/§6/§7).
2. **Build** `scenarios/L4-template-engine/` (top-level import name: `template_engine`):
   - `SPEC.md` — prompt: a small template library with `Template(source, *,
     autoescape=False).render(context: dict) -> str` and an `Environment` (loader/filters);
     syntax `{{ expr }}` with dotted/index access, `{% if %}/{% elif %}/{% else %}/{% endif %}`,
     `{% for x in items %}...{% endfor %}` with loop vars, `{% include "name" %}`, filters
     `{{ v | upper }}`; exceptions `TemplateSyntaxError(msg, line, col)` and
     `TemplateRuntimeError`; compile-once/render-many; **stdlib only, no eval/exec** of
     template expressions; autoescape must block `<script>` injection. Document §1.6.
   - `manifest.yaml` — `entrypoint.kind: python-module`, `target: template_engine`;
     budgets from GRADING §9 (wall_clock_s 3600, iterations_soft 14, iterations_hard 35,
     token_budget 350000, interventions 0); `regression.strategy: per-group-diff`;
     `gate: "acceptance_pass >= 0.95"`; `static_floor.python: [ruff, pyright]`.
   - `rubric.yaml` — `weights {COR:30, ROB:15, EFF:14, AUT:12, QUA:13, REG:8, FID:8}`
     (sum 100), `pass_threshold: 70`, gate, `denominators` = ACTUAL test counts,
     `static_floor`, `judge: {QUA, FID}`, and a full `checks:` registry.
   - `EVALUATION.md`, `tests/conftest.py`, `tests/{smoke,acceptance,adversarial}/`,
     `reference/solution/` (a CORRECT tokenizer→parser→renderer library that imports as
     `template_engine`), `reference/solution_broken/` (a mutant, e.g. interpolation-only
     with no block tags, or unescaped output → fails acceptance).
   - Cover interpolation/nested access, if/elif/else, for + loop vars, includes/partials,
     filters, autoescape blocking an injected `<script>`, strict-vs-lenient undefined,
     and position-accurate `TemplateSyntaxError`. Adversarial: malformed/unclosed tags,
     undefined vars, deep nesting, include cycles, injection attempts, filter errors.
     A `hypothesis` property test (e.g. plain text with no tags round-trips unchanged)
     is welcome.
3. **Prove it** — run the runner to `/tmp` only:
   `python3 framework/harness/run_scenario.py --scenario scenarios/L4-template-engine --solution scenarios/L4-template-engine/reference/solution --strategy ref --out /tmp/L4-ref`
   (expect gate PASS, **no denominator-drift warnings**) and the same on
   `reference/solution_broken` → `/tmp/L4-broken` (expect gate FAIL). Iterate until both
   behave; fix drift by making `denominators` equal the real test counts.
4. **Commit** the new `scenarios/L4-template-engine/` files to your branch. Do NOT commit
   run output, `__pycache__`, `.pytest_cache`, `.hypothesis`, `*.xml`, or `score.json`.

## Ground rules
- **Work ONLY in this worktree**: `/home/ken/workspace/coding-scenarios.gb/l4-grader`,
  branch `gb/l4-grader`. Do NOT touch the main checkout or sibling worktrees.
- **OWN only** `scenarios/L4-template-engine/`. Do NOT edit any `framework/` file,
  `README.md`, other scenarios, or `run_scenario.py`. If you need a change outside your
  files, record it as a `residual` and stop at that boundary.
- **Commit early and often**; do NOT push to origin. **NEVER merge to main.**
- **Host**: python3, pytest, pyyaml, hypothesis (`pip install --user hypothesis` if
  missing), pyright; ruff may be absent. Solutions stdlib-only.
- **Time bound**: honor the wall-clock; exceeding it is terminal `BUDGET`.
- **DONE.json** (gitignored) in the worktree root as your **final act**:
  `{lane:"l4-grader", session_id:<your own>, verdict:<COMPLETE|BLOCKED|PARTIAL>, branch,
  head:<sha>, pushed:false, items:[...], residuals:[...], pending_human:[...], suite:"..."}`.

## KNOWN
- Copy `scenarios/L1-csv-parser/` structure verbatim. L4 is a python-module import (like
  L0–L2), so the runner needs no changes. Gate is `>= 0.95`. Denominators must equal real
  test counts (drift warning = ambiguous grader).
