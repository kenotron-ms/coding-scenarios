# L2 — LRU Cache — EVALUATION (human-readable grader)

The machine-readable grader is `rubric.yaml`; this is its readable companion.
See `framework/GRADING.md` for the contract and `framework/HARNESS.md` for how
to run it. This scenario's grader is proven the same way `L0-roman-numerals`
is: it passes on `reference/solution/` (gate PASS, high score) and fails on
`reference/solution_broken/` (gate FAIL, `acceptance_pass < 1.0`).

## How to run it

```
python framework/harness/run_scenario.py \
    --scenario scenarios/L2-lru-cache \
    --solution <produced-solution-dir> \
    [--telemetry telemetry.json] --strategy <name> \
    --out /tmp/<run-name>/
```

`COR/ROB` come from the tiers below; `EFF/AUT` from `--telemetry`; `QUA` from
the static floor (provisional) + grader agent (final); the gate is
`acceptance_pass == 1.0`.

Requires `hypothesis` on the grading host (harness-side dependency only; the
solution under test must remain stdlib-only — REQUIREMENTS §2.4).

## Fake clock

Every acceptance/adversarial test injects `conftest.FakeClock` (never
`time.sleep`, never wall-clock reads) via the mandatory `clock=` keyword —
`FakeClock()` returns a controllable float; `.advance(dt)` moves it forward.
`conftest.CountingKey` tallies `__hash__`/`__eq__` calls for the NFR-1
complexity probe. Both live in `tests/conftest.py` (importable from every
test file because pytest puts `tests/` on `sys.path` when it loads that
conftest).

## Check registry (denominators: acceptance = 26, adversarial = 16)

### Acceptance (held-out; defines "working"; gates at 100%)

| id | criterion | axis | proves | test |
|----|-----------|------|--------|------|
| L2-AC01 | AC-1 | ROB | invalid `capacity` (0, -1, `True`, `2.0`, str, `None`) raises `ValueError` | `test_invalid_capacity_raises` |
| L2-AC02 | AC-1 | ROB | negative `ttl` raises `ValueError` | `test_invalid_ttl_raises` |
| L2-AC03 | AC-1 | COR | valid capacity/ttl combos construct without error | `test_valid_construction_succeeds` |
| L2-AC04 | AC-2 | COR | eviction victim is always the LRU entry | `test_eviction_victim_is_lru` |
| L2-AC05 | AC-2 | COR | `get` refreshes recency | `test_get_refreshes_recency` |
| L2-AC06 | AC-2 | COR | `put` refreshes recency | `test_put_refreshes_recency` |
| L2-AC07 | AC-2 | COR | capacity `1..8`: first-inserted key evicted when never read | `test_deterministic_eviction_order_across_capacities` |
| L2-AC08 | AC-3 | COR | `peek` never refreshes recency or touches stats | `test_peek_does_not_refresh_or_count` |
| L2-AC09 | AC-3 | COR | `in` never refreshes recency or touches stats | `test_contains_does_not_refresh_or_count` |
| L2-AC10 | AC-3 | COR | peek-interleaved and peek-free workloads evict identically | `test_peek_interleaved_matches_peek_free_eviction` |
| L2-AC11 | AC-4 | COR | re-`put` of an existing key at capacity: no growth, no eviction | `test_update_existing_key_at_capacity_no_eviction` |
| L2-AC12 | AC-5 | COR | `ttl=None` entries never expire | `test_ttl_none_never_expires` |
| L2-AC13 | AC-5 | COR | expired entry absent from `get`/`peek`/`in`/`len` | `test_ttl_expiry_absent_from_all_views` |
| L2-AC14 | AC-5 | COR | boundary just-under-ttl alive, exactly-at-ttl expired (inclusive policy) | `test_ttl_boundary_exact_at_ttl` |
| L2-AC15 | AC-5 | COR | `ttl=0` → immediate expiry per the declared §1.6(B) resolution | `test_ttl_zero_immediate_expiry` |
| L2-AC16 | AC-5 | COR | `ttl_policy`-branched discriminating TTL test (insertion vs sliding) | `test_ttl_policy_declared_matches_insertion_behavior` |
| L2-AC17 | AC-6 | COR | `hits`/`misses` accounted correctly; `hits+misses == get calls` | `test_stats_hit_miss_accounting` |
| L2-AC18 | AC-6 | COR | expiry is a miss, not an eviction; `evictions` is capacity-driven only | `test_stats_eviction_count_capacity_driven_only` |
| L2-AC19 | AC-6 | ROB | `stats()` snapshot: mutating the return value doesn't affect the cache | `test_stats_snapshot_is_inert` |
| L2-AC20 | AC-7 | ROB | `time.monotonic`/`time.time`/`time.perf_counter` poisoned; only `clock=` is used | `test_clock_injection_enforced_time_poisoned` |
| L2-AC21 | AC-7 | ROB | two instances share no state | `test_instance_independence` |
| L2-AC22 | AC-8 | COR | per-op `__hash__`/`__eq__` counts flat across `capacity ∈ {8,512,8192}` | `test_op_comparison_counts_flat_across_capacity` |
| L2-AC23 | AC-9 | COR | Hypothesis `RuleBasedStateMachine` vs. a naive O(n) oracle: P-1/P-2/P-4/P-5/P-6 agree after every op | `test_stateful_invariants` |
| L2-AC24 | AC-9 | COR | random put/get sequences: counters match the naive oracle exactly (P-4) | `test_property_counters_consistent_with_naive_oracle` |
| L2-AC25 | AC-9 | COR | a live `get(k)` always returns the most recently `put(k, v)` value (P-6) | `test_property_get_returns_latest_put_value` |
| L2-AC26 | AC-10 | QUA | docstrings state TTL origin, `ttl=0` resolution, thread-safety stance | `test_docstrings_present_and_describe_semantics` |

