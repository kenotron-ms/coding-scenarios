# L5 — URL Shortener — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> discovery/design scope fixed by the L5 row of `framework/ARTIFACT_GRADIENT.md`.

## 0. Scenario Summary
- **Level:** L5
- **Codename / dir:** `L5-url-shortener`
- **One-liner:** A REST service that shortens URLs, redirects short codes to their
  targets, tracks click statistics, with durable persistence and concurrency-safe
  click counting.
- **New difficulty introduced:** **First stateful service.** Everything below L5
  was verified by calling code (function, class, CLI subprocess, library import).
  L5 is the first rung where the *real path* is a **live process listening on a
  socket**: real HTTP semantics (status codes, redirects, headers), a real
  **datastore** (SQLite) whose contents must survive the process, and
  **concurrency correctness** — a class of bug that cannot be found by
  single-threaded testing and cannot be papered over by retrying. The agent must
  also keep a process healthy enough for a harness to start, poll, kill, and
  restart it.
- **Estimated reference solution size:** 200–400 LoC across 4–6 files
  (`app`, `storage`, `codec`, `schemas`, `main`), plus 3 documents under `design/`.
- **Time budget:** 90 minutes wall-clock.
- **Iteration budget:** soft 18, hard 45 edit→verify cycles.
- **Intervention budget:** 0. Any `clarify` on the §1.6 ambiguities is itself a
  finding — the ambiguities are deliberate and the agent is expected to resolve
  and document them unilaterally.

## 1. Product Requirements

- **1.1 Problem statement** — Teams embedding links in emails, SMS, chat bots and
  print media need short, stable, opaque links that redirect to long canonical
  URLs, plus a truthful count of how often each link was followed. Existing
  hosted shorteners are unacceptable for internal/regulated links, so the need is
  a small self-hosted HTTP service with durable storage that can be run as a
  single process next to the app that generates the links.

- **1.2 Target users / personas** — Two consumer archetypes; formal personas are
  **Optional** at this rung (`ARTIFACT_GRADIENT.md` L5), but the API has a real
  audience and must be designed for it:
  | Archetype | Who | What they touch |
  |-----------|-----|-----------------|
  | **Integrator** | A backend/bot developer calling the service from another service. | `POST /api/shorten`, `GET /api/stats/{code}`, `DELETE /api/{code}` |
  | **Operator** | Whoever runs the process and answers "is it up, is data safe". | `GET /health`, logs, the SQLite file |
  | **End recipient** | A human who clicks a short link. Never sees the API. | `GET /{code}` |

- **1.3 User stories**
  - **US-1** As an *Integrator*, I want to POST a long URL and get back a short
    code and a ready-to-paste short URL, so that I can embed it in an outgoing
    message without building link infrastructure.
  - **US-2** As an *End recipient*, I want a short link to send me to the intended
    destination immediately, so that the indirection is invisible to me.
  - **US-3** As an *Integrator*, I want an accurate click count per code, so that
    I can report campaign engagement without an analytics vendor.
  - **US-4** As an *Integrator*, I want to delete a code, so that a link published
    in error stops working immediately.
  - **US-5** As an *Operator*, I want a health endpoint and structured request
    logs, so that I can wire the service into a supervisor and debug failures.
  - **US-6** As an *Operator*, I want click counts and links to survive a process
    restart, so that a deploy or crash does not silently destroy reporting data.
  - **US-7** As an *Integrator*, I want malformed and dangerous URLs rejected at
    creation time with a clear 4xx, so that my service never mints a link that
    executes script or reads a local file on a recipient's machine.

- **1.4 Functional requirements**
  - **FR-1 Shorten.** `POST /api/shorten` with a JSON body containing a valid
    `http`/`https` URL creates a link and returns **201** with the generated
    `code` and an absolute `short_url`. The mapping is durably persisted before
    the response is returned.
  - **FR-2 Reject bad input.** The service returns **400** (explicitly *not* 422,
    not 500) when the request body is not JSON, is missing `url`, has a non-string
    `url`, has an empty/whitespace `url`, has a scheme other than `http`/`https`
    (including `javascript:`, `file:`, `data:`, `ftp:`, scheme-relative `//host`),
    has no host, or exceeds the size limit in NFR-4.
  - **FR-3 Redirect.** `GET /{code}` for a known code returns **302** with a
    `Location` header equal to the stored target URL. The response body is
    irrelevant; the status and header are the contract.
  - **FR-4 Atomic click counting.** Each `GET /{code}` that returns 302 increments
    that code's `clicks` by exactly one, atomically and durably. Requests that
    return 404 do not increment anything. See **NFR-2** for the load-bearing
    concurrency requirement.
  - **FR-5 Stats.** `GET /api/stats/{code}` for a known code returns **200** with
    `url`, `code`, `clicks`, `created_at`. `clicks` reflects every redirect that
    has already returned a response to a client — reads come from the datastore,
    never from an in-process counter that could diverge from it.
  - **FR-6 Delete.** `DELETE /api/{code}` for a known code returns **204** with an
    empty body and removes the link. After deletion: `GET /{code}` → **404**,
    `GET /api/stats/{code}` → **404**, and a second `DELETE /api/{code}` → **404**.
  - **FR-7 Health.** `GET /health` returns **200** with a JSON body containing
    `"status": "ok"`. It must succeed on a brand-new empty database, must require
    no auth, and must actually touch the datastore (a health check that cannot
    fail is not a health check).
  - **FR-8 Unknown code.** Any unknown code returns **404**. API paths return a
    JSON error body; `GET /{code}` may return any body with the 404.
  - **FR-9 Wrong method.** A known path invoked with an unsupported method returns
    **405** (e.g. `GET /api/shorten`, `PUT /api/shorten`, `POST /api/stats/{code}`,
    `DELETE /health`).
  - **FR-10 Persistence across restart.** Links, click counts and `created_at`
    values survive a full process stop and restart against the same database
    file. No data may live only in process memory.
  - **FR-11 Code generation.** Generated codes are unique, URL-safe, match the
    charset/length policy documented under §1.6, and never collide with a reserved
    path segment (`health`, `api`, `docs`, `redoc`, `openapi.json`, `favicon.ico`,
    and the empty string). The collision-handling strategy is documented and
    exercised — a code the service cannot serve is a bug, not an edge case.

