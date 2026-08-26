# Lane sprint4_realtime

## Outcome

Implement Sprint 4 (Activity Feed & Real-time) of the L7 Kanban application, building on Sprints 0-3 already in `scenarios/L7-kanban-sprints/solution/`. This is the capstone sprint: it adds an immutable activity log for every mutation, a paginated activity feed API, a live update channel (WebSocket or SSE) that pushes mutations to other viewers of the same board within 2 seconds (p95), connection status UI, reconnect-with-backfill, and concurrent-move convergence. All Sprint 0-3 behavior must remain 100% intact.

Concrete changes (repo-relative paths under `scenarios/L7-kanban-sprints/solution/`):

- `backend/migrations/0005_activity.sql` (or .py): creates `activity` table with per-board monotonic `seq`
- `backend/realtime/`: WebSocket (or SSE) channel manager — subscribe, authorize, broadcast
- `backend/services/activity_service.py`: single choke point for emitting activity records on every mutation
- `backend/api/activity.py`: `GET /api/boards/{id}/activity` paginated + authorized
- `backend/api/realtime.py`: WebSocket endpoint `WS /api/boards/{id}/socket` (or SSE `GET /api/boards/{id}/events`)
- All existing service-layer mutations updated to call `activity_service.record()` at a single choke point
- `frontend/src/`: activity feed panel, connection status indicator (connected/reconnecting/stale), incoming update application that preserves open editor / active filter / scroll position, ARIA live region for live updates, keyboard-navigable feed
- `tests/smoke/sprint_4/`: Playwright smoke tests — open two clients -> move a card in one -> the other shows the move
- `design/sprints/sprint-4.md`, `design/retros/retro-4.md`
- `design/mockups/s4-activity-feed.md`
- `design/interaction/s4-realtime-states.md`
- `design/a11y/annotations-s4.md`
- `design/CHANGELOG-design.md` updated

Key implementation requirements:

