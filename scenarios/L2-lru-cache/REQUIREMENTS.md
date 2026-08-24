# L2 — LRU Cache — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`.
> Artifact obligations per `framework/ARTIFACT_GRADIENT.md` row **L2**.

## 0. Scenario Summary
- **Level:** L2
- **Codename / dir:** `L2-lru-cache`
- **One-liner:** Implement a capacity-bounded LRU (least-recently-used) cache with
  optional per-entry TTL and O(1) `get`/`put`.
- **New difficulty introduced:** Two firsts, arriving together.
  1. **First stateful unit.** Behavior now depends on *history*, not just the
     current argument. Correctness is a property of an operation *sequence*, so
     the strategy must reason about invariants rather than input→output pairs.
  2. **First required interface design.** The agent must design and document a
     contract (recency effects, expiry visibility, counter semantics) *before*
     implementing it — the first rung where design is a graded deliverable.
  Time semantics are made deterministic by an **injected clock**: no
  `time.sleep`, no wall-clock flakiness, eviction and expiry are fully
  reproducible.
- **Estimated reference solution size:** 120–200 LoC, 1 module + 1 contract doc.
- **Time budget:** 20 minutes wall-clock.
- **Iteration budget:** soft 8, hard 20 edit→verify cycles.
- **Intervention budget:** 0 (the §1.6 ambiguities are resolvable from this
  document; a `clarify` intervention here means the strategy did not read it).

## 1. Product Requirements
- **1.1 Problem statement** — Provide an in-process, dependency-free cache that
  bounds memory by a fixed entry count, evicts the least-recently-used entry
  when full, optionally expires entries after a time-to-live, and reports its own
  hit/miss/eviction behavior — with O(1) reads and writes so it can sit on a hot
  path without becoming the bottleneck it was added to remove.
- **1.2 Target users / personas** — N/A — the consumer is a calling programmer.
  Per `ARTIFACT_GRADIENT.md` row L2, the **interface contract speaks for the
  user**; there is no human-facing surface to research.
- **1.3 User stories** — N/A — no end-user surface. Replaced by the interface
  contract in §2.1 and the design deliverable in §5.4.
- **1.4 Functional requirements**
  - **FR-1 Construction & validation.** `LRUCache(capacity, ttl=None, *, clock=time.monotonic)`.
    Raise `ValueError` if `capacity` is not an integer or `capacity < 1`. Raise
    `ValueError` if `ttl` is negative. `ttl=None` means entries never expire.
    `ttl=0` is deliberately ambiguous — see §1.6.
  - **FR-2 Store & retrieve.** `put(key, value)` stores `value` under `key`.
    `get(key)` returns the value from the most recent `put` for that key while
    the entry is live, or `default` if the key is absent, evicted, or expired.
  - **FR-3 LRU eviction.** When the cache holds `capacity` live entries and a
    **new** key is inserted, exactly one entry — the least-recently-used — is
    evicted. `len(cache)` never exceeds `capacity` at any observable point.
  - **FR-4 Recency refresh on both reads and writes.** A **successful** `get`
    and **every** `put` (insert or update) mark the key most-recently-used. A
    `get` miss creates nothing and refreshes nothing. Recency ordering is a
    total order, so eviction is deterministic: with `capacity=N` and `N+1`
    distinct keys inserted and never read, the first key inserted is evicted.
  - **FR-5 `peek` is non-disturbing.** `peek(key)` returns the live value (or
    `default`) **without** changing recency and **without** recording a hit or a
    miss. A peek-only workload must produce the identical eviction sequence to
    the same workload with the peeks removed.
  - **FR-6 Update-in-place does not grow the cache.** `put` on an existing live
    key replaces the value and refreshes recency, leaving `len(cache)` unchanged
    and causing **no** eviction — even when the cache is exactly at capacity.
  - **FR-7 Optional TTL with lazy expiry.** When `ttl` is set, an entry whose age
    exceeds `ttl` (age measured per the §1.6 resolution, via the injected clock)
    is **absent**: `get`/`peek` return `default`, `key in cache` is `False`, and
    the entry is excluded from `len(cache)`. Expiry is **lazy** — detected on
    access rather than by a timer or background thread — but must be
    *observationally* immediate: no operation may ever surface an expired value.
  - **FR-8 `__len__` counts live entries only.** `len(cache)` returns the number
    of non-expired entries; expired-but-not-yet-reclaimed entries do not count.
  - **FR-9 `__contains__` is live-only and non-disturbing.** `key in cache` is
    `True` only for a present, non-expired entry, and — like `peek` — changes
    neither recency nor the counters.
  - **FR-10 Accounting.** `stats()` returns at least `hits`, `misses`, and
    `evictions` as non-negative, monotonically non-decreasing integers, where:
    - a `get` that returns a live value increments `hits`;
    - a `get` for an absent, evicted, **or expired** key increments `misses`;
    - therefore `hits + misses == (number of get calls)` — `put`, `peek`,
      `len`, and `in` never touch these two counters;
    - `evictions` counts **capacity-driven** removals only. Expiry-driven
      removal is **not** an eviction (an expired-key `get` is a miss, not an
      eviction). Reporting expirations separately is Optional/Stretch.
    The returned mapping is a snapshot: mutating it must not affect the cache.
  - **FR-11 Clock injection.** Every time read in the expiry path goes through
    the injected `clock` callable. The implementation must not call
    `time.monotonic`/`time.time`/`time.perf_counter` directly anywhere in
    `__init__`, `get`, `put`, `peek`, `__len__`, or `__contains__` — the only
    permitted reference to `time` is the **default value** of the `clock`
    parameter. The clock is assumed non-decreasing; the cache must behave
    correctly across arbitrarily large forward jumps.
  - **FR-12 Instance independence.** Two `LRUCache` instances share no state:
    no class-level mutable containers, no module globals, no cross-instance
    counters.