- **1.5 Out of scope** — Authentication/authorization and API keys; user accounts;
  custom "vanity" codes chosen by the caller; link expiry/TTL; rate limiting;
  analytics richer than a monotonic counter (no referrer, geo, user-agent, unique
  visitors); QR codes; bulk/list endpoints and pagination; multi-node or
  replicated deployment; HTTPS termination; a migrations framework; an admin UI.

- **1.6 Ambiguities the agent must resolve** — Deliberately under-specified. Each
  has more than one defensible answer. The acceptance suite does **not** pin a
  particular answer; it pins **consistency with the answer the solution
  documents**, so an undocumented choice fails even if the behavior is sane.
  | # | Ambiguity | Acceptable resolutions | How acceptance pins it |
  |---|-----------|------------------------|------------------------|
  | **A-1** | **Idempotency:** does shortening the *same* URL twice return the *same* code or a new one? | (a) **Idempotent/dedupe** — return the existing code (201 or 200, documented) and do **not** reset `clicks`. (b) **Always-new** — mint a distinct code per request; both codes redirect to the same target and count clicks independently. | Suite POSTs the same URL twice and asserts the documented branch: under (a) both responses carry the same `code` and stats show one link with preserved clicks; under (b) codes differ, both redirect, and counters are independent. Mixed behavior across repeats fails either way. |
  | **A-2** | **Code length & charset.** | Any fixed or bounded length in `[4, 12]` over a documented URL-safe alphabet (base62 `[0-9A-Za-z]` recommended; base36 or a homoglyph-reduced alphabet is fine). Must be declared as a regex in the OpenAPI spec and the data-model doc. | Suite mints ≥ 50 codes and asserts every one matches the declared regex, all are unique, and none equals a reserved segment from FR-11. |
  | **A-3** | **URL normalization / trailing slash.** Is `https://ex.com/a` distinct from `https://ex.com/a/`? Is the input stored verbatim or canonicalized (case-folded host, default port stripped, fragment dropped)? | (a) **Store verbatim, no normalization** — `Location` is byte-identical to the submitted URL. (b) **Documented canonicalization** — state exactly which transforms are applied. | Suite asserts `Location` and `stats.url` equal the documented transform of the input, and that the *same* transform is applied on every path (create, redirect, stats). Under A-1(a), dedupe must key on the same normalized form it stores. |

## 2. Technical Requirements

