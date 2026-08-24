# L1 — CSV Parser — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`.

## 0. Scenario Summary
- **Level:** L1
- **Codename / dir:** `L1-csv-parser`
- **One-liner:** Implement an RFC 4180-subset CSV parser as a pure function,
  correctly handling quoted fields, escaped quotes, embedded delimiters and
  embedded newlines.
- **New difficulty introduced:** **Real edge-case density plus deliberate spec
  ambiguity.** L0 was fully specified; here three behaviors are intentionally
  left open (§1.6) and the agent must *choose, apply consistently, and document*
  a resolution without asking a human. Still a pure function with no I/O, but
  the correct implementation is a character-level state machine rather than a
  lookup table, and the held-out tests probe corners the visible examples never
  show.
- **Estimated reference solution size:** 60–120 LoC, 1 file.
- **Time budget:** 15 minutes wall-clock.
- **Iteration budget:** soft 6, hard 15 edit→verify cycles.
- **Intervention budget:** 0. Note that "what should unterminated quotes do?" is
  a *deliberate* ambiguity, not a spec defect — asking is a `clarify`
  intervention and is scored against the run (§8.2).

## 1. Product Requirements
- **1.1 Problem statement** — Provide a dependency-free parser that turns CSV
  text into rows of string fields, correct on the quoting constructs that make
  naive `text.split(",")` implementations wrong: delimiters inside quotes,
  newlines inside quotes, and doubled quotes.
- **1.2 Target users / personas** — N/A — the consumer is a calling programmer;
  the interface contract in §2.1 fully represents their needs at this rung
  (`ARTIFACT_GRADIENT.md` row L1).
- **1.3 User stories** — N/A — no user-facing surface. Replaced by the interface
  contract in §2.1 and the functional requirements below.
- **1.4 Functional requirements**
  - **FR-1** `parse_csv` decomposes `text` into records and each record into
    fields, returning `list[list[str]]`. Empty input returns `[]`.
  - **FR-2** A field whose first character is `quotechar` is a **quoted field**:
    its content runs to the matching closing `quotechar`, and the enclosing
    quotes are removed from the returned value.
  - **FR-3** Inside a quoted field, a doubled quote (`""`) is an escaped literal
    quote: `"say ""hi"""` → `say "hi"`.
  - **FR-4** Inside a quoted field, `delimiter` is ordinary data and does not
    end the field: `a,"b,c",d` → `["a", "b,c", "d"]`.
  - **FR-5** Inside a quoted field, a newline (`\n` or `\r\n`) is ordinary data
    and does not end the record. The embedded newline is preserved **verbatim**
    as it appeared in the input (no translation of `\r\n` → `\n`).
  - **FR-6** Empty fields are supported in any position — leading, interior, and
    trailing. The invariant is positional, not content-based: a record with `n`
    top-level delimiters yields exactly `n + 1` fields. `a,,b` → three fields;
    `z,,` → `["z", "", ""]`.
  - **FR-7** A blank interior line yields a record of one empty field, `[""]`,
    per the FR-6 invariant. Blank lines are **not** skipped. (This deliberately
    differs from the stdlib `csv` module, which yields `[]` — see §2.4, where
    that module is forbidden anyway.)
  - **FR-8** A single record separator at the very end of `text` terminates the
    final record and does **not** create an extra empty row. Input without a
    trailing separator still yields its final record.
  - **FR-9** At top level, both `\r\n` and `\n` terminate a record, and `\r\n`
    counts as one separator, never two. A lone `\r` at top level that is not
    followed by `\n` is ordinary data. Mixed line endings within one document
    are supported.
  - **FR-10** Unicode-safe: parsing operates on `str` code points. Fields may
    contain any code point (non-BMP, combining marks, RTL marks) and are
    returned unchanged — no normalization, no encoding or decoding.
  - **FR-11** `delimiter` and `quotechar` are keyword-only, each exactly one
    character, and may be any character (e.g. `\t`, `;`, `|`, `'`). A value that
    is not a single character, or `delimiter == quotechar`, raises `ValueError`.
  - **FR-12** `quotechar` is significant only at the *start* of a field and
    within a quoted field. A quote inside an unquoted field is ordinary data:
    `a"b` → `a"b`.
  - **FR-13** The function is **pure**: no I/O, no globals, no mutation of
    arguments, no dependence on locale or platform newline mode. Equal inputs
    always return equal outputs.
