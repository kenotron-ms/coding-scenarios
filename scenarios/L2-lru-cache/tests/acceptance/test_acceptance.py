"""Acceptance tier (HELD OUT). Denominator = 26 (see rubric.yaml). Defines "working".

One test function == one weight-bearing check (registry ids L2-AC.. in
rubric.yaml / EVALUATION.md). Fully deterministic: fake clock only, no
`time.sleep`, no unseeded randomness outside Hypothesis (which is itself
seeded/deterministic per its own default derandomization across CI runs is
not required at this rung -- see GRADING.md §8).
"""

from __future__ import annotations

import time as _time

import pytest
from conftest import CountingKey, FakeClock
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from lru import LRUCache

# --------------------------------------------------------------------------
# AC-1 (FR-1): invalid capacity/ttl raise ValueError; valid ones construct.
# --------------------------------------------------------------------------


def test_invalid_capacity_raises():  # L2-AC01
    for bad in (0, -1, True, False, 2.0, "3", None):
        with pytest.raises(ValueError):
            LRUCache(bad, clock=FakeClock())


def test_invalid_ttl_raises():  # L2-AC02
    for bad in (-1, -0.5, -100.0):
        with pytest.raises(ValueError):
            LRUCache(2, ttl=bad, clock=FakeClock())


def test_valid_construction_succeeds():  # L2-AC03
    LRUCache(1, clock=FakeClock())
    LRUCache(5, ttl=None, clock=FakeClock())
    LRUCache(5, ttl=0, clock=FakeClock())
    LRUCache(5, ttl=10.5, clock=FakeClock())
    LRUCache(1000, ttl=1, clock=FakeClock())


# --------------------------------------------------------------------------
# AC-2 (FR-2, FR-3, FR-4): eviction victim always LRU; get/put refresh
# recency; eviction order is deterministic.
# --------------------------------------------------------------------------


def test_eviction_victim_is_lru():  # L2-AC04
    c = LRUCache(3, clock=FakeClock())
    for k in ("a", "b", "c"):
        c.put(k, k)
    c.put("d", "d")  # evicts "a", the LRU entry
    assert "a" not in c
    assert c.get("b") == "b"
    assert c.get("c") == "c"
    assert c.get("d") == "d"
    assert c.stats()["evictions"] == 1


def test_get_refreshes_recency():  # L2-AC05
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # "a" now MRU, "b" becomes LRU
    c.put("c", 3)  # evicts "b"
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_put_refreshes_recency():  # L2-AC06
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 99)  # update -> "a" now MRU
    c.put("c", 3)  # evicts "b" (LRU), NOT "a"
    assert c.get("a") == 99
    assert c.get("b") is None
    assert c.get("c") == 3


def test_deterministic_eviction_order_across_capacities():  # L2-AC07
    for capacity in range(1, 9):
        c = LRUCache(capacity, clock=FakeClock())
        for i in range(capacity + 1):
            c.put(i, i)
        # N+1 distinct keys, never read: the FIRST key inserted is evicted.
        assert 0 not in c
        for i in range(1, capacity + 1):
            assert i in c
        assert c.stats()["evictions"] == 1


# --------------------------------------------------------------------------
# AC-3 (FR-5, FR-9): peek/in change neither recency nor counters;
# peek-interleaved and peek-free workloads evict identically.
# --------------------------------------------------------------------------


def test_peek_does_not_refresh_or_count():  # L2-AC08
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    before = c.stats()
    assert c.peek("a") == 1
    assert c.stats() == before
    c.put("c", 3)  # peek must NOT have refreshed "a" -> "a" is still LRU
    assert "a" not in c
    assert c.get("b") == 2


def test_contains_does_not_refresh_or_count():  # L2-AC09
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    before = c.stats()
    assert ("a" in c) is True
    assert c.stats() == before
    c.put("c", 3)  # "in" must NOT have refreshed "a"
    assert "a" not in c


def test_peek_interleaved_matches_peek_free_eviction():  # L2-AC10
    def run(with_peeks: bool) -> dict:
        c = LRUCache(3, clock=FakeClock())
        for k in ("a", "b", "c"):
            c.put(k, k)
        if with_peeks:
            c.peek("a")
            c.peek("b")
            c.peek("zzz")
        c.put("d", "d")
        c.put("e", "e")
        return {k: (k in c) for k in ("a", "b", "c", "d", "e")}

    assert run(True) == run(False)


