# L6 — Kanban App — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> discovery/design obligations fixed by the **L6 row** of
> `framework/ARTIFACT_GRADIENT.md`.
>
> **Relationship to L7 — read this first.** L6 and L7 deliberately **share the
> same application** (`VISION.md` §3). L6 is *"build it once, correctly."* L7
> re-delivers the same Kanban app as five scripted sprints so we can measure
> iterative delivery and regression safety on a system the strategy has already
> had to reason about. Concretely: **L7 Sprint 0 ≈ L6's CRUD + persistence**,
> **L7 Sprint 1 ≈ L6's ordering + drag-and-drop**, **L7 Sprint 2 ≈ L6's auth and
> authorization**, and L6 additionally ships the labels/assignee slice that L7
> sequences into its Sprint 3. The **data model, persona archetypes, endpoint
> surface, error envelope, and NFR floors defined here are authoritative for the
> application**; L7 is authoritative for the *delivery process*. Nothing in this
> document may be changed without checking `scenarios/L7-kanban-sprints`.

---

## 0. Scenario Summary

- **Level:** L6
- **Codename / dir:** `L6-kanban-app`
- **One-liner:** A single-team **Kanban board web application** — Python REST API
  plus a React/TypeScript single-page app — with boards, columns and cards,
  drag-and-drop reordering that persists, durable storage, and light session
  authentication with per-user board ownership.
- **New difficulty introduced:** **A real end-user application.** Every rung below
  L6 was verified by calling something: a function, a class, a CLI subprocess, a
  library import, an HTTP socket. L6 is the first rung where the *product itself
  is a human experience*, and four new classes of hardness arrive together:
  1. **A non-trivial data model with business rules** — nested entities,
     cascading deletes, and an **ordering invariant** (a total, dense, gap-free
     order per column) that must hold across concurrent-ish edits, deletes, and
     restarts. Ordering is the rung's signature bug factory.
  2. **An interactive UI** — a real SPA with client state, optimistic updates,
     rollback on failure, and empty/loading/error states, which is a second
     codebase with its own failure modes and its own build.
  3. **End-to-end verification through a real browser** — the acceptance path is
     Playwright driving the real DOM against the real API against real storage.
     Nothing here can be satisfied by a mock.
  4. **A required product and design surface** — personas, JTBD, a PRD, a
     prioritized backlog, lo-fi wireframes → hi-fi mockups, design tokens,
     interaction specs, and **WCAG 2.1 AA accessibility including a
     keyboard-operable alternative to drag-and-drop**. At this rung, "working"
     explicitly includes "meets the product and design intent"
     (`ARTIFACT_GRADIENT.md` §3).
- **Estimated reference solution size:** **1,800–2,800 LoC across 30–45 files**
  (backend `api`/`services`/`repositories`/`migrations`, frontend
  `components`/`state`/`api`), plus **~14 product/design artifact files** under
  `design/`. For calibration against the sibling rung: this is L7's cumulative
  state at its Sprint-2 boundary (~1,900 LoC / 32 files) plus the labels and
  assignee slice.
- **Time budget:** **4 hours** wall-clock.
- **Iteration budget:** **soft 30 / hard 80** edit→verify cycles. The budget is
  generous relative to L5 because two toolchains (Python and Node) each impose
  their own build/verify latency; it is *not* generous enough to permit
  discovering the ordering invariant by trial and error.
- **Intervention budget:** **0.** Note the calibration: the §1.6 ambiguities here
  are genuinely open **product** questions, so a `clarify` intervention against
  one of them is scored at the low end of its severity band rather than as a
  design failure (`CONVERGENCE_METRICS.md` §3). A `clarify` on a *technical*
  matter that this document already fixes — the endpoint table, the error
  envelope, the ordering invariant — carries full severity.

```
Budget summary (mirrored into manifest.yaml §2.5)

Wall-clock      14,400 s
Iterations      soft 30 / hard 80
Token budget    2.5 M
Interventions   0
Gate            100% of P0 acceptance criteria AND >= 90% of all criteria
Pass threshold  68
```

---

## 1. Product Requirements

### 1.1 Problem statement

A single delivery team of six to ten people tracks its work on a whiteboard of
sticky notes, mirrored into a spreadsheet whenever someone remembers. Neither
artifact survives contact with reality. The whiteboard is invisible to the three
people who work remotely, who navigate from a photo taken at some point on
Tuesday. The spreadsheet has no concept of order, so "what's next" is whatever
row happens to be on top after the last sort. Nothing is durable: a wiped board
or a botched paste destroys a week of prioritisation and nobody can reconstruct
it.

They need a **shared, durable, web-based Kanban board**: named columns
representing their workflow, cards representing real work, and — critically —
**hand-ordered cards whose order means something and survives a reload**. The
board must belong to a real account so it is not a public URL anyone can edit,
and it must be operable by every member of the team, including one who works
entirely from the keyboard with a screen reader.

The scope is deliberately one team, one board owner, no collaboration
mechanics. This is the smallest thing that is genuinely a *product* rather than
a service: it has an interface a human forms habits around, and its quality is
judged by whether a human can get their work done in it.

### 1.2 Target users / personas

**Required** at this rung (`ARTIFACT_GRADIENT.md` L6). Personas are not
decoration here — three functional requirements (FR-21 keyboard drag, FR-22
optimistic rollback, FR-23 empty/loading/error states) exist because of a
specific persona's stated need, and the acceptance suite tests them.

The strategy must author these into `design/research/personas.md` with goals,
frustrations, key tasks, and the requirements each one motivates.

---

**Maya Okonjo — Team Lead.** *"I need to see the shape of the work, and change
its order in front of people."*

| Attribute | Detail |
|-----------|--------|
| Context | Runs a six-person delivery team; owns the board; drives a 15-minute standup daily with the board projected on a screen. |
| Goals | Represent the team's actual workflow as columns. Re-prioritise **live, during the meeting**, without a save button or a page reload. See the whole board at a glance without scrolling hunting. Trust that what she left on Friday is what she finds on Monday. |
| Frustrations | Spreadsheets that lose order the moment someone sorts a column. Tools that need three clicks and a modal to move one card. Losing structure because someone deleted a column and took its cards with it silently. Being unable to tell whether a change was actually saved. |
| Key tasks | Create a board; create/rename/reorder columns; create cards; **drag cards up and down a column and across columns while people watch**; delete stale cards; attach a label to make a category visible without opening cards. |
| Motivates | FR-1..FR-5 (board/column structure), FR-8..FR-12 (ordering and drag), FR-13..FR-15 (labels/assignee), FR-22 (optimistic UI — the drag must feel instant *in front of an audience*), NFR-1 (latency). |
| Anti-goal | Does **not** want configuration, permissions, workflow automation, or WIP limits. She wants the whiteboard, but durable. |

---

**Sam Whitfield — Contributor (keyboard-only, screen-reader user).** *"If I can't
move a card without a mouse, this tool doesn't work for me at all."*

| Attribute | Detail |
|-----------|--------|
| Context | An engineer on Maya's team. Works entirely from the keyboard with a screen reader; a mouse is not part of Sam's workflow. Touches the board several times a day, in short bursts. |
| Goals | Find their own cards quickly. Edit a card title without a modal ceremony. **Move a card to another column when the work advances — by keyboard**. Know, unambiguously, whether an action succeeded. |
| Frustrations | Drag-and-drop implemented as a mouse-only affordance, which silently makes a core feature unavailable. Focus rings removed "for aesthetics". Card containers that break tab order so the board becomes an unnavigable soup of divs. Status changes that happen visually with no announcement, leaving Sam unsure whether the move landed. |
| Key tasks | Tab to a card; open and edit it; **grab it, move it, drop it — all by keyboard**; delete it; confirm the result was announced. |
| Motivates | FR-21 (keyboard-operable DnD equivalent — **P0, not a polish item**), FR-23 (states must be perceivable, not just visible), NFR-4 (WCAG 2.1 AA in full), and the §5.3 requirement that the interaction spec carry a documented key map and announcement copy. |
| Anti-goal | Does **not** want a separate "accessible mode" or a stripped-down alternate UI. One UI, operable by everyone. |

---

**Carried forward for L7 continuity** (secondary at L6; their jobs are served by
features this rung either ships or explicitly defers):

| Persona | Role | Primary job | Status at L6 |
|---------|------|-------------|--------------|
| **Marco Silva** | IC engineer | Move a card to Done without ceremony; not lose work | Served by the same surfaces as Sam, without the keyboard constraint |
| **Jules Okafor** | Cross-functional stakeholder, reads rarely writes | Check status without interrupting anyone; watch it update live | **Partially deferred** — read access works; live update is L7 Sprint 4 (§1.5) |

> **Consistency note (honest, not silent).** L7 carries this roster forward and
> records its delivery-lead persona as **Priya Raman**. Maya Okonjo and Priya
> Raman are the *same archetype* — board owner, runs standup, reorders live. The
> **archetype is the load-bearing thing, not the name**; a strategy running both
> rungs should pick one name and use it consistently, and a scorer must not treat
> the rename as persona drift. Sam Whitfield is the same person in both
> documents; L7 lists Sam's role as "any of the above" because Sam's constraint
> is orthogonal to job title.

### 1.3 User stories

**Required** (`ARTIFACT_GRADIENT.md` L6). Every story traces to at least one
`FR-n` and one `AC-n`. Priority (`P0`/`P1`) is defined in §4.3 and is what the
hard gate keys on.

**Boards**
- **US-1** As *Maya*, I want to create a named board, so that my team's work has a
  home. `P0`
- **US-2** As *Maya*, I want to see a list of my boards and open one, so that I
  can get to work in one click. `P0`
- **US-3** As *Maya*, I want to rename a board, so that it keeps matching what the
  team actually does. `P0`
- **US-4** As *Maya*, I want to delete a board I no longer need, and understand
  that its columns and cards go with it, so that stale boards don't accumulate. `P0`

**Columns**
- **US-5** As *Maya*, I want to add named columns to a board, so that the board
  represents our real workflow stages. `P0`
- **US-6** As *Maya*, I want to rename and delete columns, so that the workflow can
  change without rebuilding the board. `P0`
- **US-7** As *Maya*, I want to reorder columns, so that the board reads
  left-to-right in the order work actually flows. `P1`

**Cards**
- **US-8** As *Sam*, I want to create a card with a title and an optional longer
  description, so that a piece of work is captured with enough context to act on. `P0`
- **US-9** As *Sam*, I want to edit a card's title and description in place, so
  that keeping it accurate is cheap. `P0`
- **US-10** As *Sam*, I want to delete a card, so that finished or abandoned work
  leaves the board. `P0`
- **US-11** As *Maya*, I want to attach colored labels to a card, so that
  categories are visible without opening every card. `P1`
- **US-12** As *Maya*, I want to assign a card to a named team member, so that
  ownership is explicit on the board face. `P1`

**Ordering and drag-and-drop**
- **US-13** As *Maya*, I want to drag a card to a different position within its
  column, so that priority order is visible to everyone in the room. `P0`
- **US-14** As *Maya*, I want to drag a card into a different column, so that I can
  advance work during standup. `P0`
- **US-15** As *Maya*, I want my ordering to be exactly the same after a reload —
  and after the server restarts — so that I never redo it. `P0`
- **US-16** As *Sam*, I want a keyboard equivalent for grabbing, moving and
  dropping a card, so that reordering is not a mouse-only feature. `P0`
- **US-17** As *Maya*, I want a drag to feel instant and, if the server rejects it,
  to visibly snap back with an explanation, so that I never believe a change
  landed when it didn't. `P0`

**Accounts and ownership**
- **US-18** As *Maya*, I want to register an account and log in, so that my boards
  are mine and not a public URL. `P0`
- **US-19** As *Maya*, I want other accounts to be unable to see or change my
  boards, so that I can use this for real work. `P0`
- **US-20** As *Sam*, I want to log out on a shared machine and know the session is
  actually dead, so that nobody inherits my access. `P0`