- **2.1 Interface / API contract**

  | Method | Path | Success | Response body |
  |--------|------|---------|---------------|
  | `POST` | `/api/shorten` | **201** | `{"code": "<str>", "short_url": "<absolute url>"}` |
  | `GET` | `/{code}` | **302** | *(empty/any)* — `Location: <target url>` |
  | `GET` | `/api/stats/{code}` | **200** | `{"url","code","clicks","created_at"}` |
  | `DELETE` | `/api/{code}` | **204** | *(empty)* |
  | `GET` | `/health` | **200** | `{"status":"ok", ...}` |

  ```http
  POST /api/shorten HTTP/1.1
  Content-Type: application/json

  {"url": "https://example.com/a/very/long/path?utm_source=email"}

  HTTP/1.1 201 Created
  Content-Type: application/json

  {"code": "aB3xK9", "short_url": "http://127.0.0.1:8000/aB3xK9"}
  ```

  ```http
  GET /aB3xK9 HTTP/1.1

  HTTP/1.1 302 Found
  Location: https://example.com/a/very/long/path?utm_source=email
  ```

  ```http
  GET /api/stats/aB3xK9 HTTP/1.1

  HTTP/1.1 200 OK
  Content-Type: application/json

  {"url": "https://example.com/a/very/long/path?utm_source=email",
   "code": "aB3xK9",
   "clicks": 7,
   "created_at": "2026-08-24T18:04:11Z"}
  ```

  **Response field contract (schema-validated):**
  | Field | Type | Constraint |
  |-------|------|------------|
  | `code` | string | matches the A-2 regex; stable for the life of the link |
  | `short_url` | string | absolute `http(s)` URL whose path is exactly `/{code}` |
  | `url` | string | the stored target, per the A-3 policy |
  | `clicks` | integer | `≥ 0`, monotonic non-decreasing for a live code |
  | `created_at` | string | ISO-8601 UTC, parseable by `datetime.fromisoformat` |

  **Error model:**
  | Status | Condition |
  |--------|-----------|
  | **400** | Invalid/missing/oversized `url`, non-JSON body, forbidden scheme (FR-2) |
  | **404** | Unknown or deleted code on any route |
  | **405** | Known path, unsupported method |

  Error responses on `/api/*` MUST be `Content-Type: application/json` with a
  non-empty human-readable message under a **single documented key** (`detail`,
  `error`, or `message` — pick one, use it everywhere, declare it in the OpenAPI
  spec). Acceptance asserts the status code strictly and the *declared* key's
  presence. Stack traces or HTML error pages on any documented path are a failure.

- **2.2 Architecture constraints**
  - At least two separated layers: an **HTTP/transport** layer (routing,
    validation, status codes) and a **storage** layer (SQL, transactions). No SQL
    string literals in route handlers.
  - All SQL is **parameterized**. String-interpolated SQL is an automatic `QUA` 0
    and a security finding even if no test exploits it.
  - Single process, single SQLite file. No background worker, no message queue,
    no cache tier, no external network calls at runtime.
  - The DB connection strategy (per-request connection, thread-local, or pool)
    must be safe under the server's concurrency model. `check_same_thread=False`
    without a serialization discipline is a defect, not a shortcut.
  - Configuration comes from environment variables (§2.5). No hardcoded absolute
    paths, no writing outside the workspace or the configured DB path.

- **2.3 Data model**

  ```sql
  CREATE TABLE IF NOT EXISTS links (
      code       TEXT PRIMARY KEY,
      url        TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      clicks     INTEGER NOT NULL DEFAULT 0
  );
  ```

  - Additional columns/indexes are permitted (e.g. an `id INTEGER` autoincrement
    for base62 derivation, or `CREATE UNIQUE INDEX ... ON links(url)` to implement
    A-1(a)). Removing or renaming the four columns above is not.
  - The schema must be created idempotently on startup so a fresh DB file works
    with no manual migration step and an existing DB file is left intact.
  - **Code generation — document the choice** in `design/DATA_MODEL.md`:
    | Strategy | Mechanics | Trade-off to state |
    |----------|-----------|--------------------|
    | **base62 of autoincrement id** | Insert row, encode `id` in base62. | Deterministic and collision-free, but codes are enumerable/guessable and leak volume. Needs a two-step insert or a computed column. |
    | **random + collision retry** | Draw *k* random chars, `INSERT`, retry on `UNIQUE` violation, bounded attempts. | Opaque codes, but requires a real retry loop and a defined behavior when attempts are exhausted (must be a 5xx, never a silent overwrite of an existing code). |
  - The increment in FR-4 must be expressed so that the datastore, not Python,
    owns the arithmetic — e.g. `UPDATE links SET clicks = clicks + 1 WHERE code = ?`
    inside a committed transaction. A `SELECT` followed by a Python `+ 1` and an
    `UPDATE ... SET clicks = ?` is the canonical lost-update bug this rung exists
    to catch.

- **2.4 Technology constraints**
  - Python ≥ 3.11.
  - Web framework: **FastAPI** or **Flask** (plus its own server: `uvicorn` /
    `waitress` / `flask run` — declare it). No other framework.
  - Persistence: **SQLite**. The stdlib `sqlite3` module is acceptable and
    sufficient; an ORM (SQLAlchemy) is permitted but not rewarded. No Postgres,
    Redis, or any process the harness would have to provision.
  - Dependencies pinned in `solution/requirements.txt` and installable offline
    from the harness cache. Anything not declared there does not exist at run time.
  - The service must bind `127.0.0.1` on a port supplied by the harness and must
    not require root, Docker, or a writable directory outside the workspace.

