# Lane sprint1_drag

## Outcome

Implement Sprint 1 (Drag & Drop and Ordering) of the L7 Kanban application, building on the Sprint 0 MVP already in `scenarios/L7-kanban-sprints/solution/`. This sprint adds card and column position ordering, drag-and-drop in the UI, a keyboard move equivalent, and failure reconciliation. All Sprint 0 behavior must remain 100% intact (no regressions).

Concrete changes (repo-relative paths under `scenarios/L7-kanban-sprints/solution/`):

- `backend/migrations/0002_positions.sql` (or .py): adds `position` INTEGER to `card` and `column` tables; backfills existing rows by `created_at` order
- `backend/api/`: new routes `PATCH /api/cards/{id}/move` and `PATCH /api/columns/{id}/move`
- `backend/services/`: ordering logic — dense renormalization (0..n-1, no gaps, no duplicates) on move and on delete; atomic transactions so a failed move leaves state unchanged
- `backend/repositories/`: updated queries to return cards ordered by `position`, columns ordered by `position`
- `frontend/src/`: drag-and-drop UI (any library or hand-rolled); keyboard move mode (grab/move/drop with documented key mapping); failure reconciliation (card snaps back with error message on rejected move)
- `tests/smoke/sprint_1/`: Playwright smoke tests — move card to index 0 -> GET board shows it first; reload -> still first
- `design/sprints/sprint-1.md`, `design/retros/retro-1.md`, `design/research/usability/session-1.md`
- `design/interaction/s1-drag-states.md` (idle -> grabbed -> over-valid-target -> over-invalid-target -> dropping -> persisting -> error-reconciling; keyboard key-map)
- `design/a11y/annotations-s1.md`
- `design/CHANGELOG-design.md` updated with Sprint 1 entry

Key implementation requirements:

- `PATCH /api/cards/{id}/move` body: `{column_id, position}` (0-based target index). Returns `BoardDetail` (full nested board). Renormalizes both source and destination columns to dense 0..n-1.
- `PATCH /api/columns/{id}/move` body: `{position}`. Returns `BoardDetail`.
- Deleting a card must renormalize surviving cards in that column.
- `GET /api/boards/{id}` returns cards in `position` order, columns in `position` order.
- Idempotent: repeating the same move produces identical state (no drift).
- Keyboard move mode: a card can be grabbed (e.g. Space/Enter), moved with arrow keys, dropped (Space/Enter), cancelled (Escape). Key mapping documented in `s1-drag-states.md`.
- Failed server move: UI reconciles by restoring card to its true position and showing an error message.
- WCAG 2.1 AA maintained: zero critical/serious axe violations including during drag/grab state. Tab order not broken by drag containers.
- `health.schema_version` must report `2` after migration `0002` is applied.
- Sprint 0 regression gate: all Sprint 0 smoke tests still pass.

## Steps

1. **Migration 0002**: Write `backend/migrations/0002_positions.sql` adding `position INTEGER NOT NULL DEFAULT 0` to `card` and `column`. Backfill: `UPDATE card SET position = (SELECT COUNT(*) FROM card c2 WHERE c2.column_id = card.column_id AND c2.created_at < card.created_at)`. Same for columns within boards. Update migration runner to apply this migration and bump `schema_version` to 2.

2. **Repository updates**: Update `card_repo.py` and `column_repo.py` to:
   - Return cards ordered by `position ASC` (not `created_at`)
   - Return columns ordered by `position ASC`
   - Implement `move_card(card_id, target_column_id, target_position)` with dense renormalization in a single transaction
   - Implement `move_column(column_id, target_position)` with dense renormalization
   - On card delete, renormalize remaining cards in the column

3. **Service layer**: Add `card_service.move_card()` and `column_service.move_column()` validating target column exists, target position is within bounds (clamp or error), and calling repo inside a transaction. A failed move must leave state exactly as before.

4. **API routes**: Add `PATCH /api/cards/{id}/move` and `PATCH /api/columns/{id}/move`. Both return the full `BoardDetail` response so the client can reconcile authoritatively.

5. **Frontend - drag and drop**: Implement drag-and-drop for cards (within column and cross-column) and columns. Use a library (e.g., `@dnd-kit/core`) or hand-rolled HTML5 drag events. Show drop target affordances. On drop, call `PATCH /api/cards/{id}/move`. On failure, restore card to previous position and show error.

6. **Frontend - keyboard move mode**: Implement keyboard equivalent for drag. When a card is focused: Space/Enter enters grab mode (announced via ARIA live region), arrow keys move the card up/down within column or left/right across columns, Space/Enter drops it, Escape cancels. Produce identical server state as mouse drag.

7. **Frontend - reconciliation**: On a rejected move (server returns error), snap the card back to its true position (from the server's response or by re-fetching) and display an error message.

8. **Smoke tests**: Write `tests/smoke/sprint_1/test_sprint1.spec.ts` covering: move card to index 0 -> GET board shows it first; hard-reload -> still first. Install `npx playwright install chromium` before running.

9. **Design artifacts**: Create/update `design/sprints/sprint-1.md` (goal, backlog, AC-1.x, DoD, risks), `design/retros/retro-1.md` (went well, didn't, regression risk found, >= 1 action for Sprint 2), `design/research/usability/session-1.md` (>= 5 tasks, findings with severity, >= 1 major finding groomed into Sprint 2 backlog), `design/interaction/s1-drag-states.md`, `design/a11y/annotations-s1.md`, update `design/CHANGELOG-design.md`.

10. **Regression check**: Before declaring done, run Sprint 0 smoke tests to confirm no regressions: `npx playwright test tests/smoke/sprint_0 --reporter=line`.

11. **Verify**: Start server, run Sprint 1 smoke tests headlessly, confirm exit 0.

## Done when

The following command exits 0 (run from repo root):

```bash
cd scenarios/L7-kanban-sprints/solution && make migrate && make run &SERVER_PID=$!; sleep 5; npx playwright test tests/smoke/sprint_1 --reporter=line; STATUS=$?; kill $SERVER_PID 2>/dev/null; exit $STATUS
```

This verifies:
- Migration 0002 applied (schema_version = 2)
- App starts on port 8080
- Sprint 1 smoke tests pass: card move persists, reload confirms order

## Final step (REQUIRED)

After all work is complete and the Done-when check passes with exit 0, write the file `artifacts/sprint1_drag.done` containing exactly `sprint1_drag:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action taken.
