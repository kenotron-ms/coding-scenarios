# Lane sprint3_labels

## Outcome

Implement Sprint 3 (Labels, Filters & Search) of the L7 Kanban application, building on Sprints 0-2 already in `scenarios/L7-kanban-sprints/solution/`. This sprint adds board-scoped labels, card-label many-to-many assignment, board member roster, card assignee, server-side filtering (OR-within-facet / AND-across-facet), server-side text search, URL-reflected filter state, and XSS-safe rendering. All Sprint 0, 1, and 2 behavior must remain 100% intact.

Concrete changes (repo-relative paths under `scenarios/L7-kanban-sprints/solution/`):

- `backend/migrations/0004_labels_members.sql` (or .py): creates `label`, `card_label`, `board_member` tables; adds `assignee_id` to `card`
- `backend/api/`: label CRUD routes, member roster routes, card label assignment, filter/search on `GET /api/boards/{id}/cards`
- `backend/services/`: label_service, member_service; filter/search logic (server-side, correct for large boards)
- `backend/repositories/`: label_repo, member_repo; updated card_repo for filter/search queries
- `frontend/src/`: filter bar (label multi-select, assignee multi-select, search input), label chips on cards, assignee display, URL query params for filter state, filtered empty state with clear action
- `tests/smoke/sprint_3/`: Playwright smoke tests — create label -> attach to card -> filter by label -> only that card returns
- `design/sprints/sprint-3.md`, `design/retros/retro-3.md`, `design/research/usability/session-3.md`
- `design/mockups/s3-filter-search.md`
- `design/interaction/s3-filter-behavior.md`
- `design/a11y/annotations-s3.md`
- `design/CHANGELOG-design.md` updated

Key implementation requirements:

- **Labels**: `POST /api/boards/{id}/labels {name, color}`, `GET /api/boards/{id}/labels`, `PATCH /api/labels/{id} {name?, color?}`, `DELETE /api/labels/{id}`. Board-scoped: a label belongs to one board. `color` is a hex triplet (e.g., `#FF5733`). Deleting a label removes `card_label` rows; cards survive.
- **Card-label assignment**: `PUT /api/cards/{id}/labels {label_ids: [...]}`. Many-to-many. A card cannot hold a label from another board (returns 400/404).
- **Board members**: `POST /api/boards/{id}/members {name, email?}`, `GET /api/boards/{id}/members`, `DELETE /api/members/{id}`. Roster entries are data, not accounts — grant no access. `PATCH /api/cards/{id} {assignee_id?}` assigns a card to a member. Off-roster assignee_id rejected. Deleting a member sets card.assignee_id to NULL; cards survive.
- **Filter endpoint**: `GET /api/boards/{id}/cards?label=<id>&label=<id>&assignee=<id>&q=<text>`. OR within facet (multiple `label=` params), AND across facets. Server-side: correct for boards larger than the client's initial page. Filtering NEVER mutates stored positions — positions in the DB are unchanged after any filter query.
- **Search**: Case-insensitive substring over `title` and `description`. Composable with label/assignee filters (AND).
- **URL reflection**: Filter state (label ids, assignee ids, search text) reflected in URL query params. Survives reload.
- **Empty state**: A filter matching nothing shows an explicit empty state with a one-click clear action.
- **XSS safety**: All user-supplied text (label name, member name, card title, description, search query) escaped on render. A `<script>` payload in a name renders as text.
- **Authorization**: All new label/member endpoints go through the existing authz choke point (`require_board_owner`). FR-2.4 still holds.
- **Accessibility**: Filter state announced via ARIA live region ("N of M cards shown"). Filter controls keyboard-reachable. Label chips meet contrast >= 3:1. Zero critical/serious axe violations.
- `health.schema_version` reports `4` after migration 0004.

## Steps

1. **Migration 0004**: Write `backend/migrations/0004_labels_members.sql`:
   - Create `label` table: `id, board_id -> board, name (<=40 chars), color (hex triplet), created_at`
   - Create `card_label` table: `card_id -> card, label_id -> label` (composite PK)
   - Create `board_member` table: `id, board_id -> board, name (<=80 chars), email (optional), created_at`
   - Add `assignee_id` column to `card` (nullable FK -> board_member)
   - Add indexes: `card_label(label_id)`, `card(assignee_id)`
   - Bump schema_version to 4

2. **Repository layer**: Add `label_repo.py` (CRUD + board-scope validation), `member_repo.py` (CRUD). Update `card_repo.py` to support filter queries with parameterized SQL (no SQL injection): filter by label ids (OR), assignee ids (OR), text search (ILIKE or LOWER LIKE). Filtering must not write positions back.

3. **Service layer**: Add `label_service.py` (validate color format, enforce board scope), `member_service.py` (validate name length). Add filter logic in `card_service.py` or a dedicated `filter_service.py`. Ensure filtering never touches stored `position` values.

4. **API routes**: Implement all Sprint 3 endpoints. All board-scoped routes go through `require_board_owner`. `PUT /api/cards/{id}/labels` validates all label_ids belong to the card's board. `PATCH /api/cards/{id}` extended to accept `assignee_id`. `GET /api/boards/{id}/cards` accepts filter params.

5. **Frontend - filter bar**: Add a filter bar to the board view with: multi-select label facet (label chips with color), assignee facet (dropdown or chip), search text input. Reflect state in URL query params (`?label=<id>&label=<id>&assignee=<id>&q=<text>`). On page load, restore filter from URL params.

6. **Frontend - label chips**: Show label chips on card thumbnails. Label colors must meet contrast requirements.

7. **Frontend - filtered empty state**: When filter returns no cards, show explicit empty state ("No cards match your filters") with a "Clear filters" button that resets all filters.

8. **Frontend - XSS**: Ensure all user text is rendered via React's JSX (escaped by default), never via `dangerouslySetInnerHTML`. Verify `<script>` payloads render as text.

9. **Frontend - ARIA live region**: When filter results change, announce "N of M cards shown" via an ARIA live region (`aria-live="polite"`).

10. **Smoke tests**: Write `tests/smoke/sprint_3/test_sprint3.spec.ts` covering: create label -> attach to card -> filter by label -> only that card returns.

11. **Design artifacts**: Create `design/sprints/sprint-3.md`, `design/retros/retro-3.md` (must note the filter-writeback regression risk and authz extension risk), `design/research/usability/session-3.md` (>= 5 tasks on filter/search, >= 1 major finding groomed into Sprint 4), `design/mockups/s3-filter-search.md`, `design/interaction/s3-filter-behavior.md`, `design/a11y/annotations-s3.md`, update `design/tokens/tokens.json` with label color tokens and contrast ratios, update `design/CHANGELOG-design.md`.

12. **Regression check**: Before declaring done, run Sprint 0, 1, and 2 smoke tests to confirm no regressions. Specifically verify: dense ordering is unchanged after a filter query (query the DB directly to confirm positions are untouched), Sprint 2 authz still holds for new label/member endpoints.

13. **Verify**: Start server, run Sprint 3 smoke tests headlessly, confirm exit 0.

## Done when

The following command exits 0 (run from repo root):

```bash
cd scenarios/L7-kanban-sprints/solution && make migrate && make run &SERVER_PID=$!; sleep 5; npx playwright test tests/smoke/sprint_3 --reporter=line; STATUS=$?; kill $SERVER_PID 2>/dev/null; exit $STATUS
```

This verifies:
- Migration 0004 applied (schema_version = 4)
- App starts on port 8080
- Sprint 3 smoke tests pass: label created, attached to card, filter returns only that card

## Final step (REQUIRED)

After all work is complete and the Done-when check passes with exit 0, write the file `artifacts/sprint3_labels.done` containing exactly `sprint3_labels:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action taken.
