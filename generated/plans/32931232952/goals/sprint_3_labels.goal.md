# Lane sprint_3_labels

## Outcome

Deliver Sprint 3 (Labels, filters & search) of the L7 Kanban application, building on Sprints 0–2. The application must gain board-scoped labels (CRUD), card-label many-to-many assignments, a board member roster with card assignees, server-side filtering (OR-within-facet / AND-across-facet), server-side text search, URL-reflected filter state, and a filter bar UI. All Sprint 3 acceptance criteria (AC-3.1 through AC-3.11) must pass, AND the cumulative regression suite from Sprints 0–2 (AC-0.* ∪ AC-1.* ∪ AC-2.*) must still pass 100%.

Concrete files that must exist at the end (in addition to all Sprint 0–2 files):

- `scenarios/L7-kanban-sprints/solution/backend/migrations/0004_labels_members.sql` (or `.py`) — adds label, card_label, board_member, card.assignee_id
- `scenarios/L7-kanban-sprints/solution/tests/sprint_3/` — strategy-owned tests for Sprint 3
- `scenarios/L7-kanban-sprints/design/sprints/sprint-3.md`
- `scenarios/L7-kanban-sprints/design/retros/retro-3.md`
- `scenarios/L7-kanban-sprints/design/research/usability/session-2.md` — usability session from end of Sprint 2
- `scenarios/L7-kanban-sprints/design/mockups/s3-filter-search.md`
- `scenarios/L7-kanban-sprints/design/interaction/s3-filter-behavior.md`
- `scenarios/L7-kanban-sprints/design/a11y/annotations-s3.md`
- `scenarios/L7-kanban-sprints/design/CHANGELOG-design.md` updated with Sprint 3 entry

## Steps

1. **Sprint 3 design artifacts first**: Author `design/mockups/s3-filter-search.md` (filter bar + search UI mockups: multi-select label facet, assignee facet, search input, active-filter chips, clear-all, filtered-empty state). Author `design/interaction/s3-filter-behavior.md` (filter semantics, URL encoding, live-region copy for "N of M cards shown"). Author `design/a11y/annotations-s3.md` (label chip contrast, filter state announcement via live region). Update `design/tokens/tokens.json` with label color tokens and documented contrast ratios (≥4.5:1 for text, ≥3:1 for non-text). Update `design/CHANGELOG-design.md`. Confirm `design/research/usability/session-2.md` exists and ≥1 finding is groomed into this sprint's backlog.

2. **Migration 0004**: Create `solution/backend/migrations/0004_labels_members.sql` (or Alembic equivalent) that:
   - Creates `label` table: `id`, `board_id→board`, `name` (≤40 chars), `color` (hex triplet)
   - Creates `card_label` table: `card_id→card`, `label_id→label` (composite PK)
   - Creates `board_member` table: `id`, `board_id→board`, `name` (≤80 chars), `email?` — roster entry, NOT a user account
   - Adds `card.assignee_id → board_member`, nullable
   - Adds indexes: `card_label(label_id)`, `card(assignee_id)`
   - Cascade: deleting a label removes card_label rows (cards survive); deleting a member sets card.assignee_id to NULL (cards survive)
   - Migration is forward-only, data-preserving

3. **Backend — label CRUD**: Implement:
   - `POST /api/boards/{board_id}/labels {name, color}` → Label (board-scoped, authorized)
   - `GET /api/boards/{board_id}/labels` → [Label]
   - `PATCH /api/labels/{label_id} {name?, color?}` → Label
   - `DELETE /api/labels/{label_id}` → 204 (removes card_label rows; cards survive)
   - `PUT /api/cards/{card_id}/labels {label_ids: [...]}` → Card (many-to-many; a card cannot hold a label from another board → 400/404)
   - All endpoints authorized via the Sprint 2 choke point (FR-2.4 still holds for all new endpoints)

