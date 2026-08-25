# Grading Contract

This document turns the prose of each scenario's §6 (Verification) and §7 (Rubric)
into a **machine- and agent-checkable grader**. It is **authoritative for grading
mechanics**; `VERIFICATION_CONTRACT.md` remains authoritative for test tiers and
the run protocol, and `RUBRIC_FRAMEWORK.md` for axis meaning and weights.

It exists to close three defects found in review:

1. **Undefined denominator.** Gate floors are "fractions of acceptance
   assertions," but scenarios described *families* of tests, not counted
   assertions. Two graders could score the same run differently. → **The check
   registry (§1) makes every weight-bearing assertion an explicit, counted
   check.**
2. **Gate can't be a single float.** Five distinct gate *shapes* exist across the
   ladder (plain floor; floor + named non-negotiable; P0-criteria + overall;
   per-sprint + cumulative regression; P0 + perf + security + overall). → **The
   gate expression grammar (§4) expresses all of them.**
3. **Flat `score.json` can't represent L7.** → **The nested score schema + L7
   per-sprint variant (§7).**

---

## 1. The check registry (resolves the denominator)

Each scenario ships an `EVALUATION.md` (human-readable) and a `rubric.yaml`
(machine-readable) whose core is a **check registry**: every weight-bearing
acceptance/adversarial assertion is a row with a stable id. **The denominator for
any tier or group is the sum of `weight` over its registered checks — nothing is
counted that is not registered.** A `criterion` is a named group of checks; this
is the explicit criteria↔assertion mapping the gates need.

Row schema (one per assertion):

```yaml
- id: L6-AC09-a            # stable, unique within scenario
  criterion: AC-9          # the acceptance criterion this rolls up to
  traces: [FR-22, INV-4]   # requirements this proves (from REQUIREMENTS §4.3)
  tier: acceptance         # smoke | acceptance | adversarial | regression
  priority: P0             # P0 | P1  (gate membership; omit => P1)
  group: drag-persistence  # regression-attribution bucket (optional)
  axis: [COR, REG]         # which rubric axes this check feeds
  weight: 1                # denominator contribution (default 1)
  gate_authority: false    # true => this single check can fail the gate alone
  advisory: false          # true => excluded from gate denominator, reported only
  retry: none              # none | flaky-guard:N  (see §8)
```

Rules:
- **Every scenario declares its counts.** `rubric.yaml` must state, per tier, the
  number of registered checks (the denominator). A floor of "≥95%" is meaningless
  until the denominator is fixed; declaring it is mandatory.
- `smoke` checks are visible to the agent and are **not** weight-bearing (they do
  not enter any denominator or axis); they exist for the agent's own loop.
- `adversarial` checks feed `COR`/`ROB` but **never** the gate (§4).
- `advisory: true` checks (e.g., a latency assertion that could not be calibrated
  under load) are reported but excluded from denominators.

---

## 2. `rubric.yaml` shape

```yaml
scenario: L6-kanban-app
weights: {COR: 22, ROB: 12, EFF: 15, AUT: 15, QUA: 12, REG: 12, FID: 12}  # sum 100
pass_threshold: 68
denominators:                       # explicit; the fix for the defect
  acceptance: 41
  adversarial: 18
  p0: 12                            # count of P0 acceptance checks
gate: >                             # gate expression (see §4)
  p0_pass == 1.0 and acceptance_pass >= 0.90
static_floor:                       # QUA hard floor (see §6)
  python: [ruff, pyright]
  ts: [eslint, "tsc --noEmit"]
judge:                              # AI-graded axes (see §6)
  QUA: {agent: grader, rubric: rubric/qua.md}
  FID: {agent: grader, rubric: rubric/fid.md, inputs: [design/hifi/]}
checks:                             # the registry (§1) — inline or in EVALUATION.md
  - {id: L6-AC01-a, criterion: AC-1, tier: acceptance, priority: P0, axis: [COR], weight: 1}
  # ...
```

---

## 3. Axis → score computation

