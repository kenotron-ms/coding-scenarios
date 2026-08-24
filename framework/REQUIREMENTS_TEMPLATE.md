# Canonical Requirements Template

Every `scenarios/L*/REQUIREMENTS.md` MUST follow this structure and section order.
This keeps all nine scenarios readable in the same shape and makes them
mechanically comparable. Sections that do not apply to a rung are kept but
marked `N/A — <reason>` (honest omission, never silent).

---

## 0. Scenario Summary
- **Level:** L{n}
- **Codename / dir:** `L{n}-{slug}`
- **One-liner:** single sentence describing the deliverable.
- **New difficulty introduced:** the *distinct* class of hardness this rung adds.
- **Estimated reference solution size:** LoC band + file count (orienting only).
- **Time budget:** wall-clock ceiling for a run.
- **Iteration budget:** soft/hard caps on edit→verify cycles.
- **Intervention budget:** number of allowed human interventions before the run
  is scored as non-autonomous.

## 1. Product Requirements
- **1.1 Problem statement** — what need the software serves.
- **1.2 Target users / personas** — who uses it (or `N/A` with reason).
- **1.3 User stories** — `As a <role>, I want <capability>, so that <outcome>.`
- **1.4 Functional requirements** — numbered `FR-n`, testable, unambiguous.
- **1.5 Out of scope** — explicit non-goals to prevent scope creep.
- **1.6 Ambiguities the agent must resolve** — deliberate under-specification
  (upper rungs) and the acceptable resolutions.

## 2. Technical Requirements
- **2.1 Interface / API contract** — signatures, endpoints, CLI grammar, schemas.
- **2.2 Architecture constraints** — module boundaries, allowed/forbidden deps.
- **2.3 Data model** — entities, relationships, persistence (or `N/A`).
- **2.4 Technology constraints** — language, runtime, permitted libraries.
- **2.5 Entrypoint contract** — how the harness invokes the solution
  (must match `manifest.yaml`; see `VERIFICATION_CONTRACT.md`).

## 3. Non-Functional Requirements
Numbered `NFR-n`. Only the applicable categories are filled; others are `N/A`.
- **3.1 Performance** — latency/throughput/complexity budgets.
- **3.2 Reliability & error handling** — failure modes, recovery, idempotency.
- **3.3 Security** — input validation, authz/authn, secrets, injection.
- **3.4 Accessibility** — WCAG level, keyboard, semantics (UI rungs).
- **3.5 Maintainability** — structure, readability, docstrings, complexity caps.
- **3.6 Observability** — logging, errors, health (service rungs).
- **3.7 Portability / footprint** — install, dependencies, resource limits.

## 4. The Ask (Deliverables & Definition of Done)
- **4.1 Required artifacts** — exact list of files/outputs expected.
- **4.2 Definition of Done** — the checklist that must be green to claim complete.
- **4.3 Acceptance criteria** — bullet criteria mapped back to `FR-n`/`NFR-n`.

## 5. Discovery & Design Activities
Which upfront/parallel activities are required for this rung. Each item is
tagged **Required**, **Optional/Stretch**, or **N/A — reason**.
- **5.1 User research** — interviews, surveys, JTBD, usability tests.
- **5.2 Product design** — PRD, backlog, story mapping, prioritization.
- **5.3 Interaction/visual design** — wireframes, hi-fi mockups, design tokens,
  interaction specs, accessibility annotations.
- **5.4 Design artifacts to produce** — concrete files to land under `design/`.

## 6. Verification Method
- **6.1 Test tiers** — what lives in `smoke` (visible), `acceptance`
  (held-out, defines working), `adversarial` (hidden, run once).
- **6.2 "Working" definition** — the objective condition that is the hard gate.
- **6.3 Verification mechanics** — how each tier is executed and observed
  (unit, property, subprocess/golden-file, live HTTP, browser/E2E).
- **6.4 Anti-gaming measures** — how overfitting to visible tests is detected.

## 7. Scoring Rubric
- **7.1 Weight profile** — this rung's weights across the shared axes (sum 100).
- **7.2 Per-axis scoring guide** — what 0/2/4 looks like *for this scenario*.
- **7.3 Hard gate** — acceptance pass-rate floor below which the run fails.
- **7.4 Pass threshold** — weighted score required to call the rung "converged".

## 8. Convergence Signals
- **8.1 Healthy convergence** — what a good strategy's trace looks like here.
- **8.2 Pathological patterns** — thrash, oscillation, test-gaming, rescue-reliance
  specific to this rung, and how they surface in telemetry.
- **8.3 Instrumentation notes** — any scenario-specific telemetry to capture
  beyond the shared `CONVERGENCE_METRICS.md` set.
