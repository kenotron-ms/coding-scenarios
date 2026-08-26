# Lane implement_lru_cache

## Outcome

Create the following files in the repository under `scenarios/L2-lru-cache/solution/`:

1. `scenarios/L2-lru-cache/solution/lru.py` — the `LRUCache` class (importable as `lru.LRUCache`)
2. `scenarios/L2-lru-cache/solution/design/API_CONTRACT.md` — the required interface contract document

The harness imports `from lru import LRUCache` with `SOLUTION_DIR=scenarios/L2-lru-cache/solution` on `sys.path`.

## Steps

### 1. Create `scenarios/L2-lru-cache/solution/lru.py`

Implement `LRUCache` using `collections.OrderedDict` with `move_to_end` for O(1) recency tracking. Key design decisions (already resolved by the SPEC.md):

**§1.6(A) — TTL measured from INSERTION** (`ttl_policy = "insertion"`):
- Every `put` (insert or update) stamps a fresh `expires_at = clock() + ttl`.
- `get`/`peek` do NOT extend the TTL window.

**§1.6(B) — `ttl=0` means immediate expiry**:
- Construction and `put` succeed; entries are immediately expired.
- `get`/`peek`/`in` report absent; `len` excludes them.
- Do NOT use `if self.ttl:` — `0` is falsy but semantically meaningful.

**Constructor validation** (`__init__`):
- `capacity` must be `type(capacity) is int` (reject `bool`, `float`, non-int). Raise `ValueError` if not an `int` or if `capacity < 1`.
- Raise `ValueError` if `ttl` is not `None` and `ttl < 0`.
- Store `self._clock = clock`. Never call `time.monotonic`/`time.time`/`time.perf_counter` directly in any method body.

**Internal data model**:
- `self._cache: OrderedDict[Hashable, tuple[Any, float | None]]` — maps key → `(value, expires_at)` where `expires_at` is `None` when `ttl is None`, else `insertion_time + ttl`.
- `self._hits = self._misses = self._evictions = 0`
- Recency: LRU end = `last=False` (front), MRU end = `last=True` (back). On access/insert, call `move_to_end(key)`. On eviction, call `popitem(last=False)`.

**`_is_expired(expires_at)` helper** (single choke point for expiry check):
- Returns `True` if `expires_at is not None` and `self._clock() >= expires_at`.
- Note: use `>=` for the boundary — entry is expired when `clock() >= expires_at` (age ≥ ttl).

**`_evict_if_needed()` helper** (single choke point for eviction):
- While `len(self._cache) >= self._capacity`, pop the LRU item (`popitem(last=False)`), increment `self._evictions`.

**Method implementations**:

```python
def put(self, key, value):
    # If key exists (even expired), remove it first (no eviction counted)
    if key in self._cache:
        del self._cache[key]
    # Evict LRU if at capacity (only for new keys)
    self._evict_if_needed()
    # Compute expires_at
    expires_at = (self._clock() + self._ttl) if self._ttl is not None else None
    self._cache[key] = (value, expires_at)
    # move_to_end not needed since we just inserted at the end

def get(self, key, default=None):
    if key not in self._cache:
        self._misses += 1
        return default
    value, expires_at = self._cache[key]
    if self._is_expired(expires_at):
        del self._cache[key]
        self._misses += 1
        return default
    self._cache.move_to_end(key)
    self._hits += 1
    return value

def peek(self, key, default=None):
    if key not in self._cache:
        return default
    value, expires_at = self._cache[key]
    if self._is_expired(expires_at):
        return default
    return value

def __len__(self):
    # Reclaim expired entries lazily
    expired = [k for k, (_, exp) in self._cache.items() if self._is_expired(exp)]
    for k in expired:
        del self._cache[k]
    return len(self._cache)

def __contains__(self, key):
    if key not in self._cache:
        return False
    _, expires_at = self._cache[key]
    return not self._is_expired(expires_at)

def stats(self):
    return {"hits": self._hits, "misses": self._misses, "evictions": self._evictions}
```

**Critical correctness notes**:
- `put` on an existing key: remove old entry first (so `_evict_if_needed` sees the correct count), then insert fresh. This ensures no eviction for an update-in-place.
- `_evict_if_needed` uses `>=` comparison: evict while `len >= capacity` (before inserting the new key, so after removing the old key for updates, count is `capacity - 1` → no eviction needed).
- `__len__` may do O(expired) work but each entry is reclaimed at most once — amortized O(1).
- `stats()` returns a plain dict copy — mutating it does not affect the cache.
- Class attribute: `ttl_policy: str = "insertion"`.
- Docstring must state: insertion-based TTL, `ttl=0` means immediate expiry, not thread-safe.

**Validation of capacity type** — reject `bool` and `float`:
```python
if not isinstance(capacity, int) or isinstance(capacity, bool):
    raise ValueError(f"capacity must be an int >= 1, got {capacity!r}")
if capacity < 1:
    raise ValueError(f"capacity must be >= 1, got {capacity!r}")
```

### 2. Create `scenarios/L2-lru-cache/solution/design/API_CONTRACT.md`

Write the required design document containing all 9 required sections per REQUIREMENTS.md §5.4:
1. Full signatures with type annotations
2. Semantic matrix (recency effect, counter effect, expired-entry visibility, eviction possibility per method)
3. Stated invariants
4. Exception contract table
5. TTL-origin decision with rationale (`ttl_policy = "insertion"`)
6. `ttl=0` decision with rationale (immediate expiry)
7. Complexity guarantees per method
8. Thread-safety stance (not thread-safe)
9. At least two worked call sequences showing eviction and expiry

### 3. Create `scenarios/L2-lru-cache/solution/__init__.py` (empty, if needed)

The solution directory needs to be importable. Check if `__init__.py` is needed based on how the harness adds `SOLUTION_DIR` to `sys.path` (it adds the directory itself, so `lru.py` at the top level of `solution/` is imported as `lru` — no `__init__.py` needed for `lru`, but `design/` is not a module).

### 4. Verify smoke tests pass first

Run `pytest scenarios/L2-lru-cache/tests/smoke -q` before running acceptance.

## Done when

The following command exits 0:

```
pytest scenarios/L2-lru-cache/tests/acceptance -q --tb=short
```

with `SOLUTION_DIR=scenarios/L2-lru-cache/solution` set in the environment (the conftest.py picks this up automatically; if not set it falls back to the reference solution — so set it explicitly or run from within the scenario directory with the solution in place).

All acceptance tests must pass (100% pass rate, `acceptance_pass == 1.0`).

## Final step (REQUIRED)

After the work is done and `pytest scenarios/L2-lru-cache/tests/acceptance -q --tb=short` exits 0, write the file `artifacts/implement_lru_cache.done` containing exactly:

```
implement_lru_cache:ok
```

and nothing else (no trailing newline beyond what is written). This marker file is how the batch orchestrator confirms the lane finished — it MUST be the last action taken.