- **2.5 Entrypoint contract** — `kind: http-service`. The harness owns process
  lifecycle; the solution owns being startable, pollable, and killable.

  ```yaml
  entrypoint:
    kind: http-service
    start_cmd: "python -m solution.main"      # must honor the env vars below
    base_url: "http://127.0.0.1:${PORT}"
    health_path: "/health"
    ready_timeout_s: 15
  env:
    PORT:              # harness-assigned free port; bind exactly this
    URLSHORT_DB:       # absolute path to a throwaway SQLite file (may not exist yet)
    URLSHORT_SEED:     # integer; seed any RNG used for code generation
    URLSHORT_BASE_URL: # optional; if set, short_url MUST use it verbatim as prefix
  ```

  - Startup MUST complete and `/health` MUST return 200 within `ready_timeout_s`.
  - The process MUST exit cleanly on `SIGTERM` within 5 s, flushing/committing all
    accepted writes. The restart test in §6.3 depends on this.
  - If `URLSHORT_BASE_URL` is unset, `short_url` is derived from the request
    (`Host` header or configured bind address); either way its path is `/{code}`.
  - The service MUST NOT delete or recreate an existing `URLSHORT_DB` on startup.
    Wiping the DB at boot passes every single-process test and fails FR-10.

## 3. Non-Functional Requirements

- **3.1 Performance & concurrency**
  - **NFR-1 Latency.** On localhost under light load (single client, warm process,
    ≤ 8 concurrent connections), **redirect (`GET /{code}`) p95 < 50 ms** and
    p99 < 150 ms, measured client-side over 200 requests after a 20-request
    warmup. `POST /api/shorten` p95 < 100 ms. A global mutex serializing every
    request is acceptable *only* if it still meets this budget.
  - **NFR-2 Concurrency exactness (load-bearing).** Given a fresh code and
    **N = 200** concurrent `GET /{code}` requests issued from ≥ 16 workers,
    `GET /api/stats/{code}` afterwards MUST report **clicks == 200 exactly** —
    not 199, not 201. No lost updates, no double counting, no
    `sqlite3.OperationalError: database is locked` surfacing as a 5xx to a
    client. This is the single most important non-functional requirement on this
    rung and is **part of the hard gate** (§7.3).

- **3.2 Reliability & error handling**
  - **NFR-3.** Writes are durable at response time: a 201 or a 302 that has been
    returned to a client implies the corresponding row/increment is committed. A
    `SIGKILL` immediately after a response may lose nothing already acknowledged.
    Data survives an orderly stop/start cycle (FR-10). Unexpected internal
    failures return a JSON 5xx with no stack trace and are logged; they never
    return 200 with wrong data. Retries of a `DELETE` are safely idempotent in
    effect (204 then 404, never a 500).

- **3.3 Security**
  - **NFR-4.** (a) **Scheme allowlist:** only `http` and `https` are accepted;
    `javascript:`, `file:`, `data:`, `ftp:`, and scheme-relative inputs are
    rejected with 400 — this is the mitigation for turning the service into a
    script/exfiltration vector. (b) **Open-redirect posture:** redirecting to
    caller-supplied targets is the product, so the mitigation is the allowlist
    plus refusing control characters (`CR`/`LF`/`NUL`) anywhere in the URL, so a
    caller can never inject a second header into the 302 response. (c)
    **Parameterized SQL only** — no interpolation, and codes from the path are
    treated as untrusted data. (d) **Size limits:** `url` ≤ 2048 bytes and total
    request body ≤ 8 KiB; over-limit → 400 (not 413, not a hang, not an OOM). (e)
    Path traversal or SQL metacharacters in `{code}` produce 404, never an error
    page or a query error.

- **3.4 Accessibility** — **N/A** — no required human-facing UI. If the optional
  landing form (§5.3) is produced it is a stretch artifact and is not scored for
  WCAG conformance at this rung; a11y becomes Required at L6.

- **3.5 Maintainability**
  - **NFR-5.** `ruff` and `pyright` clean. Layered per §2.2 with the storage seam
    importable and testable independently of the web framework. Public functions
    and every route handler carry docstrings; the §1.6 resolutions are documented
    in code *and* in `design/`. Cyclomatic complexity ≤ 10 per function. No
    duplicated SQL for the same operation in two places.

- **3.6 Observability**
  - **NFR-6.** `GET /health` per FR-7, plus one **structured log line per request**
    to stdout or stderr, machine-parseable (JSON preferred), containing at minimum:
    timestamp, method, path (or route template), status code, duration in ms, and
    — for code-bearing routes — the `code`. Logs must not contain the full target
    URL at `INFO` if it carries credentials in userinfo; truncate or omit. Startup
    logs the resolved DB path and bind address.

- **3.7 Portability / footprint**
  - **NFR-7.** `pip install -r solution/requirements.txt` then `start_cmd` is the
    entire install path. Cold start to healthy < 5 s. Idle RSS < 200 MB. No
    compiled extensions requiring a toolchain. Runs on Linux with only a writable
    `URLSHORT_DB` path.

## 4. The Ask (Deliverables & Definition of Done)

