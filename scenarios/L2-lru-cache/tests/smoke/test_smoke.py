"""Smoke tier (VISIBLE to the strategy). Not weight-bearing; a fast self-check."""

import pytest
from conftest import FakeClock
from lru import LRUCache


def test_smoke_put_get_basic():
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert len(c) == 2


def test_smoke_eviction_at_capacity():
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # capacity 2: evicts "a", the LRU entry
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert len(c) == 2
    assert c.stats()["evictions"] == 1


def test_smoke_update_existing_key_no_growth():
    c = LRUCache(2, clock=FakeClock())
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 99)  # update, not insert -> no eviction, no growth
    assert len(c) == 2
    assert c.get("a") == 99
    assert c.stats()["evictions"] == 0


def test_smoke_ttl_expiry_with_injected_clock():
    clk = FakeClock()
    c = LRUCache(4, ttl=10.0, clock=clk)
    c.put("a", 1)
    assert c.get("a") == 1  # live at t=0
    clk.advance(10.1)
    assert c.get("a") is None
    assert "a" not in c
    assert len(c) == 0


def test_smoke_capacity_less_than_one_raises():
    with pytest.raises(ValueError):
        LRUCache(0, clock=FakeClock())
    with pytest.raises(ValueError):
        LRUCache(-1, clock=FakeClock())