# --------------------------------------------------------------------------
# AC-4 (FR-6): re-put of an existing key at capacity: size unchanged, zero
# evictions, value and recency updated.
# --------------------------------------------------------------------------


def test_update_existing_key_at_capacity_no_eviction():  # L2-AC11
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 42)  # exactly at capacity; update, not insert
    assert len(c) == 2
    assert c.stats()["evictions"] == 0
    assert c.get("a") == 42
    assert c.get("b") == 2


# --------------------------------------------------------------------------
# AC-5 (FR-7, FR-8): TTL absence from get/peek/in/len at the boundaries;
# ttl_policy-branched behavior; the declared ttl=0 resolution.
# --------------------------------------------------------------------------


def test_ttl_none_never_expires():  # L2-AC12
    clk = FakeClock()
    c = LRUCache(2, ttl=None, clock=clk)
    c.put("a", 1)
    clk.advance(10**9)
    assert c.get("a") == 1
    assert "a" in c
    assert len(c) == 1


def test_ttl_expiry_absent_from_all_views():  # L2-AC13
    clk = FakeClock()
    c = LRUCache(2, ttl=5.0, clock=clk)
    c.put("a", 1)
    clk.advance(5.0001)
    assert c.get("a") is None
    assert c.peek("a") is None
    assert ("a" in c) is False
    assert len(c) == 0


def test_ttl_boundary_exact_at_ttl():  # L2-AC14
    clk = FakeClock()
    c = LRUCache(2, ttl=5.0, clock=clk)
    c.put("a", 1)
    clk.advance(4.999999)
    assert c.get("a") == 1  # still alive just under ttl

    clk2 = FakeClock()
    c2 = LRUCache(2, ttl=5.0, clock=clk2)
    c2.put("a", 1)
    clk2.advance(5.0)  # exactly at ttl -- reference policy is inclusive
    assert c2.get("a") is None


def test_ttl_zero_immediate_expiry():  # L2-AC15
    c = LRUCache(2, ttl=0, clock=FakeClock())
    c.put("a", 1)  # construction and put both succeed
    assert c.get("a") is None
    assert c.peek("a") is None
    assert ("a" in c) is False
    assert len(c) == 0


def test_ttl_policy_declared_matches_insertion_behavior():  # L2-AC16
    assert LRUCache.ttl_policy in ("insertion", "sliding")
    clk = FakeClock()
    ttl = 10.0
    c = LRUCache(4, ttl=ttl, clock=clk)
    c.put("a", 1)
    clk.advance(ttl * 0.5)
    assert c.get("a") == 1  # still alive at half-life
    clk.advance(ttl * 0.75)  # total age since the put is now 1.25 * ttl
    result = c.get("a")
    if LRUCache.ttl_policy == "insertion":
        assert result is None  # insertion TTL: the 0.5*ttl read did not extend it
    else:
        assert result == 1  # sliding TTL: the read refreshed the window


# --------------------------------------------------------------------------
# AC-6 (FR-10): hits + misses == get-call count; evictions == capacity-driven
# removals only; stats() snapshot is inert.
# --------------------------------------------------------------------------


def test_stats_hit_miss_accounting():  # L2-AC17
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.get("a")  # hit
    c.get("zzz")  # miss
    c.get("a")  # hit
    c.put("b", 2)
    c.put("c", 3)  # evicts "a"
    c.get("a")  # miss (evicted)
    s = c.stats()
    assert s["hits"] == 2
    assert s["misses"] == 2
    assert s["hits"] + s["misses"] == 4  # number of get() calls above


def test_stats_eviction_count_capacity_driven_only():  # L2-AC18
    clk = FakeClock()
    c = LRUCache(2, ttl=5.0, clock=clk)
    c.put("a", 1)
    c.put("b", 2)
    clk.advance(10.0)  # both expire -- NOT an eviction
    assert c.get("a") is None
    assert c.get("b") is None
    assert c.stats()["evictions"] == 0
    c.put("c", 3)
    c.put("d", 4)
    c.put("e", 5)  # capacity-driven: evicts "c"
    assert c.stats()["evictions"] == 1


def test_stats_snapshot_is_inert():  # L2-AC19
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.get("a")
    snap = c.stats()
    snap["hits"] = 999999
    snap["evictions"] = 999999
    snap["bogus"] = 1
    fresh = c.stats()
    assert fresh["hits"] == 1
    assert fresh["evictions"] == 0
    assert "bogus" not in fresh


