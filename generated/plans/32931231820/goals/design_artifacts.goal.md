# Lane design_artifacts

## Outcome

Produce all required `design/` artifacts and `solution/DECISIONS.md` under `scenarios/L6-kanban-app/` as specified in REQUIREMENTS.md §5.4 and §1.6. These files are the product and design surface required by AC-22 and AC-23.

Concrete files to create (all repo-relative paths under `scenarios/L6-kanban-app/`):

- `solution/DECISIONS.md` — resolves every §1.6 ambiguity (a)–(h) with a one-paragraph rationale each
- `design/personas.md` — ≥3 personas (Maya, Sam, Ravi + any additions) with goals, frustrations, key tasks, FRs driven
- `design/research/interviews.md` — ≥2 synthesized interview sessions (one per primary persona), labelled as synthesized, with script, questions, responses, and "decisions changed by this" with ≥3 concrete traceable changes
- `design/research/jtbd.md` — ≥4 JTBD statements in when/I want to/so I can form, each mapped to FRs served and FRs deliberately not built (§1.5)
- `design/prd.md` — problem statement, target users, goals/non-goals (consistent with §1.5), success metrics, scope by P0/P1, key risks, open questions with §1.6 resolutions, Definition of Done
- `design/user-stories.md` — US-1..US-21 from §1.3 (and any additions), each with per-story acceptance criteria and FR traces
- `design/backlog.md` — P0/P1 ordered backlog with dependencies and estimates; matches §4.1; dependency chain: auth → boards → columns → cards → drag/persistence → authz → states → labels/assignee/polish
- `design/wireframes/login.md` — ASCII/text wireframe of the login screen
- `design/wireframes/board-list.md` — ASCII/text wireframe of the board list (populated)
- `design/wireframes/board-list-empty.md` — ASCII/text wireframe of the board list (empty state)
- `design/wireframes/board-detail.md` — ASCII/text wireframe of the board detail (populated)
- `design/wireframes/board-detail-empty.md` — ASCII/text wireframe of the board detail (empty state)
- `design/wireframes/card-detail.md` — ASCII/text wireframe of the card detail modal
- `design/wireframes/drag-in-progress.md` — ASCII/text wireframe of drag-in-progress state
- `design/hifi/login.md` — hi-fi spec/description of the login screen at 1280×800
- `design/hifi/board-list.md` — hi-fi spec of the board list (populated)
- `design/hifi/board-list-empty.md` — hi-fi spec of the board list (empty state)
- `design/hifi/board-detail.md` — hi-fi spec of the board detail (populated)
- `design/hifi/board-detail-empty.md` — hi-fi spec of the board detail (empty state)
- `design/hifi/card-detail.md` — hi-fi spec of the card detail modal
- `design/hifi/drag-in-progress.md` — hi-fi spec of drag-in-progress state
- `design/hifi/board-detail-loading.md` — hi-fi spec of board detail loading state
- `design/hifi/board-detail-error.md` — hi-fi spec of board detail error state
- `design/design-tokens.json` — color (with contrast pairs), spacing scale, type scale, radii, elevation, motion durations; token names must match those used in `design/tokens.css` and in the app's CSS
- `design/tokens.css` — CSS custom properties mirroring design-tokens.json; this file must be imported by the SPA
- `design/interaction-specs.md` — state machines for drag (idle→picked-up→over-target→dropped/cancelled) and keyboard equivalent; optimistic-update and rollback sequences; per-view state matrix (loading/empty/error/populated); validation and focus behavior
- `design/a11y-annotations.md` — ARIA role/name/state map for board, column, card, card detail; FR-26 keyboard interaction table (which keys, what is announced); live-region wording; focus-order diagrams per screen; contrast-checked token pairs; any justified moderate axe findings

## Steps

1. Read `scenarios/L6-kanban-app/REQUIREMENTS.md` fully before writing anything.
2. Create `scenarios/L6-kanban-app/solution/DECISIONS.md` resolving all §1.6 items:
   - (a) Ordering: choose fractional/REAL positions with gap allocation (a2/a3 hybrid) — document that `position REAL` is stored per parent, new items get max+1.0, moves use midpoint insertion, rebalance when gap < 0.001
   - (b) Delete semantics: hard delete with confirmation step (b1)
   - (c) Label model: fixed palette of 8 named labels stored in a join table (c1)
   - (d) Assignee identity: free-text assignee name on the card (d1), escaped and length-limited to 100 chars
   - (e) Session: server-side session with HttpOnly SameSite=Lax cookie (e1); CSRF defended via SameSite=Lax + origin check
   - (f) Not-found vs forbidden: 404 uniformly (f1)
   - (g) Board list sort: most-recently-updated first; card face shows title + assignee + label chips
   - (h) Visual direction: clean minimal palette with CSS custom properties from design-tokens.json
3. Create all `design/` files listed in Outcome. Each must be internally consistent and trace to FR/AC ids. Wireframes may be ASCII art or structured markdown describing layout. Hi-fi files must describe the visual target in enough detail that an implementation can be diffed against them.
4. For `design/design-tokens.json`, define tokens with names like `--color-primary`, `--color-surface`, `--color-text`, `--spacing-sm`, `--spacing-md`, `--radius-card`, `--shadow-card`, `--motion-duration-standard`. Ensure contrast pairs are documented (e.g., `--color-text` on `--color-surface` ≥4.5:1).
5. For `design/tokens.css`, emit all tokens as CSS custom properties on `:root`. This file will be imported by `src/styles/tokens.css` in the frontend.
6. For `design/a11y-annotations.md`, include the complete FR-26 keyboard table: Space/Enter=pick up, Arrow keys=move one position, Shift+Arrow=move across columns, Escape=cancel, Space/Enter=drop.
7. For `design/interaction-specs.md`, include the optimistic-update sequence: (1) snapshot pre-mutation state, (2) apply optimistic update to store, (3) fire API call, (4) on success: update store with server response, (5) on failure: restore snapshot, show dismissible error toast.

## Done when

The following command exits 0:

```bash
test -f scenarios/L6-kanban-app/solution/DECISIONS.md && \
test -f scenarios/L6-kanban-app/design/personas.md && \
test -f scenarios/L6-kanban-app/design/prd.md && \
test -f scenarios/L6-kanban-app/design/user-stories.md && \
test -f scenarios/L6-kanban-app/design/backlog.md && \
test -f scenarios/L6-kanban-app/design/research/interviews.md && \
test -f scenarios/L6-kanban-app/design/research/jtbd.md && \
test -f scenarios/L6-kanban-app/design/interaction-specs.md && \
test -f scenarios/L6-kanban-app/design/a11y-annotations.md && \
test -f scenarios/L6-kanban-app/design/design-tokens.json && \
test -f scenarios/L6-kanban-app/design/tokens.css
```

All eleven files must exist with non-empty content.

## Final step (REQUIRED)

After all the above files exist and the check above passes, write the file `artifacts/design_artifacts.done` containing exactly `design_artifacts:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
