# Artifact Gradient

A core teaching goal of this ladder: as complexity climbs, the amount of
**product and design work that must surround the code** climbs with it. At L0 the
spec *is* the truth and no discovery is warranted. At A2 you cannot deliver
responsibly without personas, a groomed backlog, evolving designs, and
per-sprint acceptance. This document is the authoritative matrix; each scenario's
§5 must be consistent with the row for its level.

## 1. The matrix

Legend: **R** = Required deliverable · **O** = Optional/Stretch · **—** = N/A for this rung.

| Activity | L0 | L1 | L2 | L3 | L4 | L5 | A1 | A2 | A3 |
|----------|----|----|----|----|----|----|----|----|----|
| **User research** ||||||||||
| Stakeholder/user interviews | — | — | — | O | O | O | R | R | R |
| Jobs-to-be-done / needs analysis | — | — | — | O | O | R | R | R | R |
| Personas | — | — | — | — | — | O | R | R | R |
| Usability testing | — | — | — | — | — | — | O | R | R |
| **Product** ||||||||||
| Spec / acceptance criteria | R | R | R | R | R | R | R | R | R |
| PRD (problem, scope, success metrics) | — | — | — | O | R | R | R | R | R |
| User stories | — | — | — | R | R | R | R | R | R |
| Prioritized backlog | — | — | — | — | O | O | R | R | R |
| Sprint plans + goals | — | — | — | — | — | — | — | R | — |
| Definition of Done | R | R | R | R | R | R | R | R | R |
| Retrospective artifacts | — | — | — | — | — | — | — | R | — |
| **Interaction / visual design** ||||||||||
| Interface/API contract design | — | — | R | R | R | R | R | R | R |
| CLI UX / output format design | — | — | — | R | — | — | — | — | — |
| Wireframes (lo-fi) | — | — | — | — | — | O | R | R | R |
| Hi-fi mockups | — | — | — | — | — | — | R | R | R |
| Design tokens / system | — | — | — | — | — | — | R | R | R |
| Interaction/state specs | — | — | — | — | — | O | R | R | R |
| Accessibility annotations (WCAG) | — | — | — | — | — | — | R | R | R |
| **Security & performance** ||||||||||
| Threat model / security design | — | — | — | — | — | O | O | O | R |
| Performance budget spec | — | — | — | — | — | O | O | O | R |

## 2. Why the gradient is shaped this way

- **L0–L1 (algorithmic):** The requirement is fully knowable in advance and
  cheaply expressible as tests. Adding "user research" would be theater. The
  honest deliverable is a precise spec + acceptance suite. Teaching point: *not
  every task needs discovery; forcing it is waste.*
- **L2 (stateful unit):** First appearance of **design** — you must design an
  interface/contract before implementing. Still no user research; the "user" is a
  calling programmer and the contract speaks for them.
- **L3 (CLI):** First real **UX** surface (argument grammar, output formats, exit
  codes, help text) and first **user stories** (operator scenarios). Research is
  optional because conventions are well established.
- **L4 (library):** Product framing (PRD) matters because a library has an API
  audience; design centers on the public API and its examples.
- **L5 (service):** JTBD for API consumers becomes required; data-model and API
  design are load-bearing; light product framing (PRD-lite + OpenAPI).
- **A1 (app):** Full product+design surface — personas, wireframes → hi-fi, a
  design system, and accessibility become **required**, because the software now
  has human end-users whose experience is part of "working."
- **A2 (iterative app):** Everything at A1 **plus** the continuous machinery of
  iterative delivery — a groomed backlog, per-sprint goals and acceptance,
  usability feedback informing the next sprint, retrospectives, and design that
  *evolves* across sprints rather than being fixed up front.

## 3. How these artifacts are evaluated

For rungs where an artifact is **Required (R)**, it becomes part of the
Definition of Done and is scored under **Product/Design Fidelity (`FID`)**:

- Product artifacts (PRD, stories, backlog, sprint plans) are checked for
  existence, internal consistency, and traceability to `FR`/acceptance criteria.
- Design artifacts (wireframes, hi-fi, tokens, a11y annotations) are checked for
  existence and for the **implementation matching them** (design diff review).
- Missing a Required artifact caps `FID` and may drop the run below its pass
  threshold even if code tests pass — because at these rungs, "working" includes
  "meets the product and design intent," not just "passes functional tests."

## 4. Producing the artifacts

Where a scenario requires design/research artifacts, they are authored into the
scenario's `design/` directory (wireframes as committed files/markup, personas
and PRDs as markdown, API contracts as OpenAPI/JSON schema, sprint plans as
markdown). The requirements docs in this pass *specify what must be produced*;
the artifacts themselves are produced when a strategy runs the scenario (they are
part of the deliverable the strategy is being evaluated on at upper rungs), with
reference exemplars provided in the harness-build pass.
