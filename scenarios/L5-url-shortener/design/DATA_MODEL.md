# Data Model — URL Shortener

## Schema

```sql
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    clicks     INTEGER NOT NULL DEFAULT 0
);
```

The schema is created idempotently on startup (`CREATE TABLE IF NOT EXISTS`), so a fresh database file works with no manual migration step and an existing database file is left intact.

## Indexes

- **`code` (PRIMARY KEY)** — Provides O(log n) lookup for redirects (`GET /{code}`), stats (`GET /api/stats/{code}`), and deletes (`DELETE /api/{code}`). This is the hot path.
- **`url` (optional, for A-1 dedupe)** — An index on `url` supports O(log n) lookup for idempotency deduplication in `POST /api/shorten`. Without it, the dedupe query does a full table scan; with it, deduplication is fast even for large link tables. The implementation performs `SELECT ... WHERE url = ?` for every POST, so this index is recommended for production use.

## Code Generation Strategy

**Strategy chosen: Random + collision retry.**

### Mechanics

1. Draw `CODE_LENGTH = 6` random characters from `ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"` using a seeded `random.Random` instance.
2. If the generated code equals a reserved segment (`health`, `api`, `docs`, `redoc`, `openapi.json`, `favicon.ico`, or the empty string), redraw immediately.
3. Attempt `INSERT INTO links (code, url) VALUES (?, ?)`. On `UNIQUE` constraint violation (collision), retry up to 10 times.
4. If all 10 attempts are exhausted, return HTTP 500. This is a defined failure mode, not a silent overwrite.

### Trade-off

| Aspect | Random + collision retry |
|--------|--------------------------|
| **Opacity** | Codes are opaque — not guessable or enumerable. Volume is not leaked. |
| **Collision probability** | With 62^6 = 56,800,235,584 possible codes, the probability of a collision is negligible until the table contains tens of millions of rows. |
| **Retry loop** | Requires a real retry loop and a defined failure mode when attempts are exhausted (HTTP 500, never a silent overwrite of an existing code). |
| **Determinism** | Not deterministic — the same URL submitted twice produces different codes (unless A-1 dedupe returns the existing code first). |

The alternative strategy — **base62 of autoincrement id** — would be deterministic and collision-free but would make codes guessable and leak the total link volume. This was rejected because opacity is more important than determinism for this use case.

## Atomic Increment Strategy

The datastore owns the arithmetic. Click counting uses a single SQL statement inside a committed transaction:

```sql
UPDATE links SET clicks = clicks + 1 WHERE code = ?
```

This is executed atomically by SQLite. The result is then read back with a `SELECT` in the same transaction to return the updated row.

### Why not Python arithmetic?

A `SELECT` followed by Python `+1` followed by `UPDATE ... SET clicks = ?` is the canonical **lost-update bug**. Under concurrent load (NFR-2), two concurrent reads both see the same value, both add 1, and one update overwrites the other. With 200 concurrent redirect requests, the final click count could be anywhere from 1 to 200. The SQL `clicks = clicks + 1` form is immune to this because SQLite serializes the update atomically.

## Concurrency Model

- **WAL mode** (`PRAGMA journal_mode=WAL`) allows concurrent readers without blocking writers and vice versa.
- **Write serialization** — A `threading.Lock` (`_write_lock`) serializes all write operations (`INSERT`, `UPDATE`, `DELETE`). This prevents `sqlite3.OperationalError: database is locked` errors under concurrent load from multiple threads sharing the same process.
- **Per-request connections** — Each storage function opens a new connection, uses it, and closes it in a `finally` block. This is safe under `check_same_thread=False` because write operations are serialized by `_write_lock`.
- **`PRAGMA synchronous=NORMAL`** — Balances durability and performance. Writes are durable after the OS write cache is flushed, which is sufficient for the restart persistence requirement (FR-10) under orderly shutdown.

## Persistence Guarantee

The mapping is durably persisted before the 201 response is returned (FR-1, NFR-3). Each write operation calls `conn.commit()` before returning. A `SIGTERM` triggers a clean shutdown via uvicorn's signal handling, flushing all committed writes. A `SIGKILL` immediately after a committed response loses nothing already acknowledged.