- **4.1 Required artifacts**
  | Path | Contents |
  |------|----------|
  | `solution/main.py` | Entrypoint honoring §2.5 env vars; binds `PORT`; handles `SIGTERM`. |
  | `solution/app.py` | Routes, request validation, status-code mapping, error handlers. |
  | `solution/storage.py` | Schema init, parameterized queries, transactional increment. |
  | `solution/codec.py` | Code generation + reserved-word guard (may fold into storage). |
  | `solution/requirements.txt` | Pinned dependencies. |
  | `solution/README.md` | How to run; **the §1.6 A-1/A-2/A-3 resolutions, stated explicitly**. |
  | `design/openapi.yaml` | OpenAPI 3.x for all five endpoints incl. error responses and the A-2 code pattern. |
  | `design/DATA_MODEL.md` | Schema, indexes, the code-generation choice + trade-off, the atomic-increment strategy. |
  | `design/PRD.md` | PRD-lite: problem, scope/non-goals, the §1.3 stories, success metrics. |
  | `design/JTBD.md` | Jobs-to-be-done for the Integrator and Operator (§5.1). |

- **4.2 Definition of Done**
  - [ ] `smoke` tests pass against a locally started server.
  - [ ] `acceptance` suite ≥ 95% **and** the NFR-2 concurrency-exactness assertion
        passes (hard gate, §7.3).
  - [ ] Server starts from a clean checkout with only declared deps, becomes
        healthy < 15 s, and exits cleanly on `SIGTERM`.
  - [ ] Data and click counts verified present after a stop/restart cycle.
  - [ ] `ruff` + `pyright` clean; no interpolated SQL anywhere.
  - [ ] All four `design/` artifacts exist, are internally consistent, and the
        OpenAPI spec matches the implemented responses (path, status, schema).
  - [ ] A-1, A-2, A-3 resolved, implemented consistently, and documented in both
        `solution/README.md` and `design/`.

- **4.3 Acceptance criteria**
  | ID | Criterion | Traces to |
  |----|-----------|-----------|
  | **AC-1** | Full lifecycle over real HTTP: shorten → 201, redirect → 302 + correct `Location`, stats → 200 with `clicks == 1`, delete → 204, then all reads → 404. | FR-1,3,5,6,8 |
  | **AC-2** | Every documented bad input yields **400** with the declared JSON error key; no 422, no 500, no HTML. | FR-2, NFR-4 |
  | **AC-3** | 200 concurrent redirects on a fresh code yield `clicks == 200` exactly, with zero 5xx responses. | FR-4, **NFR-2** |
  | **AC-4** | After `SIGTERM` + restart on the same DB file, codes still redirect and `clicks`/`created_at` are unchanged. | FR-10, NFR-3 |
  | **AC-5** | Unknown code → 404 and wrong method → 405 on every route. | FR-8, FR-9 |
  | **AC-6** | `/health` returns 200 on an empty DB and after load. | FR-7, NFR-6 |
  | **AC-7** | All success responses validate against the §2.1 schema; 50 minted codes match the declared A-2 regex, are unique, and avoid reserved segments. | FR-11, A-2 |
  | **AC-8** | The A-1 and A-3 policies behave exactly as documented, repeatably. | §1.6 |
  | **AC-9** | Redirect p95 < 50 ms under the NFR-1 protocol. | NFR-1 |
  | **AC-10** | Required `design/` artifacts present and consistent with the implementation. | §5.4, `FID` |

## 5. Discovery & Design Activities

Consistent with the **L5 row** of `framework/ARTIFACT_GRADIENT.md`.

- **5.1 User research**
  - **Jobs-to-be-done / needs analysis — Required.** The API has consumers whose
    jobs shape the contract (batch minting, idempotent retries after a timeout,
    reporting cadence). Produce `design/JTBD.md` covering the Integrator and the
    Operator: the job, the current workaround, the trigger, and the "hired for"
    criterion. The A-1 idempotency decision must be justified *from* a JTBD
    statement (e.g. "a bot retrying a timed-out POST must not mint duplicates"),
    not asserted.
  - **Stakeholder/user interviews — Optional/Stretch.**
  - **Personas — Optional/Stretch.** The archetype table in §1.2 is sufficient.
  - **Usability testing — N/A** — no human-facing UI at this rung.

- **5.2 Product design**
  - **Spec + acceptance criteria — Required** (this document plus §4.3).
  - **PRD-lite — Required.** `design/PRD.md`: problem, in/out of scope, the §1.3
    user stories, and success metrics (e.g. redirect p95, zero lost clicks,
    zero data loss across restarts).
  - **User stories — Required** (§1.3 is the baseline; the PRD may extend).
  - **Definition of Done — Required** (§4.2).
  - **Prioritized backlog — Optional/Stretch.** The FR set is small and fully
    known; grooming it would be ceremony.
  - **Sprint plans / retrospectives — N/A** — single delivery, no iteration
    protocol at this rung (that is L7).

- **5.3 Interaction / visual design**
  - **Interface/API contract design — Required.** `design/openapi.yaml` is the
    design artifact: paths, request/response schemas, status codes, the error
    object, and the A-2 code pattern as a regex. It must be written to describe
    the *intended* contract and must end the run matching reality.
  - **Wireframes (lo-fi) — Optional/Stretch.** A minimal landing form (paste URL →
    get short link) is permitted; if built, sketch it under `design/` first. It is
    never exercised by acceptance.
  - **Interaction/state specs — Optional/Stretch.** A short state note for the link
    lifecycle (`created → clicked* → deleted`) is welcome.
  - **Hi-fi mockups, design tokens, a11y annotations — N/A** — L6 concerns.