# --------------------------------------------------------------------------
# AC-7 (FR-11, FR-12): time.* poisoning; instance independence.
# --------------------------------------------------------------------------


def test_clock_injection_enforced_time_poisoned(monkeypatch):  # L2-AC20
    def _poison(*_a, **_kw):
        raise AssertionError("direct time.* call detected -- clock must be injected")

    monkeypatch.setattr(_time, "monotonic", _poison)
    monkeypatch.setattr(_time, "time", _poison)
    monkeypatch.setattr(_time, "perf_counter", _poison)

    clk = FakeClock()
    c = LRUCache(3, ttl=5.0, clock=clk)
    c.put("a", 1)
    c.get("a")
    c.peek("a")
    assert "a" in c
    assert len(c) == 1
    clk.advance(1.0)
    c.put("b", 2)
    c.get("a")


def test_instance_independence():  # L2-AC21
    c1 = LRUCache(2, clock=FakeClock())
    c2 = LRUCache(5, clock=FakeClock())
    c1.put("a", 1)
    c1.put("b", 2)
    c1.put("c", 3)  # c1 at capacity 2 -> evicts "a"
    assert len(c1) == 2
    assert len(c2) == 0
    assert c2.stats() == {"hits": 0, "misses": 0, "evictions": 0}
    assert c1.stats()["evictions"] == 1
    assert "a" not in c2  # c2 was never touched
    c2.put("a", "different-value")
    assert c2.get("a") == "different-value"
    assert c1.get("a") is None  # c1 unaffected by c2


# --------------------------------------------------------------------------
# AC-8 (NFR-1): per-op comparison counts do not grow with capacity.
# --------------------------------------------------------------------------


def test_op_comparison_counts_flat_across_capacity():  # L2-AC22
    counts = {}
    for capacity in (8, 512, 8192):
        c = LRUCache(
            capacity, clock=FakeClock()
        )  # ttl=None: isolates the LRU structure
        keys = [CountingKey(i) for i in range(capacity)]
        for k in keys:
            c.put(k, k.value)
        CountingKey.reset()
        c.get(keys[0])
        c.put(keys[1], 999)
        c.peek(keys[2])
        _ = keys[3] in c
        counts[capacity] = CountingKey.total()
    assert len(set(counts.values())) == 1, (
        f"comparison counts grew with capacity: {counts}"
    )


# --------------------------------------------------------------------------
# AC-9 (NFR-2): property/stateful invariants over randomized sequences.
# --------------------------------------------------------------------------


class _NaiveOracle:
    """Deliberately O(n) reference model, used only to differentially check
    the real cache's OBSERVABLE behavior (REQUIREMENTS §6.3)."""

    def __init__(self, capacity: int, ttl: float | None, clock) -> None:
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock
        self.entries: list[list] = []  # [key, value, inserted_at]; MRU at the end
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _purge_expired(self) -> None:
        if self.ttl is None:
            return
        now = self.clock()
        self.entries = [e for e in self.entries if now - e[2] < self.ttl]

    def _find(self, key) -> int | None:
        for i, e in enumerate(self.entries):
            if e[0] == key:
                return i
        return None

    def get(self, key, default=None):
        self._purge_expired()
        i = self._find(key)
        if i is None:
            self.misses += 1
            return default
        entry = self.entries.pop(i)
        self.entries.append(entry)
        self.hits += 1
        return entry[1]

    def put(self, key, value) -> None:
        self._purge_expired()
        now = self.clock()
        i = self._find(key)
        is_new = i is None
        if i is not None:
            self.entries.pop(i)
        self.entries.append([key, value, now])
        if is_new and len(self.entries) > self.capacity:
            self.entries.pop(0)
            self.evictions += 1

    def peek(self, key, default=None):
        self._purge_expired()
        i = self._find(key)
        return default if i is None else self.entries[i][1]

    def __len__(self) -> int:
        self._purge_expired()
        return len(self.entries)

    def __contains__(self, key) -> bool:
        self._purge_expired()
        return self._find(key) is not None

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}


_SM_CAPACITY = 4
_SM_TTL = 5.0
_SM_KEYS = list(range(6))


