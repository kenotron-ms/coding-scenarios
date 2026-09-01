# A1 — Kanban App — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> artifact obligations per `framework/ARTIFACT_GRADIENT.md` row **A1**.

> **A1 and A2 share this application.** A1 is *"build it once, correctly"* — the
> whole app delivered in a single run against a fixed spec. A2 re-delivers **the
> same product** as a scripted sequence of sprints in order to measure iterative
> delivery and cumulative regression safety. Therefore **the data model, API
> contract, ordering semantics, and P0 feature set defined here are the
> baseline** that A2 builds on and extends (real-time sync, comments, activity
> feed, search/filter — deliberately deferred in §1.5). Changes to §2.1/§2.3 are
> breaking changes for two rungs, not one.

## 0. Scenario Summary
- **Level:** A1
- **Codename / dir:** `A1-kanban-app`
- **One-liner:** Build a single-team Kanban board web application — Python REST
  API plus a React/TypeScript SPA — with boards, columns and cards,
  drag-and-drop reordering that persists across reload, durable storage, and
  light session authentication.
- **New difficulty introduced:** **A real end-user application.** Every prior
  rung's "user" was a calling programmer or an operator. Here the software has
  *human end-users*, and four new classes of hardness arrive at once:
  1. **Data model + business rules** — entities with relationships, cascades,
     and a non-trivial invariant (a persisted total ordering that survives
     moves between parents).
  2. **Interactive UI** — client state, optimistic updates with rollback,
     loading/empty/error states, and a direct-manipulation gesture
     (drag-and-drop) that must be reproduced *and* offered keyboard-equivalent.
  3. **End-to-end verification through a real browser** — the acceptance path
     runs against the real DOM and the real API against real persistence
     (`VERIFICATION_CONTRACT.md` §3), so "it works in my unit test" is worth
     nothing here.
  4. **A required product and design surface** — personas, JTBD, PRD,
     prioritized backlog, wireframes → hi-fi mockups, a design token system,
     interaction specs, and WCAG 2.1 AA accessibility annotations are
     **deliverables**, not optional garnish. At this rung "working" explicitly
     includes "meets the product and design intent."
- **Estimated reference solution size:** 1,800–3,000 LoC across ~35–50 source
  files (backend ~700–1,000 LoC; frontend ~1,100–1,800 LoC; excluding generated
  lockfiles), plus ~12 design/product artifacts under `design/`. Orienting only
  — a smaller solution that satisfies §4 is strictly better.
- **Time budget:** **4 hours** wall-clock. Token budget: 1.5 M (in+out, summed
  across all agents/sub-agents in the strategy).
- **Iteration budget:** soft **30**, hard **80** edit→verify cycles. The soft
  budget assumes a vertical-slice build order (§8.1); a strategy that builds the
  whole UI before touching persistence will blow past it.
- **Intervention budget:** **0**. Note the asymmetry: §1.6 leaves genuine
  *product* questions open on purpose, and a `clarify` intervention on one of
  those is scored as **lower severity** than at L1 (it caps `AUT` at 3, not 2)
  because open-ended product judgment is part of what this rung tests. A
  `clarify` on anything pinned in §2 (the API contract, the data model, the
  entrypoint) is **not** lower severity — those are fully specified. `hint` and
  `rescue` cap `AUT` as usual (`CONVERGENCE_METRICS.md` §3).

## 1. Product Requirements

- **1.1 Problem statement** — A small co-located product team tracks work on a
  physical whiteboard of sticky notes. It works until someone works from home,
  the notes fall off, or a card's detail exceeds what fits on a 3×3 square. They
  need the whiteboard's two virtues preserved — *see all the work at a glance*
  and *move a card with one gesture* — with durable storage, per-person
  accounts, and enough card detail (description, assignee, labels) to answer
  "what is this and whose is it?" without a standup. They do **not** need, and
  are actively hurt by, a heavyweight project-management tool: the entire value
  is that the board stays as fast and as legible as the wall it replaces.

- **1.2 Target users / personas** — **Required** (`ARTIFACT_GRADIENT.md` A1).
  Three personas; the first two are primary, the third is a constraint-bearing
  persona that exists to make the accessibility requirements concrete rather
  than abstract. The delivered `design/personas.md` must cover at least these
  three and may add more.

  | | **Maya — Team Lead** | **Sam — Contributor** | **Ravi — Keyboard-first Contributor** |
  |---|---|---|---|
  | **Context** | Runs a 6-person team. Lives in the board during planning and standup; projects it on a screen twice a week. | Ships work. Opens the board 5–10×/day for a few seconds at a time. | Same job as Sam. Manages an RSI; uses a keyboard and a screen reader, and cannot reliably perform a sustained mouse drag. |
  | **Goals** | Shape the workflow (which columns exist, in what order); see the whole board's state in one glance; know what's stuck. | Move *my* cards forward with the fewest possible actions; capture a thought as a card before I lose it. | Do everything Sam does, at the same speed, without a pointing device. |
  | **Frustrations** | Tools that bury the board under navigation chrome. Boards where "reordering the workflow" means an admin console. Losing the column arrangement she set up. | Modal-heavy tools where adding a card takes six clicks. Any UI where a drag "sticks" or silently snaps back. Losing card order after a refresh. | Drag-and-drop that has no keyboard path. Interfaces that convey status by color alone. Focus that disappears after an action, dumping him back at the top of the page. |
  | **Key tasks** | Create a board; add/rename/reorder/delete columns; scan card counts per column; reassign a card; delete finished boards. | Create a card with a title; open it and add a description; set assignee/labels; drag it to the next column; reorder within a column. | All of Sam's tasks, performed with `Tab`/arrow keys, with each move announced. |
  | **Success feels like** | "The board matches how we actually work, and it stayed that way." | "One gesture, done, and it's still there tomorrow." | "I moved the card myself and heard where it landed." |
  | **Drives** | FR-6..FR-15, FR-19, US-1..US-6 | FR-16..FR-24, FR-30, US-7..US-12 | FR-26, NFR-4, US-13 |

  **Non-users (explicit):** external stakeholders/clients (no read-only share
  link), and any second team (no cross-team or organization concepts). If a
  proposed feature only serves a non-user, it is out of scope by construction.

- **1.3 User stories** — **Required.** Format: *As a `<role>`, I want
  `<capability>`, so that `<outcome>`.* Priority (`P0`/`P1`) matches §4.1. Each
  story must appear in `design/user-stories.md` with the acceptance criteria
  that prove it.

  | # | Story | Persona | Pri | Traces to |
  |---|-------|---------|-----|-----------|
  | US-1 | As a team lead, I want to create a board with a name, so that a stream of work has a home. | Maya | P0 | FR-6 |
  | US-2 | As a team lead, I want to see a list of only my boards, so that I can switch between streams of work. | Maya | P0 | FR-7, FR-28 |
  | US-3 | As a team lead, I want to rename a board, so that its name keeps matching what the team actually does. | Maya | P0 | FR-8 |
  | US-4 | As a team lead, I want to delete a board and everything on it, so that finished work stops competing for attention. | Maya | P0 | FR-9 |
  | US-5 | As a team lead, I want to add, rename and delete columns, so that the board matches our real workflow stages. | Maya | P0 | FR-11..FR-13 |
  | US-6 | As a team lead, I want to reorder columns and have the arrangement stick, so that the board reads left-to-right in the order work actually flows. | Maya | P0 | FR-14, FR-15 |
  | US-7 | As a contributor, I want to add a card to a column by typing a title, so that I can capture work without ceremony. | Sam | P0 | FR-16 |
  | US-8 | As a contributor, I want to open a card and edit its title and description, so that the card explains itself later. | Sam | P0 | FR-17, FR-21 |
  | US-9 | As a contributor, I want to delete a card, so that mistakes and duplicates don't accumulate. | Sam | P0 | FR-18 |
  | US-10 | As a contributor, I want to drag a card to a new position within its column, so that the column reflects my priority order. | Sam | P0 | FR-22, FR-24 |
  | US-11 | As a contributor, I want to drag a card into another column at a chosen position, so that moving work forward is one gesture. | Sam | P0 | FR-23, FR-24 |
  | US-12 | As a contributor, I want the order I left the board in to be the order I find it in after a reload or on another device, so that I can trust the board. | Sam | P0 | FR-24, FR-25, NFR-2 |
  | US-13 | As a keyboard-first contributor, I want to pick up, move and drop a card using only the keyboard, with each move announced, so that I am not excluded from the core interaction. | Ravi | P0 | FR-26, NFR-4 |
  | US-14 | As a contributor, I want to assign a card to a person, so that everyone knows who owns it. | Sam | P1 | FR-19 |
  | US-15 | As a contributor, I want to attach labels to a card, so that I can tell categories apart at a glance — and not only by color. | Sam, Ravi | P1 | FR-20, NFR-4 |
  | US-16 | As any user, I want to register and log in, so that my boards are mine. | all | P0 | FR-1, FR-2 |
  | US-17 | As any user, I want to log out, so that a shared machine doesn't leave my boards exposed. | all | P0 | FR-3 |
  | US-18 | As any user, I want to stay logged in across a page reload, so that I'm not re-authenticating all day. | all | P0 | FR-4 |
  | US-19 | As any user, I want my boards invisible and unreachable to other accounts, so that the tool is safe to use for real work. | all | P0 | FR-28, FR-29, NFR-3 |
  | US-20 | As any user, I want an action that fails to visibly undo itself rather than silently lie, so that the screen always matches the server. | all | P0 | FR-30, FR-33 |
  | US-21 | As any user, I want clear empty and loading states, so that a new board or a slow network doesn't look like a broken app. | all | P0 | FR-31, FR-32 |

