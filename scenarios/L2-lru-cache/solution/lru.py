"""Capacity-bounded LRU cache with optional per-entry TTL.

TTL origin (§1.6(A)): **insertion-based** (``ttl_policy = "insertion"``).
Every ``put`` — insert or update — stamps a fresh ``expires_at = clock() +
ttl``; reads (``get``/``peek``) never extend an entry's life.

``ttl=0`` (§1.6(B)): **immediate expiry**. Construction and ``put`` both
succeed, but the entry is expired the instant it is written (age >= 0 holds
immediately), so it is never observable again via ``get``/``peek``/``in``/
``len``. This is deliberately distinct from "no expiry" — the classic
``if self.ttl:`` falsy-check bug would (wrongly) treat ``ttl=0`` as unset.

Thread-safety (NFR-5): **not thread-safe**. No internal locking is
performed; concurrent callers must synchronize externally.

Complexity (NFR-1): ``get``, ``put``, ``peek``, and ``__contains__`` are
O(1) amortized (an ``OrderedDict`` gives O(1) ``move_to_end``/``popitem``).
``__len__`` is O(n) in expired-but-unreclaimed entries (lazy expiry), but
amortized O(1) per entry over lifetime.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from typing import Any


class LRUCache:
    """Capacity-bounded least-recently-used cache with optional per-entry TTL.

    Recency: a successful ``get`` and every ``put`` (insert or update) mark
    the key most-recently-used; ``peek`` and ``__contains__`` never do.

    Counters: a ``get`` that returns a live value increments ``hits``; a
    ``get`` for an absent/evicted/expired key increments ``misses``. ``put``,
    ``peek``, ``len``, and ``in`` never touch these two counters. ``evictions``
    counts only capacity-driven removals; expiry is a miss, never an eviction.

    TTL origin (§1.6(A)): **insertion-based** (``ttl_policy = "insertion"``).
    Every ``put`` stamps a fresh ``expires_at = clock() + ttl``; reads never
    extend an entry's life.

    ``ttl=0`` (§1.6(B)): **immediate expiry**. Construction and ``put`` both
    succeed, but the entry is expired the instant it is written, so it is
    never observable via ``get``/``peek``/``in``/``len``.

    Thread-safety (NFR-5): **not thread-safe**. No internal locking is
    performed; concurrent callers must synchronize externally.

    Complexity (NFR-1): ``get``, ``put``, ``peek``, and ``__contains__`` are
    O(1) amortized. ``__len__`` is O(n) in expired-but-unreclaimed entries
    (lazy expiry), amortized O(1) per entry over lifetime.
    """

    ttl_policy: str = "insertion"

    def __init__(
        self,
        capacity: int,
        ttl: float | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(capacity) is not int:
            raise ValueError(
                f"LRUCache: capacity must be an int >= 1, got {capacity!r}"
            )
        if capacity < 1:
            raise ValueError(
                f"LRUCache: capacity must be an int >= 1, got {capacity!r}"
            )
        if ttl is not None and ttl < 0:
            raise ValueError(
                f"LRUCache: ttl must be >= 0 or None, got {ttl!r}"
            )
        self._capacity = capacity
        self._ttl = ttl
        self._clock = clock
        # _cache maps key -> (value, expires_at)
        # OrderedDict maintains insertion order; MRU is at the end (last=True).
        self._cache: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # -- internal helpers --------------------------------------------------

    def _is_expired(self, expires_at: float) -> bool:
        """Return True if the entry has expired (clock() >= expires_at)."""
        return self._clock() >= expires_at

    def _evict(self) -> None:
        """Remove the LRU entry from _cache and increment _evictions.

        This is the single eviction choke point.
        """
        self._cache.popitem(last=False)
        self._evictions += 1

    # -- public API --------------------------------------------------------

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value for ``key``, or ``default`` if absent/expired.

        Recency: refreshes (moves ``key`` to most-recently-used) on a hit.
        Counters: hit -> ``hits += 1``; miss -> ``misses += 1``.
        Expiry visibility: expired entries are treated as absent (miss).
        Eviction: never triggers eviction.
        """
        if key not in self._cache:
            self._misses += 1
            return default
        value, expires_at = self._cache[key]
        if self._is_expired(expires_at):
            del self._cache[key]
            self._misses += 1
            return default
        self._cache.move_to_end(key, last=True)
        self._hits += 1
        return value

    def put(self, key: Hashable, value: Any) -> None:
        """Insert or update ``key`` -> ``value``.

        Recency: always refreshes (moves to most-recently-used) and stamps a
        fresh TTL window (§1.6(A) insertion-based TTL).
        Counters: never touches hits/misses.
        Eviction: evicts the LRU entry only when this insert is a **new** key
        and the number of live entries equals capacity; an update never evicts.
        Expiry visibility: expired entries at the LRU end are silently removed
        without counting as evictions before a capacity-driven eviction occurs.
        """
        now = self._clock()
        expires_at = float('inf') if self._ttl is None else now + self._ttl

        # If key already exists, remove it (no eviction counted).
        if key in self._cache:
            del self._cache[key]
            # Re-insert at MRU end with new expires_at.
            self._cache[key] = (value, expires_at)
            self._cache.move_to_end(key, last=True)
            return

        # New key: check if we need to evict.
        # Count live entries (non-expired) to determine if at capacity.
        # Simpler approach: pop expired entries from front, then evict if needed.
        # We need to ensure live count < capacity before inserting.
        # Strategy: while len >= capacity, pop from front; if popped entry is
        # expired, don't count as eviction; if live, count as eviction.
        while len(self._cache) >= self._capacity:
            # Peek at the front (LRU) entry
            front_key, (front_value, front_expires_at) = next(iter(self._cache.items()))
            if self._is_expired(front_expires_at):
                # Expired entry: remove without counting as eviction
                del self._cache[front_key]
            else:
                # Live entry: this is a real eviction
                self._evict()
                break

        self._cache[key] = (value, expires_at)
        self._cache.move_to_end(key, last=True)

    def peek(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value for ``key`` without affecting recency.

        Recency: never refreshes (no move_to_end).
        Counters: never records a hit or miss.
        Expiry visibility: expired entries are treated as absent.
        Eviction: never triggers eviction.
        """
        if key not in self._cache:
            return default
        value, expires_at = self._cache[key]
        if self._is_expired(expires_at):
            return default
        return value

    def __len__(self) -> int:
        """Count of live (non-expired) entries.

        O(n) in expired-but-unreclaimed entries (lazy expiry), amortized O(1)
        per entry over the cache's lifetime.
        """
        now = self._clock()
        return sum(
            1 for _value, expires_at in self._cache.values()
            if now < expires_at
        )

    def __contains__(self, key: object) -> bool:
        """True iff ``key`` is present and live (not expired).

        Recency: no recency or counter effect (mirrors ``peek``).
        Counters: never records a hit or miss.
        Expiry visibility: expired entries are treated as absent.
        """
        if key not in self._cache:
            return False
        _value, expires_at = self._cache[key]
        return not self._is_expired(expires_at)

    def stats(self) -> dict:
        """Return a snapshot ``{"hits", "misses", "evictions"}``.

        Recency: no effect on recency.
        Counters: no effect on internal counters.
        Expiry visibility: returns current counter values regardless of expiry.
        Eviction: never triggers eviction.

        The returned dict is a fresh copy; mutating it never affects the
        cache's internal counters.
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }
