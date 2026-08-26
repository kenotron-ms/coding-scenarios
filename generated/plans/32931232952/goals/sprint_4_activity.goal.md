# Lane sprint_4_activity

## Outcome

Deliver Sprint 4 (Activity feed & real-time) of the L7 Kanban application, building on Sprints 0–3. The application must gain an immutable activity log appended on every mutation, a paginated activity API, a live channel (WebSocket or SSE) that pushes mutations to other viewers of the same board, client-side apply-without-clobber, connection status UI with backfill on reconnect, and concurrent-move convergence. All Sprint 4 acceptance criteria (AC-4.1 through AC-4.10) must pass, AND the full cumulative regression suite from Sprints 0–3 (AC-0.* ∪ AC-1.* ∪ AC-2.* ∪ AC-3.*) must still pass 100%.

Concrete files that must exist at the end (in addition to all Sprint 0–3 files):

- `scenarios/L7-kanban-sprints/solution/backend/migrations/0005_activity.sql` (or `.py`) — adds activity table + indexes
- `scenarios/L7-kanban-sprints/solution/backend/realtime/` — WS or SSE channel + broadcast logic
- `scenarios/L7-kanban-sprints/solution/tests/sprint_4/` — strategy-owned tests for Sprint 4
- `scenarios/L7-kanban-sprints/design/sprints/sprint-4.md`
- `scenarios/L7-kanban-sprints/design/retros/retro-4.md`
- `scenarios/L7-kanban-sprints/design/research/usability/session-3.md` — usability session from end of Sprint 3
- `scenarios/L7-kanban-sprints/design/mockups/s4-activity-feed.md`
- `scenarios/L7-kanban-sprints/design/interaction/s4-realtime-states.md`
- `scenarios/L7-kanban-sprints/design/a11y/annotations-s4.md`
- `scenarios/L7-kanban-sprints/design/CHANGELOG-design.md` updated with Sprint 4 entry

## Steps

1. **Sprint 4 design artifacts first**: Author `design/mockups/s4-activity-feed.md` (activity feed panel design: grouping, relative timestamps, actor attribution, pagination/"load more"). Author `design/interaction/s4-realtime-states.md` (real-time state spec: `connected / reconnecting / stale / conflict-resolved`, visual treatment of incoming change, live-region announcement copy, reduced-motion variant for update animations). Author `design/a11y/annotations-s4.md` (live region for activity feed and connection state, focus preservation during live updates). Update `design/CHANGELOG-design.md`. Confirm `design/research/usability/session-3.md` exists and ≥1 finding is groomed into this sprint's backlog.

2. **Migration 0005**: Create `solution/backend/migrations/0005_activity.sql` (or Alembic equivalent) that:
   - Creates `activity` table: `id`, `seq` (per-board monotonically increasing integer), `board_id→board`, `actor_id→user`, `verb`, `entity_type`, `entity_id`, `payload` (JSON), `created_at`
   - Creates index `activity(board_id, seq DESC)` for NFR-1
   - `seq` is per-board monotonic — implement as a sequence or MAX(seq)+1 within a transaction
   - Activity records are append-only (no update/delete endpoints)

3. **Backend — activity write choke point**: Implement a single activity-write path in the service layer (NOT sprinkled into route handlers). Every mutation class must emit exactly one activity record:
   - Board create/update/delete
   - Column create/update/delete/move
   - Card create/update/delete/move
   - Label create/update/delete, card-label assignment
   - Member create/delete, card assignee change
   - Activity write failure must NOT lose the mutation (handle gracefully)
   - All user-supplied text in activity payload is escaped on render (XSS surface — NFR-3)

4. **Backend — activity API**: Implement:
   - `GET /api/boards/{board_id}/activity?limit=&before=` → [Activity], newest first, paginated, authorized by FR-2.4 (user B gets denial on user A's board activity)
   - No endpoint exists to edit or delete activity records (AC-4.3)
   - Performance: activity page fetch ≤300 ms (NFR-1)

5. **Backend — live channel**: Implement WebSocket or SSE (strategy's choice, documented in `design/interaction/s4-realtime-states.md`):
   - `GET /api/boards/{board_id}/events` (SSE) or `WS /api/boards/{board_id}/socket` (WebSocket)
   - Authorization: a client may only subscribe to boards it is permitted to read (FR-2.4 applies to the socket — AC-4.9)
   - Broadcast: every committed mutation is pushed to all other viewers of the same board within NFR-9 budget (p95 ≤2000 ms, no single trial >5000 ms, measured client-to-client)
   - Event envelope: `{seq, board_id, type, actor, at, data}` per REQUIREMENTS.md §2.1
   - `seq` is per-board monotonic — clients use gaps in `seq` to detect dropped events
   - Backfill: on reconnect, client sends `?since=<last_seq>`; server sends all events since that seq
   - Connection state: `connected / reconnecting / stale` visible in the UI (AC-4.7)
   - Log connect/disconnect/backfill events with board and client ids (NFR-6)
   - **NOT polling** — a persistent channel must exist (gaming check)

6. **Frontend — apply-without-clobber**: When an incoming live update arrives:
   - Apply the update without losing: an open card editor, an active filter, scroll position (AC-4.5)
   - The Sprint-3 filter must NOT be silently reset by every incoming event (scar: Incoming live event resets the active filter)
   - Optimistic local updates must not resurrect Sprint-1 ordering bugs
   - Live changes announced via ARIA live region (AC-4.6); feed is keyboard-navigable

7. **Frontend — connection status UI**: Display `connected / reconnecting / stale` state visibly. On reconnect, trigger backfill (`?since=<last_seq>`) so the board converges to server truth (AC-4.7). Board remains fully usable with the socket down (NFR-2 degraded mode).

8. **Concurrent-move convergence**: Implement server-side conflict resolution so that after two clients issue conflicting moves, both clients settle to the same ordering equal to the server's — no duplicated, ghosted, or vanished cards (AC-4.8, FR-4.8). This requires the move endpoint to be atomic and the broadcast to include the authoritative post-move state.

9. **Cumulative regression**: Run Sprints 0–3 test suites. The regression gate specifically watches: activity writes must not slow mutations past NFR-1 (≤200 ms for CRUD writes), the broadcast path must not bypass authorization (FR-2.4 on the socket), optimistic local updates must not resurrect Sprint-1 ordering bugs, and the Sprint-3 filter must not be silently reset by every incoming event.

10. **Strategy tests**: Write `solution/tests/sprint_4/` covering AC-4.1 through AC-4.10. Include two-client Playwright tests for: AC-4.4 (move in client 1 appears in client 2 within NFR-9 budget), AC-4.5 (open editor + active filter + scroll preserved during incoming update), AC-4.7 (kill channel, restore, backfill with seq gap detection), AC-4.8 (concurrent conflicting moves converge, repeated trials), AC-4.9 (unauthorized socket subscribe denied). Run Sprints 0–3 tests to confirm no regression.

11. **Sprint plan and retro**: Write `design/sprints/sprint-4.md` and `design/retros/retro-4.md` (what went well, what didn't, regression risk discovered, ≥1 concrete action — this is the final sprint so the action can be a post-mortem item). Update `design/backlog.md` with all Sprint 4 items closed. Update `design/a11y/wcag-checklist.md` signed for Sprint 4.

## Done when

The following command exits 0:
```
bash -c "test -f scenarios/L7-kanban-sprints/solution/backend/migrations/0005_activity.sql && test -f scenarios/L7-kanban-sprints/design/sprints/sprint-4.md && test -f scenarios/L7-kanban-sprints/design/retros/retro-4.md && test -f scenarios/L7-kanban-sprints/design/research/usability/session-3.md"
```

This passes when:
- `solution/backend/migrations/0005_activity.sql` exists (the activity migration)
- `design/sprints/sprint-4.md` exists
- `design/retros/retro-4.md` exists
- `design/research/usability/session-3.md` exists (Sprint 3 usability session)

Additionally verify that the live channel is a real persistent connection (not polling), that activity is written through a single choke point, and that all Sprints 0–3 tests still pass.

## Final step (REQUIRED)

After all the work above is done and the verifier check passes, write the file `artifacts/sprint_4_activity.done` containing exactly `sprint_4_activity:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished — it must be the LAST action taken.
