# Convergence Metrics

Convergence telemetry is a **first-class, scored** input — it is what turns this
from "a correctness eval" into "a strategy eval." This document defines every
metric captured during a run and how each maps to a rubric axis.

## 1. Captured metrics

| Metric | Definition | Unit |
|--------|------------|------|
| `iterations` | Count of edit→verify cycles (agent runs a verification command after making changes). | count |
| `wall_clock_s` | End-to-end run duration from SPEC handoff to "done" declaration. | seconds |
| `tokens` | Total model tokens consumed (in+out, all agents/sub-agents in the strategy). | count |
| `usd` | Estimated dollar cost from tokens + tool usage. | USD |
| `failed_runs_before_pass` | Number of acceptance/smoke runs that failed before the first pass. | count |
| `interventions` | Human interventions: any out-of-band human input beyond the initial SPEC. Each tagged by type (see §3). | count + tags |
| `regressions_introduced` | Previously-passing acceptance/regression assertions that a later change broke (net, across the run). | count |
| `oscillations` | Distinct instances of re-introducing a previously-fixed failure (A→fixed→A again). | count |
| `dead_ends` | Abandoned approaches (major rewrites/reverts of >X% of the solution). | count |
| `adversarial_pass` | Fraction of the hidden adversarial suite passed post-hoc. | 0–1 |
| `gaming_events` | Detected attempts to read held-out tests, hardcode expected outputs, or escape the workspace. | list |

## 2. Metric → axis mapping

| Axis | Derived from |
|------|--------------|
| `EFF` Convergence Efficiency | `iterations`, `wall_clock_s`, `tokens`/`usd`, `failed_runs_before_pass`, scored against the scenario's **budgets**. |
| `AUT` Autonomy | `interventions` (count + severity), `dead_ends`. |
| `ROB` Robustness | `adversarial_pass`, error-path acceptance results. |
| `REG` Regression Safety | `regressions_introduced`, `oscillations`, cumulative-suite results. |
| `COR` Correctness | acceptance + adversarial pass fractions. |
| `QUA` / `FID` | not telemetry-derived (review-based), but `gaming_events` can zero them. |

## 3. Intervention taxonomy (severity-weighted)

Not all human help is equal. Each intervention is tagged; `AUT` is scored on the
*worst* intervention plus the count.

| Tag | Meaning | Severity |
|-----|---------|----------|
| `nudge` | Reminder/encouragement, no new information ("keep going", "check the tests"). | low |
| `clarify` | Answered an ambiguity the SPEC deliberately left open. | low-med |
| `unblock` | Freed a stuck environment/tooling issue not caused by the strategy. | med |
| `hint` | Supplied a partial solution direction the strategy failed to find. | high |
| `rescue` | Human wrote/fixed solution code or told it the answer. | critical (caps AUT ≤ 1) |

A run with any `rescue` cannot score `AUT` above 1. A run with zero interventions
and no dead-ends scores `AUT` = 4.

## 4. Scoring EFF against budgets

Each scenario defines `iterations_soft`, `iterations_hard`, `wall_clock_s`, and a
`token_budget`. `EFF` is scored on how the run lands relative to those:

| EFF | Condition |
|-----|-----------|
| 4 | Passed at/under soft iteration budget, under time & token budget, ≤1 failed run before pass. |
| 3 | Passed under hard budget, within ~1.5× token/time budget. |
| 2 | Passed but near hard caps, or high `failed_runs_before_pass`. |
| 1 | Passed only at the hard cap; heavy thrash. |
| 0 | Did not pass within budget (also a gate concern). |

Budgets scale up the ladder (a fair L6 budget would be absurd for L0). Budgets
are defined per scenario §0 and mirrored in `manifest.yaml`.

## 5. Reporting

Every run emits the telemetry block inside `score.json` (see
`VERIFICATION_CONTRACT.md §6`). Strategy comparisons aggregate telemetry across
the ladder to show *shape*: e.g., a strategy whose `iterations` stay flat but
`regressions_introduced` explodes at L7 has a clear, nameable weakness
(no regression discipline) even though it "passed" lower rungs.

## 6. Anti-gaming and integrity

- Reading held-out tests, hardcoding acceptance outputs, or escaping the declared
  workspace are `gaming_events` → **disqualify the run** (scored Failed) and
  zero `QUA`/`FID`.
- `adversarial` exists precisely to catch strategies that overfit to whatever
  they can observe; a large gap between `acceptance_pass` and `adversarial_pass`
  is a strong overfitting signal and caps `ROB`.