**Everyday reliability**
- **US-21** As *Sam*, I want every screen to tell me clearly when it is loading,
  when it is empty, and when something failed, so that I am never staring at a
  blank rectangle guessing. `P0`
- **US-22** As *Maya*, I want bad input to be rejected with a message naming the
  problem, so that I can fix it rather than lose my work. `P0`

### 1.4 Functional requirements

Numbered `FR-n`, testable, with priority. `P0` requirements are the hard gate
(§7.3); `P1` requirements count toward the ≥ 90% overall floor.

#### A. Boards

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-1** | Create a board with a `name`: non-empty after trimming, ≤ 120 characters. Returns **201** with the created board. | P0 |
| **FR-2** | List the authenticated user's boards (`GET /api/boards`) as board summaries. The list contains **only** boards owned by that user. | P0 |
| **FR-3** | Read one board (`GET /api/boards/{id}`) returning the **full nested board — columns, each with its cards — in a single round trip**, in a stable documented order (columns by `position`, cards by `position`). No `N+1` query pattern (NFR-1). | P0 |
| **FR-4** | Rename (`PATCH`) and delete (`DELETE` → **204**) a board. Deleting a board cascades its columns, cards, labels and roster entries. | P0 |

#### B. Columns

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-5** | Create, rename, and delete columns within a board. `name` non-empty after trimming, ≤ 60 characters. **Deleting a column cascades its cards** — no orphan rows, and the board read must not crash afterwards. | P0 |
| **FR-6** | Columns carry a persisted `position` within their board; the board read (FR-3) returns them in that order deterministically. | P0 |
| **FR-7** | A column can be **reordered** within its board to any valid target index via `PATCH /api/columns/{id}/move`, and the new order persists. | P1 |

#### C. Cards

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-8** | Create, read, update and delete cards within a column. `title` non-empty after trimming, ≤ 200 characters; `description` optional, ≤ 4,000 characters, may contain newlines. | P0 |
| **FR-9** | Cards carry a persisted `position` **within their column**; FR-3 returns them in position order deterministically, with no reliance on insertion order or `id` ordering. | P0 |

#### D. Ordering and drag-and-drop — *the signature requirement of this rung*

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-10** | A card can be **reordered within its column** to any target index `0..n-1` via `PATCH /api/cards/{id}/move`. | P0 |
| **FR-11** | A card can be **moved across columns** to any target index `0..m` in the destination column, in the same single operation. Both the source and destination columns end in a valid order. | P0 |
| **FR-12** | **Canonical dense ordering invariant.** After *any* mutation — create, move, delete — every column's cards occupy exactly the positions `0..n-1`: **no gaps, no duplicates, no negatives**, and the same is true of a board's columns. Deleting a card from the middle renormalizes the survivors. The server, not the client, owns this invariant, and the move response returns authoritative state so the client can reconcile. | P0 |
| **FR-13** | **Ordering is durable.** The order survives a browser reload *and* a full server process restart against the same database. Nothing about ordering may live only in process memory or client state. | P0 |
| **FR-14** | The SPA supports **drag-and-drop** of a card within a column and between columns, using real pointer interaction with a visible drop affordance, and the resulting order is persisted via FR-10/FR-11. | P0 |
| **FR-15** | **Keyboard-operable equivalent.** Every move achievable by dragging is achievable by keyboard alone — a documented grab / move / drop mapping — and produces **byte-identical server state** to the mouse path. This is a `P0` requirement, not an accessibility afterthought. | P0 |
| **FR-16** | **Idempotent moves.** Repeating an identical move produces no drift: no reordering churn, no duplicate positions, no extra writes that change observable order. | P0 |

#### E. Labels and assignee

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-17** | A board owns a set of **labels** (`name` ≤ 40 chars, `color` as a `#rrggbb` hex triplet). Label CRUD is board-scoped. | P1 |
| **FR-18** | A card may carry **zero or more labels**, many-to-many and **board-scoped**: attaching a label belonging to a different board is rejected. Deleting a label removes it from its cards **without deleting the cards**. | P1 |
| **FR-19** | A board owns a **member roster** (`name` ≤ 80 chars, optional `email`). A card may have zero or one `assignee` drawn from that roster; assigning an off-roster member is rejected. **Roster entries are board-scoped data, not user accounts, and grant no access whatsoever** — FR-22's authorization invariant is untouched by this feature. | P1 |

#### F. Authentication and authorization

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-20** | **Register.** `POST /api/auth/register` with `{email, password}` creates an account. Email is unique and compared case-insensitively; password minimum 8 characters; the password is stored **only** as a salted hash from a slow KDF (NFR-3). | P0 |
| **FR-21** | **Login / logout.** `POST /api/auth/login` establishes a **server-side session** delivered as an `HttpOnly; SameSite=Lax` cookie. `POST /api/auth/logout` **invalidates the session server-side** — replaying the old cookie afterwards fails. `GET /api/auth/me` returns the current user or **401**. | P0 |
| **FR-22** | **Ownership and the authorization invariant.** Every board is owned by exactly one user. A request from user *B* touching a board owned by user *A* — read, write, move, delete, on the board **or any of its columns, cards, labels or roster entries, addressed by their own nested IDs** — is denied. The denial code is chosen per §1.6 A-2 and applied everywhere. | P0 |
| **FR-23** | **Auth is required for mutations and reads of app data.** Every board/column/card/label/member endpoint requires an authenticated session; unauthenticated requests receive **401**, never 200 and never 5xx. `GET /api/health` is the only unauthenticated endpoint. | P0 |
| **FR-24** | The SPA provides register, login and logout screens, an authenticated shell, and a **session-expired flow** that returns the user to login with an explanation rather than a blank screen or a silent failure. | P0 |

