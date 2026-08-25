# L2 — LRU Cache — SPEC (prompt handed to the strategy under test)

Implement a single class `LRUCache` in a module `lru.py` in your workspace.

```python
import time
from collections.abc import Callable, Hashable, Mapping
from typing import Any

class LRUCache:
    def __init__(self, capacity: int, ttl: float | None = None, *,
                 clock: Callable[[], float] = time.monotonic) -> None: ...
    def get(self, key: Hashable, default: Any = None) -> Any: ...
    def put(self, key: Hashable, value: Any) -> None: ...
    def peek(self, key: Hashable, default: Any = None) -> Any: ...
    def __len__(self) -> int: ...
    def __contains__(self, key: object) -> bool: ...
    def stats(self) -> Mapping[str, int]: ...   # >= {"hits", "misses", "evictions"}
```

Requirements:
- Capacity-bounded LRU cache. `capacity` is the max number of live entries.
  When a **new** key is inserted at capacity, evict exactly one entry: the
  least-recently-used. `len(cache)` never exceeds `capacity`.
- `get` and `put` both refresh recency (mark the key most-recently-used).
  `peek` and `__contains__` **never** refresh recency and never touch
  `stats()`.
- `put` on an **existing** key updates the value and recency, does **not**
  grow the cache, and causes **no** eviction — even exactly at capacity.
- Optional TTL: pass `ttl` (seconds) to expire entries. Expiry is **lazy**
  (checked on access — no timers/threads) but must be observationally
  immediate: no method may ever return or report an expired entry.
  - **§1.6(A) resolution — TTL is measured from INSERTION.** Every `put`
    (whether it inserts or updates) stamps a fresh TTL window; reads
    (`get`/`peek`) never extend it. Declare this with a class attribute
    `ttl_policy = "insertion"`.
  - **§1.6(B) resolution — `ttl=0` means immediate expiry.** Construction and
    `put` both succeed, but the entry is expired before it can ever be
    observed again: `get`/`peek`/`in` report it absent, `len` excludes it.
    Do **not** treat `ttl=0` as "no expiry" (`if self.ttl:` is a classic
    falsy-check bug — `0` is falsy but semantically meaningful here).
  - `ttl=None` means entries never expire.
- Raise `ValueError` if `capacity` is not an `int`, or is `< 1` (this
  includes rejecting `True`/`False` and floats like `2.0` — they are not
  "an integer" for this purpose even though `bool` is an `int` subclass).
- Raise `ValueError` if `ttl` is negative.
- Every time read on the expiry path must go through the injected `clock`
  callable — never call `time.monotonic`/`time.time`/`time.perf_counter`
  directly anywhere; the only permitted reference to `time` is the
  **default value** of the `clock` parameter.
- `get(key)`/`peek(key)` return `default` (default `None`) for an absent,
  evicted, or expired key — **never raise** on a miss. Because `None` is
  itself a storable value, use `key in cache` to disambiguate "stored
  `None`" from "absent".
- `stats()` returns at least `{"hits", "misses", "evictions"}` as
  non-negative, monotonically non-decreasing ints: a `get` that returns a
  live value increments `hits`; a `get` for an absent/evicted/expired key
  increments `misses` (so `put`, `peek`, `len`, and `in` never touch these
  two counters); `evictions` counts **capacity-driven** removals only —
  expiry-driven removal is a miss, not an eviction. The returned mapping is
  a snapshot: mutating it must not affect the cache.
- `get`, `put`, `peek`, and `__contains__` are O(1) amortized — no work
  proportional to `capacity` or to the number of live entries (an
  `OrderedDict` with `move_to_end`, or a hand-rolled dict + doubly-linked
  list, are both fine; a linear victim scan is not). Eviction logic must
  live at a single choke point.
- Two `LRUCache` instances share no state (no class-level mutable
  containers, no module globals).
- Standard library only, Python ≥ 3.11. Document the §1.6(A) TTL origin,
  the §1.6(B) `ttl=0` behavior, and your thread-safety stance (you are not
  required to be thread-safe — just say so) in the class docstring.

You are given `tests/smoke/` to check your work. Held-out acceptance and
adversarial suites will grade you (see `EVALUATION.md` for what they
measure).

**Entrypoint:** the harness imports `lru` from your workspace and constructs
`lru.LRUCache(...)` directly, always passing an explicit `clock=` (see
`manifest.yaml`).
