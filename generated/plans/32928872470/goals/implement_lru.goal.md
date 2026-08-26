# Lane implement_lru

## Outcome

Implement the `LRUCache` class in `scenarios/L2-lru-cache/solution/lru.py` (creating the file and the `solution/` directory if needed) so that the full acceptance suite at `scenarios/L2-lru-cache/tests/acceptance/test_acceptance.py` passes at 100%.

Also create `scenarios/L2-lru-cache/solution/design/API_CONTRACT.md` containing the required design document (see Steps below).

The harness imports the solution as:
```python
import sys; sys.path.insert(0, "scenarios/L2-lru-cache/solution")
from lru import LRUCache
```
(The `conftest.py` at `scenarios/L2-lru-cache/tests/conftest.py` sets `SOLUTION_DIR` or falls back to the reference; set `SOLUTION_DIR=scenarios/L2-lru-cache/solution` when running tests locally.)

## Steps

### 1. Create `scenarios/L2-lru-cache/solution/lru.py`

Implement `class LRUCache` with:

**Constructor:**
```python
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from typing import Any

class LRUCache:
    ttl_policy: str = "insertion"

    def __init__(
        self,
        capacity: int,
        ttl: float | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None: ...
```

- Raise `ValueError` if `capacity` is not `int` (reject `bool`, `float`, `str`, `None` — use `type(capacity) is not int`).
- Raise `ValueError` if `capacity < 1`.
- Raise `ValueError` if `ttl` is not `None` and `ttl < 0`.
- `ttl=0` means **immediate expiry** (construction succeeds; every entry is immediately expired). Do NOT treat `ttl=0` as falsy "no expiry".
- Store `clock` for use in expiry checks.

**Internal data model** — use `collections.OrderedDict` for O(1) LRU:
- `_cache: OrderedDict[key, (value, expires_at)]` where `expires_at = clock() + ttl` at insertion time (insertion-based TTL), or `float('inf')` when `ttl is None`.
- `_hits`, `_misses`, `_evictions`: int counters.

**`_is_expired(expires_at: float) -> bool`:** returns `True` if `clock() >= expires_at`. This is the single expiry check used everywhere.

**`get(key, default=None)`:**
- Look up `key` in `_cache`.
- If absent: increment `_misses`, return `default`.
- If present but expired (`_is_expired(expires_at)`): remove from `_cache`, increment `_misses`, return `default`.
- If live: move to end (MRU), increment `_hits`, return value.

**`put(key, value)`:**
- Compute `expires_at = clock() + ttl` (or `float('inf')` if `ttl is None`).
- If `key` already in `_cache`: remove it (no eviction counted).
- Else if `len(live entries) >= capacity`: evict the LRU entry — pop from the front of `_cache` using `_evict()`, increment `_evictions`. **Important:** count live (non-expired) entries for capacity check. The simplest correct approach: before evicting, first check whether the front entry is expired; if so, remove it without counting as eviction. Repeat until the live count is below capacity or the cache is empty.
- Insert `key -> (value, expires_at)` at the end (MRU).

**`_evict()`:** private method that removes the LRU entry from `_cache` and increments `_evictions`. This is the single eviction choke point.

**`peek(key, default=None)`:**
- Look up `key`; if absent or expired, return `default`. No recency change, no counter change.

**`__len__()`:**
- Count only live (non-expired) entries. With lazy expiry, iterate and count entries where `not _is_expired(expires_at)`. This is O(n) in expired-but-unreclaimed entries, amortized O(1) per entry over lifetime.

**`__contains__(key)`:**
- Return `True` only if `key` in `_cache` and not expired. No recency or counter change.

**`stats()`:**
- Return a fresh `dict` snapshot: `{"hits": self._hits, "misses": self._misses, "evictions": self._evictions}`.

**Critical correctness details:**
- `ttl=0`: `expires_at = clock() + 0 = clock()`. Since `_is_expired` checks `clock() >= expires_at`, and the clock does not go backwards, any access after the put (even at the same instant) will see `clock() >= expires_at` as True. This correctly implements immediate expiry.
- `ttl` boundary at exactly `ttl`: the acceptance test at `clk2.advance(5.0)` expects the entry to be **absent** (`c2.get("a") is None`). So use `>=` (inclusive) for expiry: expired when `clock() >= expires_at`.
- `ttl_policy = "insertion"`: TTL window starts at `put` time, not refreshed by reads.
- Capacity check for eviction: when `put` inserts a new key, if the number of **live** entries (after the new key) would exceed capacity, evict the LRU. The simplest approach: check `len(self._cache)` after removing the key (if it existed) and before inserting — if it equals `capacity`, evict the LRU.
- For the capacity check, note that `_cache` may contain expired entries. When evicting, pop the LRU (front of OrderedDict). If it is expired, do NOT count it as an eviction (it was already logically absent). Keep popping until a live entry is evicted or the cache is below capacity.
- `bool` subclasses `int` in Python — reject `True`/`False` as capacity: use `type(capacity) is not int` (strict type check, not `isinstance`).

**Class docstring must include:**
- TTL origin: "insertion-based" (TTL measured from insertion time, not last access)
- `ttl=0` behavior: "immediate expiry"
- Thread-safety stance: "not thread-safe"

**Every public method** (`get`, `put`, `peek`, `stats`) must have a docstring describing its recency effect, counter effect, and expiry visibility.

### 2. Create `scenarios/L2-lru-cache/solution/__init__.py`

Empty file (so `solution/` is a package, though the harness imports `lru` directly from `sys.path`).

### 3. Create `scenarios/L2-lru-cache/solution/design/API_CONTRACT.md`

The design document must contain all 9 required sections per REQUIREMENTS §5.4:
1. Full signatures with type annotations
2. Semantic matrix (recency effect, counter effect, expired-entry visibility, eviction possibility per method)
3. Stated invariants
4. Exception contract table
5. §1.6(A) TTL-origin decision with rationale
6. §1.6(B) `ttl=0` decision with rationale
7. Complexity guarantees per method
8. Thread-safety stance
9. At least two worked call sequences (eviction and expiry examples)

### 4. Verify

Run the smoke suite first:
```bash
cd scenarios/L2-lru-cache
SOLUTION_DIR=solution pytest tests/smoke -q
```

Then the acceptance suite:
```bash
cd scenarios/L2-lru-cache
SOLUTION_DIR=solution pytest tests/acceptance -q --tb=short
```

All 26 acceptance tests must pass.

## Done when

The following command exits 0 from the repository root:

```bash
SOLUTION_DIR=scenarios/L2-lru-cache/solution pytest scenarios/L2-lru-cache/tests/acceptance -q --tb=short
```

All 26 acceptance test cases pass (gate: `acceptance_pass == 1.0`).

## Final step (REQUIRED)

After the work is done and the acceptance suite passes, write the file `artifacts/implement_lru.done` containing exactly `implement_lru:ok` and nothing else.

This marker file is how the batch orchestrator confirms the lane finished. It MUST be the last action taken. Create the `artifacts/` directory if it does not exist.