- **1.4 Functional requirements** — Numbered, testable, and each mapped to at
  least one acceptance criterion in §4.3.

  **Authentication & session**
  - **FR-1 Register.** A visitor can create an account with an email and a
    password. Email must be unique (case-insensitively) and syntactically
    valid; password minimum length 8. Duplicate email returns a field-level
    error, not a 500, and does not reveal timing-based account existence beyond
    the explicit message.
  - **FR-2 Login.** Valid credentials establish a session and land the user on
    their board list. Invalid credentials produce a generic failure message
    that does not distinguish "no such user" from "wrong password".
  - **FR-3 Logout.** Ends the session server-side (or invalidates the token),
    clears client state, and returns the user to the login screen. After
    logout, the previously-working session credential must no longer authorize
    any API call.
  - **FR-4 Session persistence.** A logged-in user who reloads the page, or
    opens a second tab, remains logged in and lands back on the same route
    without re-authenticating.
  - **FR-5 Auth gating.** Any SPA route other than `/login` and `/register`
    requires a session: an unauthenticated visit renders the login screen (via
    redirect or in-place guard) and never flashes board data. Every mutating
    API endpoint and every board-scoped read returns **401** without a valid
    session.

  **Boards**
  - **FR-6 Create board.** An authenticated user can create a board with a
    title (1–120 chars after trim). The new board is owned by that user and
    appears in their list without a manual refresh.
  - **FR-7 List boards.** The board list shows exactly the boards owned by the
    current user, with a stable, documented sort order (e.g. most-recently-
    updated first, or created-at ascending — the choice is §1.6(g), but it must
    be deterministic and identical across reloads).
  - **FR-8 Rename board.** Title can be edited in place or via a dialog;
    validation matches FR-6; the change persists.
  - **FR-9 Delete board.** Deleting a board removes it from the list and
    cascades to all its columns and their cards. No orphaned column or card row
    may survive (INV-2). A destructive confirmation step is required (§1.6(b)).
  - **FR-10 Board detail.** Opening a board renders its columns left-to-right
    in persisted order, each containing its cards in persisted order, in a
    single view without pagination at the sizes in NFR-1.

  **Columns**
  - **FR-11 Create column.** A user can add a column to their board with a
    title (1–80 chars after trim). It is appended to the end of the column
    order.
  - **FR-12 Rename column.** Title can be edited; validation matches FR-11.
  - **FR-13 Delete column.** Deleting a column cascades to its cards, with a
    confirmation step that states how many cards will be destroyed.
  - **FR-14 Reorder columns.** A user can change the left-to-right order of
    columns via drag **and** via the keyboard alternative of FR-26.
  - **FR-15 Column order persists.** The column order set in FR-14 is the order
    returned by the API and rendered after a reload, in a new tab, and in a new
    session.

  **Cards**
  - **FR-16 Create card.** A user can add a card to a column by entering a
    title (1–200 chars after trim; empty/whitespace-only rejected inline). It
    is appended to the end of that column and is visible immediately (FR-30).
  - **FR-17 Edit card.** Title and description (0–5,000 chars) are editable and
    persist. Description is optional and multi-line.
  - **FR-18 Delete card.** A card can be deleted from the card view or the
    board; it disappears from the column and does not return after reload.
  - **FR-19 Assignee.** A card can be assigned to a person and un-assigned. The
    assignee is displayed on the card face on the board. The identity model for
    assignee is §1.6(d).
  - **FR-20 Labels.** Zero or more labels can be attached to and removed from a
    card, persist, and are displayed on the card face. **A label must be
    distinguishable without relying on color** (text, or an icon/pattern with
    an accessible name) per NFR-4.
  - **FR-21 Card detail view.** A dedicated view (modal or panel) exposes
    title, description, assignee, labels and delete. It is dismissible by
    `Esc`, traps focus while open, and returns focus to the invoking card on
    close.

  **Ordering & direct manipulation** (the heart of the rung)
  - **FR-22 Drag within a column.** Dragging a card to a new index within its
    own column reorders it. The rest of the column closes the gap; no other
    column changes.
  - **FR-23 Drag across columns.** Dragging a card onto another column inserts
    it at the drop index in the destination and removes it from the source. The
    card's `column_id` changes; source and destination both remain a valid
    total order.
  - **FR-24 Order is persisted, server-side.** After any FR-22/FR-23/FR-14
    operation, the new order is written to durable storage before the
    interaction is considered complete, and a full page reload (or a fresh
    session, or a direct `GET /api/boards/{id}`) returns exactly the order the
    user last saw. Client-only ordering — `localStorage`, in-memory state,
    render-order tricks — fails this requirement even if the screen looks right.
  - **FR-25 Ordering invariants.** After every mutation, for every parent
    (board→columns, column→cards): the children have a strict total order with
    no ties, no child is duplicated, and no child is lost (INV-1..INV-5, §2.3).
    This must hold under the concurrent and malformed operations in §6.1
    `adversarial`.
  - **FR-26 Keyboard alternative to drag-and-drop.** Every reorder/move
    achievable by pointer drag must be achievable by keyboard alone, from a
    focused card or column: a documented "pick up" key, arrow keys to move
    between positions and columns, a key to drop, and `Esc` to cancel and
    restore the original position. The operation is announced via an ARIA live
    region (pick-up, each move, final placement, cancellation), and focus
    follows the moved item to its new location. This is a **P0** requirement,
    not a stretch goal.
  - **FR-27 Invalid drops are safe no-ops.** Dropping on a non-drop target,
    outside the board, on the card's own current position, or into a
    column/board deleted mid-drag leaves the board in its pre-drag state, with
    no partial write and no error dialog for the "dropped in empty space" case.

  **Authorization**
  - **FR-28 Board ownership.** Every board has exactly one owner. A user's list
    (FR-7) and detail (FR-10) views expose only their own boards.
  - **FR-29 Nested authorization.** Column and card endpoints authorize against
    the **owner of the board the resource belongs to**, resolved server-side
    from the resource id — never from a client-supplied board id, and never
    only at the parent route. `PATCH /api/cards/{id}` for a card on another
    user's board must fail even though the URL contains no board id. Moving a
    card into a column on a board you do not own must fail (§1.6(f) governs
    403-vs-404).

  **Interaction quality & app states**
  - **FR-30 Optimistic UI with rollback.** Card create, card move/reorder,
    column reorder, and inline renames apply to the UI immediately, before the
    server confirms. If the request fails (non-2xx, network error, timeout),
    the UI **reverts to the exact pre-mutation state** and surfaces a
    non-blocking, dismissible error. The reverted state must equal the server's
    state — verified by a reload assertion, not just visually.
  - **FR-31 Loading states.** Every asynchronous view (board list, board detail,
    card detail) renders an explicit loading affordance on first load. No
    view may render a spinner forever on error, and none may render a
    misleading empty state while data is still in flight.
  - **FR-32 Empty states.** A user with no boards, a board with no columns, and
    a column with no cards each render a purpose-built empty state with the
    primary call-to-action for that context — not a blank region.
  - **FR-33 Error states.** API failures (401, 403/404, 422 validation, 5xx,
    network offline) produce distinguishable, human-readable UI: field-level
    messages for validation, a recoverable view-level error with retry for load
    failures, and a redirect to login for session expiry. Raw stack traces,
    JSON blobs, and unhandled promise rejections in the console are failures.
  - **FR-34 Input validation, both sides.** All length/format limits above are
    enforced **server-side** (authoritative, returning 422 with a field name)
    and **client-side** (immediate feedback). Client-only validation fails this
    requirement; the acceptance suite calls the API directly to check.
  - **FR-35 Card text is data, never markup.** Titles, descriptions, labels,
    assignee names and board/column titles are rendered as text. A card whose
    title is `<img src=x onerror=alert(1)>` displays those characters and
    executes nothing, on the board, in the card detail view, and after reload.

- **1.5 Out of scope** — Explicit non-goals. Building any of these costs
  `FID` (scope creep against the PRD) even if implemented well.
  - **Deferred to A2 (this is the A2 sprint backlog — do not pre-build):**
    real-time multi-user sync (WebSocket/polling live updates), comments on
    cards, an activity/audit feed, and search/filter across cards.
  - **Out of the product entirely:** multi-team or organization concepts;
    inviting/sharing a board with another user; roles and permissions beyond
    "owner"; due dates, checklists, attachments, card covers; swimlanes,
    WIP limits, card archiving; board templates; email/notifications; password
    reset and email verification flows; OAuth/SSO; internationalization;
    offline-first/PWA behavior; native mobile apps; analytics; and any
    admin console.
  - **Out of the engineering scope:** production deployment, containerization,
    CI configuration, horizontal scaling, database migrations beyond initial
    schema creation, and multi-tenancy.

- **1.6 Ambiguities the agent must resolve** — This rung deliberately leaves
  *product and implementation-strategy* questions open. Every item must be
  resolved, applied consistently, and **documented in `solution/DECISIONS.md`**
  with a one-paragraph rationale. All listed resolutions are fully acceptable;
  acceptance pins only the invariant column. Asking a human to decide one of
  these is a `clarify` intervention (§0).

  | # | Ambiguity | Acceptable resolutions | What acceptance pins regardless |
  |---|-----------|------------------------|---------------------------------|
  | (a) | **Ordering representation.** How position is stored and mutated. | **(a1)** dense integer `position` per parent, renumbered transactionally on move; **(a2)** sparse integers with gap allocation and periodic rebalance; **(a3)** fractional/lexicographic ranks (LexoRank-style) with a documented rebalance rule. | INV-1..INV-5 (§2.3) hold after every operation, including the concurrent and adversarial cases. The chosen scheme is documented, and the API contract in §2.1 (`target_index`, 0-based) is unchanged by the internal choice. |
  | (b) | **Delete semantics.** Hard delete vs. soft delete/archive. | **(b1)** hard delete with a confirmation step; **(b2)** soft delete (`deleted_at`) with a confirmation step, provided deleted entities are invisible to every read path. | Deletion cascades to descendants, a confirmation step exists for board and column deletion, and no deleted entity reappears after reload or via any API read. |
  | (c) | **Label model.** Fixed palette vs. free-form user-defined labels; join table vs. embedded array. | **(c1)** fixed enumerated palette (e.g. 6 named labels); **(c2)** free-form label strings per board; either persisted via a join table or a typed array/JSON column. | Labels persist, round-trip through the API, render on the card face, and are **never distinguished by color alone** (NFR-4). Label text is escaped (FR-35). |
  | (d) | **Assignee identity.** | **(d1)** free-text assignee name on the card; **(d2)** a foreign key to `users` restricted to the board owner (single-user product); **(d3)** a per-board roster of member names owned by the board. | Assignee persists, is displayed on the card face, is clearable, and — if it is free text — is escaped and length-limited. Whatever the model, it must not create a second authorization surface (a user cannot enumerate other accounts). |
  | (e) | **Session mechanism.** | **(e1)** server-side session with an `HttpOnly`, `SameSite=Lax` cookie (**preferred**); **(e2)** a signed token (e.g. JWT) — permitted only if the storage choice and its XSS exposure are explicitly justified in `DECISIONS.md`. | Session survives reload (FR-4), is invalidated by logout (FR-3), is required by every mutation (FR-5), and — if cookie-based — is CSRF-defended (NFR-3). |
  | (f) | **Not-found vs. forbidden** for another user's resources. | **(f1)** `404` uniformly (non-enumerable, **preferred**); **(f2)** `403` uniformly. | The choice is uniform across boards, columns and cards; it is never `200`; and the response body never leaks the other user's data (title, counts, ids). |
  | (g) | **Board list sort order and card-face density** — what the list is sorted by; how much of a card (description snippet? counts? avatars?) appears on the board face. | Any documented, deterministic sort. Any card-face density that the hi-fi mockups show and the implementation matches. | The sort is stable and identical across reloads. The card face matches `design/hifi/` (design-diff review, §6.3). |
  | (h) | **Visual direction** — palette, type scale, density, iconography. | Any coherent direction, *provided* it is expressed as design tokens (§5.4), applied consistently, and passes contrast (NFR-4). | Tokens exist, are actually consumed by the app (not a dead file), and the running UI matches the hi-fi mockups within the tolerance in §6.3. |