#### G. SPA behaviour and UX

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-25** | The SPA renders a board and supports **all** board/column/card CRUD from the UI. No capability may be API-only. | P0 |
| **FR-26** | **Optimistic UI with rollback.** A move (and, at the strategy's option, other mutations) may apply optimistically for perceived instantness, but a server rejection or failure **must visibly reconcile**: the card returns to its true position and an error is surfaced to the user. A permanent optimistic lie — UI showing state the server never accepted — is a failure. | P0 |
| **FR-27** | **Empty, loading and error states for every view**: board list, board detail, column, card list, card editor, and the auth screens. Each state is distinguishable: an empty board must not be visually identical to a failed load. | P0 |
| **FR-28** | Validation failures return **400** with the structured error envelope (§2.1); unknown IDs return **404**. **No 5xx on any user-supplied input.** Errors surfaced in the UI name the offending field. | P0 |

#### H. Platform

| ID | Requirement | Pri |
|----|-------------|-----|
| **FR-29** | **Durable persistence.** All state is persisted in a real datastore. A full process stop and restart against the same database loses nothing: boards, columns, cards, positions, labels, roster, users and unexpired sessions all survive. | P0 |
| **FR-30** | `GET /api/health` returns **200** with `{status, version, schema_version}`, requires no auth, succeeds on a brand-new empty database, and **actually touches the datastore**. | P0 |
| **FR-31** | Schema is created/upgraded by a **single documented command** (`migrate_cmd`, §2.5) and never implicitly at import time in a way that could drop or recreate populated tables. | P0 |

### 1.5 Out of scope

Explicit non-goals. Building these is scope creep and is penalised under `FID`
(you shipped something nobody asked for instead of something they did) and
`EFF` (you spent budget on it). Most are **deliberately deferred to L7's
sprints 3–4**, where they exist precisely to create regression pressure against
the L6 baseline:

| Non-goal | Why / where it lives |
|----------|----------------------|
| **Real-time multi-user sync** (WebSocket/SSE, live cursors, presence) | **L7 Sprint 4.** At L6 the board updates on the acting client only; another tab sees changes after a reload. |
| **Comments / discussion on cards** | Out of the product entirely. |
| **Activity feed / audit log** | **L7 Sprint 4.** |
| **Search and filtering** of cards by text, label or assignee | **L7 Sprint 3.** L6 ships labels and assignee as *data and display*; it does **not** ship the filter bar or `?q=` search. |
| Board sharing between accounts, roles, permission matrices | Ownership is single-owner. Roster entries are labels-for-humans, not accounts. |
| Attachments, checklists, due dates, swimlanes, WIP limits, card archive, undo/redo | Out of the product. |
| Email, notifications, invitations, password reset, OAuth/SSO, MFA | Out; auth here is deliberately "light session auth". |
| Offline mode, native mobile apps, i18n/l10n, theming beyond the design tokens | Out. |
| Multi-team / organisation / workspace hierarchy; horizontal scale-out; cache tier | Out. |
| Collaborative rich-text editing of card bodies | Out. Descriptions are plain text. |

### 1.6 Ambiguities the agent must resolve

Deliberate under-specification. Each has more than one defensible answer. The
acceptance suite does **not** pin a particular answer — it pins **consistency
with the answer the solution documents**, so an undocumented choice fails even
when the behaviour is sane. Every resolution must appear in
`solution/README.md` **and** in the corresponding `design/` artifact.

These are genuinely open **product** questions, which is why a `clarify`
intervention against them is scored at the low end of its band (§0). They are
still expected to be resolved unilaterally and in writing.

| # | Ambiguity | Acceptable resolutions | What acceptance actually asserts |
|---|-----------|------------------------|----------------------------------|
| **A-1** | **Position encoding.** How is order represented in storage? | (a) **Dense integers** with server-side renormalization on every write. (b) **Fractional / gapped keys** (e.g. `LexoRank`-style or float midpoints) with periodic compaction. Either must be documented in `design/data-model.md` with its trade-off stated. | `GET` returns a **total order** that is stable, **gap-free and duplicate-free after settle** (FR-12), and **idempotent under repeated identical moves** (FR-16). Under (b), the compaction trigger must be documented and the invariant must still hold after 200 sequential moves in one column. |
| **A-2** | **Denial code for cross-user access.** | **404** (leaks no existence) **or** **403**. Pick one, apply it **everywhere**, document it. | If **404** is chosen, the response for "board owned by someone else" must be **byte-identical** to "board that does not exist" — same status, same body, no timing tell. Either way: never **200**, never a body containing another user's data, never **500**. |
| **A-3** | **Optimistic vs pessimistic drag UI.** | Either. Optimistic-with-rollback, or await-the-server-then-render. | Server state is authoritative; a rejected move is **visibly reconciled** (FR-26); and the chosen approach meets the NFR-1 perceived-latency budget. A strategy that picks pessimistic must still feel instant or it fails NFR-1, not FR-26. |
| **A-4** | **Session lifetime and storage.** | Any documented lifetime **≥ 30 minutes**. Server-side session table, or a signed token with a server-side revocation list — but **logout must invalidate server-side either way**. | Logout invalidates immediately regardless of the choice; a replayed cookie yields 401. Expiry behaves as documented. A stateless JWT with no revocation path **fails FR-21** — this is a constraint, not an ambiguity. |
| **A-5** | **Card editor surface.** Modal dialog, side panel, or inline expansion? | Any of the three, provided it is designed in `design/wireframes/` and `design/hifi/` first and the implementation matches. | Whatever is chosen: focus is moved into it on open and **restored to the invoking card on close**, `Escape` dismisses without losing unsaved text silently, and it is announced to assistive technology. The a11y contract is fixed; the surface is not. |
| **A-6** | **Board deletion confirmation.** Is destructive deletion confirmed, and how? | Confirm dialog, type-to-confirm, or undo-window. Or no confirmation, *if documented as a deliberate choice*. | Whichever is documented is what the E2E test drives. Silent unconfirmed cascade delete is *permitted* but must be stated in the PRD as an accepted risk — an undocumented one is a `FID` finding. |
| **A-7** | **Empty-board bootstrap.** Does a new board start with default columns (e.g. To Do / Doing / Done) or genuinely empty? | Either. Seeded defaults are a real product decision with a real trade-off. | The empty state (FR-27) must be correct for whichever is chosen: if seeded, the *column* empty state is what's tested; if not, the *board* empty state must offer a clear first action, not a blank rectangle. |

---

## 2. Technical Requirements

### 2.1 Interface / API contract

**This surface is authoritative for both L6 and L7.** L7 introduces exactly
these endpoints across its sprints; L6 ships all of them at once.

```
# ---- Auth -------------------------------------------------------------
POST   /api/auth/register              {email, password}          -> User (201) + Set-Cookie
POST   /api/auth/login                 {email, password}          -> User (200) + Set-Cookie
POST   /api/auth/logout                                           -> 204  # server-side invalidation
GET    /api/auth/me                                               -> User | 401

# ---- Boards -----------------------------------------------------------
GET    /api/boards                                                -> [BoardSummary]
POST   /api/boards                     {name}                     -> Board (201)
GET    /api/boards/{board_id}                                     -> BoardDetail  # nested columns -> cards
PATCH  /api/boards/{board_id}          {name?}                    -> Board
DELETE /api/boards/{board_id}                                     -> 204  # cascades everything below

# ---- Columns ----------------------------------------------------------
POST   /api/boards/{board_id}/columns  {name}                     -> Column (201)
PATCH  /api/columns/{column_id}        {name?}                    -> Column
DELETE /api/columns/{column_id}                                   -> 204  # cascades its cards
PATCH  /api/columns/{column_id}/move   {position}                 -> BoardDetail

# ---- Cards ------------------------------------------------------------
POST   /api/columns/{column_id}/cards  {title, description?}      -> Card (201)
GET    /api/cards/{card_id}                                       -> Card
PATCH  /api/cards/{card_id}            {title?, description?,
                                        assignee_id?}             -> Card
DELETE /api/cards/{card_id}                                       -> 204  # renormalizes survivors
PATCH  /api/cards/{card_id}/move       {column_id, position}      -> BoardDetail

# ---- Labels (P1) ------------------------------------------------------
GET    /api/boards/{board_id}/labels                              -> [Label]
POST   /api/boards/{board_id}/labels   {name, color}              -> Label (201)
PATCH  /api/labels/{label_id}          {name?, color?}            -> Label
DELETE /api/labels/{label_id}                                     -> 204
PUT    /api/cards/{card_id}/labels     {label_ids: [...]}         -> Card   # full replace

# ---- Board member roster (P1) -----------------------------------------
GET    /api/boards/{board_id}/members                             -> [Member]
POST   /api/boards/{board_id}/members  {name, email?}             -> Member (201)
DELETE /api/members/{member_id}                                   -> 204   # assigned cards -> unassigned

# ---- Platform ---------------------------------------------------------
GET    /api/health                     -> {status, version, schema_version}   # no auth
```

**Move semantics — the contract that FR-10..FR-12 hang on:**

- `position` in a move request is a **0-based target index in the destination
  list**, *not* an opaque sort key and *not* a swap partner.
- The server is responsible for producing the **canonical dense order** (FR-12).
  The client sends intent; the server returns truth.
- Both move endpoints return the **affected `BoardDetail`** so the client can
  reconcile authoritatively rather than guessing (this is what makes FR-26's
  rollback implementable without a refetch).
- Out-of-range indices are **clamped** to `[0, n]` for a cross-column move and
  `[0, n-1]` for a within-column move, and clamping is **not** an error. A
  nonexistent `column_id` or `card_id` **is** an error (404).

**Representative exchanges:**

```http
POST /api/boards/b_01H8.../columns HTTP/1.1
Content-Type: application/json
Cookie: session=...

{"name": "In Progress"}

HTTP/1.1 201 Created
Content-Type: application/json

{"id": "col_01H8...", "board_id": "b_01H8...", "name": "In Progress",
 "position": 1, "created_at": "2026-08-24T10:14:02Z"}
```

```http
PATCH /api/cards/c_01H8.../move HTTP/1.1
Content-Type: application/json
Cookie: session=...

{"column_id": "col_01H8DONE...", "position": 0}

HTTP/1.1 200 OK
Content-Type: application/json

{"id": "b_01H8...", "name": "Q3 Delivery",
 "columns": [
   {"id": "col_01H8TODO...", "name": "To Do", "position": 0,
    "cards": [{"id": "c_...", "title": "Spike auth", "position": 0, ...}]},
   {"id": "col_01H8DONE...", "name": "Done", "position": 2,
    "cards": [{"id": "c_01H8...", "title": "Fix ordering", "position": 0, ...},
              {"id": "c_...",     "title": "Ship it",      "position": 1, ...}]}
 ]}
```

**Response field contract (schema-validated by acceptance):**

| Entity | Field | Type | Constraint |
|--------|-------|------|------------|
| `Board` | `id` | string | opaque, stable for the entity's life |
| | `name` | string | 1–120 chars, trimmed |
| | `created_at` / `updated_at` | string | ISO-8601 UTC, parseable by `datetime.fromisoformat` |
| `BoardSummary` | | | `Board` fields; may add counts. **Must not** embed columns/cards |
| `BoardDetail` | `columns` | array | ordered by `position` ascending, dense from 0 |
| `Column` | `name` | string | 1–60 chars, trimmed |
| | `position` | integer | `≥ 0`, dense within its board |
| | `cards` | array | ordered by `position` ascending, dense from 0 |
| `Card` | `title` | string | 1–200 chars, trimmed |
| | `description` | string \| null | ≤ 4,000 chars |
| | `column_id` | string | FK; changes on a cross-column move |
| | `position` | integer | `≥ 0`, dense within its column |
| | `labels` | array | `[Label]`, possibly empty |
| | `assignee_id` | string \| null | FK to `board_member` on the same board |
| `Label` | `color` | string | matches `^#[0-9a-fA-F]{6}$` |
| `User` | `email` | string | **never** returns `password_hash` or any password material |

**Error envelope** — one shape, everywhere, forever. L7 freezes this at its
Sprint 0 and treats any later change to it as a regression, so it is fixed here:

```json
{
  "error": {
    "code": "validation_error",
    "message": "title must be 1-200 characters",
    "field": "title"
  }
}
```

`code` is a stable machine-readable string; `message` is human-readable and must
not contain a stack trace, a SQL fragment, or a file path; `field` is present
for validation errors and omitted otherwise.

**Status matrix:**

| Status | Condition |
|--------|-----------|
| **200 / 201 / 204** | Success per the endpoint table |
| **400** | Validation failure: missing/empty/oversized field, malformed JSON, bad `color`, label or assignee from another board, non-integer `position` |
| **401** | No session, expired session, or a session invalidated by logout, on any non-health endpoint |
| **403 / 404** | Cross-user access, per the §1.6 A-2 choice — applied uniformly |
| **404** | Unknown `board_id` / `column_id` / `card_id` / `label_id` / `member_id` |
| **405** | Known path, unsupported method |
| **409** | Duplicate registration email (or **400** — document which; be consistent) |
| **5xx** | **Never** on user-supplied input. A 5xx anywhere in the acceptance run is a `ROB` finding even if the assertion it hit passed. |

### 2.2 Architecture constraints

- **Backend layering, enforced:** `api/` (HTTP, routing, serialization) →
  `services/` (business rules: ordering, cascade, authorization) →
  `repositories/` (persistence). HTTP request/response objects must not reach the
  repository layer; SQL must not reach the API layer. Ordering logic lives in
  **exactly one place** — a second implementation of "renormalize positions" is
  an automatic `QUA` finding and the root cause of most L7 Sprint-3 regressions.
- **One authorization choke point.** Ownership checks live in a single enforced
  seam (a dependency/middleware plus a service-level guard), **not** copy-pasted
  per endpoint. Every nested entity (column, card, label, member) resolves to its
  owning board through that seam. This is a hard architectural requirement, not
  a style preference: FR-22 is verified by an exhaustive endpoint × cross-user
  sweep, and copy-paste authorization reliably misses one.
- **All SQL parameterized.** String-interpolated SQL is an automatic `QUA` 0 and
  a security finding even if no test exploits it.
- **Frontend:** component-based; a **typed API client** generated from or
  hand-written against §2.1 with no `any` at the boundary; board state held in a
  **store** (see §2.4) rather than scattered across component local state — this
  is what makes optimistic rollback (FR-26) implementable and is what L7's
  Sprint 4 depends on.
- **Schema changes are numbered, forward migrations** applied by `migrate_cmd`.
  No implicit `create_all()` drift, and **no destructive recreate of a populated
  table**. L6 ships a single `0001_init`; the discipline exists because L7 adds
  four more migrations on top of this schema.
- **Forbidden:** committing a database file as the source of truth; committed
  secrets; runtime calls to external network services; a frontend that talks to
  the database directly; disabling or skipping tests to make a suite green.

### 2.3 Data model

Entities, fields, and their L7 sprint of origin (shown so the two rungs stay
verifiably aligned). IDs are opaque strings; all timestamps are UTC ISO-8601.

| Entity | Fields | L7 origin |
|--------|--------|-----------|
| `user` | `id`, `email` (unique, case-insensitive), `password_hash`, `display_name`, `created_at` | S2 |
| `session` | `token` (unique), `user_id→user`, `created_at`, `expires_at`, `revoked_at` | S2 |
| `board` | `id`, `owner_id→user` (NOT NULL), `name`, `created_at`, `updated_at` | S0 + S2 |
| `column` | `id`, `board_id→board`, `name`, `position`, `created_at` | S0 + S1 |
| `card` | `id`, `column_id→column`, `title`, `description`, `position`, `assignee_id→board_member` (nullable), `created_at`, `updated_at` | S0 + S1 + S3 |
| `label` | `id`, `board_id→board`, `name`, `color` | S3 |
| `card_label` | `card_id→card`, `label_id→label` (composite PK) | S3 |
| `board_member` | `id`, `board_id→board`, `name`, `email?` — *roster entry, **not** an account* | S3 |

```
user 1───* board 1───* column 1───* card *───* label
                │                    │
                ├───* label          └───? board_member  (assignee, 0..1)
                └───* board_member

Cascade and integrity rules (all enforced server-side, all tested):

  delete user          -> cascade boards (and everything under them), sessions
  delete board         -> cascade columns, cards, labels, card_label, members
  delete column        -> cascade its cards                       (FR-5)
  delete card          -> RENORMALIZE surviving positions 0..n-1  (FR-12)
  delete column        -> RENORMALIZE surviving column positions  (FR-12)
  delete label         -> remove card_label rows; CARDS SURVIVE   (FR-18)
  delete member        -> assigned cards fall back to NULL; CARDS SURVIVE (FR-19)
  card.assignee_id     -> MUST reference a board_member of the SAME board
  card_label.label_id  -> MUST reference a label of the card's OWN board
```

**Ordering strategy — document the choice** in `design/data-model.md`
(this is §1.6 A-1):

| Strategy | Mechanics | Trade-off to state |
|----------|-----------|--------------------|
| **Dense integer `position`** | On every move, recompute `0..n-1` for the affected column(s) inside one transaction. | Simple, trivially verifiable, always dense. Costs `O(n)` writes per move and needs a real transaction so a partial renormalize can never be observed. |
| **Fractional / gapped keys** | Store a sortable key (float midpoint or lexicographic rank); a move writes **one** row; compact periodically. | `O(1)` writes and no contention on neighbours, but requires a documented compaction trigger, precision-exhaustion handling, and an explicit answer for what "dense" means at read time. FR-12's invariant is asserted **after settle**, so this is a legitimate choice — but the compaction path is what acceptance's 200-move probe attacks. |

Whichever is chosen, the **move must be atomic**: a failed move leaves ordering
exactly as it was, with no half-applied renormalization (NFR-2).

**Indexes required by NFR-1:** `card(column_id, position)`,
`column(board_id, position)`, `board(owner_id)`, `session(token)`,
`user(lower(email))` unique, `card_label(label_id)`, `card(assignee_id)`.

### 2.4 Technology constraints

| Layer | Constraint |
|-------|-----------|
| **Backend** | Python ≥ 3.11. **FastAPI** or **Flask** (declare which, and its server: `uvicorn` / `waitress`). Pydantic or an equivalent for request/response validation. |
| **Persistence** | **SQLite** locally; the harness may run either SQLite or **Postgres** via a single connection-string env var. No feature that works on only one of the two. SQLAlchemy or the stdlib driver — an ORM is permitted, not rewarded. |
| **Migrations** | Alembic, or hand-authored numbered SQL applied by a committed runner. Either is fine; *versioned and forward-only* is not optional. `schema_version` is reported by `/api/health`. |
| **Password hashing** | bcrypt / argon2 / scrypt via a maintained library. **Hand-rolled hashing, unsalted hashing, or a fast digest (`md5`, `sha256` bare) is an automatic FR-20 failure**, not a style note. |
| **Frontend** | **TypeScript + React 18+**, built with **Vite**. `strict: true`. No `any` at the API boundary. |
| **Client state** | A store — **Zustand** is the reference choice; Redux Toolkit, Jotai, or a hand-rolled context+reducer are acceptable. Board state must not live only in component local state (§2.2). |
| **Drag & drop** | Any library (`dnd-kit`, `react-dnd`, …) or hand-rolled — **but FR-15's keyboard path must exist regardless**. A library that cannot be made keyboard-operable is the wrong choice, and choosing it is not an excuse. |
| **Styling** | Any approach (CSS modules, Tailwind, vanilla-extract, plain CSS) **provided the design tokens in `design/tokens/` are the single source of colour, spacing, type scale and focus-ring values**, and the shipped UI demonstrably uses them. |
| **Testing (the strategy's own)** | `pytest` for the API, Playwright for E2E, `axe-core` for a11y. These live in the strategy's workspace; the graded suites do not. |
| **Dependencies** | Pinned: `solution/backend/requirements.txt` and a committed `package-lock.json`/`pnpm-lock.yaml`. Installable offline from the harness cache. Undeclared dependencies do not exist at run time. |
| **Forbidden** | Reading/writing outside the declared workspace; runtime calls to external services; committed secrets; a committed database file as the source of truth; a committed `node_modules`. |

### 2.5 Entrypoint contract

`kind: web-app`. The harness owns process lifecycle and browser control; the
solution owns being **startable, migratable, resettable, pollable and
killable** — from a clean checkout, with one command each.

```yaml
# scenarios/L6-kanban-app/manifest.yaml   (authored in the harness pass)
level: 6
language: python+typescript
workspace: solution/
entrypoint:
  kind: web-app
  start_cmd: "make run"                 # backend + BUILT SPA, single command, single port
  url: "http://localhost:${PORT}"
  health_path: "/api/health"            # {status, version, schema_version}
  ready_timeout_s: 60
  e2e_runner: "npx playwright test"
  migrate_cmd: "make migrate"           # applies forward migrations; idempotent to re-run
  reset_cmd: "make reset-db"            # drops + re-migrates a THROWAWAY db only
build:
  setup:
    - "pip install -r solution/backend/requirements.txt"
    - "npm ci --prefix solution/frontend && npm run build --prefix solution/frontend"
env:
  PORT:              # harness-assigned free port; bind exactly this
  KANBAN_DB_URL:     # sqlite:///abs/path.db  OR  postgresql://...  (may not exist yet)
  KANBAN_SECRET:     # session signing secret; MUST be read from env, never hardcoded
verify:
  smoke:       "pytest tests/smoke -q"
  acceptance:  "pytest tests/acceptance -q --json-report"
  e2e:         "npx playwright test tests/e2e --reporter=json"
  adversarial: "pytest tests/adversarial -q --json-report"
budgets:
  wall_clock_s: 14400
  iterations_soft: 30
  iterations_hard: 80
  interventions: 0
gate:
  p0_floor: 1.0        # 100% of P0 acceptance criteria
  overall_floor: 0.90  # >= 90% of all acceptance criteria
```

Contract details that are load-bearing:

- **One command, one URL.** `make run` must serve the built SPA and the API such
  that a browser at `url` gets a working application. A dev server that requires
  a second terminal, or a frontend on a different origin without a working proxy,
  fails the entrypoint contract — and the harness cannot score what it cannot
  start.
- **The SPA must be served *built*** (production build), not via a hot-reload dev
  server. Perf assertions (NFR-1) and axe scans run against what a user would get.
- Startup must complete and `/api/health` must return 200 within
  `ready_timeout_s`.
- The process must exit cleanly on `SIGTERM` within 10 s, committing all accepted
  writes. The restart-persistence test (FR-13, FR-29) depends on this.
- **`start_cmd` must never wipe or recreate a populated `KANBAN_DB_URL`.** Only
  `reset_cmd` may destroy data. Wiping at boot passes every single-process test
  and fails FR-29 outright — this is the same trap as L5's AC-4, one level up.
- `KANBAN_SECRET` must come from the environment. A hardcoded fallback secret is
  a security finding (NFR-3) even if it works.

---

## 3. Non-Functional Requirements

### 3.1 Performance

- **NFR-1.** Measured on the harness fixture (**3 boards × 5 columns × 50 cards**),
  built SPA, localhost:

  | Operation | Budget |
  |-----------|--------|
  | `GET /api/boards/{id}` (full nested board) | **p95 ≤ 300 ms** |
  | Any single CRUD write | **p95 ≤ 200 ms** |
  | `PATCH /api/cards/{id}/move` | **p95 ≤ 200 ms** |
  | SPA first interactive (cold load, built assets) | **≤ 2.5 s** |
  | **Perceived drag latency** — pointer-down to the card visually following, and drop to the board settling in its new order | **≤ 100 ms**, i.e. the drag must feel instant with no spinner and no visible round-trip stall |

  The board read must **not** issue an `N+1` query: the number of queries is
  bounded and independent of card count. The harness counts queries via the
  driver, so "it's fast enough on 50 cards" does not pass this.

### 3.2 Reliability & error handling

- **NFR-2.** **No unhandled 5xx on any user-supplied input** — this includes
  hostile IDs, oversized text, malformed JSON and out-of-range indices.
  **Moves are atomic**: a rejected or failed move leaves ordering exactly as it
  was, with no half-applied renormalization and no card left with a duplicate or
  orphaned position. **Restart loses nothing** (FR-29). The frontend degrades
  honestly: an API failure produces a visible, dismissible error and a UI state
  that matches the server, never a silent no-op and never a spinner that never
  resolves. Retrying a `DELETE` is safely idempotent in effect (204 then 404,
  never 500).

### 3.3 Security

- **NFR-3.**
  - **(a) Authentication.** Passwords salted and hashed with a slow KDF (§2.4);
    never logged, never returned in any response, never present in a JSON body.
    Session cookie is `HttpOnly`, `SameSite=Lax`, `Secure` when served over TLS,
    and is **not readable from `document.cookie`**.
  - **(b) Authorization is deny-by-default.** Every board-scoped endpoint
    resolves ownership through the single choke point (§2.2). An endpoint that
    forgets its check is a security defect regardless of whether a test happens
    to catch it.
  - **(c) Input validation** on every field: type, presence, trimmed length,
    `color` format, integer `position`. Reject at the boundary; do not coerce
    silently.
  - **(d) Output encoding — stored XSS is the L6-specific attack surface.** All
    user-supplied text (**card title and description, board name, column name,
    label name, member name**) is rendered as **text, not markup**. A card titled
    `<img src=x onerror=alert(1)>` must appear on screen as those literal
    characters and must execute nothing. `dangerouslySetInnerHTML` on
    user-supplied content is an automatic finding. If any markdown rendering is
    added (it is not required), it must be sanitized with an allowlist.
  - **(e) CSRF.** Session cookies are `SameSite=Lax`, and any state-changing
    endpoint reachable by a simple cross-site form must additionally be protected
    (token, custom-header requirement, or an origin check). The chosen mechanism
    is documented in the README.
  - **(f) Parameterized SQL only**; path and body IDs are untrusted data. A
    hostile ID (`'; DROP TABLE cards;--`, `../../etc/passwd`, a 5,000-char string,
    a NUL byte) yields **404 or 400**, never 500 and never a query error.
  - **(g) Size limits.** Request body ≤ 64 KiB; over-limit is a **400**, not a
    hang, not an OOM, not a 413-shaped surprise.
  - **(h) No secrets in the repository**; `KANBAN_SECRET` from env only.

### 3.4 Accessibility — **REQUIRED at this rung**

- **NFR-4. WCAG 2.1 Level AA.** This is the first rung where accessibility is a
  required deliverable rather than N/A (`ARTIFACT_GRADIENT.md` L6), and it is
  graded under both `FID` and the P0 acceptance criteria. Concretely:

  | Requirement | Detail |
  |-------------|--------|
  | **Automated scan** | **Zero critical or serious `axe-core` violations** on every screen: board list, board detail, card editor, register, login. Scanned in default state **and during an active drag/grab state**. |
  | **Keyboard operability** | **Every** function, including card and column reordering (FR-15), is reachable and operable by keyboard alone. A documented key map (e.g. `Space`/`Enter` to grab, arrows to move, `Space`/`Enter` to drop, `Escape` to cancel) lives in `design/interaction-specs.md`. |
  | **Focus** | Visible focus indicator on every interactive element, meeting **≥ 3:1** contrast against adjacent colours. Logical focus order. Focus is **never lost or trapped** — not by the card editor (A-5), not by drag/grab mode, not by an error toast. Focus returns to the invoking element when a dialog closes. |
  | **Semantics / ARIA** | Board, columns and cards carry meaningful roles and accessible names: a list/listbox (or equivalent) structure for columns and cards, each column labelled by its heading, each card exposing its title as its accessible name. Landmarks (`banner`/`main`/`navigation`) and a correct heading hierarchy. Drag state exposed via appropriate `aria-grabbed`/`aria-dropeffect` alternatives or the modern pattern of `aria-describedby` + live-region instructions. |
  | **Announcements** | Grab, move, drop, and drop-cancelled are announced via an ARIA live region with copy specified in the interaction spec ("Grabbed *Fix ordering*. Use arrow keys to move. Position 2 of 5 in To Do."). Loading, empty and error states (FR-27) are perceivable non-visually. Form errors are **programmatically associated** with their inputs. |
  | **Contrast** | Text ≥ **4.5:1**; large text and non-text indicators (label chips, focus rings, drop targets) ≥ **3:1**. Label colours (FR-17) must be paired with a documented accessible foreground; contrast ratios are recorded in `design/tokens/`. |
  | **Motion** | Any drag or reorder animation respects `prefers-reduced-motion`. |
  | **Not acceptable** | A separate "accessible mode", a keyboard-only alternate page, or a hidden fallback form. One UI, operable by everyone (Sam's anti-goal, §1.2). |

### 3.5 Maintainability

- **NFR-5.** `ruff` + `pyright` clean on the backend; `eslint` +
  `tsc --noEmit` clean on the frontend, with `strict: true`. Layering per §2.2
  respected and demonstrable. **Ordering logic exists exactly once**;
  authorization exists exactly once. Cyclomatic complexity ≤ 12 per function.
  Public services and route handlers carry docstrings; the API client is fully
  typed with no `any` at the boundary. No dead code, no commented-out blocks, no
  `TODO` standing in for a requirement. The §1.6 resolutions are documented in
  `solution/README.md`.

### 3.6 Observability

- **NFR-6.** `GET /api/health` per FR-30, reporting `status`, `version` and
  `schema_version`. **One structured log line per request** to stdout/stderr,
  machine-parseable (JSON preferred), containing at minimum: timestamp, method,
  route template, status code, duration in ms, and the acting `user_id` where
  authenticated. **Never** log passwords, password hashes, session tokens, or
  full cookie headers. Startup logs the resolved database target (with
  credentials redacted), the bind address, and the applied `schema_version`.
  Unhandled exceptions are logged with a traceback **server-side** and returned
  to the client as a clean JSON 5xx with no traceback.

### 3.7 Portability / footprint

- **NFR-7.** `make setup && make migrate && make run` from a clean checkout on
  Linux is the entire install path, using only declared dependencies. Works
  against SQLite locally and Postgres in the harness with only
  `KANBAN_DB_URL` changing. No global installs, no Docker requirement, no root,
  no external network at runtime. Cold start to healthy < 20 s. Frontend
  production build completes in < 120 s. Idle backend RSS < 300 MB.

---

## 4. The Ask (Deliverables & Definition of Done)

### 4.1 Required artifacts

```
solution/
  Makefile                      # setup | run | migrate | reset-db | test | lint
  README.md                     # how to run; ARCHITECTURE; the §1.6 A-1..A-7 resolutions
  backend/
    api/                        # routes, request/response models, error handlers
    services/                   # ordering, cascade, authorization choke point
    repositories/               # persistence, parameterized queries
    migrations/0001_init.*      # the L6 baseline schema (L7 builds 0002..0005 on it)
    requirements.txt            # pinned
  frontend/
    src/api/                    # typed client for §2.1
    src/state/                  # store (Zustand or equivalent)
    src/components/             # board, column, card, card editor, auth screens
    package.json + lockfile
  tests/                        # the STRATEGY's own tests (not the graded suites)

design/
  prd.md
  backlog.md
  dod.md
  research/
    interviews.md
    jtbd.md
    personas.md
  wireframes/                   # lo-fi
  hifi/                         # hi-fi mockups
  tokens/                       # design tokens + contrast table
  interaction-specs.md
  a11y-annotations.md
  data-model.md
  openapi.yaml
```

| Path | Contents |
|------|----------|
| `solution/Makefile` | `setup`, `run`, `migrate`, `reset-db`, `test`, `lint` — all working from a clean checkout (§2.5). |
| `solution/README.md` | How to run; the architecture and its layering; **the A-1..A-7 resolutions stated explicitly**; the CSRF mechanism; the keyboard drag key map. |
| `solution/backend/**` | FR-1..FR-31 server-side, layered per §2.2. |
| `solution/frontend/**` | The SPA: FR-14, FR-15, FR-24..FR-28, NFR-4. |
| `design/**` | The §5.4 artifact set. Missing a Required file is a DoD failure and caps `FID`. |

### 4.2 Definition of Done

```
DEFINITION OF DONE — L6
[ ]  1. 100% of P0 acceptance criteria pass                       (HARD GATE)
[ ]  2. >= 90% of ALL acceptance criteria pass                    (HARD GATE)
[ ]  3. smoke suite green against a locally started application
[ ]  4. `make setup && make migrate && make run` works from a clean checkout;
        /api/health returns 200 with the expected schema_version within 60 s;
        SIGTERM exits cleanly within 10 s
[ ]  5. Data + ordering verified intact after a stop/restart cycle on the same DB
[ ]  6. Performance budgets (NFR-1) met on the harness fixture, incl. no N+1
        on the nested board read and perceived drag latency <= 100 ms
[ ]  7. WCAG 2.1 AA: zero critical/serious axe violations on EVERY screen,
        including during an active drag/grab; keyboard-only path completes the
        same moves as the mouse path with identical server state
[ ]  8. Stored-XSS check clean: script payloads in every user-text surface
        render as literal text
[ ]  9. Authorization sweep clean: user B denied on every board-scoped endpoint
        of user A, uniformly, per the A-2 choice
[ ] 10. ruff + pyright clean; eslint + tsc --noEmit clean; no interpolated SQL
[ ] 11. All §5.4 design artifacts exist, are internally consistent, and match
        what shipped (DESIGN-DIFF REVIEW: hi-fi vs implementation)
[ ] 12. Backlog shows P0/P1 prioritisation and traces to FRs; PRD states the
        problem, scope, non-goals and success metrics
[ ] 13. A-1..A-7 resolved, implemented consistently, and documented in BOTH
        solution/README.md and the relevant design/ artifact
[ ] 14. design/openapi.yaml matches the implemented contract (path, status,
        schema) — spec/implementation diff is clean
```

Items 1–2 are the automated hard gate. Items 3–10 are automated checks feeding
`COR`/`ROB`/`QUA`. Items 11–14 are artifact obligations feeding `FID` and
**capping it when missing** (`ARTIFACT_GRADIENT.md` §3).

### 4.3 Acceptance criteria

The authoritative P0/P1 matrix. **`P0` criteria must pass at 100%**; the
combined set must reach **≥ 90%** (§7.3).

| ID | Pri | Criterion | Traces to | Tier |
|----|-----|-----------|-----------|------|
| **AC-1** | **P0** | Board CRUD round-trips over live HTTP: create → read → rename → delete; deleted board is 404 on re-read. | FR-1..FR-4 | API |
| **AC-2** | **P0** | Column CRUD works; **deleting a column cascades its cards** and leaves no orphans; the board read afterwards is correct and does not error. | FR-5 | API |
| **AC-3** | **P0** | Card CRUD works; field limits (title 1–200, description ≤ 4,000) enforced with **400** + the error envelope naming the field. | FR-8, FR-28 | API |
| **AC-4** | **P0** | `GET /api/boards/{id}` returns the full nested board in **one call** in stable position order, with a bounded query count independent of card size. | FR-3, NFR-1 | API |
| **AC-5** | **P0** | Move a card to **every** index in its own column; read-back order matches exactly each time. | FR-10, FR-12 | API |
| **AC-6** | **P0** | Move a card to every index in **another** column; both source and destination renormalize to a dense `0..n-1`. | FR-11, FR-12 | API |
| **AC-7** | **P0** | Deleting a middle card leaves survivors dense and correctly ordered; the same for deleting a middle column. | FR-12 | API |
| **AC-8** | **P0** | Repeating an identical move is idempotent — no drift, no duplicate positions, no reordering churn. | FR-16 | API |
| **AC-9** | **P0** | **E2E:** create board → add two columns → add three cards → **drag a card within a column and then into the other column** → hard-reload → order is exactly as left. | FR-14, FR-13 | Browser |
| **AC-10** | **P0** | **E2E + process control:** after the drag in AC-9, restart the server process against the same DB → the order is still exactly as left. | FR-13, FR-29 | Browser + API |
| **AC-11** | **P0** | **E2E:** perform the AC-9 moves using **only the keyboard**; the resulting server state is **identical** to the mouse path. | FR-15, NFR-4 | Browser |
| **AC-12** | **P0** | **E2E + fault injection:** a move rejected by the server visibly snaps the card back to its true position and surfaces an error; the board never displays state the server did not accept. | FR-26, NFR-2 | Browser |
| **AC-13** | **P0** | Register → login → authenticated request succeeds. Duplicate email rejected; password < 8 chars rejected; passwords never stored or returned in plaintext and the hash is salted and slow. | FR-20, NFR-3 | API + DB inspection |
| **AC-14** | **P0** | Logout invalidates the session **server-side**; replaying the cookie afterwards yields **401**. Unauthenticated requests to app endpoints yield **401**, never 200 and never 5xx. | FR-21, FR-23 | API |
| **AC-15** | **P0** | **Authorization matrix:** user B receives the A-2 denial code on **every** read/write/move/delete path of user A's board, columns, cards, labels and members — enumerated endpoint by endpoint, including nested IDs. `GET /api/boards` never lists another user's board. | FR-22 | API |
| **AC-16** | **P0** | **E2E:** two browser contexts, two accounts; B cannot reach A's board by direct URL. The session cookie is `HttpOnly` and not readable from `document.cookie`. | FR-22, NFR-3 | Browser, 2 contexts |
| **AC-17** | **P0** | **Stored XSS:** script payloads placed in card title, card description, board name, column name, label name and member name render as **literal text** and execute nothing, on the board view and in the card editor. | NFR-3(d) | Browser + adversarial |
| **AC-18** | **P0** | Malformed / oversized / empty payloads return **400** with the envelope; unknown IDs return **404**; wrong methods return **405**; **zero 5xx** across the whole run. | FR-28, NFR-2 | API |
| **AC-19** | **P0** | **Zero critical/serious axe violations** on board list, board detail, card editor, register and login — including **during an active drag/grab state**. | NFR-4 | axe-core |
| **AC-20** | **P0** | **E2E:** every empty, loading and error state is present and distinguishable on board list, board detail and card editor; an empty board is not visually identical to a failed load. | FR-27 | Browser |
| **AC-21** | **P0** | Focus is visible on every interactive element, never lost or trapped by the card editor or grab mode, and returns to the invoking element on close. | NFR-4 | Browser + axe |
| **AC-22** | P1 | Column reorder works via API and via the UI, and persists across reload. | FR-7 | API + Browser |
| **AC-23** | P1 | Label CRUD is board-scoped; a card cannot take a label from another board; deleting a label removes it from cards without deleting the cards. | FR-17, FR-18 | API |
| **AC-24** | P1 | Roster CRUD works; assigning an off-roster member is rejected; deleting a member leaves its cards unassigned and intact; **roster entries grant no access** (AC-15 still holds). | FR-19 | API |
| **AC-25** | P1 | **E2E:** labels and assignee are visible on the card face and editable from the card editor; label chips meet the ≥ 3:1 non-text contrast requirement. | FR-17..FR-19, NFR-4 | Browser + axe |
| **AC-26** | P1 | Perceived drag latency ≤ 100 ms and API p95 budgets met on the standard fixture (NFR-1). | NFR-1 | Perf probe |
| **AC-27** | P1 | Keyboard grab/move/drop is **announced** via a live region using the copy specified in `design/interaction-specs.md`. | NFR-4 | Browser + axe |
| **AC-28** | P1 | Structured request logs present with the NFR-6 fields; no passwords, hashes, or session tokens appear anywhere in captured logs. | NFR-6 | Log inspection |
| **AC-29** | P1 | All required `design/` artifacts present, mutually consistent, and matching the implementation (design-diff review); `openapi.yaml` matches the implemented contract. | §5.4, `FID` | Review |
| **AC-30** | P1 | A-1..A-7 behave exactly as documented, repeatably. | §1.6 | API + Browser |

**Counts:** 21 `P0`, 9 `P1`, 30 total. The gate needs **21/21 P0** and
**≥ 27/30 overall**.

---

## 5. Discovery & Design Activities

Consistent with the **L6 row** of `framework/ARTIFACT_GRADIENT.md`. This is the
rung where the product and design surface becomes **mostly Required**, because
the software now has human end-users whose experience is part of "working".

### 5.1 User research

| Activity | Status | What must exist |
|----------|--------|-----------------|
| **Stakeholder / user interviews** | **Required** | ≥ 3 interview write-ups in `design/research/interviews.md`, grounded in the §1.2 personas: context, current workaround, pains, at least one verbatim-style quote, and the **implication for a requirement**. Being honest about method: there are no live participants inside an eval run, so these are *persona-grounded synthetic interviews*. They are scored on **rigor and traceability** — does each interview produce a stated implication, and does that implication actually appear in the backlog? — not on being genuine field research. An interview that changes nothing is theater. |
| **Jobs-to-be-done** | **Required** | ≥ 5 JTBD statements in `design/research/jtbd.md` in the form *"When ___, I want ___, so I can ___"*, each mapped to at least one backlog item. At least one must ground a §1.6 resolution — e.g. A-3's optimistic-UI choice must be justified *from* "When I'm reordering in front of the team, I want the card to move the instant I drag it, so I can keep talking," not merely asserted. |
| **Personas** | **Required** | `design/research/personas.md` containing **Maya** and **Sam** fully fleshed out (goals, frustrations, key tasks, motivated requirements, anti-goals) plus Marco and Jules at summary depth for L7 continuity. Personas must be **traceable**: each of FR-15, FR-26 and FR-27 names the persona need it serves. |
| **Usability testing** | **Optional / Stretch** | Not required at L6 (it becomes Required at L7). If attempted: a scripted walkthrough of ≥ 5 tasks against the **real running app**, with severity-rated findings. It is not scored, and it does not excuse a missing Required artifact. |

### 5.2 Product design

| Activity | Status | What must exist |
|----------|--------|-----------------|
| **Spec / acceptance criteria** | **Required** | This document plus §4.3. The strategy restates acceptance in its own words nowhere — §4.3 is authoritative. |
| **PRD** | **Required** | `design/prd.md`: problem statement, personas, **in-scope and explicit non-goals** (§1.5), the §1.3 user stories, success metrics (e.g. "a card can be reordered in ≤ 1 s of user time", "zero data loss across restart", "zero critical axe violations"), and the accepted risks including the A-6 confirmation decision. |
| **User stories** | **Required** | §1.3 is the seed; the PRD/backlog may extend it, and each story must carry its `P0`/`P1` priority and its acceptance link. |
| **Prioritized backlog** | **Required** | `design/backlog.md`: one ranked, estimated list, **explicitly sliced into P0 and P1**, every item tracing to an `FR-n`. This is the artifact that proves the strategy understood what to build *first* — a backlog where everything is P0 is not a prioritisation, and is a `FID` finding. The P0/P1 split must match §4.3's, and any deviation must be argued in the PRD. |
| **Definition of Done** | **Required** | `design/dod.md` — the §4.2 checklist, applied and evidenced. |
| **Sprint plans / retrospectives** | **N/A** | Single delivery; there is no iteration protocol at this rung. That is exactly what L7 adds. |

### 5.3 Interaction / visual design

Everything in this section is **Required** at L6. The distinguishing obligation
of this rung is that design is a **deliverable that the implementation is
diffed against**, not a sketch that gets abandoned.

| Activity | Status | What must exist |
|----------|--------|-----------------|
| **Interface / API contract design** | **Required** | `design/openapi.yaml` covering every §2.1 endpoint including error responses and the move semantics, plus `design/data-model.md` with the schema, indexes, cascade rules and the **A-1 ordering-strategy choice with its trade-off**. Both must end the run matching reality. |
| **Wireframes (lo-fi)** | **Required** | `design/wireframes/`: board list, board detail, column, card, **card editor (the A-5 surface)**, auth screens, and — explicitly — the **empty / loading / error** variants. Lo-fi means structure and hierarchy; ASCII, SVG, or exported images are all acceptable. |
| **Hi-fi mockups** | **Required** | `design/hifi/`: at minimum the board view and the card editor, rendered with real type, colour, spacing and states (default / hover / focus / dragging / error). This is what the design-diff review compares the shipped UI against. |
| **Design tokens / system** | **Required** | `design/tokens/` (`tokens.json` or equivalent + a short README): colour palette with **documented contrast ratios**, spacing scale, type scale, radii, elevation, and an explicit **focus-ring token**. Label colours (FR-17) must each ship with an accessible paired foreground and a recorded ratio. The shipped CSS must demonstrably consume these tokens — hardcoded hex values in components that contradict the tokens is a design-diff finding. |
| **Interaction / state specs** | **Required** | `design/interaction-specs.md`: the **drag state machine** — `idle → grabbed → over-valid-target → over-invalid-target → dropping → persisting → error-reconciling → idle` — with what the user sees at each state; drop-target affordances; the **keyboard move key map**; the **live-region announcement copy** for grab/move/drop/cancel; the card-editor open/close/focus-restore behaviour (A-5); and the optimistic-vs-pessimistic decision (A-3) with its rollback behaviour. |
| **Accessibility annotations** | **Required** | `design/a11y-annotations.md`: for each screen — landmarks, heading hierarchy, roles and accessible names for board/column/card, tab order, focus-management rules, the drag/grab ARIA pattern, live-region placement and politeness, form-label association and error-announcement strategy, and a **WCAG 2.1 AA checklist** with each relevant success criterion marked and evidenced. This document must be written *before* the a11y implementation, not reverse-engineered from an axe report — a file whose only content restates axe's output is a `FID` finding. |

### 5.4 Design artifacts to produce

Exact files. **Missing a Required file is a DoD failure (item 11) and caps
`FID`** (`ARTIFACT_GRADIENT.md` §3).

```
design/
  prd.md                        # problem, personas, scope, non-goals, metrics, risks
  backlog.md                    # ranked, estimated, P0/P1-sliced, traced to FR-n
  dod.md                        # the §4.2 checklist
  research/
    interviews.md               # >= 3 persona-grounded write-ups w/ implications
    jtbd.md                     # >= 5 JTBD statements -> backlog map
    personas.md                 # Maya + Sam in depth; Marco + Jules in summary
  wireframes/
    board-list.*  board-detail.*  card-editor.*  auth.*  states.*
  hifi/
    board-detail.*  card-editor.*            # + optional: auth, board-list
  tokens/
    tokens.json                 # colour/space/type/radius/focus-ring
    README.md                   # contrast ratios incl. every label colour
  interaction-specs.md          # drag state machine, key map, announcement copy,
                                #   card-editor focus behaviour, A-3 decision
  a11y-annotations.md           # per-screen semantics + WCAG 2.1 AA checklist
  data-model.md                 # schema, indexes, cascades, A-1 ordering choice
  openapi.yaml                  # the §2.1 contract
```

| File | Required? | Scored under |
|------|-----------|--------------|
| `prd.md`, `backlog.md`, `dod.md` | **Required** | `FID` — existence, traceability to FR/AC, real prioritisation |
| `research/personas.md`, `research/jtbd.md`, `research/interviews.md` | **Required** | `FID` — grounding of A-3 and of FR-15/26/27 |
| `wireframes/**`, `hifi/**` | **Required** | `FID` — **design-diff review vs the shipped UI** |
| `tokens/**` | **Required** | `FID` — tokens exist *and are consumed*; contrast documented |
| `interaction-specs.md` | **Required** | `FID` — drag states + key map match observed behaviour |
| `a11y-annotations.md` | **Required** | `FID` — WCAG checklist vs the axe/keyboard results |
| `data-model.md`, `openapi.yaml` | **Required** | `FID` — spec/implementation diff |
| `research/usability/*.md` | Optional | not scored at L6 |

---

## 6. Verification Method

### 6.1 Test tiers

Per `VERIFICATION_CONTRACT.md` §1. The `web-app` entrypoint kind means the real
path is **a real browser driving the real DOM against a real API against real
persistence**. Nothing here is satisfiable by a mock, and mock-only evidence is
not accepted as acceptance evidence.

#### `smoke` — **visible to the agent**

A handful of happy-path checks so the strategy has a legitimate feedback loop.
Deliberately small: enough to self-check, nowhere near enough to define done.

```console
# 1. API: the core lifecycle
$ curl -sS -X POST localhost:$PORT/api/auth/register -c jar \
    -H 'content-type: application/json' -d '{"email":"maya@example.com","password":"correct-horse"}'
HTTP/1.1 201 Created

$ curl -sS -b jar -X POST localhost:$PORT/api/boards \
    -H 'content-type: application/json' -d '{"name":"Q3 Delivery"}'
{"id":"b_01H8...","name":"Q3 Delivery","created_at":"..."}

$ curl -sS -b jar -X POST localhost:$PORT/api/boards/b_01H8.../columns \
    -H 'content-type: application/json' -d '{"name":"To Do"}'
{"id":"col_01H8...","name":"To Do","position":0,...}

# 2. API: move a card to the head of another column, get authoritative board back
$ curl -sS -b jar -X PATCH localhost:$PORT/api/cards/c_01H8.../move \
    -H 'content-type: application/json' -d '{"column_id":"col_01H8DONE...","position":0}'
{"id":"b_01H8...","columns":[...]}          # dense 0..n-1 in BOTH columns

# 3. API: auth gate
$ curl -sSi localhost:$PORT/api/boards
HTTP/1.1 401 Unauthorized

# 4. API: validation
$ curl -sSi -b jar -X POST localhost:$PORT/api/columns/col_01H8.../cards \
    -H 'content-type: application/json' -d '{"title":"   "}'
HTTP/1.1 400 Bad Request
{"error":{"code":"validation_error","message":"title must be 1-200 characters","field":"title"}}

# 5. Platform
$ curl -sS localhost:$PORT/api/health
{"status":"ok","version":"1.0.0","schema_version":1}
```

```ts
// 6. Browser (Playwright, visible): the one E2E worked example
test('create a board, add a card, drag it, reload, order persists', async ({ page }) => {
  await login(page, 'maya@example.com', 'correct-horse');
  await page.getByRole('button', { name: 'New board' }).click();
  await page.getByLabel('Board name').fill('Q3 Delivery');
  await page.getByRole('button', { name: 'Create' }).click();
  // ... add columns "To Do" and "Done", add card "Fix ordering" to "To Do"
  await dragCard(page, 'Fix ordering', { toColumn: 'Done', toIndex: 0 });
  await page.reload();
  await expect(cardsIn(page, 'Done')).toHaveText(['Fix ordering']);
});
```

#### `acceptance` — **held out**

The authoritative matrix: **every criterion in §4.3**, run against the live
application. Grouped:

| Group | Coverage | ACs |
|-------|----------|-----|
| Board / column / card CRUD | Full round-trips, cascade delete, field limits, error envelope | AC-1..AC-3 |
| Aggregate read | Single-call nested board, stable order, bounded query count | AC-4 |
| **Ordering** | Move to every index within-column and cross-column; delete renormalization; move idempotency; 200 sequential moves in one column with the invariant re-asserted after each | AC-5..AC-8 |
| **Browser E2E — drag & persistence** | Real pointer drag within and across columns; hard reload; **server restart**; order identical | AC-9, AC-10 |
| **Browser E2E — keyboard DnD** | The same two moves by keyboard only; server state compared byte-for-byte with the mouse path | AC-11 |
| **Optimistic rollback** | Fault-injected move rejection; card snaps back; error surfaced; no permanent optimistic lie | AC-12 |
| Auth | Register/login/logout; hash inspection in the DB; cookie flags; 401 gating; session replay after logout | AC-13, AC-14 |
| **Authorization** | Exhaustive endpoint × cross-user sweep including nested IDs; list isolation; two-context browser check | AC-15, AC-16 |
| **Stored XSS** | Payloads in all six user-text surfaces; asserted as text on board view and in the editor | AC-17 |
| Error model | 400 / 404 / 405 matrix; zero-5xx assertion across the entire run | AC-18 |
| **Accessibility** | axe sweep on all five screens incl. during grab; empty/loading/error state presence; focus visibility, non-loss, non-trapping, and restore | AC-19..AC-21, AC-27 |
| Labels & roster (P1) | Board-scoping, many-to-many, delete semantics, no-access invariant, UI display, chip contrast | AC-23..AC-25 |
| Column reorder (P1) | API + UI + persistence | AC-22 |
| Performance (P1) | Nested-read/write/move p95, N+1 query count, perceived drag latency | AC-26 |
| Observability (P1) | Log shape; secret-leak scan of captured logs | AC-28 |
| Artifacts (P1) | `design/` presence, design-diff review, OpenAPI-vs-implementation diff | AC-29 |
| Documented policy (P1) | A-1..A-7 behave as the README says | AC-30 |

#### `adversarial` — **hidden, run once** after the strategy declares done

Feeds `COR`/`ROB` only; never the gate. Indicative, not exhaustive:

| Class | Probes |
|-------|--------|
| **Authorization bypass** | Every endpoint × a cross-user actor, addressed by *nested* IDs (`PATCH /api/cards/{A's card}` with B's session), including `move` in both directions; forged, expired and post-logout cookies; session fixation; cookie replay after a password-change-shaped flow; IDs of a deleted-then-recreated board; response-timing comparison between "not yours" and "does not exist" when A-2 = 404. |
| **Stored / reflected XSS** | `<script>alert(1)</script>`, `<img src=x onerror=...>`, `javascript:` URLs, `"><svg onload=...>`, HTML entities, unicode-escaped payloads, and an SVG payload — placed in card title, card description, board name, column name, label name and member name; asserted on the board view, in the card editor, and in any error message that echoes input. |
| **Ordering under stress** | Move to index `-1`, `999999`, a non-integer, `null`; move a card onto itself; move to a nonexistent column; move into an **empty** column; move a card that was deleted mid-request; two near-simultaneous moves of the same card; two near-simultaneous moves into the same target index; delete a card while a move targeting it is in flight; **a column containing 200 cards** with the dense invariant re-asserted after a shuffle. |
| **Deep / wide structures** | A board with **30 columns**; a column with 200 cards; 30 boards for one user — asserted for correctness of the nested read *and* against NFR-1. |
| **Huge / hostile text** | A 4,000-char description (boundary, accepted) vs 4,001 (rejected); a 200-char title vs 201; a 1 MiB request body → 400, not a hang; NUL bytes, CR/LF, RTL overrides, zero-width joiners, emoji and combining characters in every text field, asserted to round-trip byte-identically and render safely. |
| **Injection** | `'; DROP TABLE cards;--`, `../../etc/passwd`, `%2e%2e%2f`, a 5,000-char ID, a NUL byte in the path → **404/400, never 500**, never a query error, never a stack trace. |
| **Method / routing matrix** | Every path × `GET`/`POST`/`PATCH`/`PUT`/`DELETE`/`HEAD`/`OPTIONS` → correct 405s, no HTML error pages. |
| **Auth hardening** | Email case and unicode-normalization collisions at registration; 7-character password; password echoed in a log line; `document.cookie` readability; a cross-site form POST against a mutating endpoint (CSRF). |
| **Frontend resilience** | API returning 500 mid-drag; API latency injected at 3 s (is there a loading state, or a frozen board?); a drag dropped outside any valid target; a browser back/forward across a board delete; a reload during an open card editor. |

### 6.2 "Working" definition (the hard gate)

```
gate  ==  P0 acceptance criteria      == 100%   (21/21)
     AND  all acceptance criteria     >= 90%    (>= 27/30)
```

Rationale for the two-part shape: the `P0` set *is* the product — an app that
loses card order on reload, or leaks one user's board to another, is not a
Kanban application in any useful sense, so it gets no slack. The 90% overall
floor exists because the `P1` set includes genuinely secondary polish (log
shape, chip contrast, column reorder) where a strategy may reasonably land at
27/30 and still have delivered the product. `adversarial` never gates; it feeds
`COR`/`ROB`.

### 6.3 Verification mechanics

`kind: web-app`. The real path is a real server, a real database, a real
production build of the SPA, and a real browser.

```
HARNESS RUN PROTOCOL
 1. Clean workspace; run build.setup (pip install + npm ci + npm run build).
 2. Allocate a free PORT; create a throwaway KANBAN_DB_URL in a per-run tmpdir;
    set KANBAN_SECRET to a random value.
 3. reset_cmd; migrate_cmd; start_cmd. Poll /api/health until 200 or 60 s.
    Assert schema_version is present. Failure to become healthy = total
    acceptance failure, reported distinctly from behavioral failure.
 4. Seed the standard fixture: 2 user accounts; 3 boards; 5 columns x 50 cards.
    Fixture IDs and titles are RANDOMIZED per run.
 5. Run acceptance API tier   (pytest + httpx, live HTTP, real cookies).
 6. Run acceptance browser tier (Playwright, built SPA, real DOM).
 7. Run the axe sweep over every screen, incl. an active grab state.
 8. Run performance probes (NFR-1) incl. the query-count check.
 9. Restart probe: SIGTERM -> wait <= 10 s -> relaunch on the SAME DB ->
    re-poll health -> re-assert ordering and content byte-for-byte.
10. Run adversarial once. Record; feeds COR/ROB.
11. Static analysis (ruff/pyright/eslint/tsc) + design-diff + artifact presence.
12. Emit score.json.
```

| Concern | Mechanism |
|---------|-----------|
| **API tier** | `pytest` + `httpx` against the live server with a real cookie jar. Never an in-process `TestClient` — mock-only evidence is not acceptance evidence at L5+, and certainly not here. |
| **DB inspection** | A small number of criteria read **directly from the database** rather than through the API, because the API cannot honestly report on itself: AC-13 (password hash is salted and slow, plaintext absent), AC-7/AC-8 (positions are dense and unique **in storage**, not merely sorted on read). |
| **Browser tier** | Playwright against the **built** SPA at `url`. Selectors are **role/label-based** (`getByRole`, `getByLabel`) — never CSS classes or test-ids the strategy could special-case — which has the useful side effect of making accessible markup a prerequisite for passing at all. |
| **Drag simulation** | Real pointer events (`mouse.down` → stepped `mouse.move` → `mouse.up`) with intermediate movements, so a handler that only listens for HTML5 `dragstart` and a handler that only listens for pointer events are both exercised honestly. The keyboard path (AC-11) is driven with **real key events**; calling a handler directly is not accepted. |
| **Mouse-vs-keyboard equivalence** | AC-11 runs the identical logical move twice on freshly reset fixtures — once by pointer, once by keyboard — snapshots the full `BoardDetail` after each, and asserts the two snapshots are identical modulo timestamps. This is the strongest available check that the keyboard path is a real path and not a decorative one. |
| **Fault injection** | Playwright route interception returns a 409/500 for a specific `move` call (AC-12), and injects 3 s latency for the loading-state checks. The assertion is on the **user-visible reconciliation**, not on a console message. |
| **Restart persistence** | `SIGTERM`, wait for exit (≤ 10 s, else `SIGKILL` **and fail**), relaunch with the same `KANBAN_DB_URL`, re-poll health, then assert the full board — content *and* positions — is byte-identical and the UI renders it identically. |
| **Accessibility** | `axe-core` injected per screen, filtered to `critical`/`serious`. The active-grab scan is taken mid-interaction (after grab, before drop). Focus assertions use `document.activeElement` snapshots across open/close cycles. Contrast for label chips is computed from the rendered colours, not read from the tokens file — the tokens must be *used*, not merely *declared*. |
| **XSS** | Payloads written via the **API**, then asserted in the **browser**: the payload's text is present as text content, no matching element was created in the DOM, and no dialog/console-error/navigation fired. Testing only the API response body would miss the entire bug class. |
| **Performance** | Client-side timing over 200 requests after a 20-request warmup for the API budgets. Perceived drag latency is measured from the synthetic pointer-down to the DOM reflecting the card's movement. Query count is captured via a driver-level hook. Timing assertions are **best-of-3** and marked **advisory (excluded from the gate denominator)** if the host fails pre-run load calibration — timing noise must not decide a gate. |
| **Determinism** | Fresh DB and randomized fixture per module; no shared state between groups; no wall-clock assertions beyond ISO-8601 parseability and ordering; Playwright runs with animations disabled and a fixed viewport. |
| **Flaky-guard** | Per `VERIFICATION_CONTRACT.md` §4: a browser test may be retried **at most twice** and only for harness-side faults (browser launch failure, port exhaustion, navigation timeout with no server response). **An ordering mismatch, an authz leak, an XSS success, or an axe violation is never retried** — those are hard fails. |
| **Teardown** | `SIGTERM`; tmpdir and DB discarded; server stdout/stderr, Playwright traces, videos and axe reports archived with the run. |

### 6.4 Anti-gaming measures

| Vector | Detection |
|--------|-----------|
| **Coding to the visible smoke** | `acceptance` covers every index in every column and both move directions; `adversarial` uses different data entirely. A large `acceptance_pass` vs `adversarial_pass` gap caps `ROB` (`CONVERGENCE_METRICS.md` §6). |
| **Hardcoding fixture values** | Board names, column names, card titles and all IDs are **randomized per run**. |
| **Client-side ordering only** | The restart probe and the direct-DB position inspection kill any scheme where order lives in `localStorage`, in the store, or in insertion order. This is the L6 analogue of L5's in-memory-counter trap. |
| **Decorative keyboard support** | AC-11 compares full server-state snapshots between the mouse and keyboard paths. A keyboard handler that merely re-renders locally, or that calls a different endpoint with different semantics, fails visibly. |
| **Fake accessibility** | Playwright selectors are role/label-based, so a UI that passes axe by adding `aria-hidden` to everything cannot be driven at all. Contrast is computed from **rendered** colours. Focus assertions run across real open/close cycles. |
| **XSS "fixed" by escaping only on write** | Payloads are injected via the API and asserted in the DOM; a solution that escapes on write but renders raw elsewhere (or vice versa) fails one of the two surfaces. |
| **Authorization checked only on the top-level route** | The sweep addresses nested entities **by their own IDs**, which is exactly where copy-pasted checks are missed. |
| **DB wiped at startup** | Restart probe fails deterministically; the harness also compares DB byte-size and file identity before/after restart. |
| **Design retro-fitted or contradictory** | Design-diff review compares `hifi/` against screenshots of the shipped UI; token consumption is checked against rendered values; the a11y annotations are compared against the axe/keyboard results. A `design/` directory that merely narrates the code caps `FID`. |
| **OpenAPI written to look right** | Spec/implementation diff across path, method, status and schema. |
| **Suite tampering** | Held-out suites live outside the workspace and are mounted read-only at scoring time. Writes outside `solution/` + `design/`, or attempts to read the harness tmpdir, are `gaming_events` → **disqualification** (`CONVERGENCE_METRICS.md` §6). |

---

## 7. Scoring Rubric

### 7.1 Weight profile

Sum 100. Matches the L6 column of `RUBRIC_FRAMEWORK.md` §3 exactly.

| Axis | `COR` | `ROB` | `EFF` | `AUT` | `QUA` | `REG` | `FID` |
|------|------|------|------|------|------|------|------|
| **Weight** | **22** | **12** | **15** | **15** | **12** | **12** | **12** |

Reading the profile: `COR` has fallen to 22 because correctness here is a broad
surface enforced largely by the gate, while `EFF` and `AUT` climb to 15 each —
at four hours and two toolchains, *how* a strategy converges is now as
informative as *whether* it does. `FID` reaches its ladder maximum of **12**
because L6 is the rung where the product and design surface first becomes fully
required, and "working" explicitly includes meeting design and accessibility
intent (`ARTIFACT_GRADIENT.md` §3). `REG` is live at 12 without sprints: see
below.

**How `REG` is measured at a single-delivery rung.** The acceptance suite is
partitioned into feature groups (boards / columns / cards / ordering / auth /
authz / labels / UI-states / a11y). The harness runs the **full suite twice** —
once on a cold database and once on a database carried over from a prior group
plus a restart — and additionally re-runs the ordering and auth groups **after**
the labels/roster groups have executed. An assertion that passes in the first
pass and fails in the second, or a group broken by work on a later group, is a
regression. The harness also mines the strategy's own iteration trace for
`oscillations` (a previously-fixed failure re-introduced). This is the same
mechanism L5 uses, sized up — and it is a deliberate preview of L7, where the
same app is graded on regression across five sprints instead of across groups.

### 7.2 Per-axis scoring guide

| Axis | 0 | 2 | 4 |
|------|---|---|---|
| **COR** | Any P0 criterion fails, or overall < 90% (gate fail) | Gate cleared, but `adversarial_pass` < 0.80 — edges survive only because they weren't tested (out-of-range moves, unicode titles, deep boards) | 100% P0, ≥ 97% overall, `adversarial_pass` ≥ 0.95, ordering invariant holds under every stress probe |
| **ROB** | 5xx or stack traces on user input; an authz bypass; a successful XSS payload; a move leaves duplicate/orphaned positions | Common bad input handled, but boundary cases leak: out-of-range index accepted silently, 4,001-char description 500s, drop-outside-target loses the card, a nested endpoint misses its ownership check | Every adversarial class survives: authz sweep clean, XSS clean in all six text surfaces, concurrent and invalid moves rejected cleanly with ordering intact, deep/wide boards correct, zero 5xx across the whole run |
| **EFF** | > 80 iterations or > 4 h, or never passed | Passed near the hard cap, or high `failed_runs_before_pass` — typically re-discovering the ordering invariant by trial and error, or fighting the two-toolchain build | Passed ≤ 30 iterations, under time and token budget, ≤ 1 failed run before pass; the ordering invariant and the keyboard path are **correct by design**, not by iteration |
| **AUT** | Any `rescue` (a human wrote the renormalization, the authz seam, or the keyboard handler) | 1–2 low-severity interventions — a `clarify` on a §1.6 **product** ambiguity sits at the top of this band; a `clarify` on something §2 already fixes sits at the bottom | Zero interventions, zero dead ends; §1.6 resolved unilaterally and documented before implementation |
| **QUA** | Lint/type errors; interpolated SQL; `any` at the API boundary; authorization copy-pasted per endpoint | Clean but accreting: ordering logic duplicated between the move and delete paths, board state smeared across component local state, thin docstrings, complexity creeping past caps | Layered per §2.2 with a single ordering implementation and a single authz choke point; typed client end to end; services independently testable; the frontend would survive L7's Sprint 4 without a rewrite |
| **REG** | A feature group broken by work on a later group and shipped that way; or a suite-tampering gaming event | 1–2 regressions or oscillations, caught and fixed before "done" — commonly: adding labels breaks the nested board read, or adding auth breaks `move` | Zero `regressions_introduced`, zero oscillations, both full-suite passes identical, ordering and auth groups unaffected by later work |
| **FID** | Required `design/` artifacts largely absent, or they contradict what shipped; or WCAG AA not met | Artifacts present but thin: backlog with no real prioritisation, a11y annotations reverse-engineered from axe output, hi-fi that describes a UI that wasn't built, tokens declared but not consumed | All §5.4 files present and mutually consistent; hi-fi matches the shipped UI on design-diff; tokens are demonstrably consumed with documented contrast; the interaction spec's drag states and key map match observed behaviour; personas visibly drove FR-15/26/27; WCAG 2.1 AA fully met including keyboard DnD |

### 7.3 Hard gate

```
p0_floor      = 1.00    # 100% of the 21 P0 acceptance criteria
overall_floor = 0.90    # >= 90% of all 30 acceptance criteria (>= 27)
```

Both conditions are required. A run that scores 29/30 while failing **one** P0
criterion **fails the gate** — because the P0 set is precisely the set of things
whose absence means you did not build a Kanban board. The three P0 criteria most
commonly responsible for a gate failure at this rung, in order:

1. **AC-10** — ordering does not survive a server restart (it lived in client
   state, in the store, or in insertion order).
2. **AC-15** — one nested endpoint missed its ownership check.
3. **AC-11** — drag-and-drop is mouse-only, so Sam cannot use the product.

`adversarial` never counts toward the gate.

### 7.4 Pass threshold

**68** — matching L5, and for the same reason: L6 has genuinely hard surface
(an ordering invariant, two toolchains, a browser-verified real path, and a full
design obligation) where a rough but honest convergence is still informative. A
run scoring 68–84 is `Converged`; a run below 68 that cleared the gate got there
by brute force, and the ladder profile should say so.

Expected shapes:

```
COR 4 (22.0) + ROB 3 (9.0) + EFF 3 (11.25) + AUT 4 (15.0)
+ QUA 3 (9.0) + REG 4 (12.0) + FID 3 (9.0)              = 87  Converged-Clean

COR 4 (22.0) + ROB 2 (6.0) + EFF 2 (7.5)  + AUT 3 (11.25)
+ QUA 2 (6.0) + REG 3 (9.0) + FID 2 (6.0)               = 68  just AT threshold

...the same run that skipped the design obligation (FID -> 0):
COR 4 (22.0) + ROB 2 (6.0) + EFF 2 (7.5)  + AUT 3 (11.25)
+ QUA 2 (6.0) + REG 3 (9.0) + FID 0 (0.0)               = 62  Converged-Rough
```

That last line is the point of the rung's weighting: at L6, a strategy that
ships working code and no product/design work **does not clear the threshold**,
which is exactly what `ARTIFACT_GRADIENT.md` §3 promises.

---

## 8. Convergence Signals

### 8.1 Healthy convergence

What a strong strategy's L6 trace looks like:

- **Product before code, briefly.** Personas, JTBD, PRD and a P0/P1-sliced
  backlog land early and cheaply — inside the first 20–30 minutes — and the
  backlog visibly drives the build order. The strategy builds the P0 spine first
  and treats labels/assignee as the P1 they are.
- **The ordering invariant is a design decision, not a discovery.** A-1 is
  resolved and written down *before* the first move endpoint exists. The
  renormalization lives in one service function, inside one transaction, and the
  move endpoint returns the authoritative board because the strategy reasoned
  about how the client would reconcile — not because a rollback test failed.
- **The authorization seam exists from the first protected endpoint.** Ownership
  resolution is a dependency, written once, and every nested entity routes
  through it. The strategy never writes a second `if board.owner_id != user.id`.
- **The keyboard path is designed with the drag, not after it.** The interaction
  spec's state machine and key map are written together, and the pointer and
  keyboard handlers call the *same* move action. Strategies that bolt keyboard
  support on afterwards show up as a late cluster of AC-11/AC-19/AC-21 failures.
- **It runs its own browser.** The strategy launches the app, drives a real drag,
  reloads, and restarts the server itself — early — rather than trusting API
  tests. The single strongest predictor of a clean L6 is whether the strategy
  ever performed a real reload-and-restart check unprompted.
- **A11y is continuous.** axe runs during development, not at the end. Contrast
  and focus tokens exist before components consume them.
- **Design and implementation converge.** Wireframes → hi-fi → tokens → build, in
  that order, with the tokens actually consumed. The design-diff review finds
  nothing because there was nothing to find.
- ≤ 30 iterations, zero interventions, and the first acceptance run passes or
  misses only on a `P1` detail.

### 8.2 Pathological patterns

| Pattern | What it looks like | Telemetry signature |
|---------|--------------------|---------------------|
| **Order lives on the client** | Cards render in the order the store happens to hold; the server never persists an index. Every API test passes. | AC-9 may pass; **AC-10 fails deterministically**. Direct-DB position inspection shows nulls, duplicates, or all-zeros. The exact L6 analogue of L5's in-memory counter. |
| **Sparse / drifting positions** | `position` is set to the target index without renormalizing neighbours, producing gaps and duplicates that only manifest after several moves. | AC-5/AC-6 pass on a 3-card fixture; **AC-7/AC-8 fail**, and the 200-move probe fails hard. Repeated "fixes" that only shrink the drift = tuning, not understanding. |
| **Two implementations of ordering** | One renormalization in the move path, another in the delete path; they disagree. | Regression signature: the ordering group passes cold and fails after the delete group. `oscillations` climbs. |
| **Mouse-only drag** | A drag library dropped in with defaults; no keyboard handler; `role="button"` sprinkled to quiet axe. | **AC-11 fails**, AC-19 fails during grab, AC-21 fails on focus loss. Often accompanied by a comment that keyboard support is "a follow-up" — which is exactly the P1-vs-P0 misjudgement this rung tests. |
| **Optimistic lie** | The card moves in the UI and the failure is swallowed; the board and the server permanently disagree until reload. | **AC-12 fails**; the fault-injection trace shows a 500 with no visible reconciliation. |
| **Authorization at the top only** | `GET /api/boards/{id}` checks ownership; `PATCH /api/cards/{id}` does not, because the card was reached by its own ID. | **AC-15 fails on a nested endpoint**, usually `move`. The adversarial authz sweep finds it even when acceptance nearly does. |
| **Escaping applied inconsistently** | Titles escaped in the card list, rendered raw in the editor or in an error toast. | **AC-17 fails on one surface only** — the tell that escaping was applied per-component rather than by using text rendering throughout. |
| **N+1 board read** | Fetch board, loop columns, loop cards. Fine on the agent's 3-card board. | AC-4's query-count assertion fails; NFR-1 p95 blows out on the 250-card fixture. |
| **A11y bolted on at the end** | A frantic remediation pass after the first axe run; `aria-label` sprayed onto divs; role-based Playwright selectors still can't find anything. | Late cluster of AC-19/AC-20/AC-21/AC-27 failures; iteration count spikes in the last quarter of the run. |
| **Design theater** | `design/` written after the code, narrating what was built; hi-fi that doesn't match; tokens declared but hardcoded hexes in components. | Design-diff findings; token-consumption check fails; caps `FID`. |
| **Backlog with no priorities** | Every item is P0; the build order is arbitrary; labels get built before persistence works. | `FID` finding; EFF degrades as the strategy discovers it built P1 before P0. |
| **Two-toolchain thrash** | Repeated iterations spent on Vite config, proxying, or the build not being served by `make run`. | High `iterations_with_build_failure`; `time_to_healthy_s` never stabilises; often ends as an entrypoint-contract failure the harness reports as "could not start". |
| **Mock-only verification** | The strategy's tests all use `TestClient` and jsdom; a real browser never runs. | Catastrophic browser-tier failure with high self-reported confidence — a strong strategy-level finding, and the same shape as L5's mock-only pathology. |
| **Ambiguity escalation** | An `interventions` entry against A-1..A-7. | Caps `AUT`; note the §0 calibration — a `clarify` on a genuine product ambiguity is low severity, while one on the endpoint table or the ordering invariant is not. |

### 8.3 Instrumentation notes

Beyond the shared `CONVERGENCE_METRICS.md` set, capture for this rung:

| Metric | Why |
|--------|-----|
| `app_start_attempts`, `time_to_healthy_s` | The deliverable can fail to *run* rather than fail to be correct — and at L6 there are two build systems that can each break it. |
| `iterations_with_build_failure` (backend vs frontend, separately) | Distinguishes toolchain thrash from behavioral thrash; a frontend-heavy split is the two-toolchain pathology. |
| `first_real_browser_run_iteration` | At what point did the strategy actually open a browser? Late values correlate strongly with AC-9..AC-12 failures. |
| `self_restart_checks` | Did the strategy stop and restart its own server to verify persistence, unprompted? The single strongest healthy-convergence predictor here. |
| `ordering_invariant_violations` | Raw count of dense-order violations observed across the whole run, with the observed position arrays (e.g. `[0,1,1,3]`) — the shape says whether it's a missing renormalize or a lost transaction. |
| `move_endpoint_5xx` | Server errors specifically on the move path, which is where atomicity bugs surface. |
| `authz_sweep_failures` | Which endpoints leaked, by name — one nested endpoint vs a systemic absence are very different findings. |
| `xss_surfaces_failed` | Which of the six user-text surfaces rendered a payload; a single surface indicates per-component escaping. |
| `axe_violations` by screen and by phase (default vs active-grab) | Separates "inaccessible UI" from "inaccessible interaction", which is the L6-specific accessibility failure. |
| `keyboard_vs_mouse_state_diff` | The literal diff between the two AC-11 snapshots — non-empty means the keyboard path is a different, lesser path. |
| `board_read_query_count` at 50 / 250 cards | The N+1 detector; a count that scales with cards is the whole finding. |
| `drag_perceived_latency_ms` (p50/p95) + host load calibration | Makes an advisory-marked AC-26 auditable. |
| `db_bytes_before_restart` / `after_restart` + file identity | Cheap detection of a boot-time wipe. |
| `design_diff_findings`, `token_consumption_findings`, `openapi_diff_findings` | Feed `FID` with auditable counts rather than a vibe. |
| `p0_failures` (list) vs `p1_failures` (list) | The gate is two-part; the score report must say *which* part failed and which criteria, because "failed AC-10" and "failed AC-28" describe very different strategies. |