### Adversarial (hidden; feeds COR/ROB; never gates — REQUIREMENTS §7.3)

| id | axis | proves | test |
|----|------|--------|------|
| L2-ADV01 | COR | `capacity=1`: every new-key insert evicts | `test_adv_capacity_one_always_evicts_new_key` |
| L2-ADV02 | COR | `capacity=1`: re-`put` of the same key never evicts | `test_adv_capacity_one_reput_same_key_no_evict` |
| L2-ADV03 | ROB | `get`/`peek` agree at the exact TTL boundary (no flip-flop) | `test_adv_ttl_boundary_inclusive_peek_and_get_agree` |
| L2-ADV04 | ROB | `ttl=0` falsy-check trap does not silently mean "no expiry" | `test_adv_ttl_zero_falsy_trap` |
| L2-ADV05 | COR | re-`put` of an existing key exactly at capacity: no eviction | `test_adv_reput_existing_key_exactly_at_capacity` |
| L2-ADV06 | COR | access → expire → reinsert same key: live again, no double-count | `test_adv_access_then_expire_then_reinsert` |
| L2-ADV07 | COR | peek-then-get ordering effects on which key dies next | `test_adv_peek_then_get_ordering_effects` |
| L2-ADV08 | COR | long interleaved put/get/peek/expire sequence with clock jumps | `test_adv_long_interleaved_sequence_with_clock_jumps` |
| L2-ADV09 | ROB | `ttl` as a large float and as an `int` are both valid | `test_adv_ttl_large_float_and_int_both_valid` |
| L2-ADV10 | ROB | stored `None`/`0`/`False`/`""` distinguishable from absent via `in` | `test_adv_falsy_values_distinguishable_from_absent` |
| L2-ADV11 | ROB | hash-colliding-but-equal keys (`1` vs `True`) treated as one key | `test_adv_hash_colliding_equal_keys_treated_as_one` |
| L2-ADV12 | ROB | unhashable key raises `TypeError` | `test_adv_unhashable_key_raises_typeerror` |
| L2-ADV13 | ROB | `capacity` as `0`, `-1`, `True`, `2.0`, or a string all raise | `test_adv_capacity_invalid_types_raise` |
| L2-ADV14 | ROB | a clock that jumps forward by `1e9` doesn't break the cache | `test_adv_huge_clock_jump` |
| L2-ADV15 | ROB | aggressively mutating (`.clear()`) the `stats()` return is inert | `test_adv_stats_snapshot_mutation_inert` |
| L2-ADV16 | COR | two instances with different capacities used in lockstep stay independent | `test_adv_two_instances_different_capacities_lockstep` |

`smoke` (visible, not weight-bearing): 5 worked sequences in `tests/smoke/`
(basic put/get, eviction at capacity, update-in-place, TTL expiry with the
injected clock, `capacity < 1` raises).

## Judge (QUA)

Static floor: `ruff` + `pyright` clean (floor failure ⇒ `QUA ≤ 1`). Graded 0–4
by the grader agent using the QUA template in `framework/GRADING.md §6`,
judging maintainability/clarity/structure only — correctness is `COR`. L2 has
no `FID` (the axis begins at L3; per REQUIREMENTS §5.4 the interface-contract
deliverable's *presentation* is judged under `QUA`, its *accuracy* under
`COR` via `L2-AC16`/`L2-AC26`).