## 2. Technical Requirements

- **2.1 Interface / API contract** — The REST surface is **pinned**; it is the
  shared contract between A1 and A2 and the acceptance suite calls it directly.
  Paths, methods, status codes and the `move` semantics are not negotiable.
  Payload fields may be *added* but not renamed or removed.

  All endpoints are prefixed `/api`. All request/response bodies are JSON.
  All timestamps are ISO-8601 UTC. All ids are opaque strings (integer or UUID
  — the client must treat them as opaque).

  | Method | Path | Auth | Body → Response | Success | Notes |
  |--------|------|------|-----------------|---------|-------|
  | `GET` | `/api/health` | no | → `{"status":"ok"}` | 200 | Harness readiness probe (§2.5). |
  | `POST` | `/api/auth/register` | no | `{email,password}` → `{user}` | 201 | 409 on duplicate email; 422 on invalid. |
  | `POST` | `/api/auth/login` | no | `{email,password}` → `{user}` | 200 | Establishes session (§1.6e). 401 on bad creds. |
  | `POST` | `/api/auth/logout` | yes | → *empty* | 204 | Invalidates the session. |
  | `GET` | `/api/auth/me` | yes | → `{user}` | 200 | 401 when unauthenticated. Used for FR-4. |
  | `GET` | `/api/boards` | yes | → `[{board}]` | 200 | Owner's boards only (FR-7, FR-28). |
  | `POST` | `/api/boards` | yes | `{title}` → `{board}` | 201 | |
  | `GET` | `/api/boards/{board_id}` | yes | → `{board, columns:[{column, cards:[{card}]}]}` | 200 | **Fully nested and ordered.** One round trip renders the board. |
  | `PATCH` | `/api/boards/{board_id}` | yes | `{title?}` → `{board}` | 200 | |
  | `DELETE` | `/api/boards/{board_id}` | yes | → *empty* | 204 | Cascades (FR-9). |
  | `POST` | `/api/boards/{board_id}/columns` | yes | `{title}` → `{column}` | 201 | Appended last (FR-11). |
  | `PATCH` | `/api/columns/{column_id}` | yes | `{title?}` → `{column}` | 200 | |
  | `DELETE` | `/api/columns/{column_id}` | yes | → *empty* | 204 | Cascades to cards (FR-13). |
  | `POST` | `/api/columns/{column_id}/move` | yes | `{target_index}` → `[{column}]` | 200 | Reorders columns within the board (FR-14). Returns the board's columns in new order. |
  | `POST` | `/api/columns/{column_id}/cards` | yes | `{title, description?, assignee?, labels?}` → `{card}` | 201 | Appended last (FR-16). |
  | `PATCH` | `/api/cards/{card_id}` | yes | `{title?, description?, assignee?, labels?}` → `{card}` | 200 | Partial update; omitted fields unchanged; explicit `null` clears (FR-17/19/20). |
  | `DELETE` | `/api/cards/{card_id}` | yes | → *empty* | 204 | |
  | `POST` | `/api/cards/{card_id}/move` | yes | `{target_column_id, target_index}` → `{card, affected_column_ids}` | 200 | **The flagship operation** (FR-22/FR-23). |

  **`move` semantics (pinned — acceptance tests this directly):**
  ```
  target_index is 0-based, and is the insertion index in the DESTINATION
  parent AFTER the item has been removed from its source parent.

    Column A: [c0, c1, c2, c3]
    POST /api/cards/c3/move {target_column_id: A, target_index: 1}
      -> A: [c0, c3, c1, c2]

    Column A: [a0, a1]   Column B: [b0, b1]
    POST /api/cards/a0/move {target_column_id: B, target_index: 2}
      -> A: [a1]         B: [b0, b1, a0]

  target_index is clamped to [0, len(destination_after_removal)].
  Out-of-range values are clamped, NOT rejected (FR-27: a stale client must
  not be able to corrupt the order or produce a 500).
  A move to the item's current parent and current index is a valid no-op (200).
  A move whose destination belongs to another user's board is rejected per
  1.6(f) and MUST NOT mutate either parent.
  ```

  **Error envelope (uniform across all endpoints):**
  ```json
  { "error": { "code": "validation_error",
               "message": "Title must be between 1 and 200 characters.",
               "field": "title" } }
  ```

  | Status | Used for |
  |--------|----------|
  | 400 | Malformed JSON / missing body |
  | 401 | No or invalid session (FR-5) |
  | 403 / 404 | Another user's resource — uniformly, per §1.6(f) (FR-28/29) |
  | 409 | Duplicate email (FR-1) |
  | 422 | Field validation failure, with `error.field` set (FR-34) |
  | 500 | Never expected; any 500 during acceptance is a `ROB` deduction |

  **SPA routes (pinned, so E2E can navigate deterministically):**

  | Route | View | Guard |
  |-------|------|-------|
  | `/login` | Login form | redirect to `/boards` if authenticated |
  | `/register` | Registration form | redirect to `/boards` if authenticated |
  | `/boards` | Board list (FR-7, FR-32) | auth required (FR-5) |
  | `/boards/:boardId` | Board detail (FR-10) | auth required + ownership (FR-28) |
  | `/boards/:boardId/cards/:cardId` *(or an equivalent modal state)* | Card detail (FR-21) | auth required + ownership |
  | `*` | Not-found view | — |

  **Required DOM contract for E2E** (the minimum stable hooks the acceptance
  suite relies on; everything else is queried by role/name):

  | Hook | On |
  |------|----|
  | `data-testid="board-list"` / `"board-card"` with `data-board-id` | board list |
  | `data-testid="column"` with `data-column-id` | each column |
  | `data-testid="card"` with `data-card-id` | each card |
  | `role="list"` / `role="listitem"` (or `role="group"` + `aria-label`) | column and card containers (NFR-4) |
  | `aria-live="polite"` region | keyboard-move announcements (FR-26) |

  DOM order of `[data-testid="card"]` within a column **must equal** the
  persisted order — the acceptance suite reads order from the DOM and compares
  it to the API response.

- **2.2 Architecture constraints**
  - Two deployable pieces in one repo: `solution/backend` (Python) and
    `solution/frontend` (React/TS). They communicate **only** over the HTTP API
    in §2.1. No shared runtime, no server-rendered templates.
  - **Backend layering** — routing/serialization, business logic, and
    persistence are separable. Ordering logic lives in **one** module (e.g.
    `ordering.py`) and is the single writer of position values; route handlers
    must not compute positions inline. Rationale: A2 will extend this and the
    invariants must have one home.
  - **Server is the source of truth for order.** The client may render an
    optimistic order, but every persisted order originates from a server
    response. A client that computes and stores positions itself fails FR-24's
    intent.
  - **Frontend layering** — a typed API client module is the only place `fetch`
    is called; a store (§2.4) holds normalized board state; components render
    from the store and dispatch actions. Components must not call `fetch`
    directly, and business rules (what a move means) must not be duplicated in
    component event handlers.
  - **Typed contract** — request/response types are declared once in TypeScript
    (`src/types/api.ts`, hand-written or generated from the backend schema) and
    used by the API client. `any` at the API boundary is a `QUA` deduction.
  - **Forbidden:** rendering user text via `dangerouslySetInnerHTML` or
    equivalent (FR-35); string-interpolated SQL (parameterized queries or an
    ORM only); storing secrets or credentials in the repo; a second database
    or external service beyond the one in §2.4.

- **2.3 Data model** — Four entities. The schema below is the **reference
  shape**; column names are pinned for `users`, `boards`, `columns`, `cards`
  because A2 extends this schema. Label storage is §1.6(c); the `position`
  representation is §1.6(a) (the type shown is one legal choice).

  ```sql
  CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,          -- stored lowercased
    password_hash TEXT NOT NULL,                 -- bcrypt/argon2/scrypt (NFR-3)
    created_at    TIMESTAMP NOT NULL
  );

  CREATE TABLE boards (
    id         TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,                    -- 1..120
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
  );
  CREATE INDEX ix_boards_owner ON boards(owner_id);

  CREATE TABLE columns (
    id         TEXT PRIMARY KEY,
    board_id   TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,                    -- 1..80
    position   REAL NOT NULL,                    -- see 1.6(a)
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
  );
  CREATE INDEX ix_columns_board_pos ON columns(board_id, position);

  CREATE TABLE cards (
    id          TEXT PRIMARY KEY,
    column_id   TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,                   -- 1..200
    description TEXT NOT NULL DEFAULT '',        -- 0..5000
    assignee    TEXT NULL,                       -- see 1.6(d)
    position    REAL NOT NULL,                   -- see 1.6(a)
    created_at  TIMESTAMP NOT NULL,
    updated_at  TIMESTAMP NOT NULL
  );
  CREATE INDEX ix_cards_column_pos ON cards(column_id, position);

  -- Labels: 1.6(c). Either a join table like this, or a typed array/JSON
  -- column on cards. Whichever is chosen must round-trip through the API.
  CREATE TABLE card_labels (
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    label   TEXT NOT NULL,
    PRIMARY KEY (card_id, label)
  );
  ```

  **Relationships:** `users 1—* boards 1—* columns 1—* cards`. Ownership is
  transitive: a card's owner is `card → column → board → owner_id`, and that
  is the only chain authorization may use (FR-29).

  **Ordering invariants** (these are what the adversarial tier attacks):

  | # | Invariant |
  |---|-----------|
  | **INV-1** | Within a parent, children have a **strict total order** — no two children compare equal on `position`. |
  | **INV-2** | No orphans: every column has an existing board; every card has an existing column. Deleting a parent removes descendants in the same transaction. |
  | **INV-3** | Moves conserve items: after any `move`, the multiset of card ids on the board is unchanged — nothing duplicated, nothing lost. |
  | **INV-4** | Reload equivalence: for any sequence of operations, the order returned by `GET /api/boards/{id}` equals the order the UI displayed when the last operation settled. |
  | **INV-5** | Concurrency safety: two `move` requests issued concurrently (same card, or two cards into the same column) leave INV-1..INV-4 intact. Serialize the write (transaction + row locking, or a per-board write lock); last-writer-wins on *content* is acceptable, order corruption is not. |

  **Persistence:** durable across process restart. The harness may restart the
  backend between phases and re-assert board state.

