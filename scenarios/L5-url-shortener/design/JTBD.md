# Jobs-to-be-Done — URL Shortener

## Role: Integrator

**Who:** A backend developer or bot/service that calls the URL shortener programmatically from another service.

**Job:** Mint short links programmatically from a bot or service without building link infrastructure.

**Current workaround:**
- Embed raw long URLs in messages — breaks in SMS (character limits), print (unreadable), and some chat systems (no click tracking).
- Use a hosted shortener (bit.ly, tinyurl.com) — unacceptable for internal or regulated data because it sends link targets to a third party, and the service may change terms or disappear.

**Trigger:** Need to send a campaign link via SMS where long URLs break, or need to track click engagement on a link without relying on an external analytics vendor.

**Hired-for criterion:**
- `POST /api/shorten` returns a short URL I can embed immediately (< 100 ms p95).
- **Idempotent retry on timeout doesn't mint duplicates** — a bot retrying a timed-out POST must not mint two codes for the same URL. If the first request committed but the response was lost in transit, the retry must return the existing code rather than creating a duplicate. This is the primary justification for **A-1 (idempotent/dedupe)**: the service deduplicates on the verbatim URL and returns 201 with the existing code, preserving click counts.
- `GET /api/stats/{code}` returns an accurate, monotonic click count that I can poll to report campaign engagement.
- `DELETE /api/{code}` removes a link immediately, so a link published in error stops working without a service restart.
- Malformed or dangerous URLs (javascript:, file:, data:, ftp:, scheme-relative) are rejected at creation time with a 400, so the service never mints a link that could execute script or read local files on a recipient's machine.

---

## Role: Operator

**Who:** The person or automation responsible for running the URL shortener process and answering "is it up, is data safe".

**Job:** Run the service as a sidecar and know it's healthy without reading source code.

**Current workaround:**
- Manual `curl` checks against the service to see if it responds — no structured output, no machine-parseable health signal.
- No structured logs — failures require reading raw output or guessing from process exit codes.
- No persistence guarantee — unclear whether a restart loses data.

**Trigger:** A deploy event or process crash; need to confirm the service is healthy and that data (links and click counts) survived the restart.

**Hired-for criterion:**
- `GET /health` returns 200 with `{"status": "ok"}` when the datastore is reachable — this is a real health check (it touches the database) that can be wired into a supervisor, load balancer, or Kubernetes liveness probe without reading source code.
- Structured JSON logs to stdout — one line per request containing timestamp, method, path, status code, and duration in ms — so failures are machine-parseable and auditable.
- Startup logs the resolved DB path and bind address, so the operator can confirm which file is being used.
- **Data and counts survive a restart** — after `SIGTERM` + restart on the same `URLSHORT_DB` file, all codes still redirect and all click counts are byte-identical. This means no in-memory-only state: everything is committed to SQLite before the response is returned (NFR-3). The operator can deploy a new version, restart the process, and trust that no reporting data was silently lost.
- Cold start to healthy in < 5 s; idle RSS < 200 MB — runnable as a lightweight sidecar alongside the main application.
