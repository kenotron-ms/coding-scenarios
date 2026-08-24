# VISION — Agent Coding Convergence Eval Ladder

## 1. Why this exists

We are building an **evaluation harness** to prove out strategies for making AI
coding agents (and the harnesses that drive them) reliably **converge on working
code**. The thing under test is *not* any single piece of code an agent produces
— it is the **strategy + harness** that repeatedly drives an agent from a
requirement to verified, working software.

A useful eval must let us answer, for a given strategy:

- Does it reach *working* code (objective, held-out verification)?
- *How well* does it converge — fast, cheaply, with few dead ends, without
  human rescue, without breaking things it already built?
- Does it hold up as task complexity climbs from a single pure function to a
  multi-sprint application that needs iterative feature delivery?

To answer those, we define a **ladder of scenarios** of increasing complexity
(L0 → L8), each with fully specified requirements, a verification method, and a
scoring rubric. Two strategies run against the same ladder produce comparable
scores. That comparability is the entire point.

## 2. What "converge on working code" means

A strategy has *converged* on a scenario when it produces an artifact that
passes the scenario's **held-out acceptance verification** without further
edits. Convergence is scored on more than the binary pass:

- **Did it work?** — objective, automated gate.
- **How efficiently did it get there?** — iterations, wall-clock, token/dollar
  cost, number of failed verification runs before passing.
- **How autonomously?** — count and severity of human interventions.
- **Did it stay converged?** — for multi-feature and multi-sprint scenarios, did
  new work regress previously-working behavior?
- **Is the result maintainable?** — quality of the code left behind, not just
  its test-passing behavior.

A strategy that brute-forces L2 in 40 iterations with 3 human rescues "passed"
but converged *poorly*. The rubric must expose that difference. See
`framework/CONVERGENCE_METRICS.md`.

## 3. The ladder at a glance

Each rung adds a *distinct* new class of difficulty, not just "more code."

```
Level  Scenario (dir)              New difficulty introduced
-----  --------------------------  --------------------------------------------------
L0     roman-numerals              Pure function. Deterministic. Sanity floor.
L1     csv-parser                  Edge cases + spec ambiguity to resolve. Held-out tests.
L2     lru-cache                   Stateful unit + interface design. Time/eviction semantics.
L3     log-analyzer                CLI: argv, files/stdin, exit codes, output formats.
L4     template-engine             Multi-module library. Component composition + public API.
L5     url-shortener               Stateful service: HTTP + persistence + concurrency.
L6     kanban-app                  Full app: data model + business rules + UI + E2E.
L7     kanban-sprints              Iterative multi-sprint delivery. Cumulative regression.
L8     markdown-editor             Native desktop (Tauri) + remote SSH I/O + security + WYSIWYM.
```

L6 and L7 deliberately **share the same application** (a Kanban board). L6 is the
"build it once, correctly" test. L7 re-frames the *same* target as a scripted
sequence of agile sprints, so we can measure iterative feature delivery and
regression safety on a system the strategy has already had to reason about. This
keeps the top of the ladder comparable across strategies: the app is fixed, only
the delivery process changes.

**L8 is a hand-curated capstone that sits above the graded ladder.** Where L0–L7
are systematically graded, L8 is a bespoke top rung — a native **Tauri** desktop
Markdown editor that reaches "vaults" over **SSH** — chosen because it stacks
several new classes of difficulty the web-app rungs never touch: a native shell,
remote and security-sensitive I/O, OS-config integration (`~/.ssh/config`,
Tailscale), a hard cold-boot performance budget, and a WYSIWYM editing
experience. Its rubric and thresholds *extend* the trajectory rather than
continuing it (see `framework/RUBRIC_FRAMEWORK.md §3`).

## 4. The artifact gradient (the pedagogical spine)

A real difference between "write a function" and "run a sprint" is **how much
product and design work must happen before and around the code**. The ladder
makes this explicit: lower rungs need almost no discovery; upper rungs demand
personas, user research, wireframes, acceptance criteria, and a groomed backlog.

```
Level  Discovery/User research   Design artifacts        Product artifacts
-----  ------------------------  ----------------------  ---------------------------
L0-L1  None (spec is the truth)  None                    Spec + acceptance tests
L2     None                      Interface/API design    API contract
L3     Light (usage scenarios)   CLI UX / output design  CLI spec + man-page
L4     Light (consumer stories)  Public API design       API reference + examples
L5     Medium (API consumers)    API + data model design PRD-lite + OpenAPI
L6     Full (personas, JTBD)     Wireframes → hi-fi + DS  PRD + user stories + a11y
L7     Full + continuous         Design evolves per      Backlog + sprint plans +
       (per-sprint feedback)     sprint                  DoD + retros
L8     Full (+ usability test)   Full + perf/motion +    PRD + backlog + threat
       (hand-curated capstone)   security/threat model   model + perf budget
```

Each scenario document defines exactly which of these activities are **required
deliverables**, which are **optional/stretch**, and which are honestly **N/A**
for that rung — with the reason. See `framework/ARTIFACT_GRADIENT.md`.