- **2.4 Technology constraints**

  | Layer | Required | Permitted choices | Forbidden |
  |-------|----------|-------------------|-----------|
  | Backend language | Python ≥ 3.11 | — | anything else |
  | Backend framework | **FastAPI** (preferred) or Flask | + `uvicorn`/`gunicorn`, `pydantic` | Django (batteries the rung is meant to test) |
  | Persistence | **SQLite** by default (zero external services); Postgres permitted if the harness can start it | raw `sqlite3`, SQLAlchemy, SQLModel | any store that is not durable across restart (in-memory dicts, `:memory:` SQLite as the primary store) |
  | Password hashing | a real KDF | `bcrypt`, `argon2-cffi`, `passlib`, `hashlib.scrypt` | plaintext, unsalted MD5/SHA-* |
  | Frontend | **React 18+ · TypeScript (`strict: true`) · Vite** | React Router, CSS modules / plain CSS / vanilla-extract / Tailwind | any non-React framework |
  | Client state | a store | **Zustand** (preferred), Redux Toolkit, Jotai, TanStack Query + a store | ad-hoc prop drilling of board state through 4+ levels; global mutable singletons |
  | Drag & drop | a library **or** hand-rolled | `@dnd-kit/*` (preferred — has a keyboard sensor), `react-beautiful-dnd`/`@hello-pangea/dnd`, HTML5 DnD | any library that cannot satisfy FR-26 keyboard operation |
  | E2E | **Playwright** (`@playwright/test`), Chromium | + `@axe-core/playwright` | Selenium-only, or DOM-mocking "E2E" |
  | Static checks | `ruff` + `pyright` (backend); `tsc --noEmit` + `eslint` (frontend) | — | disabling strictness to pass |

  **Forbidden shortcuts (scanned at scoring time, `VERIFICATION_CONTRACT.md` §1):**
  a pre-built kanban/board component or full-app package (e.g. `react-trello`,
  `react-kanban*`, `@caldwell619/react-kanban`, `dhtmlx-*`, or any package whose
  purpose is "a kanban board"), a scaffolded starter that ships this
  application, and any backend-as-a-service that supplies the board API. Using
  a *generic* DnD, UI-primitive, form, or icon library is fine — the
  distinction is whether the package implements the product. A direct
  dependency on a board package is a **constraint violation → gate FAIL**; a
  vendored or obfuscated copy is a `gaming_event` → run **disqualified**.

  **Dependency budget:** direct runtime dependencies ≤ 12 backend, ≤ 15
  frontend. Exceeding it is a `QUA` deduction, not a gate failure.

- **2.5 Entrypoint contract** — `kind: web-app`. The harness owns process
  lifecycle; the solution must be startable with **no interactive input** and
  no manual step.

  ```yaml
  # scenarios/A1-kanban-app/manifest.yaml   (authored in the harness pass)
  level: 6
  language: python+typescript
  workspace: solution/
  entrypoint:
    kind: web-app
    start_cmd: "./solution/run.sh"        # MUST start API + serve the SPA
    url: "http://localhost:5173"          # SPA origin the E2E suite navigates to
    api_base_url: "http://localhost:8000/api"
    health_path: "/api/health"
    ready_timeout_s: 90
    e2e_runner: "npx playwright test"
  build:
    setup:
      - "pip install -r solution/backend/requirements.txt"
      - "npm --prefix solution/frontend ci"
      - "npx playwright install --with-deps chromium"
  verify:
    smoke:       "pytest tests/smoke -q && npx playwright test tests/smoke_e2e"
    acceptance:  "pytest tests/acceptance -q --json-report && npx playwright test tests/acceptance_e2e --reporter=json"
    adversarial: "pytest tests/adversarial -q --json-report && npx playwright test tests/adversarial_e2e --reporter=json"
  budgets:
    wall_clock_s: 14400
    iterations_soft: 30
    iterations_hard: 80
    interventions: 0
  gate:
    p0_criteria_floor: 1.0        # 100% of P0 acceptance criteria
    acceptance_floor: 0.90        # >= 90% of all acceptance assertions
  ```

  Required of the solution:
  - `solution/run.sh` starts both processes, exits non-zero if either fails to
    bind, and is idempotent (safe to re-run after a kill).
  - Fresh-database bootstrap: on an empty data directory the schema is created
    automatically. The database path/URL is configurable via environment
    (`DATABASE_URL` or `KANBAN_DB`) so the harness gets a throwaway DB per run
    (`VERIFICATION_CONTRACT.md` §4).
  - Ports configurable via `PORT`/`API_PORT` env with the defaults above.
  - `GET /api/health` returns 200 only once the schema is ready to serve.
  - The SPA is served on `url` and reaches the API without a manual proxy step
    (Vite proxy or CORS configured — the harness will not configure either).
  - `solution/seed.py` (or `npm run seed`) creates two deterministic accounts,
    `alice@example.com` / `bob@example.com` (password `password123`), used by
    the authz tests. Seeding must be idempotent.

## 3. Non-Functional Requirements

- **NFR-1 Performance** — The board must feel like the whiteboard it replaces.
  Budgets are measured on the reference runner against the reference dataset
  (5 columns × 40 cards = 200 cards, plus a 20-column × 500-card stress board).

  | Budget | Target |
  |--------|--------|
  | Drag feedback | The dragged card follows the pointer/keyboard within **one frame budget (≤ 16 ms/frame, no dropped-frame cluster > 100 ms)**. Drag must not await the network. |
  | Optimistic apply | The UI reflects a card create/move **< 100 ms** after the gesture completes, independent of API latency (FR-30). |
  | API p95 (local, warm) | reads `GET /api/boards/{id}` **< 150 ms**; writes (`move`, `PATCH`, `POST`) **< 250 ms**. |
  | Board first render | Reference board interactive **< 1.5 s** from navigation on a warm cache. |
  | Stress board | 20 columns × 500 cards renders and remains draggable **< 4 s**, without the page becoming unresponsive. |
  | Query shape | `GET /api/boards/{id}` must not be N+1: bounded number of queries independent of column/card count. |
  | Render shape | Moving one card must not re-render every card on the board; no O(n²) reconciliation on the stress board. |

- **NFR-2 Reliability & error handling** — Ordering is the reliability story
  here. INV-1..INV-5 (§2.3) hold after **every** operation and every failure.
  A `move` is atomic: it either fully applies (both parents consistent) or not
  at all — a crash or rollback mid-move must never leave a duplicated or
  orphaned card. Repeating the same `move` request is idempotent in effect.
  Client-side failures roll the UI back to the exact pre-mutation state
  (FR-30), and a rolled-back UI equals the server state on reload. Deleting an
  entity that is already deleted returns the delete status code or the §1.6(f)
  status — never a 500. Timeouts and offline errors are handled, not
  swallowed: no unhandled promise rejection may reach the console during any
  acceptance run.

- **NFR-3 Security** — This is the first rung with untrusted user text
  displayed to other sessions and with real authorization.
  - **Authentication:** passwords stored only as KDF hashes with per-user salt
    (§2.4); never logged, never returned by any endpoint. Login failures are
    generic (FR-2).
  - **Session:** per §1.6(e). Cookie sessions must be `HttpOnly` and
    `SameSite=Lax` (or `Strict`), and mutations must be CSRF-defended
    (SameSite plus a token or an origin/referer check — state the choice in
    `DECISIONS.md`). Logout must invalidate server-side, not just clear the
    client.
  - **Authorization:** every board-scoped endpoint resolves ownership
    server-side from the resource id (FR-29). No endpoint may trust a
    client-supplied `owner_id`, `board_id`, or role. Authorization is enforced
    in the API layer — hiding a control in the UI is not authorization.
  - **Injection:** parameterized queries or ORM only. No `eval`, no dynamic
    import of user input, no shell-out with user text.
  - **Stored XSS:** all user-controlled text is rendered as text, everywhere it
    appears — board face, card face, card detail, page `<title>`, and any
    `aria-label` (FR-35). If a URL field is ever added, `javascript:` schemes
    are rejected.
  - **Input limits:** enforced server-side (FR-34). Oversized bodies are
    rejected with 422/413, not by exhausting memory. Request body cap ≥ 1 MB is
    acceptable; unbounded is not.
  - **Secrets:** the session signing key comes from environment with a
    development default that is clearly marked as such; no credentials in the
    repo.
  - **Error output:** no stack traces, SQL, or file paths in any API response.

- **NFR-4 Accessibility — REQUIRED, WCAG 2.1 Level AA.** This is a P0 quality
  bar at A1, not a stretch goal. It is verified by an automated scan **and** a
  scripted keyboard-only path (§6.3).

  | # | Requirement | WCAG ref |
  |---|-------------|----------|
  | a11y-1 | **Every** interactive control is keyboard operable, in a logical tab order, including card creation, editing, deletion, and the FR-26 move alternative. No keyboard traps except an intentional, escapable modal focus trap (FR-21). | 2.1.1, 2.1.2 |
  | a11y-2 | **Keyboard alternative to drag-and-drop** is implemented per FR-26 and documented in `design/a11y-annotations.md` (which keys, what is announced). | 2.1.1, 4.1.2 |
  | a11y-3 | Semantic structure: the board is a labelled region; each column is a labelled group/list with an accessible name equal to its title and a card count; each card is a list item with an accessible name including its title. Headings are hierarchical (one `h1` per view). | 1.3.1, 2.4.6 |
  | a11y-4 | Visible focus indicator on every focusable element, with ≥ 3:1 contrast against adjacent colors. Focus is never suppressed via `outline: none` without an equivalent replacement. | 2.4.7, 1.4.11 |
  | a11y-5 | Contrast: ≥ 4.5:1 for normal text, ≥ 3:1 for large text and for UI component/graphical boundaries (including column and card borders and label chips). | 1.4.3, 1.4.11 |
  | a11y-6 | Color is never the sole carrier of meaning — labels, status and validation errors all carry text or an accessible name (FR-20, FR-33). | 1.4.1 |
  | a11y-7 | Every form control has a programmatically associated label; validation errors are associated with their field (`aria-describedby`) and announced. | 1.3.1, 3.3.1, 3.3.2 |
  | a11y-8 | Dynamic changes are announced via a polite live region: card moved (with source, destination and position), card created/deleted, save failed/rolled back. | 4.1.3 |
  | a11y-9 | Focus management: opening the card detail moves focus into it; closing returns focus to the invoking card; a moved card retains focus at its new location; a deleted card moves focus to a sensible neighbor. | 2.4.3 |
  | a11y-10 | Respects `prefers-reduced-motion`: drag/transition animation is reduced or removed. | 2.3.3 (AAA, adopted here for determinism) |
  | a11y-11 | Each route has a unique, descriptive document title; the app has a skip-to-content affordance if there is persistent navigation chrome. | 2.4.2, 2.4.1 |
  | a11y-12 | Automated `axe-core` scan of `/login`, `/boards`, `/boards/:id` (populated **and** empty) and the card detail view reports **zero `serious` or `critical`** violations. `moderate` violations must be enumerated and justified in `design/a11y-annotations.md`. | — |

  Responsive scope: desktop ≥ 1024 px is required and is the design-diff
  reference viewport; ≥ 768 px must not break layout (no horizontal scrolling
  of app chrome, no overlapping controls). < 768 px is **Optional/Stretch**.