- **1.5 Out of scope** — Thread-safety guarantees (see NFR-5 — stance must be
  *documented*, implementation is Optional/Stretch); persistence or
  serialization; async/`await` APIs; byte- or weight-based capacity; non-LRU
  policies (LFU, ARC, 2Q, random); eager expiry via timers or background
  threads; eviction callbacks/listeners; a `functools.lru_cache`-style
  decorator; key namespacing; bulk/`update`/`pop`/`clear`/iteration APIs; stats
  reset. Adding any of these is scope creep and is penalized under `QUA`.
- **1.6 Ambiguities the agent must resolve**
  - **(A) Is TTL measured from insertion or from last access?** Both are real
    designs — "write TTL" (absolute lifetime) versus "sliding/idle TTL"
    (refreshed by reads). This document does not choose for you; you must
    choose, implement it consistently, and **declare** it:
    - **Default:** insertion-based. If you implement sliding TTL you MUST set a
      class attribute `ttl_policy = "sliding"` and say so in the class
      docstring; an undeclared implementation is scored as claiming
      `ttl_policy = "insertion"`.
    - The acceptance suite asserts the behavior the two policies **share**
      (insert → advance past ttl with no access → absent), and then reads
      `ttl_policy` to select the discriminating assertion (access at
      `0.5 * ttl`, advance another `0.75 * ttl`: still live under sliding,
      expired under insertion). A mismatch between declared policy and observed
      behavior is a **correctness failure**, not a style note.
  - **(B) What does `ttl=0` mean?** Two resolutions are acceptable, provided the
    docstring states which one you chose and the code matches:
    1. **Reject** — `ValueError` at construction (zero is not a meaningful
       lifetime); or
    2. **Immediate expiry** — construction succeeds, `put` succeeds, and the
       entry is never observable afterward (`get`/`peek`/`in` all report
       absent, `len` is 0).
    **Silently treating `ttl=0` as "no expiry" is a defect**, not a third
    resolution. It is the classic `if self.ttl:` falsy-check bug, it is
    explicitly probed by the adversarial tier, and it fails acceptance.