All axes score **0–4** against the scenario's §7.2 anchors; `score = Σ (axis/4) *
weight`, weights sum 100 (`RUBRIC_FRAMEWORK.md §3`). How each axis is derived:

| Axis | Source | Computation |
|------|--------|-------------|
| `COR` | acceptance + adversarial pass fractions over `axis∋COR` checks | map fraction pair → 0–4 via §7.2 anchors |
| `ROB` | adversarial + error-path checks (`axis∋ROB`) | pass fraction → 0–4; large `acceptance_pass − adversarial_pass` gap caps ROB |
| `REG` | regression suite per the declared strategy (§5) | `regressions_introduced`/`oscillations` → 0–4; a real regression caps REG (per scenario) |
| `EFF` | telemetry vs budgets | `iterations`,`wall_clock_s`,`tokens` vs `budgets` → 0–4 (`CONVERGENCE_METRICS §4`) |
| `AUT` | intervention log | worst intervention tag + count → 0–4 (`CONVERGENCE_METRICS §3`); any `rescue` ⇒ AUT ≤ 1 |
| `QUA` | static floor (pass/fail gate on the axis) + judge | floor fail ⇒ QUA ≤ 1; else judge 0–4 |
| `FID` | automatable criteria + design-diff judge (L3+) | checklist fraction blended with judge 0–4 |

`COR`/`ROB`/`REG`/`EFF`/`AUT` are **automated**. `QUA` (graded portion) and `FID`
(design/feel portion) are **AI-judged** — deterministic code cannot score
"reads as a coherent state machine" or "feels instant." See §6.

---

## 4. Gate expression grammar

The gate is a boolean **expression**, not a float. It is evaluated over these
named quantities (all computed from the registry):

| Name | Meaning |
|------|---------|
| `acceptance_pass` | weighted pass fraction of acceptance checks (0–1) |
| `p0_pass` | weighted pass fraction of `priority: P0` acceptance checks |
| `adversarial_pass` | fraction of adversarial checks (never gates, but nameable) |
| `regression_pass` | fraction of the regression suite (§5) |
| `perf_ok` | boolean: all `axis∋EFF`/perf `gate_authority` checks pass |
| `security_ok` | boolean: all security `gate_authority` checks pass |
| `check:<id>` | boolean: a single named `gate_authority` check passed |

Operators: `and or not`, `== != >= <= > <`, parentheses, numeric literals.
Per-scenario gates (the five shapes, now expressible):

```
L0–L2   acceptance_pass == 1.0
L1      acceptance_pass == 1.0 and check:L1-CSVLIB-none    # stdlib csv forbidden
L3–L4   acceptance_pass >= 0.95
L5      acceptance_pass >= 0.95 and check:L5-NFR2-concurrency
L6      p0_pass == 1.0 and acceptance_pass >= 0.90
L8      p0_pass == 1.0 and acceptance_pass >= 0.90 and perf_ok and security_ok
L7      per-sprint: acceptance_pass == 1.0 and regression_pass == 1.0   # see §7 variant
```

Gate false ⇒ run scored **Failed (0 overall)** regardless of axes
(`RUBRIC_FRAMEWORK.md §4`).

---

## 5. Regression strategy (declared, not implied)

`REG` differs per rung; the manifest declares which strategy applies via
`regression.strategy`:

| Strategy | Rungs | Mechanism |
|----------|-------|-----------|
| `none` | L0–L2 | REG N/A (single-shot deterministic unit). |
| `rerun-matrix` | L3 | re-run the full flag/format matrix; behavior must be stable across invocations. |
| `per-group-diff` | L4 | after each feature group lands, prior groups' checks must still pass. |
| `two-pass-persistence` | L5 | cold-DB pass + carried-over-DB pass; state must survive. |
| `workspace-snapshots` | L6 | prior acceptance re-run at mid-build snapshots. |
| `cumulative-union` | L7 | union of all prior sprints' acceptance runs at each sprint boundary (see §7). |

A detected regression (a previously-passing weight-bearing check now failing)
caps `REG` per the scenario's §7 and is recorded in telemetry
(`regressions_introduced`, `oscillations`).

---

## 6. AI-judged axes (lean into agents, not brittle code)

`QUA` and `FID` are scored by a **grader agent** (base it on the
`amplifier_evaluation` extractor/grader agents — see `HARNESS.md`). Deterministic
code provides only the **hard floor**; the graded 0–4 is a judgment call recorded
with a one-line justification (required for both, `RUBRIC_FRAMEWORK.md §7`).

**QUA floor (deterministic gate on the axis):** the `static_floor` toolchain for
the scenario's languages must pass (e.g., `ruff`+`pyright`; `eslint`+`tsc`;
`clippy`+`rustfmt`) plus any scenario probe (L1 "no `import csv`", L4 "no
`eval`/`exec`"). Floor failure ⇒ `QUA ≤ 1`.

**Grader-agent rubric prompt (QUA) — template `rubric/qua.md`:**
```
You are grading CODE QUALITY (axis QUA, 0–4) for scenario {scenario}.
Static floor result: {floor_pass}. Inputs: the solution workspace diff.
Score 0–4 using these anchors (from REQUIREMENTS §7.2):
  {qua_anchors}
