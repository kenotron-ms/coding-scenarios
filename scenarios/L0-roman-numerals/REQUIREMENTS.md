# L0 — Roman Numerals — REQUIREMENTS

> Reference exemplar. Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`.

## 0. Scenario Summary
- **Level:** L0
- **Codename / dir:** `L0-roman-numerals`
- **One-liner:** Implement two pure functions that convert between integers and
  Roman numerals.
- **New difficulty introduced:** None beyond baseline. This is the **sanity
  floor** — a deterministic, fully-specified pure-function task. If a strategy
  cannot converge cleanly here, nothing higher is meaningful.
- **Estimated reference solution size:** 30–60 LoC, 1 file.
- **Time budget:** 5 minutes wall-clock.
- **Iteration budget:** soft 4, hard 10 edit→verify cycles.
- **Intervention budget:** 0 (any intervention is a strong negative signal at L0).

## 1. Product Requirements
- **1.1 Problem statement** — Provide a reliable, dependency-free conversion
  between non-negative integers in `[1, 3999]` and standard Roman numerals, for
  use as a library primitive.
- **1.2 Target users / personas** — N/A — the consumer is a calling programmer;
  the interface contract fully represents their needs at this rung
  (`ARTIFACT_GRADIENT.md` row L0).
- **1.3 User stories** — N/A — no user-facing surface. Replaced by the interface
  contract in §2.1.
- **1.4 Functional requirements**
  - **FR-1** `to_roman(n: int) -> str` returns the standard Roman numeral for
    integers `1 ≤ n ≤ 3999` using subtractive notation (e.g., 4→`IV`, 9→`IX`,
    40→`XL`, 90→`XC`, 400→`CD`, 900→`CM`).
  - **FR-2** `from_roman(s: str) -> int` returns the integer for a valid standard
    Roman numeral string.
  - **FR-3** Round-trip identity: for all `n` in `[1, 3999]`,
    `from_roman(to_roman(n)) == n`.
  - **FR-4** `to_roman` raises `ValueError` for `n` outside `[1, 3999]` or
    non-integers.
  - **FR-5** `from_roman` raises `ValueError` for empty, malformed, or
    non-standard numerals (e.g., `IIII`, `IC`, `VV`, lowercase if not accepted —
    see §1.6).
- **1.5 Out of scope** — Numbers ≥ 4000 (no standard vinculum notation), zero,
  negatives, fractional values, localization.
- **1.6 Ambiguities the agent must resolve**
  - **Case sensitivity of `from_roman` input.** Acceptable resolutions: accept
    uppercase only (reject lowercase with `ValueError`) **or** accept
    case-insensitively. Either is acceptable *if applied consistently and
    documented*. The acceptance suite tests only uppercase for correctness and
    checks that the *chosen* policy is internally consistent.

## 2. Technical Requirements
- **2.1 Interface / API contract**
  ```python
  # solution/roman.py
  def to_roman(n: int) -> str: ...
  def from_roman(s: str) -> int: ...
  ```
  Both are **pure** (no I/O, no globals, no side effects).
- **2.2 Architecture constraints** — Single module, standard library only. No
  network, filesystem, or third-party packages.
- **2.3 Data model** — N/A — stateless.
- **2.4 Technology constraints** — Python ≥ 3.11. No external dependencies.
- **2.5 Entrypoint contract** — `kind: python-module`, `target: solution.roman`.
  Harness imports `to_roman`/`from_roman` directly.

## 3. Non-Functional Requirements
- **NFR-1 Performance** — O(1)/O(len) per call; the full `[1,3999]` round-trip
  sweep completes in < 100 ms. (Trivial, but stated to anchor the axis.)
- **NFR-2 Reliability & error handling** — Invalid inputs raise `ValueError` with
  a message naming the offending value; functions never return wrong-but-silent
  results.
- **3.3 Security** — N/A — no untrusted I/O boundary beyond input validation
  already covered by NFR-2.
- **3.4 Accessibility** — N/A — no UI.
- **NFR-3 Maintainability** — Passes `ruff` and `pyright` clean; each public
  function has a docstring stating contract and raised exceptions; cyclomatic
  complexity ≤ 8 per function.
- **3.6 Observability** — N/A — library primitive.
- **NFR-4 Portability** — Zero-dependency; importable on any Python ≥ 3.11.

## 4. The Ask (Deliverables & Definition of Done)
- **4.1 Required artifacts**
  - `solution/roman.py` implementing FR-1..FR-5.
  - Docstrings documenting the resolved §1.6 policy.
- **4.2 Definition of Done**
  - [ ] `smoke` tests pass.
  - [ ] `acceptance` suite passes at 100% (hard gate).
  - [ ] `ruff` + `pyright` clean.
  - [ ] §1.6 ambiguity resolved and documented in the `from_roman` docstring.
- **4.3 Acceptance criteria**
  - AC-1 (FR-1/2/3): round-trip identity holds across all of `[1, 3999]`.
  - AC-2 (FR-4/5): documented invalid inputs raise `ValueError`.
  - AC-3 (NFR-3): static checks clean, docstrings present.

## 5. Discovery & Design Activities
- **5.1 User research** — **N/A** — deterministic algorithm; no user need to
  discover (`ARTIFACT_GRADIENT.md` L0).
- **5.2 Product design** — **Required (minimal):** the spec + acceptance criteria
  in this document *are* the product artifact. No PRD/backlog.
- **5.3 Interaction/visual design** — **N/A** — no interface surface beyond the
  two signatures fixed in §2.1.
- **5.4 Design artifacts to produce** — None.

## 6. Verification Method
- **6.1 Test tiers**
  - `smoke` (visible): 5 worked examples — `to_roman(4)=="IV"`,
    `to_roman(1994)=="MCMXCIV"`, `from_roman("XLII")==42`, a round-trip case, and
    one `ValueError` case.
  - `acceptance` (held-out): exhaustive round-trip over `[1, 3999]`;
    representative subtractive-form checks; a table of invalid inputs expecting
    `ValueError`; the internal-consistency check for the §1.6 policy.
  - `adversarial` (hidden): non-canonical-but-tempting inputs (`IIII`, `IC`,
    `XM`, `VX`, `MMMM`, empty string, whitespace, `"iv"` depending on declared
    policy), and boundary values `1` and `3999`.
- **6.2 "Working" definition** — 100% of the `acceptance` suite passes.
- **6.3 Verification mechanics** — `pytest` unit tests + a `hypothesis` property
  test asserting `from_roman(to_roman(n)) == n`. Real path = direct function
  call (the function *is* production).
- **6.4 Anti-gaming measures** — Property-based round-trip and the exhaustive
  sweep make lookup-table hardcoding of only the smoke examples fail acceptance;
  `adversarial` boundary/invalid cases catch overfitting to the visible five.

## 7. Scoring Rubric
- **7.1 Weight profile** (sum 100): `COR 70 · ROB 15 · EFF 5 · AUT 5 · QUA 5`.
  (`REG`/`FID` N/A at L0.)
- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | acceptance < 100% (gate fail) | passes core round-trip but misses some subtractive/invalid cases in adversarial | 100% acceptance + ≥95% adversarial |
  | ROB | crashes/ silent-wrong on invalid input | validates some invalids | all documented invalids raise `ValueError` with helpful message |
  | EFF | > hard iteration cap / > budget | passed near hard cap | passed ≤ soft cap, ≤1 failed run |
  | AUT | any `rescue` | one low-severity nudge | zero interventions |
  | QUA | lint/type errors | clean but no docstrings / high complexity | clean, documented, simple |
- **7.3 Hard gate** — `acceptance_floor = 1.0` (100%).
- **7.4 Pass threshold** — **85** (a clean pass of L0 should be near-perfect; a
  sub-85 here is a red flag about the strategy itself).

## 8. Convergence Signals
- **8.1 Healthy convergence** — ≤ 4 iterations, no interventions, first
  acceptance run passes or one quick fix after a smoke miss on a subtractive edge.
- **8.2 Pathological patterns** — Iterating many times on the subtractive cases
  (`IV/IX/XL/…`) suggests the strategy is guessing rather than encoding the
  standard mapping; hardcoding the smoke five (caught by acceptance sweep);
  needing a human hint to handle validation (`AUT` → 1).
- **8.3 Instrumentation notes** — Capture `failed_runs_before_pass`; at L0 any
  value > 2 is worth flagging as friction on a task with no inherent difficulty.