## 2. Technical Requirements
- **2.1 Interface / API contract**
  ```python
  # solution/lru_cache.py
  import time
  from collections.abc import Callable, Hashable, Mapping
  from typing import Any

  class LRUCache:
      """Capacity-bounded LRU cache with optional per-entry TTL.

      Docstring MUST state: the §1.6(A) TTL origin, the §1.6(B) ttl=0
      behavior, and the NFR-5 thread-safety stance.
      """

      ttl_policy: str = "insertion"   # "insertion" | "sliding"  — see §1.6(A)

      def __init__(
          self,
          capacity: int,
          ttl: float | None = None,
          *,
          clock: Callable[[], float] = time.monotonic,
      ) -> None: ...

      def get(self, key: Hashable, default: Any = None) -> Any: ...
      def put(self, key: Hashable, value: Any) -> None: ...
      def peek(self, key: Hashable, default: Any = None) -> Any: ...
      def __len__(self) -> int: ...
      def __contains__(self, key: object) -> bool: ...
      def stats(self) -> Mapping[str, int]: ...   # >= {"hits", "misses", "evictions"}
  ```
  `default` returns `None` unless supplied. Because `None` is itself a storable
  value, callers disambiguate "stored `None`" from "absent" with `in` — this
  must be stated in the `get`/`peek` docstrings.

  **Semantic matrix** (this table *is* the contract; the design deliverable in
  §5.4 must reproduce and justify it):

  | Method | Refreshes recency | Records hit/miss | Can surface an expired entry | May evict |
  |--------|-------------------|------------------|------------------------------|-----------|
  | `get(key)` | yes, on hit | **yes** | no | no |
  | `put(key, value)` | **always** | no | no (replaces expired entry) | yes, on new-key insert at capacity |
  | `peek(key)` | **no** | **no** | no | no |
  | `__len__()` | no | no | no (excludes expired) | no |
  | `__contains__(key)` | **no** | **no** | no | no |
  | `stats()` | no | no | n/a | no |

  **Exception contract:**

  | Condition | Behavior |
  |-----------|----------|
  | `capacity < 1` or non-integer capacity | `ValueError` |
  | `ttl < 0` | `ValueError` |
  | `ttl == 0` | `ValueError` **or** immediate-expiry — declared per §1.6(B) |
  | unhashable key | `TypeError` (propagated from the underlying mapping) |
  | `get`/`peek` miss | return `default` — **never** raise |

- **2.2 Architecture constraints** — Single module, standard library only. No
  network, filesystem, subprocess, or third-party packages. Either an
  `OrderedDict` (with `move_to_end`) or a hand-rolled dict + doubly-linked list
  is acceptable; a plain `dict` plus a per-operation scan for the LRU victim is
  **not** (violates NFR-1). `functools.lru_cache` may not be used as the
  eviction engine — it cannot express TTL, capacity introspection, or `stats()`
  as specified. Eviction must live at a **single choke point** (one private
  method), not be duplicated across `put` paths. No background threads, timers,
  signals, or `atexit` hooks.
- **2.3 Data model** — In-memory, per-instance, non-persistent.

  | Entity | Fields | Notes |
  |--------|--------|-------|
  | `Entry` | `value`, plus a time stamp sufficient for the declared TTL policy (`inserted_at` for insertion TTL, `last_access_at` for sliding) | Storing a precomputed `expires_at` is acceptable and preferred for insertion TTL |
  | Recency order | total order over live keys, MRU↔LRU | Must support O(1) move-to-MRU and O(1) pop-LRU |
  | Counters | `hits`, `misses`, `evictions` | Instance-scoped ints, monotonic |

- **2.4 Technology constraints** — Python ≥ 3.11. Zero runtime dependencies.
  `pytest`/`hypothesis` are harness-side only and must not appear in the
  solution's imports or requirements.
- **2.5 Entrypoint contract** — `kind: python-module`, `target:
  solution.lru_cache`. The harness executes `from solution.lru_cache import
  LRUCache` and constructs instances directly, always passing an explicit
  `clock=`. The class name, module path, and constructor keyword `clock` are
  fixed and non-negotiable.

