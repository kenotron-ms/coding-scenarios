# Lane sprint0_mvp

## Outcome

Implement Sprint 0 (MVP) of the L7 Kanban application under `scenarios/L7-kanban-sprints/solution/`. This is the baseline sprint that establishes the full project scaffold: backend API (boards, columns, cards CRUD), durable SQLite persistence, a React/TypeScript SPA, and all required design artifacts for Sprint 0.

Concrete files and directories to create (repo-relative paths):

```
scenarios/L7-kanban-sprints/solution/
  Makefile                          # targets: run, migrate, reset-db, test, lint
  backend/
    api/                            # FastAPI route handlers (boards, columns, cards, health)
    services/                       # Business logic (board_service, column_service, card_service)
    repositories/                   # SQLAlchemy persistence layer
    migrations/
      0001_init.sql (or .py)        # creates board, column, card tables
    main.py                         # FastAPI app entry point, port 8080
    requirements.txt
  frontend/
    src/
      components/                   # Board, Column, Card, CardEditor, EmptyState, LoadingState, ErrorState
      state/                        # App state management
      api/                          # Typed API client
    index.html
    package.json
    tsconfig.json
    vite.config.ts
  tests/
    smoke/
      sprint_0/                     # Playwright smoke tests: create board -> add column -> add card -> GET board shows all three
  README.md

design/
  prd.md
  backlog.md
  dod.md
  research/
    interviews.md                   # >= 3 persona-grounded write-ups
    jtbd.md                         # >= 5 JTBD statements mapped to backlog items
    personas.md                     # The four L7 personas (Priya, Marco, Jules, Sam)
  sprints/
    sprint-0.md                     # goal + backlog slice + AC + DoD + risks
  retros/
    retro-0.md                      # went well / didn't / regression risk / >= 1 action
  wireframes/
    s0-board.md  s0-card-editor.md  s0-states.md
  mockups/
    s0-board-hifi.md
  tokens/
    tokens.json                     # v1: color, spacing, type scale, focus ring
    CHANGELOG.md
  a11y/
    annotations-s0.md
    wcag-checklist.md
  CHANGELOG-design.md
```

Key implementation requirements:

- **Backend**: Python >= 3.11, FastAPI, SQLAlchemy, Pydantic. All routes under `/api/`. Error envelope: `{"error": {"code": "...", "message": "...", "field": "..."}}`. `GET /api/health` returns `{status, version, schema_version}`. `GET /api/boards/{id}` returns full nested board (columns + cards) in one round trip. Validation: board name <= 120 chars, column name <= 60 chars, card title <= 200 chars, card description <= 4000 chars. Unknown IDs return 404. Bad input returns 400. No 5xx on user input.
- **Persistence**: SQLite (file-based, not in-memory). Migration `0001_init` creates `board`, `column`, `card` tables. `make migrate` applies migrations. `make reset-db` drops and re-migrates. Process restart loses nothing.
- **Frontend**: TypeScript + React 18+, Vite build. SPA renders board view, supports all CRUD from UI, shows empty/loading/error states. Full keyboard operability with visible focus ring.
- **Accessibility**: WCAG 2.1 AA. Zero critical/serious axe violations. All controls keyboard-reachable.
- **Layering**: `api/` -> `services/` -> `repositories/`. HTTP objects must not reach repository layer; SQL must not reach API layer.
- **`make run`**: starts the backend serving the built SPA on port 8080.

## Steps

1. **Scaffold the project structure**: Create `scenarios/L7-kanban-sprints/solution/` with `Makefile`, `backend/`, `frontend/`, `tests/`, `README.md`. Also create `design/` at `scenarios/L7-kanban-sprints/design/` (or `design/` at repo root under the scenario path).

2. **Backend - data model and migration**: Write `migrations/0001_init.sql` creating `board` (id, name, created_at, updated_at), `column` (id, board_id, name, created_at), `card` (id, column_id, title, description, created_at, updated_at) tables. Write a migration runner that applies numbered SQL files in order.

3. **Backend - repository layer**: Implement `repositories/board_repo.py`, `repositories/column_repo.py`, `repositories/card_repo.py` with SQLAlchemy models and CRUD operations. Use file-based SQLite; DB path from env var `DATABASE_URL`.

4. **Backend - service layer**: Implement `services/board_service.py`, `services/column_service.py`, `services/card_service.py` with business rules: validation, cascade delete (column delete cascades cards), error handling.

5. **Backend - API layer**: Implement FastAPI routes for all Sprint 0 endpoints. Include `GET /api/health` reporting `{status: "ok", version: "0.1.0", schema_version: 1}`. Implement error envelope for all 400/404 responses. `GET /api/boards/{id}` returns nested board with columns and cards in stable order (by `created_at`).

6. **Frontend**: Create React/TypeScript SPA with Vite. Implement: board list view, board detail view (columns + cards), card create/edit/delete modals, column create/delete. Typed API client matching the backend. Empty, loading, and error states for all surfaces. Keyboard navigation with visible focus rings. ARIA landmarks and headings.

7. **Smoke tests**: Write Playwright smoke tests in `tests/smoke/sprint_0/` covering: create board -> add column -> add card -> GET board shows all three. These must pass headlessly.

8. **Makefile**: Implement targets:
   - `make run`: builds frontend (`npm run build`), starts FastAPI on port 8080 serving built SPA
   - `make migrate`: applies all pending migrations
   - `make reset-db`: drops DB file and re-runs `make migrate`
   - `make test`: runs pytest + playwright
   - `make lint`: runs ruff + pyright + eslint + tsc

9. **Design artifacts**: Create all required `design/` files for Sprint 0: `prd.md`, `backlog.md`, `dod.md`, `research/interviews.md` (>= 3 persona write-ups), `research/jtbd.md` (>= 5 JTBD), `research/personas.md` (four personas), `sprints/sprint-0.md`, `retros/retro-0.md`, `wireframes/s0-board.md`, `wireframes/s0-card-editor.md`, `wireframes/s0-states.md`, `mockups/s0-board-hifi.md`, `tokens/tokens.json`, `tokens/CHANGELOG.md`, `a11y/annotations-s0.md`, `a11y/wcag-checklist.md`, `CHANGELOG-design.md`.

10. **Install Playwright browser**: Run `npx playwright install chromium` before running E2E tests.

11. **Verify**: Run `make migrate && make run` in background, then `npx playwright test tests/smoke/sprint_0 --reporter=line` headlessly. All tests must exit 0.

## Done when

The following command exits 0 (run from repo root):

```bash
cd scenarios/L7-kanban-sprints/solution && make migrate && make run &SERVER_PID=$!; sleep 5; npx playwright test tests/smoke/sprint_0 --reporter=line; STATUS=$?; kill $SERVER_PID 2>/dev/null; exit $STATUS
```

This verifies:
- The app starts successfully on port 8080
- Sprint 0 smoke tests pass: board CRUD works, column CRUD works, card CRUD works, data is readable after creation, all in a real headless browser

## Final step (REQUIRED)

After all work is complete and the Done-when check passes with exit 0, write the file `artifacts/sprint0_mvp.done` containing exactly `sprint0_mvp:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action taken.