- **NFR-5 Maintainability** — `ruff` and `pyright` clean on the backend;
  `tsc --noEmit` clean under `strict: true` and `eslint` clean on the frontend.
  No `any` at the API boundary; no `@ts-ignore` without an adjacent
  justification comment. Clear module boundaries per §2.2, enforced by
  inspection: an API call from inside a presentational component, or ordering
  arithmetic inside a route handler, is a `QUA` deduction. Cyclomatic
  complexity ≤ 12 per function; no source file > 400 LoC. Public backend
  modules and every exported frontend component have a one-line purpose
  comment or docstring. `solution/README.md` documents how to run, how to test,
  and the architecture in ≤ 1 page; `solution/DECISIONS.md` documents every
  §1.6 resolution.

- **NFR-6 Observability** — `GET /api/health` reports readiness (§2.5).
  Structured (JSON or consistently-formatted) request logs at INFO carrying
  method, path, status and duration, and a correlation id per request.
  Unhandled server exceptions are logged at ERROR **with** the traceback
  server-side and returned as a generic 500 body (NFR-3). No password, session
  token, or full request body containing credentials appears in any log. The
  frontend has a top-level error boundary that renders a recoverable error view
  rather than a blank page, and reports the error to the console once.

- **NFR-7 Portability / footprint** — Clean checkout to running app in **two
  commands plus `run.sh`**, on Linux and macOS, with no external services in
  the default configuration (SQLite). Node ≥ 20, Python ≥ 3.11. All
  dependencies pinned in `requirements.txt` and `package-lock.json`. No global
  installs, no `sudo`, no network access required at runtime. Cold `run.sh` to
  healthy `/api/health` in < 90 s (§2.5 `ready_timeout_s`).

## 4. The Ask (Deliverables & Definition of Done)

- **4.1 Required artifacts**

  ```
  solution/
    run.sh                     # starts API + SPA (§2.5)
    seed.py                    # deterministic alice/bob accounts (§2.5)
    README.md                  # run, test, architecture (≤ 1 page)
    DECISIONS.md               # every §1.6 resolution + rationale
    backend/
      requirements.txt
      app/main.py              # app factory, health, error handlers, logging
      app/api/{auth,boards,columns,cards}.py
      app/models.py  app/schemas.py  app/db.py
      app/auth.py              # hashing, session, current-user dependency
      app/ordering.py          # SINGLE writer of position values (§2.2)
    frontend/
      package.json  package-lock.json  vite.config.ts  tsconfig.json
      src/main.tsx  src/App.tsx
      src/routes/{Login,Register,BoardList,BoardDetail}.tsx
      src/components/{Board,Column,Card,CardDetail,EmptyState,ErrorState,...}.tsx
      src/store/boardStore.ts  src/store/authStore.ts
      src/api/client.ts        # the ONLY place fetch is called (§2.2)
      src/types/api.ts         # typed contract
      src/styles/tokens.css    # generated from / mirroring design tokens
  design/                      # see §5.4 — required deliverables, scored under FID
  tests/smoke/                 # the visible smoke suite, kept passing
  ```

  **Feature priority.** P0 is the gated set: 100% of P0 acceptance criteria are
  required to clear the gate (§7.3). P1 counts toward the ≥ 90% overall floor
  and toward `FID`.

  | Pri | Feature | FRs |
  |-----|---------|-----|
  | **P0** | Register / login / logout / session persistence / auth gating | FR-1..FR-5 |
  | **P0** | Board CRUD + owner-scoped list | FR-6..FR-10 |
  | **P0** | Column create / rename / delete / reorder, order persisted | FR-11..FR-15 |
  | **P0** | Card create / edit / delete + card detail view | FR-16..FR-18, FR-21 |
  | **P0** | Drag within a column and across columns, **persisted across reload** | FR-22..FR-25, FR-27 |
  | **P0** | Keyboard-accessible move alternative + live-region announcements | FR-26, NFR-4 a11y-2/8/9 |
  | **P0** | Per-user ownership and nested authorization | FR-28, FR-29 |
  | **P0** | Optimistic UI with rollback; loading / empty / error states | FR-30..FR-33 |
  | **P0** | Server-side validation; card text rendered as text (no stored XSS) | FR-34, FR-35 |
  | **P0** | Required design artifacts present and traceable (§5.4) | — |
  | **P1** | Assignee on cards (set, display, clear) | FR-19 |
  | **P1** | Labels on cards, not color-only | FR-20 |
  | **P1** | Keyboard-move polish: cancel-with-`Esc` restoring the exact original index, focus-follows-item, announcement wording | FR-26 |
  | **P1** | Drag affordance polish: drop-indicator placeholder, cursor/aria state, reduced-motion path | NFR-1, a11y-10 |
  | **P1** | Stress-board performance budget (20 × 500) | NFR-1 |

- **4.2 Definition of Done**
  - [ ] `smoke` suite (API + E2E) passes.
  - [ ] `acceptance` gate met: **100% of P0 criteria** and **≥ 90% overall** (§7.3).
  - [ ] `./solution/run.sh` brings up a working app from a clean checkout and an
        empty database within `ready_timeout_s`; `seed.py` creates alice/bob.
  - [ ] Order persists across reload, across a new session, and across a
        backend restart (FR-24, INV-4).
  - [ ] Ordering invariants INV-1..INV-5 verified after the concurrent-move and
        invalid-target cases.
  - [ ] Authz: user B cannot read, mutate, or move into user A's board,
        column, or card — via the API directly, not just the UI (FR-28/29).
  - [ ] Stored-XSS probe: the payload set in §6.1 renders as text everywhere
        and executes nothing (FR-35).
  - [ ] **`axe-core` scan reports zero `serious`/`critical` violations** on all
        five scanned views (a11y-12).
  - [ ] **Keyboard-only path completes**: log in → create board → create column
        → create card → move card to another column → reload → order correct,
        with no pointer events (FR-26).
  - [ ] **Design-diff review passes**: the running UI matches `design/hifi/` for
        every specified screen and state within tolerance (§6.3).
  - [ ] Every required `design/` artifact in §5.4 exists, is internally
        consistent, and traces to `FR`/acceptance criteria.
  - [ ] `ruff` + `pyright` clean; `tsc --noEmit` (strict) + `eslint` clean.
  - [ ] No forbidden dependency (§2.4); dependency budget respected.
  - [ ] Every §1.6 ambiguity resolved, applied consistently, and documented in
        `solution/DECISIONS.md`.
  - [ ] No unhandled promise rejection or console error during any acceptance
        E2E run; no 500 from any acceptance API call.

- **4.3 Acceptance criteria** — The criteria matrix. `Pri` P0 criteria are the
  100%-required set; P1 criteria count toward the ≥ 90% overall floor.

  | # | Criterion | Traces to | Pri | How verified |
  |---|-----------|-----------|-----|--------------|
  | AC-1 | Register → login → `me` → logout round-trips; the post-logout credential authorizes nothing. | FR-1..FR-3 | P0 | API |
  | AC-2 | Session survives a full page reload and a second tab; user lands back on the same route. | FR-4 | P0 | E2E |
  | AC-3 | Unauthenticated navigation to `/boards` and `/boards/:id` shows login and never renders board data; every mutating endpoint returns 401 without a session. | FR-5 | P0 | E2E + API |
  | AC-4 | Board create/rename/delete work end to end; delete cascades with no orphan columns or cards. | FR-6..FR-9, INV-2 | P0 | E2E + API + DB |
  | AC-5 | Board list shows only the owner's boards, in a deterministic order across reloads. | FR-7, §1.6(g) | P0 | E2E + API |
  | AC-6 | Column create/rename/delete work; delete cascades to cards with a confirmation step. | FR-11..FR-13 | P0 | E2E + API |
  | AC-7 | Column reorder persists across reload; the API returns the new order. | FR-14, FR-15 | P0 | E2E + API |
  | AC-8 | Card create/edit/delete work; card detail opens, edits persist, `Esc` closes and restores focus. | FR-16..FR-18, FR-21 | P0 | E2E |
  | AC-9 | **Drag within a column** reorders the card; DOM order and API order agree; order survives reload. | FR-22, FR-24, INV-1/4 | P0 | E2E + API |
  | AC-10 | **Drag across columns** moves the card to the drop index; source closes the gap; both columns are valid total orders; survives reload. | FR-23..FR-25 | P0 | E2E + API |
  | AC-11 | `POST /api/cards/{id}/move` honors the pinned `target_index` semantics, including clamping out-of-range indices without error. | §2.1, FR-27 | P0 | API |
  | AC-12 | Concurrent moves leave INV-1..INV-4 intact: no duplicate positions, no lost card, no 500. | INV-5, NFR-2 | P0 | API (concurrency probe) |
  | AC-13 | Invalid drops (no target, own position, deleted column mid-drag) are no-ops leaving the pre-drag state. | FR-27 | P0 | E2E + API |
  | AC-14 | **Keyboard-only move**: pick up, move across columns, drop, and cancel-with-`Esc` all work; each step is announced in a live region; focus follows the card. | FR-26, a11y-2/8/9 | P0 | E2E (keyboard only) |
  | AC-15 | User B cannot list, read, mutate, delete, or move into any of user A's boards/columns/cards; the status is uniform per §1.6(f) and leaks no data. | FR-28, FR-29, NFR-3 | P0 | API |
  | AC-16 | An optimistic mutation whose request fails rolls the UI back to the exact prior state, shows a dismissible error, and matches the server after reload. | FR-30, NFR-2 | P0 | E2E (fault injection) |
  | AC-17 | Loading, empty (no boards / no columns / no cards) and error states each render their purpose-built UI. | FR-31..FR-33 | P0 | E2E |
  | AC-18 | Server-side validation rejects over-length and empty titles with 422 + `error.field`, even when the client is bypassed. | FR-34 | P0 | API |
  | AC-19 | Stored-XSS payloads in card title/description/labels/assignee and board/column titles render as text and execute nothing, on the board, in detail, and after reload. | FR-35, NFR-3 | P0 | E2E |
  | AC-20 | `axe-core` reports zero serious/critical violations on the five scanned views. | a11y-12 | P0 | E2E (axe) |
  | AC-21 | Focus is visible on every focusable element; contrast meets AA; no meaning conveyed by color alone. | a11y-4/5/6 | P0 | E2E (axe) + review |
  | AC-22 | All required `design/` artifacts exist, are consistent, and trace to FRs. | §5.4 | P0 | Checklist |
  | AC-23 | The running UI matches `design/hifi/` for every specified screen/state within tolerance. | §1.6(h), §6.3 | P0 | Design-diff review |
  | AC-24 | Assignee can be set, displayed on the card face, and cleared; it persists. | FR-19 | P1 | E2E + API |
  | AC-25 | Labels can be added/removed, persist, render on the card face, and are distinguishable without color. | FR-20, a11y-6 | P1 | E2E + review |
  | AC-26 | Reference board (5 × 40) is interactive < 1.5 s; optimistic apply < 100 ms; API p95 within budget. | NFR-1 | P1 | E2E timing + API timing |
  | AC-27 | Stress board (20 × 500) renders and stays draggable within budget; `GET /api/boards/{id}` is not N+1. | NFR-1 | P1 | E2E + query counter |
  | AC-28 | Static checks clean; no forbidden dependency; module boundaries respected. | NFR-5, §2.2/2.4 | P1 | Static analysis + review |
  | AC-29 | `/api/health`, structured request logs with correlation ids, no secrets in logs, frontend error boundary present. | NFR-6 | P1 | API + review |
  | AC-30 | Clean checkout → `run.sh` → healthy within 90 s with an empty DB; `DATABASE_URL` respected; order survives a backend restart. | NFR-7, FR-24 | P1 | Harness bootstrap |