## 3. Non-Functional Requirements
- **NFR-1 Performance** — `get`, `put`, `peek`, and `__contains__` are **O(1)
  amortized**; none may perform work proportional to `capacity` or to the number
  of live entries. `__len__` is O(1) when nothing has expired; it may do work
  proportional to the number of **currently expired, unreclaimed** entries,
  since each entry is reclaimed at most once (amortized O(1) per entry over the
  cache's lifetime). Evidence, in priority order:
  1. **Deterministic operation-count probe (primary).** Acceptance drives the
     cache with a key type that counts its own `__hash__`/`__eq__` calls. Per-op
     comparison counts must stay bounded by a small constant and must **not**
     grow with `capacity` across `capacity ∈ {8, 512, 8192}`. An O(n) victim
     scan fails this even though it is behaviorally correct.
  2. **Structure review.** Reviewer confirms an O(1) recency structure and the
     absence of `min`/`max`/`sorted`/full-container scans on hot paths.
  3. **Scaling probe (telemetry, corroborating only).** Median per-op wall time
     at `N=10^5` ≤ 3× the median at `N=10^3`. Recorded as telemetry and marked
     `flaky-guarded`; it never decides the gate on its own.
- **NFR-2 Reliability & error handling** — Two hard invariants, checked after
  *every* operation in the property suite: (a) `len(cache) <= capacity`, always;
  (b) no expired value is ever returned by `get` or `peek`, nor reported by `in`
  or counted by `len`. Invalid construction fails fast with a `ValueError` whose
  message names the offending parameter and value. `get`/`peek` never raise on a
  miss. Counters never decrease. Behavior is identical across arbitrarily large
  clock jumps.
- **3.3 Security** — N/A — in-process library with no untrusted I/O boundary
  beyond the input validation already required by NFR-2. Note for completeness:
  the capacity bound is itself the memory-exhaustion defense, so FR-3 doubles as
  the only security-relevant property here.
- **3.4 Accessibility** — N/A — no UI.
- **NFR-3 Maintainability** — Passes `ruff` and `pyright` clean. The class and
  **every** public method carry docstrings that state their recency effect,
  counter effect, and expiry visibility (i.e. the §2.1 matrix, in prose).
  Cyclomatic complexity ≤ 8 per method; module ≤ 250 LoC; eviction and expiry
  logic each exist exactly once. No commented-out code, no dead parameters.
- **3.6 Observability** — N/A as a service concern (no logs, metrics endpoints,
  or health checks at a library rung). The `stats()` counters are the in-scope
  substitute and are specified **functionally** as FR-10, not here, so they are
  gate-relevant rather than advisory.
- **NFR-4 Portability** — Zero-dependency; importable on any Python ≥ 3.11. The
  only environmental coupling is the default `clock`, and injection removes even
  that under test.
- **NFR-5 Thread safety** — **Optional/Stretch.** Single-threaded correctness is
  what is scored; an unsynchronized implementation is fully acceptable. What is
  **required** is that the class docstring states the stance ("not thread-safe"
  is a complete and acceptable answer). If a lock is added, it must not alter
  any single-threaded semantics above, must not appear on a path that can
  deadlock re-entrantly via a user-supplied `clock` or key `__hash__`, and its
  cost must not break NFR-1. Adding threading machinery *and* getting it wrong
  scores worse than honestly declaring the cache unsynchronized.

## 4. The Ask (Deliverables & Definition of Done)
- **4.1 Required artifacts**
  - `solution/lru_cache.py` — the `LRUCache` class implementing FR-1..FR-12.
  - `solution/design/API_CONTRACT.md` — the documented interface contract (the
    L2 design deliverable; contents specified in §5.4).
  - Docstrings recording the resolved §1.6(A) TTL origin, the §1.6(B) `ttl=0`
    behavior, and the NFR-5 thread-safety stance.
  - `ttl_policy` class attribute set consistently with the implementation.
- **4.2 Definition of Done**
  - [ ] `smoke` tests pass.
  - [ ] `acceptance` suite passes at 100% (hard gate).
  - [ ] `ruff` + `pyright` clean; complexity ≤ 8 per method.
  - [ ] `solution/design/API_CONTRACT.md` exists, is complete per §5.4, and
        **matches the shipped code** (declared TTL policy, `ttl=0` behavior,
        and the §2.1 semantic matrix all agree with observed behavior).
  - [ ] Both §1.6 ambiguities resolved and documented in the class docstring.
  - [ ] No direct `time.*` call outside the `clock` parameter default (FR-11).
  - [ ] No item from §1.5 implemented.
- **4.3 Acceptance criteria**
  - AC-1 (FR-1) — invalid `capacity`/`ttl` raise `ValueError`; valid ones construct.
  - AC-2 (FR-2, FR-3, FR-4) — eviction victim is always the LRU entry; `get` and
    `put` both refresh recency; eviction order is deterministic.
  - AC-3 (FR-5, FR-9) — `peek` and `in` change neither recency nor counters;
    peek-interleaved and peek-free workloads evict identically.
  - AC-4 (FR-6) — re-`put` of an existing key at capacity: size unchanged, zero
    evictions, value and recency updated.
  - AC-5 (FR-7, FR-8) — with the fake clock advanced past `ttl`, entries are
    absent from `get`, `peek`, `in`, and `len`; behavior matches the declared
    `ttl_policy`; `ttl=0` matches the declared §1.6(B) resolution.
  - AC-6 (FR-10) — `hits + misses == get-call count`; `evictions` equals
    capacity-driven removals exactly; `stats()` snapshot is inert.
  - AC-7 (FR-11, FR-12) — poisoned `time.*` module functions are never invoked;
    two instances do not interfere.
  - AC-8 (NFR-1) — per-op comparison counts do not grow with `capacity`.
  - AC-9 (NFR-2) — `len(cache) <= capacity` and "no expired value returned" hold
    across all randomized property sequences.
  - AC-10 (NFR-3, §5.4) — static checks clean, docstrings present and accurate,
    API contract document complete and consistent with the code.

## 5. Discovery & Design Activities
- **5.1 User research** — **N/A** — the consumer is a calling programmer and the
  cache's semantics are fully knowable up front (`ARTIFACT_GRADIENT.md` row L2:
  interviews, JTBD, personas all `—`). Running discovery here would be theater.