- **1.5 Out of scope** — Type coercion (every field is `str`); header rows and
  `DictReader`-style mapping; serialization/writing; file, stream, or encoding
  handling; dialect sniffing; backslash-escape dialects; configuration knobs
  beyond the two parameters in §2.1; CSV-injection sanitization.
- **1.6 Ambiguities the agent must resolve**
  The spec deliberately does not fix these three. Each must be resolved,
  applied **consistently**, and **documented in the `parse_csv` docstring**.
  Both resolutions of each are fully acceptable; the acceptance suite pins only
  the behaviors that *every* resolution must satisfy, plus an
  internal-consistency probe (§6.3).

  | # | Ambiguity | Acceptable resolutions | What acceptance pins regardless |
  |---|-----------|------------------------|---------------------------------|
  | (a) | **Malformed input**, exemplified by an unterminated quoted field (`a,"bcd` with no closing quote). | **(a1)** raise `ValueError` naming the position (line and column, or absolute offset) of the offending quote; **or** **(a2)** best-effort recovery with a documented rule (e.g. treat end-of-input as an implicit closing quote). | No silent data loss: fields already accumulated are never dropped, and the row count must follow the documented rule (NFR-2). The *same* choice must apply to the sibling malformed construct — characters after a closing quote, e.g. `"ab"cd` — either both raise or both recover. |
  | (b) | **Whitespace around unquoted fields** — is ` a , b ` trimmed? | **(b1)** preserve surrounding whitespace verbatim; **or** **(b2)** strip leading/trailing whitespace of *unquoted* fields only. | Whitespace **inside quoted fields is always preserved** under either choice: `" a "` → `" a "`. Whichever is chosen applies uniformly to leading, interior, and trailing fields. |
  | (c) | **Leading UTF-8 BOM** (`U+FEFF`) at the start of `text`. | **(c1)** strip a single leading BOM before parsing; **or** **(c2)** treat it as ordinary data in the first field. | A BOM never affects record or field *counts*, and never affects any field other than the first field of the first record. |

  Resolving these by asking a human is an intervention (§8.2). Resolving them
  by silently picking a behavior and not documenting it fails the Definition of
  Done (§4.2) and caps `QUA`.

## 2. Technical Requirements
- **2.1 Interface / API contract**
  ```python
  # solution/csv_parser.py

  def parse_csv(
      text: str,
      *,
      delimiter: str = ",",
      quotechar: str = '"',
  ) -> list[list[str]]:
      """Parse RFC 4180-subset CSV text into rows of fields."""

  # Optional helper; if present it must obey the same quoting rules and must
  # not be the only public entrypoint.
  def parse_line(
      text: str,
      *,
      delimiter: str = ",",
      quotechar: str = '"',
  ) -> list[str]: ...
  ```
  `parse_csv` is **pure** (no I/O, no globals, no side effects) per FR-13.
- **2.2 Architecture constraints** — Single module, standard library only. No
  network, filesystem, or third-party packages. The parser must be a
  single-pass scanner over the input; whole-input regex matching or
  split-then-repair strategies are not acceptable structures (see NFR-1).
- **2.3 Data model** — N/A — stateless; the only "state" is scanner-local
  (in-quotes flag, current field buffer, current row buffer).
- **2.4 Technology constraints** — Python ≥ 3.11. No external dependencies.
  **The `csv` standard-library module is FORBIDDEN.** The task is to implement
  the parsing itself. This covers `import csv`, `from csv import ...`,
  `csv.reader`, `csv.DictReader`, and any dynamic equivalent
  (`importlib.import_module("csv")`, `__import__("csv")`), as well as any
  third-party CSV library. A static import-graph/AST scan runs at scoring time:
  a direct import is a **constraint violation → gate FAIL**; a dynamically
  obscured import is a `gaming_event` → run **disqualified**
  (`CONVERGENCE_METRICS.md` §6).
- **2.5 Entrypoint contract** — `kind: python-module`,
  `target: solution.csv_parser`. The harness imports `parse_csv` directly and
  calls it in-process; the function *is* the production path
  (`VERIFICATION_CONTRACT.md` §3).

