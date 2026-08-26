"""L2 broken mutant -- deliberately WRONG. Used to prove the grader discriminates.

Two intentional bugs, both named in REQUIREMENTS §8.2 as the signature L2
failure modes:

1. **Never evicts.** This is a plain `dict`, not an LRU structure -- `put`
   never checks `capacity` and never removes anything, so `len(cache)` grows
   without bound and `evictions` stays 0 forever.
2. **The classic falsy-`ttl` trap.** `if self.ttl:` treats `ttl=0` as "no
   expiry" instead of "immediate expiry" (§1.6(B)).

It must FAIL the gate (`acceptance_pass < 1.0`) and score 0 / Failed.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable, Mapping
from typing import Any


class LRUCache:
    """Broken: ignores capacity (never evicts) and mishandles ttl=0."""

    ttl_policy: str = "insertion"

    def __init__(
        self,
        capacity: int,
        ttl: float | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise ValueError(f"capacity must be an int >= 1, got {capacity!r}")
        if ttl is not None and ttl < 0:
            raise ValueError(f"ttl must be >= 0 or None, got {ttl!r}")
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock
        self.data: dict[Hashable, tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0
        self.evictions = 0  # BUG: capacity is never enforced, so this never grows

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key not in self.data:
            self.misses += 1
            return default
        value, ts = self.data[key]
        if (
            self.ttl and (self.clock() - ts) >= self.ttl
        ):  # BUG: ttl=0 is falsy -> "never expires"
            self.misses += 1
            return default
        self.hits += 1
        return value

    def put(self, key: Hashable, value: Any) -> None:
        # BUG: no capacity check, no eviction choke point at all.
        self.data[key] = (value, self.clock())

    def peek(self, key: Hashable, default: Any = None) -> Any:
        if key not in self.data:
            return default
        value, ts = self.data[key]
        if self.ttl and (self.clock() - ts) >= self.ttl:
            return default
        return value

    def __len__(self) -> int:
        return len(self.data)  # BUG: does not exclude expired entries

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def stats(self) -> Mapping[str, int]:
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}