- **5.2 Product design** — **Required (minimal):** the spec, FRs, and acceptance
  criteria in this document *are* the product artifact. No PRD, no user stories,
  no backlog at this rung.
- **5.3 Interaction/visual design** — **N/A** for wireframes, hi-fi mockups,
  design tokens, and a11y annotations — there is no visual surface. **But
  interface/API contract design is Required**: L2 is the first rung where
  `ARTIFACT_GRADIENT.md` marks "Interface/API contract design" as **R**. The
  interface is the entire user experience of this deliverable, and its hard
  parts — does `get` mutate recency? does `peek` count as a hit? is an expired
  entry "absent" or "present-but-stale"? — are **design decisions**, not
  implementation details. They must be decided and written down *before* they
  are coded, because every one of them is load-bearing for the acceptance suite.
- **5.4 Design artifacts to produce**
  - `solution/design/API_CONTRACT.md`, containing all of:

    | # | Required content |
    |---|------------------|
    | 1 | Full signatures with type annotations (mirrors §2.1) |
    | 2 | The semantic matrix — per method: recency effect, counter effect, expired-entry visibility, eviction possibility |
    | 3 | Stated invariants (`len <= capacity`; no expired value ever returned; `hits + misses == get-call count`; counters monotonic) |
    | 4 | Exception contract table (which inputs raise what) |
    | 5 | The §1.6(A) TTL-origin decision **with a one-line rationale**, matching `ttl_policy` |
    | 6 | The §1.6(B) `ttl=0` decision with rationale |
    | 7 | Complexity guarantees per method (NFR-1) |
    | 8 | Thread-safety stance (NFR-5) |
    | 9 | At least two worked call sequences showing eviction and expiry |

  - **How it is scored, honestly:** the `FID` axis does not exist below L3, so
    this document's *presentation quality* is graded under **`QUA`**. Its
    *accuracy* is not a soft judgment: acceptance branches on the declared
    `ttl_policy` and probes the declared `ttl=0` behavior, so a contract that
    disagrees with the code fails the gate under **`COR`**. Writing the contract
    and then drifting from it is worse than not writing it — which is precisely
    the lesson this rung teaches.