## 3. Non-Functional Requirements
- **NFR-1 Performance** — Single linear pass, `O(n)` in the number of input
  code points, and streaming-friendly in shape: the scanner consumes the input
  once, left to right, with bounded lookahead (one character, for `\r\n` and
  `""`). No quadratic string building — accumulate field content in a list and
  `join`, or use index slicing; never repeatedly concatenate into an
  accumulating string inside the inner loop. Budget: a 5 MB / 50k-row fixture
  parses in < 3 s on the reference runner, and doubling input size must not
  increase parse time by more than ~2.5× (super-linear scaling fails this NFR).
- **NFR-2 Reliability & error handling** — Malformed input must never silently
  produce a wrong number of rows or fields. Under resolution (a1), the raised
  `ValueError` names the position of the fault; under (a2), the recovery rule is
  documented and yields a row/field count consistent with that rule. Parameter
  validation per FR-11 raises `ValueError` naming the offending value. Parsing
  is deterministic: the same input always yields the same output.
- **3.3 Security** — N/A — pure function with no I/O boundary, no `eval`, no
  deserialization. Untrusted-input hardening is covered by NFR-2, and the
  single-pass requirement of NFR-1 removes any regex-backtracking (ReDoS)
  surface by construction. CSV-injection sanitization is out of scope (§1.5).
- **3.4 Accessibility** — N/A — no UI.
- **NFR-3 Maintainability** — Passes `ruff` and `pyright` clean. `parse_csv`
  has a docstring stating the contract, the raised exceptions, **and the three
  §1.6 resolutions**. Cyclomatic complexity ≤ 12 per function (a state machine
  is legitimately branchier than L0's mapping; above 12 suggests duplicated
  branch logic rather than a coherent machine).
- **3.6 Observability** — N/A — library primitive. Exception messages are the
  only diagnostic surface, and they are covered by NFR-2.
- **NFR-4 Portability** — Zero-dependency; importable on any Python ≥ 3.11.
  Behavior must not depend on `os.linesep`, universal-newlines translation, or
  locale; the parser sees exactly the `str` it is handed.

## 4. The Ask (Deliverables & Definition of Done)
- **4.1 Required artifacts**
  - `solution/csv_parser.py` implementing FR-1..FR-13 and NFR-1..NFR-4.
  - A `parse_csv` docstring documenting all three resolved §1.6 ambiguities.
- **4.2 Definition of Done**
  - [ ] `smoke` tests pass.
  - [ ] `acceptance` suite passes at 100% (hard gate).
  - [ ] `ruff` + `pyright` clean; complexity ≤ 12 per function.
  - [ ] No import of `csv` (or any third-party CSV library) anywhere.
  - [ ] All three §1.6 ambiguities resolved, applied consistently, and
        documented in the `parse_csv` docstring.
- **4.3 Acceptance criteria**
  - AC-1 (FR-1/2/3/4/5/12): the quoting matrix parses correctly — quoted
    fields, doubled quotes, embedded delimiters, embedded newlines, and quotes
    inside unquoted fields.
  - AC-2 (FR-6/7/8): field- and row-count invariants hold — `n` delimiters →
    `n + 1` fields, blank lines yield `[""]`, trailing separator adds no row.
  - AC-3 (FR-9): `\r\n`, `\n`, and mixed-ending documents all yield identical
    row counts and identical field values.
  - AC-4 (FR-10/11): unicode fields round-trip unchanged; alternate
    `delimiter`/`quotechar` behave identically to the defaults; invalid
    parameters raise `ValueError`.
  - AC-5 (§1.6 + NFR-2): the chosen resolutions are internally consistent
    across the whole malformed/whitespace/BOM matrix, and no malformed input
    silently produces a wrong row count.
  - AC-6 (NFR-1): the 5 MB fixture completes within budget with sub-quadratic
    scaling.
  - AC-7 (NFR-3): static checks clean, docstring present and documenting §1.6.

## 5. Discovery & Design Activities
- **5.1 User research** — **N/A** — the format is well specified by RFC 4180 and
  the consumer is a calling programmer; there is no user need to discover
  (`ARTIFACT_GRADIENT.md` L1). Conducting research here would be theater.
- **5.2 Product design** — **Required (minimal):** the spec, FR/NFR set, and
  acceptance criteria in this document *are* the product artifact. No PRD, no
  user stories, no backlog at this rung.
- **5.3 Interaction/visual design** — **N/A** — no UI, and the API surface is
  fixed verbatim in §2.1; interface/contract design first becomes **Required**
  at L2. The only design-shaped work at L1 is the **light** contract decision
  forced by §1.6 (error policy, whitespace policy, BOM policy), which is
  delivered as a docstring, not as a design artifact.