4. **Backend — member roster CRUD**: Implement:
   - `POST /api/boards/{board_id}/members {name, email?}` → Member
   - `GET /api/boards/{board_id}/members` → [Member]
   - `DELETE /api/members/{member_id}` → 204 (assigned cards fall back to unassigned)
   - `PATCH /api/cards/{card_id} {assignee_id?}` → Card (assigning an off-roster assignee → 400/404)
   - Roster entries grant NO access — FR-2.4 authorization invariant is untouched

5. **Backend — server-side filter and search**: Implement:
   - `GET /api/boards/{board_id}/cards?label=<id>&label=<id>&assignee=<id>&q=<text>` → [Card]
   - Filter semantics: OR within a facet, AND across facets (`label ∈ {A,B} AND assignee ∈ {M}`)
   - Text search: case-insensitive substring over title AND description, composable with filters (AND)
   - Filtering is server-side and correct for boards larger than one page of cards (FR-3.6)
   - **CRITICAL**: Filtering NEVER mutates stored positions (FR-3.9, scar: Filtering writes back positions). Clearing the filter restores the exact prior order. Positions in the DB are unchanged after any filter query.
   - An active filter matching nothing returns an empty list (not an error)
   - All user-supplied text (label names, member names, search query) is escaped on render — no XSS

6. **Frontend — filter bar and search UI**: Add to the SPA:
   - Filter bar with multi-select label facet, assignee facet, search input, active-filter chips, clear-all
   - Filter/search state reflected in the URL (survives reload — AC-3.8)
   - Filtered empty state with explicit "no results" message and one-click clear action (AC-3.9)
   - Filter state announced via ARIA live region ("N of M cards shown") — NFR-4
   - Label chips meet contrast requirements (≥4.5:1 text, ≥3:1 non-text)
   - Filter state fully keyboard-accessible (AC-3.11)

7. **Cumulative regression**: Run Sprints 0, 1, and 2 test suites as authenticated. The regression gate specifically watches: FR-3.9 (filtering must not touch stored positions), the full Sprint-2 authz matrix now that new board-scoped entities exist (labels, roster, and their endpoints must be authorized too), and Sprint-1 drag behavior while a filter is active.

8. **Strategy tests**: Write `solution/tests/sprint_3/` covering AC-3.1 through AC-3.11. Include: filter semantics on a seeded fixture board (AC-3.4), search composability (AC-3.5), positions-unchanged assertion (AC-3.7, query DB directly), XSS adversarial payloads in label/member names (AC-3.10). Run Sprints 0–2 tests to confirm no regression.

9. **Sprint plan and retro**: Write `design/sprints/sprint-3.md` and `design/retros/retro-3.md`. Update `design/backlog.md`.

10. **Usability session 3**: After Sprint 3 is complete, run a moderated-session simulation. Write `design/research/usability/session-3.md` (≥5 tasks covering filter/search/label flows, ≥1 severity ≥ major finding groomed into Sprint 4's backlog).

## Done when

The following command exits 0:
```
bash -c "test -f scenarios/L7-kanban-sprints/solution/backend/migrations/0004_labels_members.sql && test -f scenarios/L7-kanban-sprints/design/sprints/sprint-3.md && test -f scenarios/L7-kanban-sprints/design/retros/retro-3.md && test -f scenarios/L7-kanban-sprints/design/research/usability/session-2.md"
```

This passes when:
- `solution/backend/migrations/0004_labels_members.sql` exists (labels + members migration)
- `design/sprints/sprint-3.md` exists
- `design/retros/retro-3.md` exists
- `design/research/usability/session-2.md` exists (Sprint 2 usability session)

Additionally verify that filtering never mutates positions (query DB before and after filter, positions identical) and that all new endpoints are authorized via the Sprint 2 choke point.

## Final step (REQUIRED)

After all the work above is done and the verifier check passes, write the file `artifacts/sprint_3_labels.done` containing exactly `sprint_3_labels:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished — it must be the LAST action taken.