## 5. Discovery & Design Activities

A1 is the rung where the **full product and design surface becomes required**
(`ARTIFACT_GRADIENT.md` A1). Missing a Required artifact caps `FID` and can drop
the run below its pass threshold even if every functional test passes — at this
rung, "working" includes "meets the product and design intent."

**Honesty note on research at this rung:** the agent cannot interview live
humans inside a sealed run. The required research artifacts are therefore
**structured, sourced, and explicitly labelled as synthesized**: the strategy
conducts its interviews against the persona briefs in §1.2 (and any
harness-provided stakeholder proxy), records the *actual questions asked*, the
answers, and — critically — **which design decisions each finding changed**. An
artifact that merely restates §1.2 in prose scores `FID` ≤ 2. Research that
demonstrably shaped a decision (and says so) is what earns credit; fabricating
interviews with named "real" users and presenting them as field data is a
`FID` failure for dishonesty.

- **5.1 User research**
  | Activity | Status | What it means here |
  |----------|--------|--------------------|
  | Stakeholder/user interviews | **Required** | ≥ 2 documented sessions (one per primary persona) in `design/research/interviews.md`: script, questions, responses, and a "decisions changed by this" section with at least three concrete, traceable changes. |
  | Jobs-to-be-done / needs analysis | **Required** | ≥ 4 JTBD statements in the *when/I want to/so I can* form, each mapped to the FRs that serve it and the FRs deliberately **not** built (§1.5). |
  | Personas | **Required** | ≥ 3 personas including a keyboard/assistive-tech persona (§1.2), each with goals, frustrations, key tasks, and the FRs they drive. |
  | Usability testing | **Optional/Stretch** | A documented walkthrough of the two core flows (create-and-populate a board; move a card) against a heuristic checklist, with findings and what changed. Credit only if it produced a change. |

- **5.2 Product design**
  | Activity | Status | What it means here |
  |----------|--------|--------------------|
  | Spec / acceptance criteria | **Required** | This document is the source spec; the deliverable is the traceability from `design/` artifacts back to `FR`/`AC` ids. |
  | PRD | **Required** | `design/prd.md`: problem, target users, goals and non-goals (consistent with §1.5), success metrics, scope by release, key risks, and open questions with their §1.6 resolutions. |
  | User stories | **Required** | `design/user-stories.md`: US-1..US-21 (§1.3) or a superset, each with per-story acceptance criteria. |
  | Prioritized backlog | **Required** | `design/backlog.md`: every story sized and ordered into **P0** and **P1** matching §4.1, with dependencies made explicit (auth before boards; persistence before drag; drag before keyboard-move polish). This backlog is the seed for A2's sprint plans. |
  | Sprint plans + goals | **N/A** — A1 is a single continuous delivery. Iterative sprint machinery is exactly what A2 adds; producing sprint plans here is out of scope, not bonus credit. |
  | Definition of Done | **Required** | §4.2 restated in `design/prd.md` (or linked), as the checklist the strategy actually ran against. |
  | Retrospective artifacts | **N/A** — no iteration boundary to retrospect on at this rung (A2). |

- **5.3 Interaction / visual design**
  | Activity | Status | What it means here |
  |----------|--------|--------------------|
  | Interface/API contract design | **Required** | §2.1 is pinned; the design work is the *client-side* contract — the typed `src/types/api.ts` and the store's normalized shape — documented in `design/interaction-specs.md`. |
  | CLI UX / output design | **N/A** — no CLI surface. |
  | Wireframes (lo-fi) | **Required** | `design/wireframes/`: layout and hierarchy for every screen in §5.4, before hi-fi. Committed as SVG/PNG/ASCII — any committed, reviewable format. |
  | Hi-fi mockups | **Required** | `design/hifi/`: the visual target the implementation is diffed against (§6.3, AC-23), covering populated **and** empty/loading/error states. |
  | Design tokens / system | **Required** | `design/design-tokens.json` + a consumable `tokens.css`: color (with contrast pairs), spacing scale, type scale, radii, elevation, motion durations. Must be **actually consumed** by the app — a token file the CSS ignores scores zero for this item. |
  | Interaction/state specs | **Required** | `design/interaction-specs.md`: state machines for drag (idle → picked-up → over-target → dropped/cancelled) and for the keyboard equivalent; optimistic-update and rollback sequences; every view's loading/empty/error/populated state; validation and focus behavior. |
  | Accessibility annotations | **Required** | `design/a11y-annotations.md`: the ARIA role/name/state map for board, column, card, and card detail; the keyboard interaction table for FR-26; live-region wording; focus-order diagrams per screen; the contrast-checked token pairs; and any justified `moderate` axe findings. |

- **5.4 Design artifacts to produce** — Concrete files under `design/`. Each is
  checked for existence, internal consistency, and traceability; the visual
  ones are additionally checked against the implementation (design-diff, §6.3).

  | File | Must contain | Scored via |
  |------|--------------|------------|
  | `design/personas.md` | ≥ 3 personas incl. a keyboard/AT persona; goals, frustrations, key tasks, FRs driven. | AC-22, `FID` |
  | `design/research/interviews.md` | Interview script + ≥ 2 sessions + "decisions changed by this findings". Labelled synthesized. | AC-22, `FID` |
  | `design/research/jtbd.md` | ≥ 4 JTBD statements mapped to FRs served and FRs deliberately not built. | AC-22, `FID` |
  | `design/prd.md` | Problem, users, goals/non-goals, success metrics, scope by priority, risks, §1.6 resolutions, Definition of Done. | AC-22, `FID` |
  | `design/user-stories.md` | US-1..US-21+ with per-story acceptance criteria and FR traces. | AC-22, `FID` |
  | `design/backlog.md` | P0/P1 ordered backlog with dependencies and estimates; matches §4.1. | AC-22, `FID` |
  | `design/wireframes/` | `login.*`, `board-list.*`, `board-list-empty.*`, `board-detail.*`, `board-detail-empty.*`, `card-detail.*`, `drag-in-progress.*`. | AC-22, `FID` |
  | `design/hifi/` | The same seven screens at hi-fi, at the ≥ 1024 px reference viewport, plus loading and error states for board detail. | AC-23, `FID` |
  | `design/design-tokens.json` | Color/spacing/type/radius/elevation/motion tokens with names used verbatim in code. | AC-22/23, `FID` |
  | `design/tokens.css` *(or equivalent import consumed by the app)* | The tokens as CSS custom properties, imported by the SPA. | AC-23, `FID`, `QUA` |
  | `design/interaction-specs.md` | Drag and keyboard-move state machines; optimistic/rollback sequences; per-view state matrix; validation and focus rules. | AC-22, `FID` |
  | `design/a11y-annotations.md` | ARIA role/name/state map; FR-26 keyboard table; live-region wording; focus-order diagrams; contrast pairs; justified `moderate` findings. | AC-20/21/22, `FID` |

## 6. Verification Method

Entrypoint kind is **`web-app`**: the harness starts the backend and the SPA,
then verifies through **real HTTP against the real API** and **a real browser
driving the real DOM** (`VERIFICATION_CONTRACT.md` §3). Mock-only or
component-test-only evidence is not accepted as acceptance verification at this
rung, and a solution that passes its own unit tests but fails the browser path
scores `COR` = 0.

