"""Adversarial tier (HIDDEN). Denominator = 16. Feeds COR/ROB; never the gate.

Each test targets one of the traps named in REQUIREMENTS §6.1's adversarial
bullet: capacity=1 edge, TTL boundary/falsy trap, recency-vs-counting
distinctions, hashing edge cases, and invalid-input edges.
"""

from __future__ import annotations

import pytest
from conftest import FakeClock
from lru import LRUCache


def test_adv_capacity_one_always_evicts_new_key():
    c = LRUCache(1, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)  # new key at capacity=1 -> "a" evicted
    assert "a" not in c
    assert c.get("b") == 2
    c.put("c", 3)  # "b" evicted
    assert "b" not in c
    assert c.stats()["evictions"] == 2


def test_adv_capacity_one_reput_same_key_no_evict():
    c = LRUCache(1, clock=FakeClock())
    c.put("a", 1)
    c.put("a", 2)  # re-put of the SAME key: update, not insert -> no eviction
    c.put("a", 3)
    assert c.get("a") == 3
    assert c.stats()["evictions"] == 0


def test_adv_ttl_boundary_inclusive_peek_and_get_agree():
    # Whichever inclusive/exclusive boundary policy is chosen, get and peek
    # must agree at the exact boundary (no flip-flopping between methods).
    clk = FakeClock()
    c = LRUCache(2, ttl=3.0, clock=clk)
    c.put("a", 1)
    clk.advance(3.0)  # exactly at ttl
    get_result = c.get("a", default="__MISS__")

    clk2 = FakeClock()
    c2 = LRUCache(2, ttl=3.0, clock=clk2)
    c2.put("a", 1)
    clk2.advance(3.0)
    peek_result = c2.peek("a", default="__MISS__")

    assert (get_result == "__MISS__") == (peek_result == "__MISS__")


def test_adv_ttl_zero_falsy_trap():
    # The classic bug: `if self.ttl:` silently treats ttl=0 as "no expiry".
    # ttl=0 must behave per the declared §1.6(B) resolution -- NOT as unset.
    c = LRUCache(2, ttl=0, clock=FakeClock())
    c.put("a", 1)
    assert len(c) == 0
    assert ("a" in c) is False
    assert c.peek("a", default="ABSENT") == "ABSENT"
    assert c.get("a", default="ABSENT") == "ABSENT"


def test_adv_reput_existing_key_exactly_at_capacity():
    c = LRUCache(3, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # now exactly at capacity
    c.put("b", 99)  # re-put an existing key while at capacity
    assert len(c) == 3
    assert c.stats()["evictions"] == 0
    assert c.get("b") == 99
    assert "a" in c and "c" in c


def test_adv_access_then_expire_then_reinsert():
    clk = FakeClock()
    c = LRUCache(2, ttl=5.0, clock=clk)
    c.put("a", 1)
    c.get("a")  # access while live
    clk.advance(10.0)  # now expired
    assert "a" not in c
    misses_before = c.stats()["misses"]
    c.put("a", 2)  # reinsert the SAME key after expiry
    assert "a" in c
    assert c.get("a") == 2  # live again, fresh value
    assert c.stats()["evictions"] == 0  # expiry-then-reinsert is not an eviction
    assert c.stats()["misses"] == misses_before  # reinsert must not double-count a miss


def test_adv_peek_then_get_ordering_effects():
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.peek("a")  # non-disturbing
    c.get("b")  # "b" refreshed -> "a" is now LRU
    c.put("c", 3)  # evicts "a", not "b"
    assert "a" not in c
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_adv_long_interleaved_sequence_with_clock_jumps():
    clk = FakeClock()
    c = LRUCache(3, ttl=4.0, clock=clk)
    c.put(1, "one")
    c.put(2, "two")
    c.peek(1)
    clk.advance(1.0)
    c.put(3, "three")
    c.get(2)
    clk.advance(2.0)
    c.put(4, "four")  # capacity 3: evicts LRU among live entries
    assert len(c) <= 3
    clk.advance(5.0)  # jump well past ttl for everything remaining
    assert len(c) == 0
    for k in (1, 2, 3, 4):
        assert k not in c


def test_adv_ttl_large_float_and_int_both_valid():
    c1 = LRUCache(2, ttl=1e12, clock=FakeClock())
    c1.put("a", 1)
    assert c1.get("a") == 1

    c2 = LRUCache(2, ttl=5, clock=FakeClock())  # int ttl
    c2.put("a", 1)
    assert c2.get("a") == 1


def test_adv_falsy_values_distinguishable_from_absent():
    c = LRUCache(4, clock=FakeClock())
    for k, v in (("none", None), ("zero", 0), ("false", False), ("empty", "")):
        c.put(k, v)
    for k, v in (("none", None), ("zero", 0), ("false", False), ("empty", "")):
        assert k in c
        assert c.get(k, default="SENTINEL") == v
    assert ("missing" in c) is False
    assert c.get("missing", default="SENTINEL") == "SENTINEL"


def test_adv_hash_colliding_equal_keys_treated_as_one():
    c = LRUCache(4, clock=FakeClock())
    c.put(1, "int-one")
    c.put(True, "bool-true")  # hash(1) == hash(True) and 1 == True
    assert len(c) == 1
    assert c.get(1) == "bool-true"
    assert c.get(True) == "bool-true"


def test_adv_unhashable_key_raises_typeerror():
    c = LRUCache(2, clock=FakeClock())
    with pytest.raises(TypeError):
        c.put([1, 2, 3], "value")
    with pytest.raises(TypeError):
        c.get([1, 2, 3])


def test_adv_capacity_invalid_types_raise():
    for bad in (0, -1, True, 2.0, "2"):
        with pytest.raises(ValueError):
            LRUCache(bad, clock=FakeClock())


def test_adv_huge_clock_jump():
    clk = FakeClock()
    c = LRUCache(2, ttl=10.0, clock=clk)
    c.put("a", 1)
    clk.advance(1e9)  # a clock that jumps forward by ~1e9
    assert c.get("a") is None
    assert len(c) == 0
    c.put("b", 2)  # cache remains usable after the huge jump
    assert c.get("b") == 2


def test_adv_stats_snapshot_mutation_inert():
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.get("a")
    snap1 = c.stats()
    snap1.clear()  # aggressively mutate the returned mapping
    snap2 = c.stats()
    assert snap2["hits"] == 1
    assert snap2["misses"] == 0
    assert snap2["evictions"] == 0


def test_adv_two_instances_different_capacities_lockstep():
    small = LRUCache(1, clock=FakeClock())
    big = LRUCache(4, clock=FakeClock())
    for i in range(5):
        small.put(i, i)
        big.put(i, i)
    assert len(small) == 1
    assert len(big) == 4
    assert small.stats()["evictions"] == 4
    assert big.stats()["evictions"] == 1
    assert 4 in small and 4 in big
    assert 0 not in small and 0 not in big
