# Harness & Automation

How anyone runs a scenario against a strategy and gets a **trustworthy,
comparable** `score.json`. There are two layers, kept separate on purpose:

1. **Grade a solution** — given a produced solution in a workspace, run the
   tiers, compute axes, apply the gate, emit `score.json`. This is the
   deterministic-plus-judge grader (`framework/harness/run_scenario.py`).
2. **Drive the strategy under test** — actually run the coding agent/harness so
   it *produces* a solution, in isolation, capturing telemetry
   (iterations, tokens, interventions). This is where you plug in the strategy
   you are evaluating.

Keeping them separate means the grader is identical no matter whose strategy
produced the solution — which is what makes two strategies comparable.

## 1. Grading a solution (the reference runner)

`framework/harness/run_scenario.py` is the reference grader. It:

1. reads `scenarios/L*/manifest.yaml` + `rubric.yaml`;
2. runs each `verify` tier command (smoke visible; acceptance + adversarial held
   out), emitting JUnit XML;
3. parses results into per-check pass/fail against the **check registry**
   (`GRADING.md §1`), computing `acceptance_pass`, `p0_pass`,
   `adversarial_pass`, `regression_pass`, and the denominators;
4. runs the `static_floor` toolchain (QUA hard floor);
5. computes the **automated axes** `COR/ROB/REG/EFF/AUT` (EFF/AUT from a supplied
   `telemetry.json`; absent ⇒ `null`);
6. evaluates the **gate expression** (`GRADING.md §4`);
7. leaves `QUA`/`FID` as `null` with a `judge_pending` flag, to be filled by the
   grader agent (§3);
8. writes `score.json` to the run output dir (§4).

Usage:
```
python framework/harness/run_scenario.py \
    --scenario scenarios/L0-roman-numerals \
    --solution <path-to-produced-solution> \
    [--telemetry <telemetry.json>] \
    --out runs/<datetime>/L0/
```

The runner is intentionally small and supports the deterministic entrypoint kinds
directly (`python-module`, `cli`). For `http-service`, `web-app`, and
`desktop-app`, it shells to the scenario's declared `verify` commands (which own
the server/browser/ssh fixtures) — the runner never re-implements those.

## 2. Driving the strategy under test

To produce a solution to grade, run the coding agent/harness in **isolation**,
one clean workspace per run, and capture telemetry. Recommended: the
**`amplifier_evaluation` library** (this session's `evaluation` bundle) with a
**Digital Twin Universe (DTU) profile per variant** — it gives you isolated
environments, captured stdout/session files, and a place to diff variants. See
`@evaluation:context/workflow/harness-automation.md` and
`@evaluation:examples/EXAMPLE_INDEX.md` (example 01 is an A/B two-variant shape;
04 is a multi-task two-variant report — the closest templates for comparing
coding strategies here).

The strategy under test is handed **only** the scenario `SPEC.md` + the `smoke`
tests (its visible workspace). It must not see `acceptance`/`adversarial`.
Telemetry to capture per run → `telemetry.json`:
```json
{"iterations": 9, "wall_clock_s": 410, "tokens": 61000, "usd": 0.74,
 "failed_runs_before_pass": 3,
 "interventions": [{"tag": "clarify", "severity": "low-med", "note": "case policy"}],
 "regressions_introduced": 0, "oscillations": 0, "dead_ends": 0}
```
`interventions` is a tagged list so `AUT` scores the worst tag
(`CONVERGENCE_METRICS §3`). This file is the sole source for `EFF`/`AUT`.

## 3. Lean into agents for the fuzzy parts

Per evaluation philosophy, prefer agent judgment over brittle code wherever the
strategy could legitimately have done things differently:

- **Extraction / location.** Do not assume a fixed file layout. Locating the
  produced solution and its artifacts is best done by an extractor agent (base:
  `amplifier_evaluation` extractor) rather than hardcoded paths — a strategy may
  put the solution anywhere in its workspace.
- **Grading `QUA`/`FID`.** Scored by a **grader agent** using the rubric prompts
  in `GRADING.md §6`. Never score maintainability or design-fidelity with regexes.
- **A/B fuzzy comparisons.** If you ever want "which strategy's code is nicer"
  rather than an absolute score, use a comparison agent over two solutions and
  run multiple trials to reduce noise.

## 4. Output discipline (do NOT commit run output)

The eval **definitions** — `SPEC.md`, `manifest.yaml`, `rubric.yaml`,
`EVALUATION.md`, `tests/`, `reference/` — **are** source-controlled: they are the
benchmark.

**Run outputs are NOT.** `score.json`, captured stdout, session/transcript files,
and produced solutions can contain provider keys, prompts, responses, and
absolute paths. They go to a sortable, gitignored location:
```
runs/<sortable-datetime>/L<n>/score.json      # in-repo, gitignored (convenience)
# or, project-external per the evaluation convention:
.amplifier/evaluation/coding-scenarios/<sortable-datetime>/
```
`.gitignore` excludes `runs/` and any `.eval-out/`. Confirm the location with the
user if a project convention differs.

## 5. Running well

- **Parallelism.** Independent runs (variants × scenarios) run in parallel;
  start with ≥4 at a time.
- **Comparability.** Fix the scenario version (commit hash) across a comparison;
  never tune a strategy against the same scenarios repeatedly (overfitting) —
  the `adversarial` tier and held-back scenarios exist to catch that.
- **Sanity check every grader before trusting it.** For each scenario, the
  grader must **pass on the reference solution** and **fail on a broken mutant**.
  If it does not discriminate, the grader — not the strategy — is wrong. Fix it
  before running real strategies. (L0 ships both; see `scenarios/L0-*/reference/`.)
- **Ladder profile.** Aggregate per-scenario `score.json` into the strategy's
  ladder profile (`RUBRIC_FRAMEWORK.md §6`): the highest rung reached at/above
  its pass threshold, and the shape of the fall-off.

## 6. Dashboards

Run trees are easier to read as a dashboard. Options: delegate to
`stories:evaluation-visualizer` with the run path; run a project `visualize.py`
if present; or generate a self-contained HTML dashboard directly from a run tree.
Always offer it; never commit it into the repo (it is run output).