## 6. Verification Method
- **6.1 Test tiers**
  - `smoke` (visible): 6 worked sequences the agent can self-check against.
    ```python
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1); c.put("b", 2); c.put("c", 3)      # 1. evicts "a" (LRU)
    assert c.get("a") is None and c.get("b") == 2 and len(c) == 2

    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1); c.put("b", 2); c.get("a"); c.put("c", 3)
    assert c.get("a") == 1 and c.get("b") is None    # 2. get refreshed "a"

    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1); c.put("b", 2); c.put("a", 9)
    assert len(c) == 2 and c.get("a") == 9 and c.stats()["evictions"] == 0  # 3.

    clk = FakeClock(); c = LRUCache(4, ttl=10.0, clock=clk)
    c.put("a", 1); assert c.get("a") == 1              # live at t=0
    clk.advance(10.1)                                  # 4. TTL expiry
    assert c.get("a") is None and "a" not in c and len(c) == 0
    # NB: smoke deliberately advances past ttl measured from the LAST access,
    # so this case holds under either §1.6(A) policy. The discriminating case
    # lives in acceptance.

    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1); c.put("b", 2); c.peek("a"); c.put("c", 3)
    assert c.peek("a") is None                        # 5. peek did NOT refresh

    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1); c.get("a"); c.get("zzz"); c.put("b", 2); c.put("c", 3)
    s = c.stats()                                      # 6. accounting
    assert (s["hits"], s["misses"], s["evictions"]) == (1, 1, 1)   # "a" evicted
    ```
  - `acceptance` (held-out): the full behavioral matrix — construction
    validation; eviction victim selection across capacities 1..8; `get`-refresh
    and `put`-refresh recency; `peek`/`in` non-disturbance (differential:
    peek-interleaved vs peek-free eviction sequences must be identical);
    update-at-capacity; TTL boundaries at `t < ttl`, `t == ttl`, `t > ttl`;
    `ttl=None`; the `ttl_policy`-branched discriminating TTL test; the declared
    `ttl=0` behavior; the full counter identity set; `stats()` snapshot
    inertness; `time.*` poisoning (FR-11); instance independence; plus the
    property/stateful suite and the NFR-1 comparison-count probe. Fully
    deterministic: fake clock only, no `sleep`, no randomness outside seeded
    Hypothesis.
  - `adversarial` (hidden, run once): `capacity=1` (every insert of a new key
    evicts; re-`put` of the same key does not); TTL boundary exactly at `ttl`
    (inclusive vs exclusive — either is accepted if consistent with the
    docstring, but flip-flopping between `get` and `peek` is not); re-`put` of
    an existing key while exactly at capacity; access → expire → reinsert the
    same key (must be live again, must not double-count); `peek`-then-`get`
    ordering effects on which key dies next; long interleaved
    put/get/peek/expire sequences with clock jumps; the `ttl=0` falsy trap;
    `ttl` as a large float and as an `int`; storing `None`, `0`, `False`, and
    `""` as values (must be distinguishable from "absent" via `in`);
    hash-colliding-but-equal keys (`1` vs `True`) treated as one key; unhashable
    key raising `TypeError`; `capacity` given as `0`, `-1`, `True`, `2.0`, or a
    string; a clock that jumps forward by `1e9`; mutating the object returned by
    `stats()`; two instances with different capacities used in lockstep.
  - **Property invariants** (Hypothesis, in `acceptance`), driven as a
    `RuleBasedStateMachine` over `put`/`get`/`peek`/`advance_clock`:
    | # | Invariant |
    |---|-----------|
    | P-1 | `len(cache) <= capacity` after every operation |
    | P-2 | with `capacity >= 2`, the key just successfully `get`/`put` is never the next key evicted |
    | P-3 | after advancing the clock past `ttl` with no further `put`, every key is absent from `get`, `peek`, and `in`, and `len == 0` |
    | P-4 | `hits + misses == get-call count`; for `ttl=None` workloads, `evictions == max(0, distinct_new_key_inserts - capacity)` |
    | P-5 | inserting a `peek` anywhere in a workload does not change the eviction sequence |
    | P-6 | a live `get(k)` returns exactly the value from the most recent `put(k, v)` |