## 5. Resolved design decisions (assumptions — correct me if wrong)

You asked me to write the full set now rather than answer my five open
questions first. I resolved them with defensible defaults so the set is
internally consistent. These are the load-bearing assumptions; changing any of
them is cheap now and expensive later, so flag any you disagree with.

| # | Fork | Decision taken | Rationale |
|---|------|----------------|-----------|
| 1 | Language/stack | **Python** for L0–L5; **Python API + TypeScript/React SPA** for L6–L7. Harness is language-agnostic via a per-scenario `manifest.yaml`. | One primary toolchain keeps the harness small; full-stack only where the difficulty requires it. |
| 2 | Scoring mode | **Hybrid**: automated objective gate (hard pass/fail) + rubric axes, where subjective axes (quality, design fidelity) use an LLM-judge and/or human scorer with anchored descriptors. | Pure automation can't score maintainability or design fidelity; pure human doesn't scale. |
| 3 | Test visibility | **Three tiers**: `smoke` (visible to agent), `acceptance` (held-out, defines "working"), `adversarial` (hidden, run once, anti-overfitting). | Prevents strategies from gaming the eval by coding to the tests. |
| 4 | Convergence telemetry | **Scored, first-class.** Iterations, wall-clock, token/$ cost, intervention count, failed-runs-before-pass, regressions are captured and feed rubric axes. | This is a *strategy* eval, not just a correctness eval. |
| 5 | Top of ladder (L7) | **Fixed app + scripted sprint sequence** (not a fresh app per run). | Comparability across strategies. A fixed backlog isolates the strategy as the variable. |

## 6. How a scenario is structured

Every scenario is a self-contained directory. In this first pass we author the
**requirements set** (the documents you asked for). The executable harness
(tests, runners, manifests) is specified by these docs and built in a later
pass. Target end-state per scenario:

```
scenarios/L2-lru-cache/
  REQUIREMENTS.md    # THIS pass: product + technical + NFR + ask + design/research + verification + rubric
  SPEC.md            # later: the exact prompt handed to the agent under test
  manifest.yaml      # later: entrypoint + how the harness invokes solution & verification
  tests/             # later: smoke / acceptance / adversarial suites
  rubric.yaml        # later: machine-readable scoring config
  design/            # later + upper levels: wireframes, API contracts, personas
```

`REQUIREMENTS.md` is the canonical human-facing definition. Everything else is
derived from it. The shared shape of that document is fixed by
`framework/REQUIREMENTS_TEMPLATE.md` so all nine scenarios read the same way.

## 7. Scoring model (summary)

Full detail in `framework/RUBRIC_FRAMEWORK.md`. In brief:

- Six shared rubric **axes**: Correctness, Robustness, Convergence Efficiency,
  Autonomy, Code Quality, Regression Safety. Upper levels add a
  **Product/Design Fidelity** axis.
- Each axis scored **0–4** against anchored descriptors; weighted to a **0–100**
  scenario score.
- A **hard gate**: if the `acceptance` suite pass-rate is below the scenario's
  floor, the run **fails outright** regardless of other axes — you cannot score
  well on unworking code.
- Per-level **weight profiles** shift emphasis as you climb: L0 is almost all
  Correctness; L7 is dominated by Regression Safety, Autonomy, and Convergence
  Efficiency.

## 8. How you'll use this

1. Pick a strategy/harness to evaluate.
2. Run it against the ladder, lowest rung first, capturing telemetry.
3. Score each run with the scenario rubric → a per-level 0–100 and a **ladder
   profile** (how high the strategy climbs before it stops converging well).
4. Compare strategies by their ladder profiles, not single numbers. The
   interesting signal is *where* a strategy's convergence quality falls off.

## 9. Non-goals

- This is not a benchmark of model raw capability; it is a benchmark of
  *strategy + harness* convergence behavior.
- Scenarios are not meant to be novel/unseen research problems; they are
  well-understood tasks chosen so that "working" is unambiguous and cheaply
  verifiable.
- L8 is a hand-curated native-desktop capstone that adds OS/remote/security
  surface (Tauri + SSH) beyond the systematically-graded L0–L7 ladder.
- L6/L7 are "medium" apps by design — large enough to require iteration, small
  enough to verify end-to-end in a bounded run.

## 10. Document map

| Document | Purpose |
|----------|---------|
| `VISION.md` (this file) | Why, what, the ladder, resolved forks |
| `README.md` | Index + how to navigate/run |
| `framework/REQUIREMENTS_TEMPLATE.md` | Canonical per-scenario doc structure |
| `framework/RUBRIC_FRAMEWORK.md` | Scoring axes, scales, weights, gates |
| `framework/VERIFICATION_CONTRACT.md` | Test tiers, visibility, entrypoint contract |
| `framework/CONVERGENCE_METRICS.md` | Telemetry definitions + capture |
| `framework/ARTIFACT_GRADIENT.md` | Which research/design/product artifacts apply per level |
| `scenarios/L0..L8/REQUIREMENTS.md` | The nine scenario definitions |