- **5.4 Design artifacts to produce**
  | File | Required? | Scored under |
  |------|-----------|--------------|
  | `design/openapi.yaml` | **Required** | `FID` — existence + spec/implementation diff |
  | `design/DATA_MODEL.md` | **Required** | `FID` — schema + code-gen + concurrency rationale |
  | `design/PRD.md` | **Required** | `FID` — traceability to FR/AC |
  | `design/JTBD.md` | **Required** | `FID` — grounds the A-1 decision |
  | `design/wireframe-*.{md,png,svg}` | Optional | not scored |

## 6. Verification Method

- **6.1 Test tiers**
  - **`smoke` (visible)** — ~6 worked request/response examples the agent can run
    against its own server, shown curl-style so the expected wire behavior is
    unambiguous:
    ```console
    $ curl -sS -X POST localhost:$PORT/api/shorten \
        -H 'content-type: application/json' -d '{"url":"https://example.com/hello"}'
    HTTP/1.1 201 Created
    {"code":"aB3xK9","short_url":"http://127.0.0.1:8000/aB3xK9"}

    $ curl -sSi localhost:$PORT/aB3xK9
    HTTP/1.1 302 Found
    Location: https://example.com/hello

    $ curl -sS localhost:$PORT/api/stats/aB3xK9
    {"url":"https://example.com/hello","code":"aB3xK9","clicks":1,
     "created_at":"2026-08-24T18:04:11Z"}

    $ curl -sSi -X POST localhost:$PORT/api/shorten \
        -H 'content-type: application/json' -d '{"url":"javascript:alert(1)"}'
    HTTP/1.1 400 Bad Request

    $ curl -sSi -X DELETE localhost:$PORT/api/aB3xK9
    HTTP/1.1 204 No Content

    $ curl -sS localhost:$PORT/health
    {"status":"ok"}
    ```
  - **`acceptance` (held-out)** — the authoritative behavioral matrix, all over
    real HTTP against a live process:
    | Group | Coverage |
    |-------|----------|
    | Lifecycle | create → redirect → stats → delete → 404 (AC-1), multiple links independent |
    | Validation | full bad-input table: non-JSON, missing/empty/non-string `url`, `javascript:`/`file:`/`data:`/`ftp:`/`//host`, no host, 2049-byte URL, CR/LF in URL (AC-2) |
    | **Concurrency** | N=200 parallel redirects → `clicks == 200` exactly, zero 5xx (AC-3) |
    | **Persistence** | SIGTERM → restart same DB → data + counts intact (AC-4) |
    | Routing | unknown code 404 on all three code routes; 405 matrix (AC-5) |
    | Health | empty DB and post-load (AC-6) |
    | Schema | every success response validated against §2.1; 50 codes vs the declared regex; reserved-segment check (AC-7) |
    | Documented policy | A-1 double-shorten branch, A-3 normalization/trailing-slash branch (AC-8) |
    | Performance | redirect p95 (AC-9) |
    | Artifacts | `design/` presence + OpenAPI-vs-implementation diff (AC-10) |
  - **`adversarial` (hidden, run once)** — inputs the agent could not have coded to:
    - Dangerous/exotic schemes: `JavaScript:` (mixed case), `jAvAsCrIpT:%0aalert(1)`,
      `data:text/html;base64,...`, `file:///etc/passwd`, `http:/example.com` (one
      slash), `https://` (no host), unicode-confusable and punycode hosts.
    - Oversized: 2048-byte URL (boundary, accepted) vs 2049 (rejected); 1 MiB body.
    - Injection: `{code}` values of `'; DROP TABLE links;--`, `../../etc/passwd`,
      `%2e%2e%2f`, a 5000-char code, `null` bytes → all 404, never 500.
    - Method matrix on every path including `HEAD`, `OPTIONS`, `PATCH`, `TRACE`.
    - **Concurrent shorten of the same URL** from 32 workers simultaneously —
      asserts the A-1 policy holds under a race (dedupe must not produce two rows;
      always-new must not produce duplicate codes or a `UNIQUE` 500).
    - **Code-collision path** — the RNG seed is fixed so a collision is forced;
      the service must retry and succeed, never overwrite an existing mapping and
      never hand out a code already in use.
    - Interleaved delete-during-redirect: delete a code while redirects are in
      flight — every request must return exactly 302 or 404, never 500, and stats
      must never resurrect.
    - Redirect on a code whose target is 2048 bytes (header-size handling).

- **6.2 "Working" definition** — Both conditions, together:
  1. **≥ 95%** of `acceptance` assertions pass, **and**
  2. the **NFR-2 concurrency-exactness assertion passes**. It is exempt from the
     5% slack: a run may lose up to 5% of assertions anywhere *except* here. A
     shortener that miscounts under load is not working, however well it demos.