- **6.2 "Working" definition** — 100% of the `acceptance` suite passes.
- **6.3 Verification mechanics** — `pytest` unit tests plus `hypothesis`
  property and stateful tests. The real path *is* the class (per
  `VERIFICATION_CONTRACT.md` §3, L0–L2), so direct construction and method calls
  are the production path — no mocks of the unit under test.
  - **Fake clock:** the harness injects `FakeClock` (`__call__` returns the
    current float; `advance(dt)` moves it forward). All time-dependent
    assertions are exact, not tolerance-based. `time.sleep` appears nowhere.
  - **Clock-injection enforcement:** acceptance monkeypatches
    `time.monotonic`/`time.time`/`time.perf_counter` to raise, then exercises a
    cache built with an explicit `clock=` — any direct time read fails loudly
    and deterministically (FR-11).
  - **Differential model testing:** the stateful machine runs the cache beside a
    deliberately naive O(n) list-based reference oracle and asserts equal
    observable behavior after every operation, so recency bugs surface as a
    concrete divergent sequence rather than a vague failure.
  - **Complexity probe:** `CountingKey` instances tally `__hash__`/`__eq__`
    calls; per-op counts are asserted flat across `capacity ∈ {8, 512, 8192}`.
- **6.4 Anti-gaming measures** — The visible smoke sequences are exactly the
  shape a strategy would be tempted to special-case, and they are useless as a
  lookup table: the stateful differential suite generates sequences no
  hardcoding can anticipate. `ttl_policy` branching means the agent cannot
  satisfy TTL by guessing a policy — it must declare one and match it. The
  comparison-count probe catches an implementation that is behaviorally perfect
  but secretly O(n), which is the one way to "pass" this rung while missing its
  point. `time.*` poisoning catches a fake clock that is accepted but ignored.
  A large gap between `acceptance_pass` and `adversarial_pass` caps `ROB` per
  `CONVERGENCE_METRICS.md` §6.

## 7. Scoring Rubric
- **7.1 Weight profile** (sum 100): `COR 45 · ROB 20 · EFF 12 · AUT 10 · QUA 13`.
  (`REG` N/A — no prior behavior to protect at this rung; `FID` N/A — the
  Product/Design Fidelity axis begins at L3, so the L2 design deliverable is
  scored under `QUA` for quality and under `COR` for accuracy, per §5.4.)
- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | acceptance < 100% (gate fail) — e.g. exceeds capacity, serves expired values, or `peek` refreshes recency | 100% acceptance but adversarial gaps: `capacity=1`, TTL boundary, or access→expire→reinsert misbehaves | 100% acceptance + ≥95% adversarial; declared `ttl_policy` and `ttl=0` behavior match the code exactly |
  | ROB | crashes or silently corrupts state on invalid input; counters drift | validates construction but fumbles a boundary (stored `None` indistinguishable from absent, `stats()` mutable, huge clock jump) | every documented invalid input raises the right exception with a naming message; all boundary and falsy-value traps handled |
  | EFF | > hard cap (20) or over time budget | passed near the hard cap, or high `failed_runs_before_pass` from oscillating on recency semantics | passed ≤ 8 iterations, under time budget, ≤ 1 failed run before pass |
  | AUT | any `rescue`, or a `clarify` that just asks which §1.6 option to take | one low-severity nudge, or one dead-end (e.g. abandoning a hand-rolled linked list mid-way) | zero interventions, zero dead-ends; §1.6 resolved unaided |
  | QUA | lint/type errors, or no `API_CONTRACT.md` | clean code but a thin contract doc, missing docstring semantics, duplicated eviction logic, or out-of-scope extras from §1.5 | clean + complete contract doc matching the code, per-method semantics documented, single eviction choke point, O(1) structure obvious on reading |