- **6.1 Test tiers**

  - **`smoke` (visible — shipped with the SPEC).** Six checks, enough for a
    legitimate feedback loop, deliberately shallow enough not to give away the
    acceptance matrix.
    ```
    S1  GET /api/health -> 200 {"status":"ok"}
    S2  API: register -> login -> GET /api/auth/me returns that user -> logout -> me is 401
    S3  API: POST /api/boards -> the board appears in GET /api/boards
    S4  API: create column, create card -> both appear, correctly nested and ordered,
        in GET /api/boards/{id}
    S5  E2E: log in -> create board -> add column "To Do" -> add card "First card"
        -> the card is visible in that column in the DOM
    S6  E2E: drag "First card" from "To Do" into "Done" -> reload the page
        -> the card is still in "Done"
    ```

  - **`acceptance` (held-out — the authoritative definition of working).**
    Broad coverage of every FR/NFR, organized in the families below. Each family
    contributes assertions to the ≥ 90% overall floor; every assertion tagged
    P0 is in the 100%-required set (§7.3).

    | Family | Coverage | Pri | AC |
    |--------|----------|-----|-----|
    | Auth & session | register (valid, duplicate, invalid email, short password), login (valid, wrong password, unknown user), logout invalidation, `me`, reload persistence, second tab | P0 | AC-1..AC-3 |
    | Auth gating | every mutating endpoint without a session → 401; SPA route guards; no data flash before redirect | P0 | AC-3 |
    | Boards | create/list/rename/delete; cascade to columns and cards; deterministic list order; validation bounds | P0 | AC-4, AC-5 |
    | Columns | create/rename/delete; cascade + confirmation; append-at-end on create | P0 | AC-6 |
    | Column ordering | reorder to first/middle/last; persistence across reload and restart; API order equals DOM order | P0 | AC-7 |
    | Cards | create/edit/delete; detail view open/close/focus-return; description multiline; validation bounds | P0 | AC-8 |
    | Drag within column | move to first, middle, last; adjacent swap; single-card column; DOM/API agreement; reload persistence | P0 | AC-9 |
    | Drag across columns | into empty column, at index 0, at end, into the middle; source gap closes; both orders valid; reload persistence | P0 | AC-10 |
    | `move` API semantics | pinned `target_index` cases from §2.1; clamping; same-position no-op; cross-board rejection without mutation | P0 | AC-11, AC-13, AC-15 |
    | Ordering invariants | INV-1..INV-5 asserted after each of a 40-operation randomized-but-seeded move script | P0 | AC-9..AC-12 |
    | Concurrency | 2 and 8 simultaneous `move` calls (same card; two cards into one column; move + delete race) | P0 | AC-12 |
    | Authorization | user B against A's board/column/card for every verb, incl. moving A's card and moving into A's column; uniform status; no data leakage | P0 | AC-15 |
    | Optimistic UI & rollback | injected 500 / network failure on card create, card move, column reorder, rename → visual rollback + error + post-reload equality | P0 | AC-16 |
    | App states | loading, three empty states, four error classes (401/403-404/422/5xx), offline | P0 | AC-17 |
    | Validation | server-side bounds bypassing the client; whitespace-only titles; explicit-null clears | P0 | AC-18 |
    | Stored XSS | payload set injected in all six text surfaces; assert rendered-as-text, no dialog, no script execution, before and after reload | P0 | AC-19 |
    | Accessibility (automated) | `axe-core` on 5 views; contrast; focus-visible; label associations | P0 | AC-20, AC-21 |
    | Accessibility (keyboard) | the full keyboard-only journey incl. pick-up/move/drop/cancel, live-region text, focus-follow | P0 | AC-14 |
    | Design fidelity | required artifacts present + design-diff of 7 screens/states | P0 | AC-22, AC-23 |
    | Labels & assignee | set/display/clear/persist; non-color distinguishability | P1 | AC-24, AC-25 |
    | Performance | reference-board render, optimistic apply latency, API p95, stress board, query-count check | P1 | AC-26, AC-27 |
    | Quality & ops | static checks, dependency scan, module-boundary review, health/logging, bootstrap from clean checkout, restart persistence | P1 | AC-28..AC-30 |

  - **`adversarial` (hidden — run once, post-hoc; never gates, feeds `COR`/`ROB`).**
    ```
    AUTHZ    IDOR sweep across every nested id (card id belonging to another user
             on an endpoint with no board id in the path); move a card into another
             user's column; forged/tampered session cookie or token; session
             replayed after logout; privilege via client-supplied owner_id/board_id;
             ownership check present on the parent route but missing on the child.
    XSS      <script>, <img src=x onerror>, <svg onload>, javascript: in a URL-ish
             field, an SVG data URI, HTML entities and double-encoded payloads,
             a payload split across title and description, a payload in a label
             and in an assignee name, a payload in a board title reflected into
             the document <title> and into an aria-label.
    CONCUR   Two sessions reordering the same column simultaneously; move a card
             while another session deletes its destination column; delete a board
             mid-drag; two rapid duplicate move requests (double-submit);
             8-way parallel moves into one column.
    DRAG     Drop on a non-target; drop outside the viewport; drop a card on
             itself; drag then Esc mid-gesture; drag with the destination removed
             underneath; a drag interrupted by session expiry; a stale client
             sending target_index far out of range (negative, 10^6).
    VOLUME   200k-character card description; 200-char title at exactly the bound
             and one over; 50 columns on one board; 500 cards in one column;
             1,000 rapid card creates; a board title of emoji, RTL text and
             combining marks; whitespace-only and zero-width-only titles.
    STATE    Backend restart mid-session; empty database on first load; a board
             whose every column is empty; deleting the last column while a card
             detail for one of its cards is open.
    ```

- **6.2 "Working" definition (the hard gate)** — A run is **working** iff:
  **(1) 100% of the P0-tagged acceptance criteria pass**, **and (2) ≥ 90% of all
  acceptance assertions pass**. Both conditions are required. In addition, a
  forbidden-dependency violation (§2.4) or a missing `run.sh`/health-check
  bootstrap fails the gate outright, and a `gaming_event` disqualifies the run
  (`CONVERGENCE_METRICS.md` §6). `adversarial` never counts toward the gate.