- **6.3 Verification mechanics** — `kind: http-service`; the real path is a real
  server, a real socket, and a real SQLite file.
  | Step | Mechanism |
  |------|-----------|
  | Start | Harness allocates a free port, creates a throwaway `URLSHORT_DB` in a per-run tmpdir, sets `URLSHORT_SEED`, launches `start_cmd` as a subprocess with captured stdout/stderr. |
  | Ready | Poll `GET /health` until 200 or `ready_timeout_s`; failure to become healthy = total acceptance failure (gate fail), reported distinctly from behavioral failures. |
  | Behavioral | `pytest` + `httpx`/`requests` with redirects **disabled** so the 302 and `Location` are asserted directly, never followed silently. |
  | Schema | `jsonschema`/`pydantic` validation of every success body; the A-2 regex is read from the solution's own OpenAPI spec, so the solution is held to what it declared. |
  | **Concurrency probe** | Fresh code; `ThreadPoolExecutor` (≥ 16 workers) with a `threading.Barrier` release so requests actually overlap; 200 requests; assert 200 responses were 302, zero 5xx, then `stats.clicks == 200`. Repeated for **3 trials**, each on a new code; **all three must be exact**. |
  | **Restart persistence** | Create links, drive a known number of clicks, `SIGTERM` the process, wait for exit (≤ 5 s, else `SIGKILL` and fail), relaunch with the **same** `URLSHORT_DB`, re-poll health, then assert `clicks`, `url` and `created_at` are byte-identical and redirects still work. |
  | Teardown | `SIGTERM`; tmpdir and DB discarded. Server stdout/stderr archived with the run. |
  | Determinism | Fresh DB + fixed seed per test module; no shared state between groups; no wall-clock assertions beyond ISO-8601 parseability and ordering. |
  | Flaky-guard | Per `VERIFICATION_CONTRACT.md §4`: a concurrency trial is *invalid* (re-run, up to 2 retries) only if the **harness** faults — transport-level connection exhaustion or the host failing a pre-run load calibration. A count mismatch is **never** retried; it is a hard fail. The AC-9 latency assertion is best-of-3 and is recorded **advisory (excluded from the gate denominator)** if the host fails load calibration — timing noise must not decide a gate, but lost updates must. |

- **6.4 Anti-gaming measures**
  - Acceptance URLs and codes are **randomized per run**, so no expected value can
    be hardcoded; the A-2 regex is read from the solution's own spec.
  - The **restart test kills in-memory shortcuts**: an in-process counter or dict
    cache passes every single-process test and fails AC-4 outright.
  - The **concurrency probe kills the naive read-modify-write**, which is otherwise
    invisible; a strategy cannot pass it by retrying or by sleeping (sleeps blow
    AC-9 and the wall-clock budget).
  - Redirects are asserted with following **disabled**, so a service that returns
    200 with an HTML meta-refresh, or 301 instead of 302, fails visibly.
  - `acceptance` is never run against an in-process test client (`TestClient`,
    `app.test_client()`); mock-only evidence is not acceptance evidence at L5.
  - The OpenAPI-vs-implementation diff catches a spec written to look right while
    the code does something else.
  - Reading held-out tests, writing outside `solution/` + `design/`, or probing
    the harness tmpdir are `gaming_events` → disqualification per
    `CONVERGENCE_METRICS.md §6`.

## 7. Scoring Rubric

- **7.1 Weight profile** (sum 100):
  `COR 28 · ROB 15 · EFF 14 · AUT 13 · QUA 12 · REG 10 · FID 8`.
  `REG` is live at L5 even without prior sprints: the acceptance suite is
  partitioned into feature groups (shorten / redirect / stats / delete / health /
  persistence) and the harness re-runs the full suite twice — once on a cold DB,
  once on a DB carried over from a prior group and a restart. An assertion that
  passes in the first pass and fails in the second, or a group broken by work on a
  later group, is a regression.

- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | **COR** | acceptance < 95% or concurrency-exactness fails (gate fail) | ≥ 95% acceptance but adversarial exposes real gaps (scheme bypass, 500s on hostile codes, A-1 race produces duplicates) | 100% acceptance, exact counts on all 3 trials, ≥ 95% adversarial |
  | **ROB** | 5xx or stack traces on documented bad input; SQL errors reach the client | most invalid inputs handled, but boundary/exotic cases leak (mixed-case `JavaScript:`, oversized body, delete-during-redirect 500) | every documented and hidden hostile input yields the right 4xx/404 with a clean JSON error; zero 5xx across the adversarial run |
  | **EFF** | > 45 iterations or > 90 min, or never passed | passed near the hard cap, or many failed runs — typically re-discovering concurrency by trial and error | passed ≤ 18 iterations, under time/token budget, ≤ 1 failed run before pass; concurrency correct **by design** on first attempt |
  | **AUT** | any `rescue` (human wrote the increment/transaction, or answered a §1.6 ambiguity as a `hint`) | one `clarify`/`unblock`, or ≥ 1 dead-end rewrite of the storage layer | zero interventions, zero dead ends |
  | **QUA** | lint/type errors, or interpolated SQL anywhere | clean, but no storage seam (SQL in handlers), thin docstrings, duplicated queries | layered per §2.2, storage independently testable, parameterized throughout, documented policies, complexity ≤ 10 |
  | **REG** | later work broke earlier-passing groups and shipped that way | 1–2 regressions or oscillations, caught and fixed before "done" | zero `regressions_introduced`, zero oscillations, both suite passes identical |
  | **FID** | required `design/` artifacts missing | artifacts present but thin or drifted from the implementation (spec says 400, code returns 422) | all four artifacts present, mutually consistent, OpenAPI matches reality, A-1 justified from a JTBD statement |

