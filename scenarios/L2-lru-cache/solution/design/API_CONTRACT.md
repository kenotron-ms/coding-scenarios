# LRUCache API Contract

## 1. Full Signatures with Type Annotations

```python
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any

class LRUCache:
    ttl_policy: str  # class variable, value = "insertion"

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
    def stats(self) -> dict: ...
```

## 2. Semantic Matrix

| Method          | Recency Effect         | Counter Effect          | Expired-Entry Visibility | Eviction Possible |
|-----------------|------------------------|-------------------------|--------------------------|-------------------|
| `get(key)`      | Refreshes on hit       | hits+1 or misses+1      | Expired = miss           | No                |
| `put(key, val)` | Always refreshes       | None                    | Expired entries may be silently removed | Yes (new key at capacity) |
| `peek(key)`     | None                   | None                    | Expired = absent         | No                |
| `__len__()`     | None                   | None                    | Expired excluded         | No                |
| `__contains__`  | None                   | None                    | Expired = False          | No                |
| `stats()`       | None                   | None                    | N/A                      | No                |

## 3. Stated Invariants

- **P-1**: `len(cache) <= capacity` at all times (counting only live entries).
- **P-2**: After `put(k, v)`, `get(k)` returns `v` (if not expired and not evicted).
- **P-3**: The entry evicted by a capacity-driven `put` is the least-recently-used live entry.
- **P-4**: `hits + misses == number of get() calls` at all times.
- **P-5**: `evictions` counts only capacity-driven removals; TTL expiry is never an eviction.
- **P-6**: `peek` and `__contains__` never change recency order or counters.
- **P-7**: `stats()` returns a fresh dict; mutating it does not affect internal counters.

## 4. Exception Contract Table

| Condition                                    | Exception    | Message pattern                              |
|----------------------------------------------|--------------|----------------------------------------------|
| `type(capacity) is not int`                  | `ValueError` | "capacity must be an int >= 1"               |
| `capacity < 1`                               | `ValueError` | "capacity must be an int >= 1"               |
| `ttl is not None and ttl < 0`                | `ValueError` | "ttl must be >= 0 or None"                   |
| `bool` passed as capacity (True/False)       | `ValueError` | Rejected by `type(capacity) is not int` check |
| `float`, `str`, `None` passed as capacity   | `ValueError` | Rejected by `type(capacity) is not int` check |

No other public method raises an exception under normal usage.

## 5. §1.6(A) TTL-Origin Decision with Rationale

**Decision**: `ttl_policy = "insertion"` — TTL is measured from insertion time, not last access.

**Rationale**: Insertion-based TTL provides predictable, bounded staleness guarantees. The TTL window starts when `put` is called and is never extended by reads. This means:
- A `get` or `peek` on a key never resets its expiry clock.
- Every `put` (insert or update) stamps a fresh `expires_at = clock() + ttl`.
- This is the simpler and more common policy for cache invalidation scenarios where data freshness is measured from when it was written, not when it was last read.

## 6. §1.6(B) `ttl=0` Decision with Rationale

**Decision**: `ttl=0` means **immediate expiry**. Construction and `put` both succeed, but every entry is immediately expired.

**Rationale**: `ttl=0` is a valid, useful sentinel meaning "cache nothing" (useful for testing or disabling caching without changing code structure). The implementation sets `expires_at = clock() + 0 = clock()`. Since `_is_expired` checks `clock() >= expires_at`, and the clock is non-decreasing, any access after the `put` (even at the same instant) will see the entry as expired. This is deliberately distinct from `ttl=None` (no expiry). A naive `if self.ttl:` check would incorrectly treat `ttl=0` as "no TTL", which is wrong.

## 7. Complexity Guarantees per Method

| Method          | Time Complexity                                      | Space Complexity |
|-----------------|------------------------------------------------------|------------------|
| `__init__`      | O(1)                                                 | O(capacity)      |
| `get`           | O(1) amortized (OrderedDict hash lookup + move_to_end) | O(1)           |
| `put`           | O(1) amortized (hash lookup + popitem + append)      | O(1)             |
| `peek`          | O(1) amortized (hash lookup only)                    | O(1)             |
| `__len__`       | O(n) where n = number of entries (including expired but unreclaimed) | O(1) |
| `__contains__`  | O(1) amortized (hash lookup only)                    | O(1)             |
| `stats`         | O(1)                                                 | O(1)             |

Note: `__len__` is O(n) due to lazy expiry — it must iterate all entries to count live ones. This is amortized O(1) per entry over the cache's lifetime since each entry is counted at most once per `__len__` call.

## 8. Thread-Safety Stance

**Not thread-safe.** No internal locking or synchronization is performed. Concurrent callers accessing the same `LRUCache` instance must synchronize externally (e.g., using `threading.Lock`). The `OrderedDict` operations (`move_to_end`, `popitem`, `__setitem__`, `__delitem__`) are not atomic with respect to the surrounding logic.

## 9. Worked Call Sequences

### Example 1: Eviction Sequence

```python
from lru import LRUCache

c = LRUCache(capacity=3)

c.put("a", 1)   # cache: {a:1}
c.put("b", 2)   # cache: {a:1, b:2}
c.put("c", 3)   # cache: {a:1, b:2, c:3}  -- at capacity

c.get("a")      # returns 1; "a" moves to MRU; cache order: b, c, a
                # stats: hits=1, misses=0, evictions=0

c.put("d", 4)   # new key at capacity; LRU is "b" -> evicted
                # cache: {c:3, a:1, d:4}
                # stats: hits=1, misses=0, evictions=1

assert "b" not in c   # evicted
assert c.get("a") == 1
assert c.get("c") == 3
assert c.get("d") == 4
```

### Example 2: TTL Expiry Sequence

```python
from lru import LRUCache

# Using a controllable fake clock for determinism
class FakeClock:
    def __init__(self): self._t = 0.0
    def __call__(self): return self._t
    def advance(self, dt): self._t += dt

clk = FakeClock()
c = LRUCache(capacity=5, ttl=10.0, clock=clk)

c.put("x", 100)   # expires_at = 0.0 + 10.0 = 10.0
clk.advance(5.0)  # now = 5.0; entry still live (5.0 < 10.0)
assert c.get("x") == 100   # hit; stats: hits=1

clk.advance(5.0)  # now = 10.0; entry expired (10.0 >= 10.0)
assert c.get("x") is None  # miss (expired); stats: misses=1
assert "x" not in c        # expired -> absent
assert len(c) == 0         # no live entries
assert c.stats()["evictions"] == 0  # expiry is NOT an eviction

# ttl=0 immediate expiry example
c2 = LRUCache(capacity=5, ttl=0, clock=clk)
c2.put("y", 42)    # expires_at = 10.0 + 0 = 10.0; immediately expired
assert c2.get("y") is None   # already expired
assert "y" not in c2
assert len(c2) == 0
```