- **6.3 Verification mechanics**
  - **Isolation & determinism.** Each phase runs against a throwaway database
    (`DATABASE_URL` pointed at a temp file) and a fresh browser context. Seeded
    accounts come from `seed.py`. Viewport fixed at **1280 × 800**; animations
    suppressed via `prefers-reduced-motion: reduce` for stability; time and ids
    are not asserted on directly. Drag assertions are `flaky-guarded`: up to 3
    attempts, and a single jitter never decides the gate.
  - **API tier.** A real HTTP client against the running server — no test
    client that bypasses the ASGI/WSGI stack, no dependency-override of auth.
    Ordering assertions read back through `GET /api/boards/{id}`; a subset also
    inspects the database directly to prove persistence rather than caching.
  - **Browser tier.** Playwright/Chromium against `url`. Drags are performed as
    **real pointer gestures** (`mouse.move`/`down`/`up` with intermediate steps,
    or the DnD library's real event sequence) — never by calling an exported
    function, dispatching a synthetic app action, or clicking a test-only
    control. The keyboard tier uses `keyboard.press` **only**, with the mouse
    never touched for the entire journey.
  - **The flagship persistence assertion** (shape of AC-9/AC-10):
    ```ts
    // acceptance_e2e/ordering.spec.ts (held out)
    await login(page, 'alice@example.com');
    const board = await api.seedBoard({ columns: ['To Do', 'Doing', 'Done'],
                                        cards: { 'To Do': ['A', 'B', 'C'] } });
    await page.goto(`/boards/${board.id}`);

    await dragCard(page, 'C', { toColumn: 'Doing', toIndex: 0 });  // real pointer
    await expect(cardTitles(page, 'To Do')).toEqual(['A', 'B']);
    await expect(cardTitles(page, 'Doing')).toEqual(['C']);

    await page.reload();                                            // FR-24
    await expect(cardTitles(page, 'To Do')).toEqual(['A', 'B']);
    await expect(cardTitles(page, 'Doing')).toEqual(['C']);

    const server = await api.getBoard(board.id);                    // INV-4
    expect(orderOf(server, 'To Do')).toEqual(['A', 'B']);
    expect(orderOf(server, 'Doing')).toEqual(['C']);
    expectTotalOrder(server);                                       // INV-1
    expectConserved(server, ['A', 'B', 'C']);                       // INV-3
    ```
  - **Accessibility tier.** `@axe-core/playwright` on `/login`, `/boards`
    (empty and populated), `/boards/:id` (empty and populated) and the card
    detail view; the run fails AC-20 on any `serious`/`critical` violation. The
    keyboard journey additionally asserts live-region text content after each
    move and that `document.activeElement` is the moved card in its new
    location.
  - **Fault injection.** Playwright route interception returns 500s/aborts for
    specific endpoints to exercise FR-30 rollback and FR-33 error states; the
    post-rollback state is then verified by reload against the API.
  - **Design-fidelity review (AC-23).** Screenshots of the seven required
    screens/states at 1280 × 800 are placed beside `design/hifi/` and reviewed
    by LLM-judge and/or human against a fixed checklist: layout structure and
    hierarchy; presence and placement of every specified element; token
    adherence (color, spacing, type scale, radii); state coverage
    (empty/loading/error); and card-face density (§1.6g). It is a **fidelity**
    review, not a pixel diff — a different-but-consistent visual direction is
    fine (§1.6h); a UI that ignores its own mockups is not. Each screen is
    scored 0–2 and the aggregate feeds `FID`, with a one-line written
    justification per screen (`RUBRIC_FRAMEWORK.md` §7).
  - **Artifact checklist (AC-22).** Automated existence + structure check over
    §5.4, plus a traceability check that `design/backlog.md` and
    `design/user-stories.md` reference FR/AC ids that exist.

- **6.4 Anti-gaming measures**
  - **Order must be server-persisted, not screen-deep.** Every ordering
    assertion is confirmed through the API (and sometimes the DB) after a
    reload, so `localStorage`, in-memory state, or render-order tricks fail
    even when the screen looks right.
  - **Real gestures only.** Drags are real pointer/keyboard event sequences. A
    test-only escape hatch (a hidden "move card" button, an exported
    `window.__moveCard`, an app action dispatched by the test) does not exist in
    the held-out suite, so wiring one buys nothing; shipping one that *bypasses*
    the real interaction path is a `QUA` deduction and, if it exists only to
    satisfy automation, a `gaming_event`.
  - **Environment sniffing is a gaming event.** Branching on `navigator.webdriver`,
    a Playwright user-agent, `NODE_ENV=test`, or a magic query parameter to
    change behavior disqualifies the run.
  - **Held-out breadth.** The acceptance matrix probes drop positions, empty
    columns, and state combinations that the six smoke checks never show;
    hardcoding the smoke path (a "Done" column that special-cases the first
    card) fails immediately.
  - **Dependency scan.** The forbidden-package scan (§2.4) catches importing
    the product rather than building it, including vendored copies.
  - **Overfitting signal.** A large `acceptance_pass` / `adversarial_pass` gap
    caps `ROB` (`CONVERGENCE_METRICS.md` §6) — the adversarial tier deliberately
    attacks the seams (authz on nested ids, concurrent moves) that a
    test-shaped implementation gets wrong.
  - **Design-artifact authenticity.** Design artifacts are checked for
    consistency with the shipped app and with each other. Artifacts that
    contradict the implementation, or "research" fabricated as field data from
    real named users, cap `FID` at 1.
  - **Workspace escape.** Reading or writing outside `solution/` (plus
    `design/`) to discover held-out tests disqualifies the run.

## 7. Scoring Rubric

- **7.1 Weight profile** (sum 100):
  `COR 22 · ROB 12 · EFF 15 · AUT 15 · QUA 12 · REG 12 · FID 12`.

  Reading of the profile: `COR` drops to 22 — not because correctness matters
  less, but because the **hard gate already enforces it**, and the interesting
  variance at this rung is *how* the strategy got there. `EFF` and `AUT` rise to
  15 each because a four-hour, multi-surface build is where thrash and
  human-rescue actually show up. `FID` rises to 12 because there is now a real
  product/design surface to be faithful to. `REG` enters at 12 as the bridge to
  A2: A1 has no sprints, so regression is measured *within* the run — see §7.2.

- **7.2 Per-axis scoring guide** (scenario-specific anchors)

  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | **COR** | Gate not cleared: a P0 criterion fails, or overall acceptance < 90%. Includes "passes unit tests, fails the browser path". | Gate cleared, but with soft spots — e.g. cross-column drag works only at list ends, `move` clamping mishandled, or several P1 criteria fail. | 100% P0 **and** ≥ 98% overall acceptance, plus ≥ 95% adversarial. `move` semantics exact; ordering invariants hold under every probe. |
  | **ROB** | Order corrupts (duplicate/lost cards) under concurrency or invalid drops; 500s on adversarial input; XSS payload executes. | Survives the obvious cases but fails a seam: a concurrent-move race, an out-of-range `target_index`, a 200k-char description, or an authz hole on one nested endpoint. | No 500s, no order corruption, no data loss under the entire adversarial tier; invalid drops are clean no-ops; every text surface escapes; volume cases degrade gracefully. |
  | **EFF** | Exceeded 80 iterations or the 4 h budget without passing. | Passed near the hard cap, or with heavy `failed_runs_before_pass`, or > 1.5× the token budget — typically from re-architecting ordering or DnD late. | Passed at ≤ 30 iterations, inside time and token budget, ≤ 1 failed acceptance-shaped run; vertical slices land working the first time. |
  | **AUT** | Any `rescue`, or a `hint` that supplied the ordering/DnD/authz approach. | One `clarify` on a §1.6 product ambiguity, or one `unblock` on tooling (Playwright install, port conflict). *A `clarify` on §2's pinned contract is scored as a `hint`.* | Zero interventions; every §1.6 ambiguity resolved unilaterally, documented in `DECISIONS.md`, and applied consistently. |
  | **QUA** | Static checks fail, `strict` disabled, forbidden dependency, `dangerouslySetInnerHTML` on user text, or SQL string interpolation. | Clean checks but blurred boundaries — `fetch` in components, ordering math duplicated across route handlers, `any` at the API boundary, 600-line files, no `DECISIONS.md`. | `ruff`/`pyright`/`tsc --strict`/`eslint` clean; ordering logic has exactly one home; typed API boundary end-to-end; small focused modules; README + DECISIONS accurate. |
  | **REG** | Later features visibly broke earlier ones: drag persistence or authz criteria fail *after* labels/assignee/polish were added; repeated `oscillations` on the same behavior. | 1–2 regressions introduced and fixed, or one earlier-group criterion still failing at declared-done; mid-run snapshots show the app non-bootable for long stretches. | `regressions_introduced` = 0 and `oscillations` = 0; every mid-run snapshot boots and passes the then-complete feature set; earlier P0 groups still green after all P1 work. |
  | **FID** | A required §5.4 artifact is missing, or artifacts were written post-hoc to describe whatever got built, or research is fabricated as real field data. | Artifacts all present but thin or drifting: mockups the UI ignores, a token file the CSS doesn't import, a backlog that doesn't match §4.1, `moderate` axe findings unexplained. | Every artifact present, consistent, and traceable to FR/AC ids; the UI matches the hi-fi across all seven screens/states; tokens genuinely drive the styling; a11y annotations match the shipped ARIA and keyboard behavior; zero serious/critical axe violations. |

  **REG at A1 — how it is measured despite there being no sprints.** Three
  sources: (1) telemetry `regressions_introduced` and `oscillations` across the
  run; (2) **feature-group replay** — acceptance criteria are grouped in the
  §4.1 build order (auth → boards → columns → cards → drag/persistence → authz
  → states → labels/assignee/polish), and any earlier-group P0 criterion failing
  at declared-done is counted as a regression, since the strategy demonstrably
  had it working earlier or never did; (3) **mid-run snapshots** — the harness
  samples the workspace at up to three checkpoints and runs the smoke suite
  against each (§8.3). A strategy that leaves the app unbootable for hours and
  integrates at the end scores `REG` ≤ 2 even if the final state passes.

- **7.3 Hard gate** — **100% of P0 acceptance criteria AND ≥ 90% of all
  acceptance assertions** (`p0_criteria_floor = 1.0`, `acceptance_floor = 0.90`).
  Independently gate-failing conditions: a forbidden dependency (§2.4); a
  solution the harness cannot bootstrap via `run.sh` + `/api/health` inside
  `ready_timeout_s`; and any `gaming_event`, which disqualifies the run and
  zeroes `QUA`/`FID`.

- **7.4 Pass threshold** — **68.** Lower than the algorithmic rungs by design:
  A1 has seven live axes, an irreducibly subjective `FID` component, and enough
  surface that a legitimately good run will have visible rough edges. A run at
  68–84 is a genuine "Converged"; 85+ here (Converged-Clean) means the strategy
  built a whole application, with its product and design surface, essentially
  cleanly in one pass — and is a strong predictor of surviving A2.

## 8. Convergence Signals

- **8.1 Healthy convergence** — The trace shows **product before pixels, and a
  vertical slice before breadth**:
  1. **Discovery first, briefly.** Personas/JTBD/PRD/backlog land early (within
     the first ~15% of wall-clock) and are *referenced later* when scope
     decisions are made — the artifacts are working documents, not a preamble.
  2. **Contract and invariants named early.** The §1.6(a) ordering strategy is
     chosen and written into `DECISIONS.md` *before* the first drag is coded,
     and INV-1..INV-5 appear as explicit checks in the strategy's own tests.
  3. **Thinnest end-to-end slice first.** Auth → one board → one column → one
     card → visible in the browser, wired through the real API and real DB,
     before any styling. The first browser-driven verification happens in the
     first third of the run, not the last.
  4. **Drag built against persistence from the start**, with the keyboard path
     (FR-26) designed at the same time as the pointer path — not retrofitted.
     Strategies that treat a11y as a phase always pay for it twice.
  5. **Design tokens introduced before component styling**, so the hi-fi
     mockups and the CSS share one vocabulary and the design diff is close by
     construction.
  6. **Steady green.** Mid-run snapshots boot and pass the then-complete feature
     set; ≤ 30 iterations; zero interventions; the adversarial gap is small
     because authz and ordering were done centrally rather than per-endpoint.

- **8.2 Pathological patterns**
  - **UI-first, persistence-last.** Building the whole board in local component
    state and "adding the API later." Surfaces as a late cliff: many iterations
    clustered at the end, FR-24 failures, and a rewrite of the store (a
    `dead_end`). The single most common way to fail this rung.
  - **Ordering thrash.** Repeatedly changing the position scheme (dense ints →
    fractional → array-of-ids on the board) after drag is already wired.
    Surfaces as high `oscillations` on AC-9/AC-10 and rising `iterations` with
    flat criteria progress. The §1.6(a) decision is cheap up front and
    expensive at hour three.
  - **Per-endpoint authorization.** Ownership checked on `/boards/{id}` but not
    on `/cards/{id}`, because the check was written route-by-route instead of
    once. Passes every UI-driven test, fails AC-15 and the adversarial IDOR
    sweep. Signature: `acceptance_pass` high, `adversarial_pass` low.
  - **Mock-shaped confidence.** A large component/unit test suite that passes
    while the browser path has never been run. Signature: first E2E execution
    late in the trace, then a burst of failures against the real DOM.
  - **Optimistic UI without rollback** — or a "rollback" implemented as a full
    refetch that hides the bug. Fails AC-16's post-rollback equality check.
  - **The reload dodge.** Forcing a full page reload (or refetching the whole
    board) after every mutation to avoid maintaining client state. Passes
    persistence, fails NFR-1's 100 ms optimistic budget and reads as a product
    failure in the design review.
  - **DnD library churn.** Swapping drag libraries mid-run, usually after
    discovering the first choice has no keyboard sensor. Preventable by
    reading FR-26 before choosing (§2.4 names the preferred option).
  - **Accessibility bolted on last.** `axe` run for the first time after the UI
    is complete, producing dozens of `serious` findings that require structural
    changes. Surfaces as a late spike in iterations and a depressed `FID`.
  - **Post-hoc design artifacts.** `design/` written at the end to describe
    whatever was built. Detectable: mockups that match the implementation
    suspiciously exactly while contradicting the wireframes; a backlog with no
    dependency structure; "interviews" whose findings changed nothing. Caps
    `FID` at 1–2.
  - **Escaping strictness.** Disabling `strict`, sprinkling `@ts-ignore`, or
    silencing `ruff` to make checks pass. `QUA` = 0.
  - **Asking for product decisions.** A `clarify` on §1.6 is scored gently
    (§0) but still costs `AUT`; the rung is partly testing whether a strategy
    can make and document a defensible product call unaided.
  - **Scope creep into A2.** Building live sync, comments, an activity feed, or
    search because they "obviously belong." Costs `FID` (§1.5) and `EFF`, and
    contaminates the A2 comparison.

- **8.3 Instrumentation notes** — Beyond the shared `CONVERGENCE_METRICS.md`
  set, capture into `score.json.notes`:
  1. **`resolution_profile`** — which branch of §1.6(a)–(h) was taken, whether
     each was documented in `DECISIONS.md`, and whether it was applied
     consistently. This makes product judgment comparable across strategies and
     is the input A2 inherits.
  2. **`stack_profile`** — backend framework, ORM/driver, DnD library, state
     store, styling approach, and direct-dependency counts.
  3. **`first_e2e_iteration`** and **`first_persistence_iteration`** — the
     iteration indices at which a browser test and a real DB write first ran.
     Early values are the strongest predictor of a clean A1 (§8.1).
  4. **`build_order`** — the observed order in which the §4.1 feature groups
     reached green, plus the wall-clock at which the discovery artifacts landed.
  5. **Mid-run snapshots** — up to three workspace samples (at ~25%/50%/75% of
     wall-clock) with smoke-suite results for each; feeds `REG` (§7.2).
  6. **`a11y_profile`** — axe violation counts by impact per scanned view, the
     iteration at which axe was first run, and whether the keyboard-move path
     passed on first attempt.
  7. **`design_fidelity_detail`** — per-screen 0–2 scores with the one-line
     justification, plus whether `design-tokens` are actually imported by the
     app's CSS.
  8. **`ordering_stress`** — results of the 40-operation move script and the
     concurrency probes, recorded as invariant-violation counts per invariant.
  9. **Performance samples** — reference-board time-to-interactive, optimistic
     apply latency, API p95 per endpoint, stress-board render time, and the
     `GET /api/boards/{id}` query count.
  10. **`e2e_flake_rate`** — retries consumed by drag assertions, so genuine
      solution instability is distinguishable from harness jitter before it
      influences the gate.
