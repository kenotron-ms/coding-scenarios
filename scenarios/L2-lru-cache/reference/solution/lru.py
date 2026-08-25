"""Capacity-bounded LRU cache with optional per-entry TTL — L2 reference solution.

Used to sanity-check the grader: it MUST pass the gate and score high.
"""

from __future__ import annotations

import heapq
import itertools
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from typing import Any


class _Entry:
    """Internal record: a stored value plus its (optional) expiry timestamp."""

    __slots__ = ("expires_at", "seq", "value")

    def __init__(self, value: Any, expires_at: float | None, seq: int) -> None:
        self.value = value
        self.expires_at = expires_at
        self.seq = seq


class LRUCache:
    """Capacity-bounded least-recently-used cache with optional per-entry TTL.

    Recency: a successful `get` and every `put` (insert or update) mark the
    key most-recently-used; `peek` and `__contains__` never do.

    Counters: a `get` that returns a live value increments `hits`; a `get`
    for an absent/evicted/expired key increments `misses`. `put`, `peek`,
    `len`, and `in` never touch these two counters. `evictions` counts only
    capacity-driven removals; expiry is a miss, never an eviction.

    TTL origin (§1.6(A)): **insertion-based** (``ttl_policy = "insertion"``).
    Every `put` — insert or update — stamps a fresh `expires_at = clock() +
    ttl`; reads (`get`/`peek`) never extend an entry's life.

    ``ttl=0`` (§1.6(B)): **immediate expiry**. Construction and `put` both
    succeed, but the entry is expired the instant it is written (age >= 0
    holds immediately), so it is never observable again via `get`/`peek`/
    `in`/`len`. This is deliberately distinct from "no expiry" — the classic
    ``if self.ttl:`` falsy-check bug would (wrongly) treat `ttl=0` as
    unset.

    `default` (on `get`/`peek`) is returned verbatim for an absent, evicted,
    or expired key. Because `None` is itself a storable value, use
    ``key in cache`` to disambiguate "stored `None`" from "absent".

    Thread-safety (NFR-5): **not thread-safe**. No internal locking is
    performed; concurrent callers must synchronize externally.

    Complexity (NFR-1): `get`, `put`, `peek`, and `__contains__` are O(1)
    amortized (an `OrderedDict` gives O(1) `move_to_end`/`popitem`; the TTL
    heap gives O(log k) push/pop where k is the number of not-yet-reaped
    timed entries, amortized O(1) per entry reclaimed at most once over the
    cache's lifetime). `__len__` is O(1) when nothing has expired.
    """

    ttl_policy: str = "insertion"

    def __init__(
        self,
        capacity: int,
        ttl: float | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise ValueError(
                f"LRUCache: capacity must be an int >= 1, got {capacity!r}"
            )
        if ttl is not None and ttl < 0:
            raise ValueError(f"LRUCache: ttl must be >= 0 or None, got {ttl!r}")
        self._capacity = capacity
        self._ttl = ttl
        self._clock = clock
        self._store: OrderedDict[Hashable, _Entry] = OrderedDict()
        self._expiry_heap: list[tuple[float, int, Hashable]] = []
        self._seq_counter = itertools.count()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # -- internal helpers (single choke points for expiry / eviction) ----

    def _reap_expired(self) -> None:
        """Remove every entry whose TTL has elapsed as of `clock()` now.

        O(1) when the heap's earliest expiry is still in the future; O(k)
        for the k entries that actually become reclaimable at this call
        (each timed `put` is popped from the heap at most once, ever).
        """
        if self._ttl is None or not self._expiry_heap:
            return
        now = self._clock()
        heap = self._expiry_heap
        store = self._store
        while heap and heap[0][0] <= now:
            _expires_at, seq, key = heapq.heappop(heap)
            entry = store.get(key)
            if entry is not None and entry.seq == seq:
                del store[key]

    def _evict_if_needed(self) -> None:
        """Single eviction choke point: pop LRU entries while over capacity."""
        while len(self._store) > self._capacity:
            self._store.popitem(last=False)
            self._evictions += 1

    # -- public API --------------------------------------------------------

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value for `key`, or `default` if absent/expired.

        Recency: refreshes (moves `key` to most-recently-used) on a hit.
        Counters: hit -> `hits += 1`; miss -> `misses += 1`. Never raises.
        """
        self._reap_expired()
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return default
        self._store.move_to_end(key, last=True)
        self._hits += 1
        return entry.value

    def put(self, key: Hashable, value: Any) -> None:
        """Insert or update `key` -> `value`.

        Recency: always refreshes (moves to most-recently-used) and stamps a
        fresh TTL window (§1.6(A)). Counters: never touches hits/misses.
        Eviction: evicts the LRU entry only when this insert is a **new**
        key at capacity; an update never evicts and never grows the cache.
        """
        self._reap_expired()
        now = self._clock()
        expires_at = None if self._ttl is None else now + self._ttl
        seq = next(self._seq_counter)
        is_new_key = key not in self._store
        self._store[key] = _Entry(value, expires_at, seq)
        self._store.move_to_end(key, last=True)
        if expires_at is not None:
            heapq.heappush(self._expiry_heap, (expires_at, seq, key))
        if is_new_key:
            self._evict_if_needed()

    def peek(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value for `key` without affecting recency.

        Recency: never refreshes. Counters: never records a hit or a miss.
        Expiry: a peek on an expired entry may reclaim it (freeing memory)
        but this is not an eviction and does not reorder any other key.
        """
        self._reap_expired()
        entry = self._store.get(key)
        return default if entry is None else entry.value

    def __len__(self) -> int:
        """Count of live (non-expired) entries; O(1) when nothing expired."""
        self._reap_expired()
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        """True iff `key` is present and live. Non-disturbing: no recency
        or counter effect (mirrors `peek`)."""
        self._reap_expired()
        return key in self._store

    def stats(self) -> Mapping[str, int]:
        """Return a snapshot ``{"hits", "misses", "evictions"}``.

        The mapping is a fresh dict each call; mutating the return value
        never affects the cache's internal counters.
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }
