# Goal — lane `l3-grader`: build and PROVE the L3 log-analyzer runnable grader

## Outcome
A fully-runnable, PROVEN grader for scenario **L3 (log-analyzer, a CLI tool)**,
mirroring the L0/L1/L2 pattern exactly, such that `framework/harness/run_scenario.py`
gives **gate PASS** on the correct reference solution and **gate FAIL** on a broken
mutant.

## Exit
Complete when **either** every item below reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items
ending FAIL or BLOCKED are residuals, not failures of the goal.
Terminal states: `PASS` / `FAIL-<reason>` / `BLOCKED-<reason>` / `PENDING-HUMAN-<reason>`.

## Items
1. **Read (read-only)** the proven exemplar + contract: `scenarios/L1-csv-parser/` (all),
   `scenarios/L0-roman-numerals/` (all), `framework/GRADING.md`, `framework/HARNESS.md`,
   `framework/harness/run_scenario.py`, and `scenarios/L3-log-analyzer/REQUIREMENTS.md`
   (§4.3 criteria, §6 tiers, §7 rubric).
2. **Build** `scenarios/L3-log-analyzer/` (CLI/module name: `loganalyze`):
   - `SPEC.md` — prompt: a CLI `loganalyze [OPTIONS] [FILE]` reading stdin or FILE;
     options `--top N` (default 10), `--status`, `--since`/`--until` (ISO), `--format
     text|json` (default text), `--help`, `--version`; **exit codes 0 ok / 1 runtime /
     2 usage**; input = Common Log Format subset
     `HOST - - [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD PATH HTTP/x.y" STATUS BYTES`;
     stdlib only; stream input (bounded memory). Document the §1.6 ambiguities.
   - `manifest.yaml` — `entrypoint.kind: cli`; budgets from GRADING §9
     (wall_clock_s 1800, iterations_soft 10, iterations_hard 25, token_budget 200000,
     interventions 0); `regression.strategy: rerun-matrix`;
     `gate: "acceptance_pass >= 0.95"`; `static_floor.python: [ruff, pyright]`.
   - `rubric.yaml` — `weights {COR:35, ROB:18, EFF:12, AUT:10, QUA:12, REG:5, FID:8}`
     (sum 100), `pass_threshold: 72`, gate (same), `denominators` = your ACTUAL
     acceptance/adversarial test counts, `static_floor`, `judge: {QUA, FID}`, and a
     full `checks:` registry (one row per test → id/criterion/tier/axis).
   - `EVALUATION.md`, `tests/conftest.py`, `tests/{smoke,acceptance,adversarial}/`,
     `reference/solution/loganalyze.py` (correct), `reference/solution_broken/loganalyze.py`
     (mutant that mis-parses or emits wrong aggregates → fails acceptance).
   - **Tests invoke the REAL CLI via subprocess** (golden-file / exit-code /
     stdout+stderr assertions), locating it via `SOLUTION_DIR` (like L0's conftest).
     Acceptance gate is `>= 0.95`, adversarial feeds COR/ROB. Include empty input,
     all-malformed input, `--top 0`, unknown flag (exit 2), missing file (exit 1),
     time-window boundaries, and a bounded-memory check.
3. **Prove it** — run the runner to `/tmp` only:
   `python3 framework/harness/run_scenario.py --scenario scenarios/L3-log-analyzer --solution scenarios/L3-log-analyzer/reference/solution --strategy ref --out /tmp/L3-ref`
   (expect gate PASS, **no denominator-drift warnings**) and the same on
   `reference/solution_broken` → `/tmp/L3-broken` (expect gate FAIL). Iterate until both
   behave; fix drift by making `denominators` equal the real test counts.
4. **Commit** the new `scenarios/L3-log-analyzer/` files to your branch. Do NOT commit
   run output, `__pycache__`, `.pytest_cache`, `.hypothesis`, `*.xml`, or `score.json`.

## Ground rules
- **Work ONLY in this worktree**: `/home/ken/workspace/coding-scenarios.gb/l3-grader`,
  branch `gb/l3-grader`. Do NOT touch the main checkout or sibling worktrees.
- **OWN only** `scenarios/L3-log-analyzer/`. Do NOT edit any `framework/` file, `README.md`,
  other scenarios, or `run_scenario.py`. **If you believe the runner needs a change to
  run a `cli` scenario, DO NOT edit it** — it is a shared seam owned by no lane. Instead
  make your tests self-contained (subprocess the CLI so they run under the existing
  `pytest tests/<tier>`) and record the exact runner change you wanted as a `residual`
  in DONE.json.
- **Commit early and often** to your branch. Do NOT push to origin (the orchestrator
  merges locally from the shared object store).
- **NEVER merge to main.** The orchestrator merges.
- **Host**: python3, pytest, pyyaml, hypothesis (`pip install --user hypothesis` if
  missing), pyright present; ruff may be absent (fine). Solutions are stdlib-only.
- **Time bound**: honor the wall-clock; exceeding it is terminal `BUDGET` — commit what
  you have, do not skip a commit to rush.
- **DONE.json** is already gitignored. Write it in the worktree root as your **final act**:
  `{lane:"l3-grader", session_id:<your own>, verdict:<COMPLETE|BLOCKED|PARTIAL>, branch,
  head:<sha>, pushed:false, items:[...], residuals:[...], pending_human:[...],
  suite:"<exact runner commands + observed PASS/FAIL>"}`.

## KNOWN
- Copy the structure of `scenarios/L1-csv-parser/` verbatim (it is proven). Runner
  summary lines 2–4 print acceptance/adversarial/gate + score + band. L3's gate is
  `>= 0.95` (not 1.0). Denominators must equal real test counts or you get a
  drift warning (= an ambiguous grader).
