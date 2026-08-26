# Product Requirements Document (PRD-lite) — URL Shortener

## Problem Statement

Teams embedding links in emails, SMS messages, chat bots, and print media need short, stable, opaque links that redirect to long canonical URLs, plus a truthful count of how often each link was followed. Existing hosted shorteners are unacceptable for internal or regulated links because they send data to a third party and may disappear or change terms. The need is a small, self-hosted HTTP service with durable storage that can be run as a single process alongside the application that generates the links.

## In Scope

- URL shortening via `POST /api/shorten` — accepts a valid http/https URL, returns a unique 6-character base62 short code and an absolute short URL.
- Redirect via `GET /{code}` — returns HTTP 302 with `Location` header equal to the stored URL.
- Click statistics via `GET /api/stats/{code}` — returns the stored URL, code, click count, and creation timestamp.
- Link deletion via `DELETE /api/{code}` — removes a link; subsequent requests to that code return 404.
- Health endpoint via `GET /health` — returns `{"status": "ok"}` when the datastore is reachable.
- SQLite persistence — all data survives a process restart against the same database file.
- Concurrency-safe click counting — atomic increment via SQL `clicks = clicks + 1`; no lost updates under concurrent load.
- Input validation — scheme allowlist (http/https only), size limits (URL ≤ 2048 bytes, body ≤ 8 KiB), control character rejection.
- Structured request logging — one JSON line per request to stdout.

## Out of Scope

- Authentication, authorization, and API keys.
- User accounts and multi-tenant isolation.
- Custom ("vanity") codes chosen by the caller.
- Link expiry / TTL.
- Rate limiting.
- Analytics richer than a monotonic click counter (no referrer, geo, user-agent, unique visitors).
- QR codes.
- Bulk or list endpoints and pagination.
- Multi-node or replicated deployment.
- HTTPS termination.
- A database migrations framework.
- An admin UI or human-facing web interface (beyond the optional landing form).

## User Stories

- **US-1** As an *Integrator*, I want to POST a long URL and get back a short code and a ready-to-paste short URL, so that I can embed it in an outgoing message without building link infrastructure.
- **US-2** As an *End recipient*, I want a short link to send me to the intended destination immediately, so that the indirection is invisible to me.
- **US-3** As an *Integrator*, I want an accurate click count per code, so that I can report campaign engagement without an analytics vendor.
- **US-4** As an *Integrator*, I want to delete a code, so that a link published in error stops working immediately.
- **US-5** As an *Operator*, I want a health endpoint and structured request logs, so that I can wire the service into a supervisor and debug failures.
- **US-6** As an *Operator*, I want click counts and links to survive a process restart, so that a deploy or crash does not silently destroy reporting data.
- **US-7** As an *Integrator*, I want malformed and dangerous URLs rejected at creation time with a clear 4xx, so that my service never mints a link that executes script or reads a local file on a recipient's machine.

## Success Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Redirect p95 latency | < 50 ms (localhost, single client, warm process) | NFR-1: redirect is the hot path; users notice > 100 ms |
| Redirect p99 latency | < 150 ms | NFR-1: tail latency bound |
| Shorten p95 latency | < 100 ms | NFR-1: write path is less frequent |
| Concurrent click exactness | `clicks == N` exactly for N = 200 concurrent redirects, zero 5xx | NFR-2: the single most important non-functional requirement — a shortener that miscounts under load is not working |
| Data survival across restart | 100% — codes, click counts, and `created_at` values byte-identical after SIGTERM + restart on the same DB file | FR-10, NFR-3 |
| Zero 5xx on documented bad input | 0 — all documented invalid inputs return 4xx with a JSON error body | FR-2, ROB |
| Cold start to healthy | < 5 s | NFR-7 |
| Idle RSS | < 200 MB | NFR-7 |

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | Full lifecycle over real HTTP: shorten → 201, redirect → 302 + correct `Location`, stats → 200 with `clicks == 1`, delete → 204, then all reads → 404. |
| AC-2 | Every documented bad input yields 400 with the declared JSON error key (`detail`); no 422, no 500, no HTML. |
| AC-3 | 200 concurrent redirects on a fresh code yield `clicks == 200` exactly, with zero 5xx responses. |
| AC-4 | After SIGTERM + restart on the same DB file, codes still redirect and `clicks`/`created_at` are unchanged. |
| AC-5 | Unknown code → 404 and wrong method → 405 on every route. |
| AC-6 | `/health` returns 200 on an empty DB and after load. |
| AC-7 | All success responses validate against the §2.1 schema; 50 minted codes match the declared A-2 regex, are unique, and avoid reserved segments. |
| AC-8 | The A-1 and A-3 policies behave exactly as documented, repeatably. |
| AC-9 | Redirect p95 < 50 ms under the NFR-1 protocol. |
| AC-10 | Required `design/` artifacts present and consistent with the implementation. |

## Definition of Done

- [ ] `smoke` tests pass against a locally started server.
- [ ] `acceptance` suite ≥ 95% **and** the NFR-2 concurrency-exactness assertion passes (hard gate).
- [ ] Server starts from a clean checkout with only declared deps, becomes healthy < 15 s, and exits cleanly on SIGTERM.
- [ ] Data and click counts verified present after a stop/restart cycle.
- [ ] `ruff` + `pyright` clean; no interpolated SQL anywhere.
- [ ] All four `design/` artifacts exist, are internally consistent, and the OpenAPI spec matches the implemented responses.
- [ ] A-1, A-2, A-3 resolved, implemented consistently, and documented in both `solution/README.md` and `design/`.
