# Lane sprint_1_ordering

## Outcome

Deliver Sprint 1 (Drag & drop and ordering) of the L7 Kanban application, building on the Sprint 0 MVP. The application must gain persisted card and column positions, a `PATCH /api/cards/{id}/move` endpoint, a `PATCH /api/columns/{id}/move` endpoint, drag-and-drop in the SPA with a keyboard-operable equivalent, and failure reconciliation. All Sprint 1 acceptance criteria (AC-1.1 through AC-1.9) must pass, AND the Sprint 0 regression suite (AC-0.1 through AC-0.9) must still pass 100%.

Concrete files that must exist at the end (in addition to all Sprint 0 files):

- `scenarios/L7-kanban-sprints/solution/backend/migrations/0002_positions.sql` (or `.py`) — adds `position` to `card` and `column`, backfills existing rows by `created_at`
- `scenarios/L7-kanban-sprints/solution/tests/sprint_1/` — strategy-owned tests for Sprint 1
- `scenarios/L7-kanban-sprints/design/sprints/sprint-1.md`
- `scenarios/L7-kanban-sprints/design/retros/retro-1.md`
- `scenarios/L7-kanban-sprints/design/interaction/s1-drag-states.md` — drag state machine + keyboard key-map
- `scenarios/L7-kanban-sprints/design/a11y/annotations-s1.md`
- `scenarios/L7-kanban-sprints/design/CHANGELOG-design.md` updated with Sprint 1 entry

## Steps

1. **Sprint 1 design artifacts first**: Author `design/interaction/s1-drag-states.md` documenting the drag state machine (`idle → grabbed → over-valid-target → over-invalid-target → dropping → persisting → error-reconciling`), drop-target affordances, the keyboard move key-map (grab/move/drop key bindings and their announcement text). Author `design/a11y/annotations-s1.md` (updated a11y annotations for grab mode). Update `design/CHANGELOG-design.md` with a Sprint 1 entry dated appropriately.

2. **Migration 0002**: Create `solution/backend/migrations/0002_positions.sql` (or Alembic equivalent) that:
   - Adds `position INTEGER NOT NULL DEFAULT 0` to `card` and `column` tables
   - Backfills `card.position` ordered by `created_at` within each column (dense 0-based integers)
   - Backfills `column.position` ordered by `created_at` within each board (dense 0-based integers)
   - Migration is forward-only, idempotent to re-run detection, and applied by `make migrate`
   - After migration, `GET /api/boards/{id}` returns cards in position order and columns in position order

3. **Backend — move endpoints**: Implement:
   - `PATCH /api/cards/{card_id}/move` body: `{column_id, position}` — moves card to target position in target column; returns updated BoardDetail; produces canonical dense ordering (0..n-1, no gaps, no duplicates) in both source and destination columns; atomic (failed move leaves ordering exactly as it was)
   - `PATCH /api/columns/{column_id}/move` body: `{position}` — reorders column within its board; returns updated BoardDetail; renormalizes all columns to dense order
   - Deleting a card renormalizes the remaining cards in its column (FR-1.5)
   - Repeated identical moves are idempotent — no drift, no duplicates (AC-1.4)

4. **Backend — indexes**: Ensure `card(column_id, position)` and `column(board_id, position)` indexes exist for NFR-1 performance.

5. **Frontend — drag-and-drop**: Add drag-and-drop to the SPA:
   - Visual drag affordances and drop-target indicators
   - Optimistic or pessimistic UI (strategy's choice, documented in `design/interaction/s1-drag-states.md`)
   - On rejected move: card snaps back to true position and an error message is surfaced (FR-1.8, AC-1.7)
   - Use any library or hand-rolled — but the keyboard path must exist regardless

6. **Frontend — keyboard move mode**: Implement keyboard-operable equivalent for card reordering (FR-1.7):
   - Grab/move/drop with the documented key mapping from `design/interaction/s1-drag-states.md`
   - Keyboard path produces identical server state to the mouse path (AC-1.6)
   - Focus is not lost or trapped by drag mode; tab order is preserved (NFR-4, scar: Tab order broken by drag containers)

7. **Cumulative regression**: Before declaring Sprint 1 done, run the Sprint 0 acceptance suite against the live application and confirm it passes 100%. The Sprint 0 regression gate specifically watches: cascade delete (AC-0.2), restart durability (AC-0.4), and the Sprint-0 keyboard path (AC-0.8). Do NOT break these.

8. **Strategy tests**: Write `solution/tests/sprint_1/` with smoke and unit tests covering AC-1.1 through AC-1.9. Also run the Sprint 0 tests from `solution/tests/sprint_0/` to confirm no regression.

9. **Sprint plan and retro**: Write `design/sprints/sprint-1.md` (sprint goal, backlog slice, AC-1.1–1.9, DoD checklist, named risks including regression risk from adding drag containers to tab order) and `design/retros/retro-1.md` (what went well, what didn't, regression risk discovered during sprint, ≥1 concrete action into Sprint 2's backlog). Update `design/backlog.md` to reflect Sprint 1 items closed and Sprint 2 slice explicit.

10. **Usability session 1**: After Sprint 1 is complete, run a moderated-session simulation against the running app — adopt each persona, execute a written task script, record per-task completion/errors/heuristic violations. Write `design/research/usability/session-1.md` (≥5 tasks, findings with severity ratings, ≥1 severity ≥ major finding groomed into Sprint 2's backlog).

## Done when

The following command exits 0:
```
bash -c "test -f scenarios/L7-kanban-sprints/solution/backend/migrations/0002_positions.sql && test -f scenarios/L7-kanban-sprints/design/sprints/sprint-1.md && test -f scenarios/L7-kanban-sprints/design/retros/retro-1.md && test -f scenarios/L7-kanban-sprints/design/interaction/s1-drag-states.md"
```

This passes when:
- `solution/backend/migrations/0002_positions.sql` exists (the positions migration)
- `design/sprints/sprint-1.md` exists
- `design/retros/retro-1.md` exists
- `design/interaction/s1-drag-states.md` exists (drag state machine + keyboard key-map)

Additionally verify that the move endpoints work correctly and that Sprint 0 tests still pass.

## Final step (REQUIRED)

After all the work above is done and the verifier check passes, write the file `artifacts/sprint_1_ordering.done` containing exactly `sprint_1_ordering:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished — it must be the LAST action taken.