class _LRUMachine(RuleBasedStateMachine):
    """Runs the real cache beside `_NaiveOracle` and asserts they agree after
    every operation (P-1, P-2, P-4, P-5, P-6)."""

    def __init__(self) -> None:
        super().__init__()
        self.clock = FakeClock()
        self.cache = LRUCache(_SM_CAPACITY, ttl=_SM_TTL, clock=self.clock)
        self.oracle = _NaiveOracle(_SM_CAPACITY, _SM_TTL, self.clock)

    @rule(k=st.sampled_from(_SM_KEYS), v=st.integers(min_value=-100, max_value=100))
    def do_put(self, k, v) -> None:
        self.cache.put(k, v)
        self.oracle.put(k, v)

    @rule(k=st.sampled_from(_SM_KEYS))
    def do_get(self, k) -> None:
        r1 = self.cache.get(k, default="__MISS__")
        r2 = self.oracle.get(k, default="__MISS__")
        assert r1 == r2, (k, r1, r2)

    @rule(k=st.sampled_from(_SM_KEYS))
    def do_peek(self, k) -> None:
        r1 = self.cache.peek(k, default="__MISS__")
        r2 = self.oracle.peek(k, default="__MISS__")
        assert r1 == r2, (k, r1, r2)

    @rule(
        dt=st.floats(
            min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False
        )
    )
    def do_advance(self, dt) -> None:
        self.clock.advance(dt)

    @invariant()
    def matches_oracle_and_capacity(self) -> None:
        assert len(self.cache) <= _SM_CAPACITY  # P-1
        assert len(self.cache) == len(self.oracle)
        for k in _SM_KEYS:
            assert (k in self.cache) == (k in self.oracle)
        cs, os_ = self.cache.stats(), self.oracle.stats()
        assert cs["hits"] == os_["hits"]
        assert cs["misses"] == os_["misses"]
        assert cs["evictions"] == os_["evictions"]


test_stateful_invariants = _LRUMachine.TestCase  # L2-AC23
test_stateful_invariants.settings = settings(
    max_examples=60, stateful_step_count=40, deadline=None, derandomize=True
)


@given(
    ops=st.lists(
        st.one_of(
            st.tuples(
                st.just("put"),
                st.integers(0, 5),
                st.integers(min_value=-50, max_value=50),
            ),
            st.tuples(st.just("get"), st.integers(0, 5)),
        ),
        max_size=150,
    )
)
@settings(max_examples=80, deadline=None, derandomize=True)
def test_property_counters_consistent_with_naive_oracle(ops):  # L2-AC24
    capacity = 4
    clk = FakeClock()
    cache = LRUCache(capacity, clock=clk)
    oracle = _NaiveOracle(capacity, None, clk)
    get_calls = 0
    for op in ops:
        if op[0] == "put":
            _, k, v = op
            cache.put(k, v)
            oracle.put(k, v)
        else:
            _, k = op
            cache.get(k)
            oracle.get(k)
            get_calls += 1
    s1, s2 = cache.stats(), oracle.stats()
    assert s1["hits"] == s2["hits"]
    assert s1["misses"] == s2["misses"]
    assert s1["evictions"] == s2["evictions"]
    assert s1["hits"] + s1["misses"] == get_calls  # P-4


@given(values=st.lists(st.integers(), min_size=1, max_size=30))
@settings(max_examples=100, deadline=None, derandomize=True)
def test_property_get_returns_latest_put_value(values):  # L2-AC25
    c = LRUCache(10, clock=FakeClock())  # capacity >> 1 key used: no eviction risk
    for v in values:
        c.put("k", v)
        assert c.get("k") == v  # P-6


# --------------------------------------------------------------------------
# AC-10 (NFR-3): docstrings present and describe the required semantics.
# --------------------------------------------------------------------------


def test_docstrings_present_and_describe_semantics():  # L2-AC26
    assert LRUCache.__doc__ and len(LRUCache.__doc__.strip()) > 0
    doc_lower = LRUCache.__doc__.lower()
    assert "insertion" in doc_lower or "sliding" in doc_lower  # §1.6(A) declared
    assert "immediate" in doc_lower or "ttl=0" in doc_lower or "ttl = 0" in doc_lower
    assert "thread" in doc_lower  # NFR-5 stance stated
    for name in ("get", "put", "peek", "stats"):
        method = getattr(LRUCache, name)
        assert method.__doc__ and len(method.__doc__.strip()) > 0
