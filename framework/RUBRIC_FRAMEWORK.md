# Rubric Framework

The shared scoring model. Every scenario's §7 references and specializes this.
The goal is a single **0–100 per-scenario score** plus a **ladder profile**, both
comparable across strategies, that reward *good convergence* rather than mere
eventual success.

## 1. Axes

Seven axes. The first six apply to every rung; **Product/Design Fidelity**
applies only from L3 upward (where there is product/design surface to be
faithful to). Each axis is scored **0–4** using the anchored descriptors below,
then multiplied by the rung's weight (see per-scenario §7.1) and summed.

| Axis | Code | Measures | Source of evidence |
|------|------|----------|--------------------|
| Correctness | `COR` | Does it pass held-out acceptance behavior? | `acceptance` + `adversarial` suites |
| Robustness | `ROB` | Edge cases, malformed input, failure handling | adversarial suite + error-path tests |
| Convergence Efficiency | `EFF` | Iterations, time, token/$ cost to reach pass | telemetry (`CONVERGENCE_METRICS.md`) |
| Autonomy | `AUT` | Ran without human rescue | intervention log |
| Code Quality | `QUA` | Maintainability, clarity, simplicity | static analysis + LLM/human review |
| Regression Safety | `REG` | New work didn't break old work | cumulative suite across features/sprints |
| Product/Design Fidelity | `FID` | Met acceptance criteria, design, a11y (L3+) | criteria checklist + design diff review |

## 2. The 0–4 anchored scale (generic)

Each scenario restates these anchors concretely, but the generic meaning is fixed:

| Score | Meaning |
|-------|---------|
| **4** | Exemplary. No meaningful deficiency on this axis. |
| **3** | Solid. Minor, non-load-bearing gaps. |
| **2** | Acceptable-with-reservations. Real gaps that a maintainer would flag. |
| **1** | Poor. Significant deficiency; barely counts as addressing the axis. |
| **0** | Absent/failing on this axis. |

Half-points are not used; force a 0–4 integer to keep scoring reproducible.

## 3. Weighting and the 0–100 score

```
scenario_score = Σ (axis_score_0_4 / 4) * axis_weight
where Σ axis_weight = 100  (per-rung weights defined in each scenario §7.1)
```

### Weight profile trajectory (informative)

Weights shift up the ladder from "is it correct?" to "did it stay correct while
being extended, autonomously, and cheaply?" Exact per-rung numbers live in each
scenario; the trend:

```
Axis   L0   L1   L2   L3   L4   L5   L6   L7   L8
COR    70   55   45   35   30   28   22   15   20
ROB    15   25   20   18   15   15   12   10   18
EFF     5    5   12   12   14   14   15   20   12
AUT     5    5   10   10   12   13   15   20   12
QUA     5   10   13   12   13   12   12   12   13
REG     -    -    -    5    8   10   12   18   10
FID     -    -    -    8    8    8   12    5   15
TOTAL 100  100  100  100  100  100  100  100  100
```

(REG is meaningful only once there is prior behavior to protect — from L3's
multi-run acceptance, growing to dominate at L7. FID appears once there is a
product/design surface. FID's weight dips at L7 because the sprint backlog, not
a static design, carries acceptance — regression and autonomy dominate there.)

**L8 extends the trajectory rather than continuing it.** L8 is a hand-curated
capstone (see `scenarios/L8-markdown-editor`) that breaks the L7 shape: a native
desktop shell (Tauri), remote/secure I/O over SSH, and a hard cold-boot budget.
`ROB` rises to 18 because robustness there **includes the security surface**
(host-key verification, secret handling, sanitization); `FID` reaches its ladder
**maximum of 15** because the WYSIWYM editing experience and perceived
performance *are* the product; `REG` eases to 10 (a single ambitious build, not a
five-sprint sequence).

## 4. The hard gate

A run is scored **FAIL (0 overall)** — regardless of other axes — if it does not
clear the scenario's **acceptance floor** (defined in each §7.3). Rationale: a
strategy cannot "score well" on non-working software. Typical floors:

- L0–L2: **100%** of the acceptance suite (these are deterministic).
- L3–L5: **≥ 95%** of acceptance assertions.
- L6: **100%** of P0 acceptance criteria, **≥ 90%** overall.
- L7: **100%** of the *current sprint's* acceptance criteria **and** **100%** of
  the accumulated regression suite from prior sprints.

`adversarial` results never count toward the gate (they are run once, post-hoc,
to detect overfitting) but they *do* feed `COR`/`ROB`.

## 5. Pass threshold and rating bands

Above the hard gate, the weighted 0–100 yields a rating:

| Band | Score | Interpretation |
|------|-------|----------------|
| Converged-Clean | 85–100 | Working *and* efficient, autonomous, maintainable. |
| Converged | 70–84 | Working with acceptable convergence quality. |
| Converged-Rough | 55–69 | Working, but convergence was costly/messy. |
| Sub-threshold | <55 (gate passed) | Technically working; strategy is weak here. |
| Failed | gate not cleared | Did not reach working code. |

A scenario's **pass threshold** (each §7.4) is the score at/above which we call
the rung "converged" for **ladder-profile** purposes.

**On the hard rungs, "passing" legitimately lands in Converged-Rough.** By design
the pass thresholds for L5–L8 (68/68/68/66) fall inside the Converged-Rough band
(55–69), *below* the Converged floor (70). This is intentional, not an
inconsistency: at those rungs — a live service, a full app, a five-sprint
delivery, a native+SSH desktop app — merely reaching working, gate-clearing code
is a real achievement, and the band label honestly reflects that getting there is
usually costly and messy. A strategy that reaches **Converged** (≥70) or
**Converged-Clean** (≥85) on L5–L8 is doing something exceptional. (The lower
rungs L0–L4 keep thresholds at/above the Converged floor, where clean convergence
is the reasonable expectation.)

## 6. Ladder profile (cross-scenario)

The headline artifact of a strategy evaluation is not one number but a profile:

```
Strategy "X" ladder profile
L0  ██████████ 96  Converged-Clean
L1  █████████░ 91  Converged-Clean
L2  ████████░░ 82  Converged
L3  ███████░░░ 74  Converged
L4  ██████░░░░ 63  Converged-Rough
L5  ████░░░░░░ 41  FAILED (gate) — could not keep concurrency-safe under load
L6  —          not attempted (below-gate at L5)
L7  —
```

The **convergence frontier** — the highest rung the strategy reaches *at or
above its pass threshold* — plus the shape of the fall-off, is the comparison
signal between strategies.

## 7. Who scores which axis

| Axis | Scoring method |
|------|----------------|
| COR, ROB, REG | **Automated** (suite results, deterministic). |
| EFF, AUT | **Automated** from telemetry against per-rung budgets. |
| QUA | **Automated floor** (lint/type/complexity) + **LLM-judge or human** for the graded portion, using the scenario's anchors. |
| FID | **Checklist automation** where criteria are testable + **LLM/human** for design/a11y judgment. |

Subjective scoring (QUA, FID) must record a one-line justification per axis so
scores are auditable and inter-rater drift is visible.