- **7.3 Hard gate** — `acceptance_floor = 1.0` (100%). The acceptance suite is
  fully deterministic (fake clock, seeded properties), so anything less than
  100% is a real defect, not noise.
- **7.4 Pass threshold** — **78.** Lower than L0's 85 because L2 legitimately
  costs more iterations (state and time semantics), but high enough that a
  strategy which brute-forces to green with a scan-based cache and no contract
  document lands below the line.

## 8. Convergence Signals
- **8.1 Healthy convergence** — Reads §1.6, picks both resolutions immediately
  and states them; writes `API_CONTRACT.md` (or at minimum the semantic matrix)
  *before* the first implementation edit; reaches for `OrderedDict` +
  `move_to_end` or a dict + doubly-linked list without deliberation; threads the
  injected clock through from the start rather than retrofitting it; ≤ 8
  iterations; typically one fix-up round on a TTL boundary or on excluding
  expired entries from `len`; zero interventions; adversarial ≥ 0.9.
- **8.2 Pathological patterns**
  | Pattern | How it surfaces in telemetry |
  |---------|------------------------------|
  | Recency-semantics oscillation (`get` refreshes → doesn't → does again) | `oscillations` > 0 concentrated on FR-4/FR-5 test names; the signature L2 failure |
  | Falsy-TTL bug (`if self.ttl:`) re-introduced after being fixed | `oscillations` on the `ttl=0` case; adversarial failure even when acceptance passes |
  | Behaviorally-correct but O(n) LRU scan | acceptance green except the comparison-count probe; flat wall-clock hides it, which is exactly why NFR-1 uses counts |
  | Expired entries still counted by `len`/`in` | acceptance failures cluster on FR-8/FR-9 while `get`/`put` tests stay green — a "half-implemented absence" signature |
  | Retrofitting the clock (direct `time.monotonic` first, injection bolted on later) | large `dead_ends`/diff churn; `time.*` poisoning test fails on the first acceptance run |
  | Contract drift (doc says insertion, code slides) | `COR` failure on the `ttl_policy`-branched test despite a polished document |
  | Scope creep from §1.5 (eviction callbacks, thread pool, decorator, `clear()`) | LoC well above the 120–200 band; `QUA` penalty; usually correlates with high iteration count |
  | Nondeterminism in the agent's own tests (`time.sleep`) | flaky smoke runs, inflated `failed_runs_before_pass` with no corresponding code change |
  | Coding to the six smoke sequences | acceptance ≫ smoke failure rate; stateful differential suite produces a short divergent sequence |
- **8.3 Instrumentation notes** — Beyond the shared `CONVERGENCE_METRICS.md` set:
  - **Design-first signal:** record whether `solution/design/API_CONTRACT.md`
    was written *before* the first edit to `lru_cache.py`. This is the first rung
    where design-before-code is measurable, and it is the single most
    interesting new datum L2 produces.
  - **Thrash attribution:** bucket failing-test names into `eviction/recency`,
    `ttl/expiry`, `stats`, and `validation`. L2 is the first rung where
    "algorithm thrash" and "semantics thrash" can be told apart; a strategy that
    burns iterations on semantics it could have decided once, up front, has a
    nameable weakness that will worsen at L4+.
  - **Complexity probe results:** persist the per-op comparison counts and the
    `N=10^3/10^4/10^5` per-op medians into telemetry even when they pass, so
    cross-strategy comparison can show *how* O(1) each solution actually is.
  - **Ambiguity handling:** record which §1.6 resolutions were chosen and
    whether they were stated before or after the implementation existed —
    post-hoc rationalization is a distinct failure mode from genuine design.
