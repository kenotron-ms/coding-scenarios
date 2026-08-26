# Coding Scenarios — Agent Convergence Eval Ladder

A set of increasing-complexity coding challenges used as an **eval / harness** to
prove out strategies for converging AI coding agents on **working code** — from a
single pure function up to a medium-sized app delivered across agile sprints,
and a native Tauri desktop editor that reaches remote Markdown vaults over SSH.

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
| [L8](scenarios/L8-markdown-editor/REQUIREMENTS.md) | Markdown vault editor | Native desktop (Tauri) + SSH + security + WYSIWYM | P0 + perf + security, ≥90% | 66 |

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
| [`framework/GRADING.md`](framework/GRADING.md) | **The grader**: check registry (counted assertions), gate-expression grammar, axis→score, AI-judge prompts, `score.json` |
| [`framework/HARNESS.md`](framework/HARNESS.md) | **The runner** (`framework/harness/run_scenario.py`): how to grade a solution and drive a strategy, output discipline |

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

## Running a strategy against the ladder

The thing you evaluate is a **strategy** — a coding agent or harness that, given
a scenario's spec, produces a solution. Running one is two separate steps, kept
apart so the grader is identical no matter who produced the solution:

**1. Drive the strategy to produce a solution.** Hand it *only* the scenario's
`SPEC.md` and its `tests/smoke/` (the visible workspace). It must produce a
solution satisfying the entrypoint in `manifest.yaml` (for L0–L2, an importable
module: `roman`, `csvparse`, `lru`). It must **never** see `tests/acceptance/`
or `tests/adversarial/` — those are held out to grade it.

**2. Grade the produced solution** with the reference runner. It runs the tiers,
computes the axes, applies the gate, and writes `score.json`.

Try it right now against the shipped reference solution (which stands in for "a
strategy's output"):

```bash
pip install -r framework/harness/requirements.txt

python3 framework/harness/run_scenario.py \
  --scenario scenarios/L1-csv-parser \
  --solution graders/references/L1-csv-parser/solution \
  --strategy my-strategy@v1 \
  --out runs/$(date +%Y%m%d-%H%M%S)/L1/
# -> gate PASS · score 98 · Converged-Clean; score.json written to the out dir
```

Point `--solution` at whatever directory your strategy produced — the runner puts
that dir on the import path and loads the `manifest.yaml` target from it.

**Wiring in your own agent.** The loop your harness automates, per scenario:

```
1. Fresh, isolated workspace. Copy in SPEC.md + tests/smoke/ ONLY.
2. Run your agent on SPEC.md until it declares done (or hits a budget).
   Capture telemetry -> telemetry.json (iterations, wall_clock_s, tokens,
   interventions[], failed_runs_before_pass, ...). See framework/HARNESS.md §2.
3. Grade it:
     python3 framework/harness/run_scenario.py \
       --scenario scenarios/L<n>-<slug> \
       --solution <the-dir-your-agent-produced> \
       --telemetry telemetry.json \
       --strategy <name> --out runs/<dt>/L<n>/
4. Read score.json: gate passed?, per-axis 0-4, weighted score, band.
5. Repeat across scenarios; aggregate score.json into the ladder profile.
```

`--telemetry` feeds the `EFF` (efficiency) and `AUT` (autonomy) axes; omit it and
those two are `null` (the score then reflects only the tiers + quality floor).
`QUA`/`FID` (the fuzzy axes) are graded by an agent — see `framework/GRADING.md §6`.

**What "fits" the grader.** A strategy passes a rung when it clears that
scenario's **gate** (e.g. L0–L2 need 100% acceptance; L1 also must not
`import csv`) *and* its weighted score reaches the **pass threshold**. Because
the acceptance/adversarial tiers are held out, a strategy can't game them — it
only ever sees `SPEC.md` + smoke.

**Driving real agents / A-B comparisons.** To run an actual coding agent
(Amplifier, Claude Code, Copilot, …) in isolation, capture its session, and
compare variants, use the `amplifier-evaluation` library with a Digital Twin
Universe profile per variant (`framework/HARNESS.md §2`). Run outputs (`runs/`,
`score.json`, transcripts) are **gitignored** — only eval *definitions* are
committed.

## Scoring in one paragraph

A run must first clear a **hard gate** (the acceptance suite floor) — you cannot
score well on non-working code. Above the gate, seven axes (Correctness,
Robustness, Convergence Efficiency, Autonomy, Code Quality, Regression Safety,
Product/Design Fidelity) are each scored **0–4**, weighted per level, and summed
to **0–100** with a rating band. The headline output for a strategy is its
**ladder profile**: the highest rung it reaches at/above the pass threshold, and
the shape of the fall-off. See `RUBRIC_FRAMEWORK.md §6`.

## Status & next pass

**Requirements set:** all nine scenarios (L0–L8) are fully specified.

**Grader layer:** the grading contract (`framework/GRADING.md`) turns each
scenario's §6/§7 into a machine- and agent-checkable grader — a counted **check
registry** (fixing the "what's the denominator?" ambiguity), a **gate-expression
grammar** (the five gate shapes across the ladder), automated axes + AI-judge
prompts for `QUA`/`FID`, and the nested `score.json` (incl. the L7 per-sprint
variant). A reference **runner** lives at `framework/harness/run_scenario.py`.

**L0, L1, and L2 are fully-runnable, proven reference evals** — each ships
`SPEC.md` + `manifest.yaml` + `rubric.yaml` + `EVALUATION.md` +
`tests/{smoke,acceptance,adversarial}` + `reference/` solutions, and each grader
**passes on a correct reference and fails on a broken mutant**:

| Rung | reference | broken mutant | extra |
|------|-----------|---------------|-------|
| L0 roman-numerals | PASS · 99 · Converged-Clean | gate FAIL · 0 | — |
| L1 csv-parser | PASS · 98 · Converged-Clean | gate FAIL · 0 (36% acc) | a `csvlib` variant hits 100% acc but **gate-FAILs** via the `check:L1-CSVLIB-none` probe |
| L2 lru-cache | PASS · 97 · Converged-Clean | gate FAIL · 0 (46% acc) | fake-clock TTL + hypothesis stateful invariants |
| L3 log-analyzer | gate PASS · acc 100% (36/36) | gate FAIL · 0 (78% acc < 95% floor) | CLI: subprocess golden-file/exit-code tests; ≥95% gate |
| L4 template-engine | gate PASS · acc 100% (47/47) | gate FAIL · 0 (13% acc) | multi-module library (lexer→parser→renderer); autoescape/injection checks |

(L3/L4 reference *scores* land in Converged-Rough on the runner-only path — like L2's 75 — because `EFF`/`AUT` need `--telemetry` and `QUA`/`FID` need the grader agent; the **gate** is what proves discrimination, and it does.)

The grader dependencies are in `framework/harness/requirements.txt`
(`pytest`, `pyyaml`, `hypothesis`).

**Next:** L5–L7 need live infra (server/browser/ssh fixtures) — the point where
the lightweight local runner gives way to the `amplifier-evaluation` driver +
DTU-per-variant. L8's REQUIREMENTS are now **gradeable-in-spec** (concrete
budgets, a declared `workspace-snapshots` regression mechanism, P0-tagged
acceptance, and named perf/security gate authorities all landed), but a *runnable*
L8 grader still needs a Tauri + SSH harness. No coding agent has been RUN against
the ladder yet — that is the driver layer.

Run output (`runs/`, `score.json`, transcripts) is **gitignored** — only the eval
*definitions* are committed.
