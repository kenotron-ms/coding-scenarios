# Lane sprint_0_mvp

## Outcome

Deliver Sprint 0 (MVP) of the L7 Kanban application under `scenarios/L7-kanban-sprints/solution/` and the accompanying design artifacts under `scenarios/L7-kanban-sprints/design/`. The application must boot with `make run`, pass `make migrate`, and expose a working board/column/card CRUD API plus an SPA, with durable SQLite persistence. All Sprint 0 acceptance criteria (AC-0.1 through AC-0.9) must pass. Design artifacts required for this sprint must exist and be consistent with what shipped.

Concrete files that must exist at the end:

- `scenarios/L7-kanban-sprints/solution/Makefile` — with `run`, `migrate`, `reset-db`, `test`, `lint` targets
- `scenarios/L7-kanban-sprints/solution/backend/` — FastAPI or Flask app with:
  - `api/` routes for boards, columns, cards, health
  - `services/` business logic layer
  - `repositories/` persistence layer
  - `migrations/0001_init.sql` (or `.py`) — creates board, column, card tables
- `scenarios/L7-kanban-sprints/solution/frontend/` — TypeScript + React + Vite SPA
- `scenarios/L7-kanban-sprints/solution/tests/sprint_0/` — strategy-owned smoke/unit tests for Sprint 0
- `scenarios/L7-kanban-sprints/solution/README.md`
- `scenarios/L7-kanban-sprints/design/prd.md`
- `scenarios/L7-kanban-sprints/design/backlog.md`
- `scenarios/L7-kanban-sprints/design/dod.md`
- `scenarios/L7-kanban-sprints/design/research/interviews.md`
- `scenarios/L7-kanban-sprints/design/research/jtbd.md`
- `scenarios/L7-kanban-sprints/design/research/personas.md`
- `scenarios/L7-kanban-sprints/design/sprints/sprint-0.md`
- `scenarios/L7-kanban-sprints/design/retros/retro-0.md`
- `scenarios/L7-kanban-sprints/design/wireframes/s0-board.md`
- `scenarios/L7-kanban-sprints/design/wireframes/s0-card-editor.md`
- `scenarios/L7-kanban-sprints/design/wireframes/s0-states.md`
- `scenarios/L7-kanban-sprints/design/mockups/s0-board-hifi.md`
- `scenarios/L7-kanban-sprints/design/tokens/tokens.json`
- `scenarios/L7-kanban-sprints/design/tokens/CHANGELOG.md`
- `scenarios/L7-kanban-sprints/design/a11y/annotations-s0.md`
- `scenarios/L7-kanban-sprints/design/a11y/wcag-checklist.md`
- `scenarios/L7-kanban-sprints/design/CHANGELOG-design.md`

## Steps

1. **Inception artifacts first** (before writing any code): author `design/research/personas.md` (the four canonical personas from REQUIREMENTS.md §1.2), `design/research/interviews.md` (≥3 write-ups grounded in the personas), `design/research/jtbd.md` (≥5 JTBD statements mapped to backlog items), `design/prd.md` (problem, personas, scope, success metrics, 5-sprint release plan), `design/backlog.md` (full five-sprint groomed backlog, ranked, estimated, sprint-sliced), and `design/dod.md` (the §4.2 checklist).

2. **Sprint 0 design artifacts**: `design/wireframes/s0-board.md`, `design/wireframes/s0-card-editor.md`, `design/wireframes/s0-states.md` (lo-fi wireframes for board, card editor, empty/loading/error states); `design/mockups/s0-board-hifi.md` (hi-fi board mockup); `design/tokens/tokens.json` (color, spacing, type scale, focus ring tokens v1); `design/a11y/annotations-s0.md` (landmarks, headings, focus order, labels); `design/a11y/wcag-checklist.md`; `design/CHANGELOG-design.md` (Sprint 0 entry dated).

3. **Backend — data model and migration**: Create `solution/backend/migrations/0001_init.sql` (or Alembic equivalent) that creates `board` (id, name, created_at, updated_at), `column` (id, board_id→board, name, created_at), `card` (id, column_id→column, title, description, created_at, updated_at) tables. Migration must be idempotent to re-run detection and applied by `make migrate`.

4. **Backend — layered architecture**: Implement `solution/backend/` with strict `api/ → services/ → repositories/` layering. No SQL in the API layer; no HTTP objects in the repository layer. Use Python ≥3.11 with FastAPI or Flask + SQLAlchemy. Use Pydantic (or equivalent) for validation.

5. **Backend — CRUD API**: Implement all Sprint 0 endpoints per REQUIREMENTS.md §2.1:
   - `GET/POST /api/boards`, `GET/PATCH/DELETE /api/boards/{board_id}`
   - `POST /api/boards/{board_id}/columns`, `PATCH/DELETE /api/columns/{column_id}`
   - `POST /api/columns/{column_id}/cards`, `GET/PATCH/DELETE /api/cards/{card_id}`
   - `GET /api/health` → `{status, version, schema_version}`
   - Error envelope: `{"error": {"code": "...", "message": "...", "field": "..."}}` on 400/404
   - `GET /api/boards/{id}` returns the full nested board (columns + cards) in one round trip, in stable order
   - Validation: board name ≤120 chars non-empty; column name ≤60 chars non-empty; card title ≤200 chars non-empty, description optional ≤4000 chars
   - Deleting a column cascades its cards (FR-0.2)
   - No 5xx on user-supplied bad input

6. **Backend — durable persistence**: Configure persistence via env var (SQLite for local, Postgres-compatible). Ensure `make reset-db` drops and re-migrates. Structured request logs (method, path, status, duration).

7. **Frontend — SPA**: Implement TypeScript + React 18+ + Vite SPA at `solution/frontend/`. Board list view, board detail view with columns and cards, card create/edit/delete modal, empty/loading/error states for all three surfaces. Full keyboard operability (every control reachable by Tab, visible focus ring). WCAG 2.1 AA: zero critical/serious axe-core violations on the board view.

8. **Makefile**: Implement `make run` (starts backend + built SPA on port 8080), `make migrate` (applies forward migrations), `make reset-db` (drops + re-migrates), `make test`, `make lint`. `make run` must work from a clean checkout on Linux with only declared dependencies.

9. **Strategy tests**: Write `solution/tests/sprint_0/` with smoke and unit tests covering AC-0.1 through AC-0.9 using pytest (API) and Playwright (E2E).

10. **Sprint plan and retro**: Write `design/sprints/sprint-0.md` (sprint goal, backlog slice with estimates, AC-0.1–0.9, DoD checklist, named risks) and `design/retros/retro-0.md` (what went well, what didn't, regression risk section noting this is the baseline, ≥1 concrete action into Sprint 1's backlog).

## Done when

The following command exits 0:
```
bash -c "test -f scenarios/L7-kanban-sprints/solution/Makefile && grep -r 'sprint_0' scenarios/L7-kanban-sprints/solution/tests/ && test -f scenarios/L7-kanban-sprints/design/sprints/sprint-0.md && test -f scenarios/L7-kanban-sprints/design/retros/retro-0.md"
```

This passes when:
- `solution/Makefile` exists
- At least one test file under `solution/tests/` references `sprint_0`
- `design/sprints/sprint-0.md` exists
- `design/retros/retro-0.md` exists

Additionally verify manually that all required design files listed in Outcome exist and that the backend API structure follows the layered architecture.

## Final step (REQUIRED)

After all the work above is done and the verifier check passes, write the file `artifacts/sprint_0_mvp.done` containing exactly `sprint_0_mvp:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished — it must be the LAST action taken.