Judge only maintainability/clarity/simplicity/structure — NOT correctness
(COR covers that). Ignore anything the acceptance suite already measures.
Return: {"axis":"QUA","score":<0-4>,"justification":"<one line naming the
specific strength/deficiency>"}.
```

**Grader-agent rubric prompt (FID) — template `rubric/fid.md` (L3+):**
```
You are grading PRODUCT/DESIGN FIDELITY (axis FID, 0–4) for scenario {scenario}.
Inputs: the running solution (or captured screenshots/CLI output) + the required
design artifacts at {design_inputs} + the acceptance criteria.
Score 0–4 using these anchors:
  {fid_anchors}
Check: (a) required design/product artifacts exist; (b) the implementation matches
them (design-diff); (c) the personas' key tasks are satisfied. Missing a required
artifact caps FID at 2.
Return: {"axis":"FID","score":<0-4>,"justification":"<one line>"}.
```

Judges must be given only what they need; they never see held-out solutions of
other strategies. Two independent judge passes may be averaged to reduce noise on
high-stakes comparisons.

---

## 7. `score.json` (nested) + L7 per-sprint variant

Standard scenarios (L0–L6, L8):

```json
{
  "scenario": "L6-kanban-app",
  "strategy": "example-harness@v3",
  "gate": {"expression": "p0_pass == 1.0 and acceptance_pass >= 0.90",
           "p0_pass": 1.0, "acceptance_pass": 0.93, "perf_ok": null,
           "security_ok": null, "passed": true},
  "denominators": {"acceptance": 41, "adversarial": 18, "p0": 12},
  "results": {"acceptance_pass": 0.93, "adversarial_pass": 0.89,
              "regression_pass": 1.0, "static_floor_pass": true},
  "axes": {"COR": 3, "ROB": 3, "EFF": 3, "AUT": 4, "QUA": 3, "REG": 4, "FID": 3},
  "weights": {"COR": 22, "ROB": 12, "EFF": 15, "AUT": 15, "QUA": 12, "REG": 12, "FID": 12},
  "score": 77, "band": "Converged",
  "telemetry": {"iterations": 24, "wall_clock_s": 6100, "tokens": 1180000,
                "usd": 14.2, "failed_runs_before_pass": 6, "interventions": [],
                "regressions_introduced": 0, "oscillations": 1, "dead_ends": 1,
                "adversarial_pass": 0.89},
  "gaming_events": [],
  "notes": {"QUA": "clean layering; two fat components", "FID": "matches hi-fi; minor spacing drift"}
}
```

`interventions` is a **list** of `{tag, severity, note}` (not an int) so `AUT` can
score the worst tag (`CONVERGENCE_METRICS §3`). `gaming_events` is a list of
`{vector, consequence}` where `consequence ∈ {disqualify, cap-REG, cap-EFF,
cap-FID, cap-QUA}`.

**L7 variant** — per-sprint blocks + aggregation:

```json
{
  "scenario": "L7-kanban-sprints",
  "sprints": [
    {"id": 0, "gate": {"acceptance_pass": 1.0, "regression_pass": 1.0, "passed": true},
     "axes": {"COR": 4, "ROB": 3, "EFF": 3, "AUT": 4, "QUA": 3, "REG": 4, "FID": 3},
     "score": 79},
    {"id": 1, "...": "..."}
  ],
  "aggregation": {"method": "mean_of_sprint_scores",
                  "reg_cap_applied": false, "frontier_sprint": 4},
  "score": 74, "band": "Converged"
}
```

L7 rules: each sprint is gated (`acceptance_pass == 1.0 and regression_pass ==
1.0`) and scored; scenario score = mean of sprint scores; **any sprint that breaks
a prior sprint's acceptance caps scenario `REG ≤ 1` and demotes the band**
(regression safety is the point of the rung); `frontier_sprint` = highest sprint
reached at/above threshold; unreached sprints are `null`, not 0.

---

## 8. Determinism, flaky-guard, gaming

- **Determinism:** acceptance/adversarial suites control time/randomness/network
  (fake clock at L2; fixed seed + throwaway DB at L5; fixed host key + fixture
  vault at L8). Non-deterministic assertions are forbidden from the gate unless
  `flaky-guard`.
- **Flaky-guard:** `retry: flaky-guard:N` retries a check up to N times **only**
  for infrastructure faults; a genuine failure (e.g., L5 concurrency count
  mismatch) is **never** retried. The per-scenario N is declared in `rubric.yaml`.
- **Gaming:** reading held-out suites, hardcoding expected outputs, weakening a
  fixture (e.g., the test `sshd` host-key policy), or escaping the declared
  workspace are `gaming_events`. Consequence per vector is declared in the
  registry/scenario; the default is `disqualify`.

---

## 9. Budgets (the `token_budget` the specs were missing)

`EFF` needs a token budget per scenario; declared in each `manifest.yaml`
`budgets.token_budget`. Reference values (tunable):

| Rung | wall_clock_s | iterations soft/hard | token_budget |
|------|-------------:|:--------------------:|-------------:|
| L0 | 300 | 4 / 10 | 40k |
| L1 | 900 | 6 / 15 | 80k |
| L2 | 1200 | 8 / 20 | 120k |
| L3 | 1800 | 10 / 25 | 200k |
| L4 | 3600 | 14 / 35 | 350k |
| L5 | 5400 | 18 / 45 | 500k |
| L6 | 14400 | 30 / 80 | 1.5M |
| L7 | 28800 (8h; ~1.5h/sprint) | 20/50 per sprint | 4M |
| L8 | 28800 (tunable; multi-session) | 60 / 150 | 3M |
