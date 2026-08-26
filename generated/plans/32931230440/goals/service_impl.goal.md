# Lane service_impl

## Outcome

Implement the URL shortener HTTP service under `scenarios/L5-url-shortener/solution/`. The following files must exist and be syntactically valid Python:

- `scenarios/L5-url-shortener/solution/main.py` — entrypoint
- `scenarios/L5-url-shortener/solution/app.py` — FastAPI routes and validation
- `scenarios/L5-url-shortener/solution/storage.py` — SQLite persistence layer
- `scenarios/L5-url-shortener/solution/codec.py` — code generation and reserved-word guard
- `scenarios/L5-url-shortener/solution/requirements.txt` — pinned dependencies

## Steps

### 1. `solution/codec.py` — code generation

Implement a `generate_code(rng: random.Random) -> str` function that:
- Draws 6 random characters from the base62 alphabet `[0-9A-Za-z]`
- Returns the 6-character string
- Never returns a reserved segment: `health`, `api`, `docs`, `redoc`, `openapi.json`, `favicon.ico`, or the empty string
- If the drawn code equals a reserved segment, redraw (loop)

Document the A-2 resolution: fixed length 6, base62 alphabet `[0-9A-Za-z]{6}`.

### 2. `solution/storage.py` — SQLite persistence layer

Implement a `Database` class (or module-level functions) with:

**Schema init (`init_db(db_path: str) -> None`):**
```sql
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    clicks     INTEGER NOT NULL DEFAULT 0
);
```
Use `check_same_thread=False` with WAL mode (`PRAGMA journal_mode=WAL`) and a threading lock around all writes, OR use a per-request connection with WAL. Enable WAL at init: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`

**`create_link(db_path, code, url) -> dict`** — INSERT a new row; return `{code, url, clicks, created_at}`.

**`get_link(db_path, code) -> dict | None`** — SELECT by code; return row dict or None.

**`increment_clicks(db_path, code) -> dict | None`** — Atomically:
```sql
UPDATE links SET clicks = clicks + 1 WHERE code = ?
```
Then SELECT and return the updated row, or None if not found. This MUST be a single transaction where the DB owns the arithmetic (no Python +1).

**`delete_link(db_path, code) -> bool`** — DELETE WHERE code = ?; return True if a row was deleted.

**`health_check(db_path) -> bool`** — Execute a trivial SELECT (e.g. `SELECT 1 FROM links LIMIT 1`) to confirm the DB is reachable; return True.

**`find_by_url(db_path, url) -> dict | None`** — SELECT WHERE url = ? for A-1 idempotency dedupe.

All SQL must be parameterized — no string interpolation. All writes must be committed before returning.

**A-1 resolution (idempotent/dedupe):** If `POST /api/shorten` receives a URL that already exists, return the existing code (201 with existing code, clicks preserved). Document this in README.

**A-3 resolution (store verbatim):** Store the URL exactly as submitted; `Location` header is byte-identical to the stored URL. Document this in README.

### 3. `solution/app.py` — FastAPI application

Create a `create_app(db_path: str, base_url: str | None = None) -> FastAPI` factory.

**Routes:**

`POST /api/shorten`:
- Parse JSON body; reject (400) if: not JSON, missing `url`, non-string `url`, empty/whitespace `url`, scheme not in `{http, https}` (case-insensitive), no host, contains CR/LF/NUL, `url` > 2048 bytes, total body > 8192 bytes.
- Check `find_by_url` — if exists, return 201 with existing code (A-1 idempotent).
- Otherwise generate a code via `generate_code`, retry on `UNIQUE` constraint violation (up to 10 attempts; 500 if exhausted).
- Return 201: `{"code": "<code>", "short_url": "<base_url>/<code>"}`.

`GET /{code}`:
- Validate code is URL-safe (reject with 404 if it contains path traversal or special chars).
- Call `increment_clicks`; if None → 404.
- Return 302 with `Location: <stored url>`.

`GET /api/stats/{code}`:
- `get_link`; if None → 404 JSON.
- Return 200: `{"url", "code", "clicks", "created_at"}` where `created_at` is ISO-8601 UTC string.

`DELETE /api/{code}`:
- `delete_link`; if False → 404 JSON.
- Return 204 empty body.

`GET /health`:
- Call `health_check`; return 200: `{"status": "ok"}`.

**Error handling:**
- All `/api/*` errors return `Content-Type: application/json` with `{"detail": "<message>"}`.
- 400 for bad input (never 422 — override FastAPI's default validation error handler to return 400).
- 404 for unknown codes.
- 405 for wrong methods on known paths.
- Add a request logging middleware that logs JSON to stdout: `{timestamp, method, path, status_code, duration_ms}`.

**Override FastAPI 422 → 400:** Add exception handler for `RequestValidationError` that returns 400 with `{"detail": "..."}`.

### 4. `solution/main.py` — entrypoint

```python
import os, signal, uvicorn
from solution.app import create_app

PORT = int(os.environ["PORT"])
DB_PATH = os.environ["URLSHORT_DB"]
BASE_URL = os.environ.get("URLSHORT_BASE_URL")
SEED = os.environ.get("URLSHORT_SEED")

# Init DB schema
from solution.storage import init_db
init_db(DB_PATH)

app = create_app(db_path=DB_PATH, base_url=BASE_URL)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_config=None)
```

Handle `SIGTERM` cleanly: uvicorn handles SIGTERM by default for graceful shutdown. Log the resolved DB path and bind address at startup.

Pass `URLSHORT_SEED` to codec's RNG if set.

### 5. `solution/requirements.txt`

Pin exact versions:
```
fastapi==0.111.0
uvicorn==0.30.1
```
(Or latest compatible versions — use `fastapi>=0.100.0` and `uvicorn>=0.20.0` if exact versions are uncertain, but prefer pinned.)

## Done when

The following command exits 0:

```bash
test -f scenarios/L5-url-shortener/solution/main.py && \
test -f scenarios/L5-url-shortener/solution/app.py && \
test -f scenarios/L5-url-shortener/solution/storage.py && \
test -f scenarios/L5-url-shortener/solution/codec.py && \
test -f scenarios/L5-url-shortener/solution/requirements.txt && \
python -m py_compile scenarios/L5-url-shortener/solution/main.py && \
python -m py_compile scenarios/L5-url-shortener/solution/app.py && \
python -m py_compile scenarios/L5-url-shortener/solution/storage.py && \
python -m py_compile scenarios/L5-url-shortener/solution/codec.py
```

All five files exist and all four Python files compile without syntax errors.

## Final step (REQUIRED)

After all files are created and the check above passes, write the file `artifacts/service_impl.done` containing exactly `service_impl:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action.