- **7.3 Hard gate** — `acceptance_floor = 0.95`, **plus** a named non-negotiable:
  the **NFR-2 concurrency-exactness assertion must pass** (all 3 valid trials
  exact). Failing it fails the run regardless of the overall pass fraction. This
  is the only rung where a single assertion carries gate authority, and that is
  deliberate: concurrency correctness is the difficulty L5 exists to measure, and
  it is exactly the failure a 95% floor would otherwise hide.

- **7.4 Pass threshold** — **68**. Lower than L0's 85 because L5 has genuinely hard
  surface (process lifecycle, transactions, races) where a rough but honest
  convergence is still informative; a run scoring 68–84 is `Converged` and a run
  below 68 that cleared the gate is a strategy that got there by brute force.

## 8. Convergence Signals

- **8.1 Healthy convergence** — Design before code: JTBD and OpenAPI drafted early,
  the three §1.6 ambiguities named and resolved in writing *before* implementation
  rather than discovered by a failing test. A storage seam exists from the first
  commit. The atomic increment is written as
  `UPDATE links SET clicks = clicks + 1 WHERE code = ?` **because the agent
  reasoned about concurrency**, not because a probe failed. The server is started
  and curled by the agent itself early (a real process, not just unit tests).
  Restart persistence is verified by the agent before declaring done. ≤ 18
  iterations, zero interventions, the first acceptance run passes or misses only
  on a documented-policy detail.

- **8.2 Pathological patterns** — These are the L5-specific failure shapes worth
  naming, and how each surfaces:
  | Pattern | Telemetry signature |
  |---------|---------------------|
  | **Read-modify-write increment** (`SELECT` → Python `+1` → `UPDATE`) | Passes all smoke, fails AC-3 with `clicks` in the 150–199 band. Repeated "fix" attempts that only shrink the gap = the strategy is tuning, not understanding. |
  | **In-memory counter / dict cache** | AC-3 passes, AC-4 fails. High `oscillations` if the agent "fixes" persistence by re-adding the cache for speed. |
  | **Sleep/lock-thrash to dodge races** | AC-3 passes but AC-9 fails; wall-clock spikes; global mutex plus per-request connection churn. |
  | **`database is locked`** | 5xx count > 0 in the concurrency probe; `OperationalError` in captured stderr. Usually `check_same_thread=False` without WAL or a serialization discipline. |
  | **DB wiped at startup** | AC-4 fails deterministically; `DROP TABLE`/`unlink` in `main`. Passes 100% of the agent's own tests. |
  | **422 instead of 400** | Framework defaults left in place — the agent never exercised its own error paths over HTTP. Cluster of AC-2 failures. |
  | **Mock-only verification** | The agent's tests all use `TestClient`; the process never actually starts (`ready_timeout_s` exceeded on the harness run). Catastrophic gate failure with a high self-reported confidence — a strong strategy-level finding. |
  | **Ambiguity escalation** | An `interventions` entry tagged `clarify` on A-1/A-2/A-3 caps `AUT`; the ambiguities exist precisely to test unilateral, documented decision-making. |
  | **Spec drift** | `design/openapi.yaml` written once and never reconciled; OpenAPI diff failures at AC-10 while code tests pass. |

- **8.3 Instrumentation notes** — Beyond the shared `CONVERGENCE_METRICS.md` set,
  capture for this rung:
  - `server_start_attempts` and `time_to_healthy_s` — a new failure mode at L5:
    the deliverable can fail to *run* rather than fail to be correct.
  - `iterations_with_server_start_failure` — distinguishes environment/lifecycle
    thrash from behavioral thrash.
  - `concurrency_trials` results as raw observed counts (e.g. `[200, 197, 200]`),
    not just pass/fail — the distribution says whether the bug is a lost update
    (slightly under N) or double counting (over N).
  - `db_locked_errors` — count of `OperationalError`/`database is locked` in
    captured server logs across the whole run.
  - `redirect_p50/p95/p99_ms` plus the host load-calibration figure, so an
    advisory-marked AC-9 is auditable.
  - `db_bytes_before_restart` / `db_bytes_after_restart` and file identity — cheap
    detection of a boot-time wipe.
  - `openapi_diff_findings` — count of spec/implementation mismatches, feeding `FID`.