- **5.4 Design artifacts to produce** — None. Nothing lands under `design/`.

## 6. Verification Method
- **6.1 Test tiers**
  - `smoke` (visible): 5 worked examples, chosen to demonstrate the constructs
    without revealing the §1.6 answers.
    ```python
    parse_csv("a,b,c\n1,2,3\n")        == [["a", "b", "c"], ["1", "2", "3"]]
    parse_csv('a,"b,c",d')             == [["a", "b,c", "d"]]
    parse_csv('"say ""hi"""')          == [['say "hi"']]
    parse_csv('x,"l1\nl2",y\r\nz,,\r\n') == [["x", "l1\nl2", "y"], ["z", "", ""]]
    parse_csv("a;b", delimiter=";")    == [["a", "b"]]
    ```
  - `acceptance` (held-out): a broad, deterministic matrix over the orthogonal
    dimensions below, plus the hypothesis property test (§6.3) and the §1.6
    consistency probe. Every cell is a fixed input/expected pair.

    | Family | Coverage |
    |--------|----------|
    | Quoting | unquoted, quoted, quoted-with-delimiter, quoted-with-newline, doubled quotes at start/middle/end, fully-empty quoted field `""`, quote inside unquoted field |
    | Empties | leading/interior/trailing empty fields, all-empty row `,,`, blank interior line, single blank line as whole input |
    | Line endings | LF-only, CRLF-only, mixed in one document, trailing separator present/absent, lone `\r` as data, `\r\n` inside a quoted field preserved verbatim |
    | Parameters | `delimiter` set to `\t`, `;`, or `\|`; `quotechar` set to `'`; non-default pairs combined; invalid parameter values → `ValueError` |
    | Unicode | non-BMP, combining marks, RTL, multi-byte delimiters' neighbors, a non-ASCII delimiter |
    | Invariants | `n` delimiters → `n + 1` fields across generated widths; row-count equality across LF/CRLF variants of the same document |
    | Ambiguity-safe | only the "pins" column of §1.6 — inside-quote whitespace preserved, BOM never changes counts, malformed input never loses accumulated fields |
    | Performance | 5 MB / 50k-row fixture within budget; 1 MB single quoted field; scaling ratio check (NFR-1) |

  - `adversarial` (hidden, run once): unterminated quoted field mid-document;
    unterminated quote at end of input; characters after a closing quote
    (`"ab"cd`); a lone `quotechar` as an entire field; mixed CRLF/LF with
    embedded newlines of the opposite kind; delimiter and newline both inside
    one quoted field; a 1 MB single field; leading BOM combined with a quoted
    first field; whitespace-padded unquoted fields; `"\r\n"` as the entire
    input; a document whose last line is a single unterminated quote.
- **6.2 "Working" definition** — 100% of the `acceptance` suite passes.
  `adversarial` never counts toward the gate but feeds `COR`/`ROB`
  (`RUBRIC_FRAMEWORK.md` §4).
- **6.3 Verification mechanics** — `pytest` unit tests plus a `hypothesis`
  property test. Real path = direct function call (the function *is*
  production).
  - **Property (round-trip):** generate a list of rows of arbitrary text →
    serialize with a **harness-owned** RFC 4180 serializer (never shipped to the
    agent) → `parse_csv` → assert equality with the original rows.
    ```python
    @given(rows=csv_rows())          # ≥1 row, ≥1 field/row, arbitrary text
    def test_round_trip(rows):
        assert parse_csv(serialize(rows)) == rows
    ```
    The generator deliberately excludes inputs governed by §1.6 so an
    ambiguity choice can never fail the property: no leading/trailing
    whitespace in unquoted-eligible fields, no `U+FEFF`, and the serializer
    always emits well-formed, fully-terminated quoting.
  - **§1.6 consistency probe:** the suite first *observes* which resolution the
    solution took (does the unterminated case raise, or recover?), then asserts
    the remainder of the malformed/whitespace/BOM matrix follows that **same**
    resolution. A solution that raises on one malformed construct and silently
    recovers on its sibling fails AC-5 even though either policy alone would
    have passed.
