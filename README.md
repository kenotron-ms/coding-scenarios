# Coding Scenarios — Agent Convergence Eval Ladder

A set of increasing-complexity coding challenges used as an **eval / harness** to
prove out strategies for converging AI coding agents on **working code** — from a
single pure function up to a medium-sized app delivered across agile sprints.

The unit under test is the **strategy + harness**, not any one piece of code.
Each scenario defines full requirements, a verification method, and a scoring
rubric so two strategies can be compared on the same ladder.

> **Start with [`VISION.md`](VISION.md).** It explains the why, the ladder, the
> resolved design decisions (five forks), and the document map. §5 of the vision
> lists the assumptions taken while authoring this set — review and correct any.

## The ladder

| Level | Scenario | New difficulty | Gate | Pass |
|-------|----------|----------------|------|------|
| [L0](scenarios/L0-roman-numerals/REQUIREMENTS.md) | Roman numerals | Pure function (sanity floor) | 100% | 85 |
| [L1](scenarios/L1-csv-parser/REQUIREMENTS.md) | CSV parser | Edge cases + spec ambiguity | 100% | 80 |
| [L2](scenarios/L2-lru-cache/REQUIREMENTS.md) | LRU cache | Stateful unit + interface design | 100% | 78 |
| [L3](scenarios/L3-log-analyzer/REQUIREMENTS.md) | Log analyzer | CLI: argv, I/O, exit codes, formats | ≥95% | 72 |
| [L4](scenarios/L4-template-engine/REQUIREMENTS.md) | Template engine | Multi-module library + public API | ≥95% | 70 |
| [L5](scenarios/L5-url-shortener/REQUIREMENTS.md) | URL shortener | Service: HTTP + persistence + concurrency | ≥95% | 68 |
| [L6](scenarios/L6-kanban-app/REQUIREMENTS.md) | Kanban app | Full app: data + rules + UI + E2E | 100% P0, ≥90% | 68 |
| [L7](scenarios/L7-kanban-sprints/REQUIREMENTS.md) | Kanban sprints | Iterative multi-sprint + regression | per-sprint | 68 |

L6 and L7 **share the same application**: L6 builds it once, L7 re-delivers it as
five scripted sprints. This keeps the top of the ladder comparable across
strategies.

## Framework (shared contracts)

| Document | Purpose |
|----------|---------|
| [`framework/REQUIREMENTS_TEMPLATE.md`](framework/REQUIREMENTS_TEMPLATE.md) | Canonical per-scenario doc structure (every scenario follows §0–8) |
| [`framework/RUBRIC_FRAMEWORK.md`](framework/RUBRIC_FRAMEWORK.md) | Seven axes, 0–4 scale, per-level weights, hard gate, rating bands, ladder profile |
| [`framework/VERIFICATION_CONTRACT.md`](framework/VERIFICATION_CONTRACT.md) | Test tiers (smoke/acceptance/adversarial), `manifest.yaml` entrypoint, `score.json` |
| [`framework/CONVERGENCE_METRICS.md`](framework/CONVERGENCE_METRICS.md) | Telemetry (iterations, cost, interventions, regressions) → axis mapping |
| [`framework/ARTIFACT_GRADIENT.md`](framework/ARTIFACT_GRADIENT.md) | Which research/product/design artifacts are required per level |

## How each scenario is structured

Every `scenarios/L*/REQUIREMENTS.md` contains, in order:

```
0. Scenario Summary        (level, one-liner, budgets: time/iterations/interventions)
1. Product Requirements    (problem, personas, user stories, FRs, out-of-scope, ambiguities)
2. Technical Requirements  (interface/API, architecture, data model, tech, entrypoint)
3. Non-Functional Reqs     (performance, reliability, security, a11y, maintainability, ...)
4. The Ask                 (deliverables, Definition of Done, acceptance criteria)
5. Discovery & Design      (user research / product / design activities — or N/A + reason)
6. Verification Method     (test tiers, "working" definition, mechanics, anti-gaming)
7. Scoring Rubric          (weight profile, per-axis guide, hard gate, pass threshold)
8. Convergence Signals     (healthy vs pathological patterns, instrumentation notes)
```

## Scoring in one paragraph

A run must first clear a **hard gate** (the acceptance suite floor) — you cannot
score well on non-working code. Above the gate, seven axes (Correctness,
Robustness, Convergence Efficiency, Autonomy, Code Quality, Regression Safety,
Product/Design Fidelity) are each scored **0–4**, weighted per level, and summed
to **0–100** with a rating band. The headline output for a strategy is its
**ladder profile**: the highest rung it reaches at/above the pass threshold, and
the shape of the fall-off. See `RUBRIC_FRAMEWORK.md §6`.

## Status & next pass

This pass authored the **requirements set** (this repo). The **executable
harness** these documents specify — per-scenario `SPEC.md`, `manifest.yaml`,
`tests/` (smoke/acceptance/adversarial), `rubric.yaml`, and reference `design/`
artifacts for the upper rungs — is the next build pass. `VERIFICATION_CONTRACT.md`
and each scenario's §6/§7 define exactly what that harness must produce.