- **Activity table**: `id, seq (per-board monotonic integer), board_id -> board, actor_id -> user, verb, entity_type, entity_id, payload (JSON), created_at`. Indexed on `(board_id, seq DESC)`. `seq` is per-board monotonic (use a DB sequence or SELECT MAX(seq)+1 within a transaction).
- **Activity write choke point**: Every mutation class (board create/update/delete, column create/update/delete/move, card create/update/delete/move, label assign/remove, assignee set/clear) appends exactly one activity record. This logic lives in the service layer's mutation path, not in route handlers. A mutation that can happen without emitting activity fails AC-4.1.
- **Activity immutability**: No endpoint exists to edit or delete activity records. `GET /api/boards/{id}/activity?limit=&before=` returns records newest-first, paginated by `before=<seq>`. Authorized by the existing authz choke point (user B gets denial on user A's board activity).
- **Live channel**: WebSocket (`WS /api/boards/{id}/socket`) or SSE (`GET /api/boards/{id}/events`). Authorization: only users who can read the board may subscribe; unauthorized subscribe receives no events and gets a denial. On connect, client may pass `?since=<seq>` to backfill missed events.
- **Live event envelope**: `{"seq": <int>, "board_id": "...", "type": "card.moved", "actor": "...", "at": "...", "data": {...}}`. The `seq` field enables gap detection for backfill.
- **Client apply-without-clobber**: When an incoming live event arrives, the client applies it without losing: an open card editor (don't close it), an active filter (don't reset it), scroll position (don't jump). The board converges to server truth without clobbering local UI state.
- **Connection status**: UI shows `connected` / `reconnecting` / `stale`. On reconnect, client sends `?since=<last_seq>` to backfill missed events. Backfill completes within 10 seconds of channel restoration.
- **Concurrent-move convergence**: Two clients issuing conflicting moves converge to one identical ordering equal to the server's. No duplicated, ghosted, or lost cards. The server is the authority; clients reconcile from server responses.
- **Performance**: Activity writes must not slow mutations past NFR-1 (single CRUD write <= 200 ms). Activity page fetch <= 300 ms. Live update propagates client-to-client p95 <= 2,000 ms over 20 trials, no single trial > 5,000 ms.
- **XSS safety in activity feed**: Actor names, entity names, and payload data rendered as text, never raw HTML.
- **Accessibility**: Live updates announced via ARIA live region (polite, not assertive for every update). Activity feed keyboard-navigable. Zero critical/serious axe violations on board + feed.
- `health.schema_version` reports `5` after migration 0005.
- `health.schema_version` must be reported in structured logs for Sprint 4.

## Steps

1. **Migration 0005**: Write `backend/migrations/0005_activity.sql`:
   - Create `activity` table: `id, seq INTEGER NOT NULL, board_id -> board, actor_id -> user, verb VARCHAR, entity_type VARCHAR, entity_id VARCHAR, payload JSON/TEXT, created_at`
   - Add unique constraint on `(board_id, seq)`
   - Add index on `(board_id, seq DESC)`
   - Bump schema_version to 5

2. **Activity service choke point**: Implement `backend/services/activity_service.py` with `record(board_id, actor_id, verb, entity_type, entity_id, payload)`. This function: computes the next `seq` for the board (SELECT MAX(seq)+1 or a DB sequence, within the same transaction as the mutation), inserts the activity row, and (after commit) publishes the event to the live channel. Update every service-layer mutation method (board_service, column_service, card_service, label_service, member_service) to call `activity_service.record()` at the end of the mutation, inside the same transaction.

3. **Activity API**: Implement `GET /api/boards/{id}/activity?limit=50&before=<seq>` in `backend/api/activity.py`. Returns activity records newest-first, paginated. Authorized by `require_board_owner`. No edit/delete endpoints.

4. **Live channel**: Implement `backend/realtime/channel.py` — a connection manager that maintains a dict of `board_id -> set[WebSocket/Queue]`. Implement `subscribe(board_id, user, ws_or_queue)` (validates authorization), `unsubscribe(board_id, ws_or_queue)`, `broadcast(board_id, event)`. Implement `WS /api/boards/{id}/socket` (or SSE `GET /api/boards/{id}/events`) in `backend/api/realtime.py`. On connect, validate session cookie (401 if unauthenticated, denial if unauthorized for this board). Accept `?since=<seq>` and backfill missed events. After `activity_service.record()` commits, call `channel.broadcast(board_id, event)`.

5. **Frontend - live connection**: Implement a WebSocket (or EventSource) client in `frontend/src/api/realtime.ts`. On connect, send `?since=<last_seq>`. On incoming event, apply the update to app state without resetting: open card editor, active filter, or scroll position. Track `last_seq` for backfill on reconnect.

6. **Frontend - connection status**: Show a status indicator in the app shell: `connected` (green), `reconnecting` (yellow, with retry count), `stale` (red, if reconnect fails for > 10 s). On reconnect, trigger backfill.

7. **Frontend - activity feed panel**: Add a side panel or drawer showing the board's activity feed. Paginated with "Load more" button. Each entry shows: actor display name, verb, entity name, relative timestamp. All text escaped. Keyboard-navigable (focus management, arrow keys through entries).

8. **Frontend - ARIA live region**: Add an ARIA live region (`aria-live="polite"`) that announces incoming live updates: "Priya moved card 'Fix bug' to Done". Reduced-motion variant: skip animations for `prefers-reduced-motion`.

9. **Smoke tests**: Write `tests/smoke/sprint_4/test_sprint4.spec.ts` covering: open two browser contexts (two sessions) -> move a card in context 1 -> context 2 shows the move without manual refresh. Use Playwright's `page.waitForSelector` or `waitForFunction` with the NFR-9 timeout (5000 ms max per trial).

10. **Design artifacts**: Create `design/sprints/sprint-4.md`, `design/retros/retro-4.md` (must note activity-write performance risk, broadcast-bypass-authz risk, filter-reset-on-event risk), `design/mockups/s4-activity-feed.md`, `design/interaction/s4-realtime-states.md` (connected/reconnecting/stale/conflict-resolved states + visual treatment), `design/a11y/annotations-s4.md`, update `design/CHANGELOG-design.md`.

11. **Regression check**: Before declaring done, run Sprint 0, 1, 2, and 3 smoke tests to confirm no regressions. Specifically verify: activity writes don't slow mutations past NFR-1; broadcast path doesn't bypass authz; incoming events don't reset active filter; Sprint-1 ordering is correct after concurrent moves.

12. **Verify**: Start server, run Sprint 4 smoke tests with two browser contexts headlessly, confirm exit 0.

## Done when

The following command exits 0 (run from repo root):

```bash
cd scenarios/L7-kanban-sprints/solution && make migrate && make run &SERVER_PID=$!; sleep 5; npx playwright test tests/smoke/sprint_4 --reporter=line; STATUS=$?; kill $SERVER_PID 2>/dev/null; exit $STATUS
```

This verifies:
- Migration 0005 applied (schema_version = 5)
- App starts on port 8080
- Sprint 4 smoke tests pass: two-client live update — card moved in client 1 appears in client 2 without manual refresh

## Final step (REQUIRED)

After all work is complete and the Done-when check passes with exit 0, write the file `artifacts/sprint4_realtime.done` containing exactly `sprint4_realtime:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action taken.