- **6.4 Anti-gaming measures** — The property test's random data makes
  hardcoding the five smoke examples fail immediately. The `csv`-import scan
  (§2.4) catches the shortcut that would trivialize the task. The adversarial
  tier probes constructs absent from smoke; a large `acceptance_pass` /
  `adversarial_pass` gap is an overfitting signal and caps `ROB`
  (`CONVERGENCE_METRICS.md` §6). Reading or writing outside the declared
  workspace to discover held-out tests disqualifies the run.

## 7. Scoring Rubric
- **7.1 Weight profile** (sum 100): `COR 55 · ROB 25 · EFF 5 · AUT 5 · QUA 10`.
  (`REG`/`FID` N/A at L1 — no prior behavior to protect, no product/design
  surface.) `ROB` is weighted 25 here, up from L0's 15, because edge cases and
  malformed input are the entire point of this rung.
- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | acceptance < 100% (gate fail) | 100% acceptance but misses adversarial constructs (e.g. `"ab"cd`, lone quotechar, mixed endings) | 100% acceptance + ≥95% adversarial |
  | ROB | crashes or silently returns wrong row/field counts on malformed input | handles unterminated quotes but inconsistently across sibling constructs, or BOM/whitespace policy leaks into counts | every §1.6 resolution applied consistently; malformed input either raises with position or recovers by the documented rule; no silent count corruption |
  | EFF | > hard cap (15) or over time budget | passed near the hard cap, or high `failed_runs_before_pass` | passed ≤ soft cap (6), ≤1 failed run |
  | AUT | any `rescue` | one `clarify` on a §1.6 ambiguity (the answer was deliberately withheld) | zero interventions; ambiguities resolved unilaterally and documented |
  | QUA | lint/type errors, or `csv` imported | clean but ambiguities undocumented, complexity > 12, or quadratic field accumulation | clean, single coherent state machine, docstring documents all three resolutions, linear single pass |
- **7.3 Hard gate** — `acceptance_floor = 1.0` (100%). Additionally, importing
  `csv` (§2.4) is a constraint violation that fails the gate outright
  regardless of test results.
- **7.4 Pass threshold** — **80**. Lower than L0's 85 because the ambiguity
  resolution legitimately costs iterations, but still high: this is a
  well-understood format and a strategy that thrashes here will not survive L2.

## 8. Convergence Signals
- **8.1 Healthy convergence** — ≤ 6 iterations, zero interventions. The trace
  shows the strategy naming the §1.6 ambiguities *early* — before or while
  implementing — choosing a policy, and writing it into the docstring in the
  same pass rather than discovering it via a failing test. The implementation
  arrives as one coherent character-scanner (in-quotes flag, field buffer, row
  buffer) rather than accreting special cases. Smoke passes on the first or
  second run; acceptance and adversarial pass together with a small gap.
- **8.2 Pathological patterns**
  - **Split-then-repair.** Splitting on `\n` and then attempting to re-join rows
    with unbalanced quote counts. Surfaces as many iterations touching the same
    few lines, high `oscillations`, and adversarial failures on embedded
    newlines even after acceptance-shaped cases pass.
  - **Regex escalation.** Successive rounds of a growing regex instead of a
    state machine. Surfaces as rising complexity, NFR-1 scaling failures, and
    catastrophic behavior on the 1 MB single-field adversarial case.
  - **Reaching for `csv`.** A direct import fails the gate (§7.3); a dynamically
    obscured one is a `gaming_event` and disqualifies the run.
  - **Asking for the answer.** Requesting a human decision on §1.6 is a
    `clarify` intervention; because L1 withholds that answer *by design*, any
    `clarify` here caps `AUT` at 2.
  - **Silent resolution.** Choosing a behavior for §1.6 but not documenting it —
    fails the Definition of Done (§4.2) and caps `QUA` at 2 even if all tests
    pass.
  - **Overfitting to the visible five.** Large `acceptance_pass` /
    `adversarial_pass` gap; caps `ROB` at 2.
- **8.3 Instrumentation notes** — Beyond the shared
  `CONVERGENCE_METRICS.md` set, capture into `score.json.notes`:
  (1) a `resolution_profile` recording which branch of §1.6 (a), (b), and (c)
  the solution took, so ambiguity choices are comparable across strategies;
  (2) whether each resolution was *documented* and whether it was *consistent*;
  (3) the iteration index at which the ambiguities were first acknowledged
  (early acknowledgement is the signal we are actually testing for at this
  rung); (4) parse time on the 5 MB fixture and the size-doubling ratio;
  (5) the result of the `csv` import scan.
