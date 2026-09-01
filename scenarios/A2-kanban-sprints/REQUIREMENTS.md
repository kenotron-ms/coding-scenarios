# A2 — Kanban Sprints — REQUIREMENTS

> Capstone rung. Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> artifact obligations per `framework/ARTIFACT_GRADIENT.md` row **A2**.
>
> **Relationship to A1.** A2 delivers the *same application* as
> `scenarios/A1-kanban-app` — same personas, same data model, same endpoint
> surface, same NFR floors. Nothing here contradicts A1; A2 only changes the
> **delivery process** from "build it once" to "build it in five scripted
> sprints, and never break what you already shipped." Where this document
> restates A1 material it is for self-containment; where the two disagree, A1 is
> authoritative for the *application* and A2 is authoritative for the *process*.

---

## 0. Scenario Summary

- **Level:** A2 (top of ladder)
- **Codename / dir:** `A2-kanban-sprints`
- **One-liner:** Deliver the A1 Kanban application as a scripted sequence of five
  agile sprints, each adding features against its own acceptance criteria, while
  a **cumulative regression suite** assembled from all prior sprints must stay
  **100% green at every sprint boundary**.
- **New difficulty introduced:** **Iterative multi-sprint delivery under
  cumulative regression pressure**, plus the continuous product/design machinery
  of agile — a groomed backlog spanning all sprints, per-sprint goals and
  acceptance, usability feedback that feeds the next sprint, retrospectives, and
  design that *evolves* per sprint rather than being fixed up front. Every rung
  below asks "can you get it working?" This rung asks **"can you keep working
  software working while you extend it?"** That is the entire point of A2, and
  it is why `REG` carries more weight here than `COR`.
- **Estimated reference solution size:** cumulative **3,000–4,500 LoC across
  45–70 files** at Sprint 4, plus ~25 product/design artifact files. Per-sprint
  deltas:

  | Sprint | Δ LoC | Δ files | Cumulative LoC | Cumulative files |
  |--------|-------|---------|----------------|------------------|
  | 0 — MVP | ~900 | ~18 | ~900 | ~18 |
  | 1 — Drag & order | ~400 | ~5 | ~1,300 | ~23 |
  | 2 — Auth & multi-user | ~600 | ~9 | ~1,900 | ~32 |
  | 3 — Labels/filter/search | ~700 | ~10 | ~2,600 | ~42 |
  | 4 — Activity + real-time | ~700 | ~9 | ~3,300 | ~51 |

- **Time budget:** **8 h wall-clock ceiling total** — a 30-minute *inception*
  block (research → PRD → groomed backlog, before Sprint 0 starts) plus **90
  minutes per sprint** × 5. Boundary verification time (harness-side) is not
  charged to the strategy.
- **Iteration budget:** **soft 20 / hard 50 edit→verify cycles per sprint**;
  cumulative soft 100 / hard 250. Iteration counters **reset at each sprint
  boundary** and are also reported cumulatively — the *shape* of the per-sprint
  curve is the signal (see §8.3).
- **Intervention budget:** **0.** Any `rescue` caps `AUT ≤ 1` for the whole
  scenario, not just the sprint in which it occurred.

```
Budget summary (mirrored into manifest.yaml §2.5)

Block        Wall-clock   Iter soft/hard   Token budget
inception       1,800 s        — / —            0.5 M
sprint 0        5,400 s       20 / 50           1.5 M
sprint 1        5,400 s       20 / 50           1.5 M
sprint 2        5,400 s       20 / 50           1.5 M
sprint 3        5,400 s       20 / 50           1.5 M
sprint 4        5,400 s       20 / 50           1.5 M
TOTAL          28,800 s      100 / 250          8.0 M
```

---

## 1. Product Requirements

### 1.1 Problem statement

A small delivery team tracks work on sticky notes and a spreadsheet. Neither
survives contact with reality: the spreadsheet loses ordering, nobody can see
who changed what, and remote members work from a stale photo of a whiteboard.
They need a **shared, durable, web-based Kanban board** — columns of cards they
can reorder by hand, owned by a real account, filterable when the board grows
past a screenful, and honest about what changed and when.

They also cannot wait six months for it. The product is delivered **incrementally**:
each sprint must ship something the team can actually use on Monday, and no
sprint may take away a capability the team already depends on. That constraint —
*ship forward without breaking backward* — is the requirement this scenario
exists to evaluate.

### 1.2 Target users / personas

**Required** artifact (`ARTIFACT_GRADIENT.md` A2). The strategy must author these
into `design/research/personas.md`; the four below are the canonical set carried
over from A1 and must be preserved, not replaced.

| Persona | Role | Primary jobs | Sprints that serve them |
|---------|------|--------------|-------------------------|
| **Priya Raman** — Delivery Lead | Owns the board, runs standup | See flow at a glance; reorder priorities live during standup; know what moved yesterday | S0, S1, S3, S4 |
| **Marco Silva** — IC engineer | Works cards daily | Find *my* cards fast; move a card to Done without ceremony; not lose work | S0, S1, S3 |
| **Jules Okafor** — Cross-functional stakeholder | Reads, rarely writes | Check status without interrupting anyone; see recent activity; watch it update live during a call | S2, S4 |
| **Sam Whitfield** — keyboard-only / screen-reader user | Any of the above roles | Do *everything* — including reordering cards — without a mouse; be told when the board changes underneath them | Every sprint (WCAG 2.1 AA is a per-sprint gate, not a Sprint-4 cleanup) |

Sam is not decoration. Drag-and-drop (Sprint 1) and live updates (Sprint 4) are
exactly the two features that most often ship inaccessible, so Sam's needs are
written into those sprints' acceptance criteria (AC-1.6, AC-4.6).

### 1.3 User stories

Stories are grouped by the sprint that delivers them. IDs are `US-{sprint}.{n}`
and every one must trace to at least one `FR-{sprint}.{n}` and one
`AC-{sprint}.{n}`.

**Sprint 0 — MVP**
- **US-0.1** As Priya, I want to create a board with named columns, so that the
  team's workflow is represented on screen.
- **US-0.2** As Marco, I want to add, edit, and delete cards in a column, so that
  the board reflects real work.
- **US-0.3** As Priya, I want the board to still be there tomorrow, so that we
  can trust it instead of the whiteboard.
- **US-0.4** As Sam, I want to reach every control by keyboard with a visible
  focus ring, so that I can use the board at all.

**Sprint 1 — Drag & drop and ordering**
- **US-1.1** As Marco, I want to drag a card to a different position in its
  column, so that priority order is visible.
- **US-1.2** As Priya, I want to drag a card into another column, so that I can
  advance work during standup.
- **US-1.3** As Marco, I want my ordering to survive a reload, so that I don't
  redo it every morning.
- **US-1.4** As Sam, I want a keyboard equivalent for moving cards, so that
  reordering isn't a mouse-only feature.

**Sprint 2 — Auth & multi-user**
- **US-2.1** As Priya, I want to register and log in, so that my boards are mine.
- **US-2.2** As Priya, I want other accounts to be unable to see or change my
  boards, so that I can use this for real work.
- **US-2.3** As Jules, I want to log out on a shared machine and know the session
  is actually dead, so that nobody inherits my access.
- **US-2.4** As Priya, I want the board I built *before* accounts existed to
  still be there after I register, so that upgrading didn't cost me my data.

**Sprint 3 — Labels, filters & search**
- **US-3.1** As Priya, I want to attach colored labels to cards, so that
  categories are visible without opening each card.
- **US-3.2** As Priya, I want to assign a card to a team member, so that
  ownership is explicit.
- **US-3.3** As Marco, I want to filter the board by label and assignee, so that
  I can see only my work.
- **US-3.4** As Marco, I want to search card text, so that I can find a card I
  half-remember.
- **US-3.5** As Sam, I want filter state announced and reachable by keyboard, so
  that filtering is usable without sight or a mouse.

**Sprint 4 — Activity feed & real-time**
- **US-4.1** As Priya, I want a per-board activity log, so that standup starts
  from facts.
- **US-4.2** As Jules, I want the board to update live while I watch it, so that
  I'm not reading a stale screen during a call.
- **US-4.3** As Marco, I want to be told when my connection drops and when it
  recovers, so that I know whether what I see is current.
- **US-4.4** As Sam, I want live changes announced politely by my screen reader,
  so that the board doesn't silently change under me.

### 1.4 Functional requirements

Convention: `FR-{sprint}.{n}`. A requirement introduced in sprint *N* is
**permanent** — it remains in force, and under test, for every sprint after *N*.
There is no sunset clause and no "temporarily disabled while I refactor."

**Sprint 0 — MVP (no auth; a single implicit user)**
- **FR-0.1** Create, read, update, delete **boards** (`name`, non-empty, ≤ 120 chars).
- **FR-0.2** Create, read, update, delete **columns** within a board (`name`,
  non-empty, ≤ 60 chars). Deleting a column deletes its cards (cascade).
- **FR-0.3** Create, read, update, delete **cards** within a column (`title`
  non-empty ≤ 200 chars; `description` optional ≤ 4,000 chars).
- **FR-0.4** All state is **durably persisted**; a full process restart loses
  nothing.
- **FR-0.5** A single implicit owner is assumed. No login exists; the API is
  unauthenticated at this sprint. (Sprint 2 replaces this — see FR-2.5.)
- **FR-0.6** `GET /api/boards/{id}` returns the board with its columns and cards
  in a **stable, documented order** (see §2.1) in one round trip.
- **FR-0.7** Validation failures return `400` with a structured error envelope
  (§2.1); unknown IDs return `404`. No 5xx on user-supplied bad input.
- **FR-0.8** The SPA renders a board, supports all CRUD from the UI, and shows
  empty / loading / error states for board, column, and card surfaces.

**Sprint 1 — Drag & drop and ordering**
- **FR-1.1** Cards carry a **persisted position** within their column; the
  board read (FR-0.6) returns cards in position order, deterministically.
- **FR-1.2** A card can be **reordered within its column** to any target index.
- **FR-1.3** A card can be **moved across columns** to any target index in the
  destination column.
- **FR-1.4** Columns themselves can be reordered within a board.
- **FR-1.5** After any move, the server returns and persists a **canonical dense
  ordering** (`0..n-1`, no gaps, no duplicates) per column. Deleting a card
  renormalizes the remaining cards.
- **FR-1.6** Ordering survives reload and process restart (composes with FR-0.4).
- **FR-1.7** Drag-and-drop in the SPA has a **keyboard-operable equivalent**
  (grab / move / drop, with a documented key mapping) that produces identical
  server state.
- **FR-1.8** A move that fails server-side is **reconciled in the UI** — the card
  returns to its true position and an error is surfaced. No permanent optimistic lie.

**Sprint 2 — Auth & multi-user**
- **FR-2.1** `register(email, password)` creates an account; email is unique and
  case-insensitive; password minimum 8 characters, stored only as a salted hash
  (§3.3).
- **FR-2.2** `login` establishes a server-side session, delivered as an
  `HttpOnly; SameSite=Lax` cookie. `logout` **invalidates the session
  server-side** — replaying the old cookie fails.
- **FR-2.3** Every board is **owned** by exactly one user account.
- **FR-2.4** **Authorization invariant:** a request from user *B* for a board
  owned by user *A* — read, write, move, or delete, on the board or any of its
  columns/cards — is denied. The denial does not leak existence (see §1.6-4).
- **FR-2.5** All board/column/card endpoints now require an authenticated
  session; unauthenticated requests receive `401`.
- **FR-2.6** Data created in Sprints 0–1 (before accounts existed) is
  **preserved** and attributed to an owner by the migration (see §1.6-6).
- **FR-2.7** The SPA gains register / login / logout screens, an authenticated
  shell, and a session-expired flow that returns the user to login without
  losing their place silently.
- **FR-2.8** **All Sprint 0 and Sprint 1 behavior is unchanged** once
  authenticated. Auth is a gate in front of the app, not a rewrite of it.

**Sprint 3 — Labels, filters & search**
- **FR-3.1** A board owns a set of **labels** (`name` ≤ 40 chars, `color` as a
  hex triplet). CRUD on labels is board-scoped.
- **FR-3.2** A card may carry zero or more labels (many-to-many, board-scoped:
  a card cannot hold a label from another board).
- **FR-3.3** A board owns a **member roster** (`name` ≤ 80 chars, optional
  `email`). A card may have zero or one `assignee` drawn from that roster.
  > Roster entries are **board-scoped data, not user accounts**. They grant no
  > access whatsoever. FR-2.4's authorization invariant is untouched by this
  > feature — this is an extension, not a contradiction.
- **FR-3.4** The board view can be **filtered** by label(s) and assignee(s).
  Semantics are fixed (not ambiguous): **OR within a facet, AND across facets**
  — `label ∈ {A,B} AND assignee ∈ {M}`.
- **FR-3.5** **Text search** across cards matches case-insensitively on `title`
  and `description`. Minimum contract: substring match. Composable with filters
  (AND).
- **FR-3.6** Filtering and search are **server-side** and correct for boards
  larger than one page of cards; the client must not fake it by filtering only
  what it happens to have loaded.
- **FR-3.7** Filter/search state is reflected in the URL and survives reload.
- **FR-3.8** An active filter that matches nothing shows an explicit empty state
  with a one-click clear — not a blank board indistinguishable from data loss.
- **FR-3.9** Filtering **never mutates** stored positions. Clearing the filter
  restores the exact prior order.

**Sprint 4 — Activity feed & real-time**
- **FR-4.1** Every mutation of a board, column, card, label, or assignment
  appends an **activity record** (`actor`, `verb`, `entity`, `at`, payload).
- **FR-4.2** `GET /api/boards/{id}/activity` returns the board's activity,
  newest first, paginated, authorized by FR-2.4.
- **FR-4.3** Activity records are **immutable** — no edit or delete endpoint.
- **FR-4.4** A mutation by one client is **pushed to other viewers of the same
  board** over WebSocket or SSE (strategy's choice, §1.6-2) within the NFR-9
  budget, without a manual refresh.
- **FR-4.5** The live channel is **authorized**: a client may only subscribe to
  boards it is permitted to read (FR-2.4 applies to the socket, not just to REST).
- **FR-4.6** The receiving client applies the update **without losing local
  state** — an open card editor, an active filter, and scroll position all survive
  an incoming update.
- **FR-4.7** Connection state is visible (`connected` / `reconnecting` / `stale`),
  and on reconnect the client **backfills missed events** so the board converges
  to server truth.
- **FR-4.8** Concurrent conflicting moves converge: after both clients settle,
  both show the **same ordering**, and that ordering equals the server's. No
  duplicated, ghosted, or vanished cards.

### 1.5 Out of scope

Explicit non-goals, for all five sprints. Building these is scope creep and is
penalized under `FID` and `EFF`:

- Board **sharing** between accounts, roles, or a permissions matrix (ownership
  is single-owner; roster entries are labels-for-humans, not accounts).
- Comments, attachments, checklists, due dates, swimlanes, WIP limits, card
  archive, undo/redo beyond what the activity log records.
- Email, notifications, invitations, password reset, OAuth/SSO, MFA.
- Collaborative rich-text editing / CRDT merge of card bodies. Real-time here
  means *broadcast of committed mutations*, not co-editing.
- Offline mode, native mobile apps, i18n/l10n, theming beyond the design tokens.
- Multi-team / organization / workspace hierarchy.
- Horizontal scale-out, sharding, or a separate cache tier.

### 1.6 Ambiguities the agent must resolve

Deliberate under-specification. Each must be **resolved, documented** (in the
sprint plan or an ADR), and **applied consistently**. Acceptance tests probe the
invariant, not the choice.

| # | Ambiguity | Acceptable resolutions | What acceptance actually asserts |
|---|-----------|------------------------|----------------------------------|
| 1 | **Position encoding** (Sprint 1) | Dense integers with renormalization on write, **or** fractional/gapped keys with periodic compaction | `GET` returns a total order that is stable, gap-free after settle, and idempotent under repeated identical moves |
| 2 | **Transport for live updates** (Sprint 4) | WebSocket **or** SSE (+ REST for writes) | Update propagates within NFR-9; reconnect backfills; channel is authorized |
| 3 | **Search semantics** (Sprint 3) | Case-insensitive substring is the floor; token/prefix/FTS is allowed on top | The substring floor holds; documented semantics match observed behavior |
| 4 | **Denial code for cross-user access** (Sprint 2) | `404` (no existence leak) **or** `403` — pick one and apply it everywhere | The response is *identical* for "board owned by someone else" and "board that does not exist" if `404` is chosen; never `200`, never a body containing another user's data |
| 5 | **Optimistic vs pessimistic drag UI** (Sprint 1) | Either | Server state is authoritative; a rejected move is visibly reconciled (FR-1.8) |
| 6 | **Fate of pre-auth data** (Sprint 2) — the load-bearing one | (a) Bind existing rows to the first account registered after migration; (b) create a seeded `legacy@local` owner and transfer on first login; (c) an explicit one-time claim flow | **No data loss.** Every board/column/card that existed at the Sprint-1 boundary still exists, with intact ordering, and is reachable by exactly one authenticated user. Silently deleting pre-auth data is an automatic Sprint-2 failure |
| 7 | **Session lifetime** | Any documented value ≥ 30 min | Logout invalidates immediately regardless; expiry behaves as documented |
| 8 | **Activity granularity** (Sprint 4) | Per-mutation, or coalesced bursts within a stated window | Every FR-4.1 mutation class is represented; coalescing is documented and does not drop classes |

### 1.7 SPRINT SEQUENCE — the scripted delivery plan

This is the spine of A2. The sequence is **fixed** (`VISION.md` §5, fork 5): a
fixed app + fixed sprint script isolates the *strategy* as the only variable, so
two strategies produce comparable scores. The strategy does not get to reorder,
merge, or skip sprints. It grooms and estimates *within* each sprint's backlog.

**Rules that bind every sprint:**

1. Sprints execute in order 0 → 4. A sprint begins only after the previous one's
   boundary verification **passes**.
2. Each sprint has its own **goal**, **backlog**, **acceptance criteria (AC)**,
   **Definition of Done (DoD)**, and **regression gate**.
3. The regression gate is **cumulative and non-negotiable**: at the boundary of
   sprint *N*, the union of acceptance suites `0..N-1` must pass at **100%**,
   alongside sprint *N*'s own suite at **100%**.
4. Prior-sprint behavior may be *extended*, never *removed*. If a Sprint-2 change
   makes a Sprint-0 assertion fail, that is a **regression**, not a "requirements
   update," and it caps `REG` for the entire scenario (§7.2.1).
5. Each sprint ends with a written **retrospective** and an updated **backlog**;
   each of Sprints 1, 2, 3 additionally ends with a **usability evaluation**
   whose findings must be groomed into the next sprint's backlog (§5.1).
6. Schema changes ship as **versioned forward migrations**. The harness will run
   a migration-safety probe against a fixture database built at an earlier
   sprint's schema (§6.3, NFR-10).

---

#### Sprint 0 — MVP: boards, columns, cards, durable persistence

**Sprint goal.** *"A team can open the app, build a board with columns and cards,
close the laptop, and find it all there tomorrow."*

**Backlog**

| ID | Item | FRs | Est | Pri |
|----|------|-----|-----|-----|
| B-0.1 | Data model + migration `0001_init` (board, column, card) | FR-0.1–0.4 | 3 | P0 |
| B-0.2 | Board/column/card CRUD API + error envelope | FR-0.1–0.3, 0.7 | 5 | P0 |
| B-0.3 | Aggregate board read in one round trip | FR-0.6 | 2 | P0 |
| B-0.4 | Durable persistence + restart survival | FR-0.4 | 2 | P0 |
| B-0.5 | SPA: board view, column view, card create/edit/delete | FR-0.8 | 5 | P0 |
| B-0.6 | Empty / loading / error states | FR-0.8 | 2 | P1 |
| B-0.7 | Keyboard reachability + focus visibility + landmarks | NFR-4 | 3 | P0 |
| B-0.8 | Lo-fi wireframes, design tokens v1, a11y annotations v1 | §5.3 | 3 | P0 |

**Acceptance criteria**

| AC | Criterion | Verified by |
|----|-----------|-------------|
| AC-0.1 | Board CRUD round-trips over live HTTP; created board is readable, updatable, deletable | API |
| AC-0.2 | Column CRUD works; deleting a column cascades its cards | API |
| AC-0.3 | Card CRUD works; field limits enforced with `400` + error envelope | API |
| AC-0.4 | Kill and restart the server process — all boards/columns/cards are intact | API + process control |
| AC-0.5 | `GET /api/boards/{id}` returns the full nested board in one call, in stable order | API |
| AC-0.6 | Malformed/oversized/empty payloads return `400`, never 5xx; unknown IDs return `404` | API |
| AC-0.7 | E2E: create board → add two columns → add three cards → reload → everything present | Playwright |
| AC-0.8 | E2E: all Sprint-0 flows completable by keyboard alone; focus is always visible | Playwright + axe |
| AC-0.9 | Zero critical/serious axe violations on the board view | axe-core |

**Definition of Done** — see §4.2 for the canonical checklist. Sprint 0 instance:
- [ ] AC-0.1 … AC-0.9 at 100%
- [ ] Regression gate: *(none — this is the baseline)*
- [ ] `design/wireframes/`, `design/tokens/`, `design/a11y/` v1 landed
- [ ] `design/sprints/sprint-0.md` (goal + backlog + AC + DoD) and
      `design/retros/retro-0.md` written
- [ ] Lint/type/format clean; migration `0001` applies to an empty DB

**Regression gate.** None. Sprint 0 **defines** the baseline. Its acceptance
suite is frozen at the boundary and becomes regression input for Sprints 1–4.

---

#### Sprint 1 — Drag & drop and ordering

**Sprint goal.** *"Priya can reprioritize the board live during standup by
dragging cards, and the order is still right after everyone reloads."*

**Backlog**

| ID | Item | FRs | Est | Pri |
|----|------|-----|-----|-----|
| B-1.1 | Migration `0002`: add `position` to cards/columns, backfill existing rows | FR-1.1, 1.4, NFR-10 | 3 | P0 |
| B-1.2 | `PATCH /api/cards/{id}/move` (within-column and cross-column) | FR-1.2, 1.3 | 5 | P0 |
| B-1.3 | Canonical dense ordering + renormalization on delete | FR-1.5 | 3 | P0 |
| B-1.4 | `PATCH /api/columns/{id}/move` | FR-1.4 | 2 | P1 |
| B-1.5 | SPA drag-and-drop with drop targets and drag affordances | FR-1.2, 1.3 | 5 | P0 |
| B-1.6 | Keyboard move mode (grab/move/drop) + documented key map | FR-1.7 | 5 | P0 |
| B-1.7 | Failure reconciliation on rejected move | FR-1.8 | 3 | P1 |
| B-1.8 | Interaction/state spec for drag; a11y annotations updated | §5.3 | 3 | P0 |

**Acceptance criteria**

| AC | Criterion | Verified by |
|----|-----------|-------------|
| AC-1.1 | Move a card to any index in its column; read-back order matches exactly | API |
| AC-1.2 | Move a card to any index in another column; both columns renormalize to `0..n-1` | API |
| AC-1.3 | Deleting a middle card leaves the survivors dense and correctly ordered | API |
| AC-1.4 | Repeating the identical move is idempotent — no drift, no duplicates | API |
| AC-1.5 | E2E: drag a card across columns, hard-reload, order persists; restart server, order persists | Playwright |
| AC-1.6 | E2E: perform the same two moves using **only** the keyboard; final server state is byte-identical to the mouse path | Playwright |
| AC-1.7 | A move rejected by the server (stale/invalid target) visibly snaps back with an error message | Playwright + fault injection |
| AC-1.8 | Column reorder persists across reload | API + Playwright |
| AC-1.9 | Zero critical/serious axe violations, including during an active drag/grab state | axe-core |

**DoD.** §4.2 checklist + AC-1.x at 100% + regression gate below + drag
interaction spec landed + `sprint-1.md`, `retro-1.md`, `usability/session-1.md`.

**Regression gate.** `acceptance/sprint-0` at **100%**. Specifically watched:
cascade delete (AC-0.2), restart durability (AC-0.4), and the Sprint-0 keyboard
path (AC-0.8) — adding drag is the classic way to break tab order.

---

#### Sprint 2 — Auth & multi-user

**Sprint goal.** *"The board is mine. I can register, log in, and be certain
nobody else can read or touch my boards — and the board I built last sprint is
still exactly where I left it."*

**Backlog**

| ID | Item | FRs | Est | Pri |
|----|------|-----|-----|-----|
| B-2.1 | Migration `0003`: `user`, `session`, `board.owner_id`; **attribute pre-auth rows** (§1.6-6) | FR-2.1–2.3, 2.6, NFR-10 | 5 | P0 |
| B-2.2 | Register / login / logout / me endpoints; hashed passwords | FR-2.1, 2.2 | 5 | P0 |
| B-2.3 | Session middleware; `401` on unauthenticated | FR-2.5 | 3 | P0 |
| B-2.4 | Ownership authorization on **every** board/column/card path | FR-2.4 | 5 | P0 |
| B-2.5 | SPA auth screens + authenticated shell + session-expired flow | FR-2.7 | 5 | P0 |
| B-2.6 | Verify Sprint 0/1 flows unchanged post-auth | FR-2.8 | 3 | P0 |
| B-2.7 | Auth hi-fi mockups, error/empty states, a11y annotations for forms | §5.3 | 3 | P0 |
| B-2.8 | Findings from `usability/session-1.md` groomed in | §5.1 | 2 | P1 |

**Acceptance criteria**

| AC | Criterion | Verified by |
|----|-----------|-------------|
| AC-2.1 | Register → login → authenticated request succeeds; duplicate email rejected; weak password rejected | API |
| AC-2.2 | Passwords are never stored or returned in plaintext; hash is salted and slow (bcrypt/argon2/scrypt) | API + DB inspection |
| AC-2.3 | Logout invalidates server-side; replaying the cookie afterwards yields `401` | API |
| AC-2.4 | **Authz matrix:** user B receives the chosen denial code on every read/write/move/delete path of user A's board, columns, and cards — enumerated endpoint by endpoint | API |
| AC-2.5 | Unauthenticated requests to app endpoints yield `401`, not `200` and not 5xx | API |
| AC-2.6 | Pre-auth fixture data survives migration `0003` with ordering intact and is owned by exactly one account | Migration probe |
| AC-2.7 | E2E: register → log in → build a board → log out → log back in → board is there | Playwright |
| AC-2.8 | E2E: two browser contexts, two accounts; B cannot navigate to A's board by direct URL | Playwright |
| AC-2.9 | Session cookie is `HttpOnly` and `SameSite`; not readable from `document.cookie` | Playwright |
| AC-2.10 | Zero critical/serious axe violations on auth screens; form errors are programmatically associated with their inputs | axe-core |

**DoD.** §4.2 + AC-2.x at 100% + regression gate + auth designs landed +
`sprint-2.md`, `retro-2.md`, `usability/session-2.md`.

**Regression gate.** `acceptance/sprint-0 ∪ sprint-1` at **100%**, re-run **as an
authenticated user**. The harness supplies a logged-in session to prior-sprint
suites; every Sprint 0/1 assertion must otherwise be unchanged. Specifically
watched: drag/move endpoints still work identically behind auth (the most common
A2 regression is an authz refactor that quietly breaks `move`), and dense
ordering survives migration `0003`.

---

#### Sprint 3 — Labels, filters & search

**Sprint goal.** *"When the board grows past a screenful, Marco can still find
his work in under five seconds."*

**Backlog**

| ID | Item | FRs | Est | Pri |
|----|------|-----|-----|-----|
| B-3.1 | Migration `0004`: `label`, `card_label`, `board_member`, `card.assignee_id` | FR-3.1–3.3, NFR-10 | 3 | P0 |
| B-3.2 | Label CRUD (board-scoped) + card↔label assignment | FR-3.1, 3.2 | 5 | P0 |
| B-3.3 | Board member roster CRUD + card assignee | FR-3.3 | 3 | P0 |
| B-3.4 | Server-side filter (label/assignee) with OR-within/AND-across semantics | FR-3.4, 3.6 | 5 | P0 |
| B-3.5 | Server-side text search over title+description | FR-3.5, 3.6 | 3 | P0 |
| B-3.6 | Filter bar + search UI; label chips; assignee picker | FR-3.4, 3.5 | 5 | P0 |
| B-3.7 | URL-reflected filter state; filtered empty state with clear action | FR-3.7, 3.8 | 3 | P1 |
| B-3.8 | Filter/search UI mockups; label color tokens with contrast proof; a11y annotations | §5.3, NFR-4 | 3 | P0 |
| B-3.9 | Findings from `usability/session-2.md` groomed in | §5.1 | 2 | P1 |

**Acceptance criteria**

| AC | Criterion | Verified by |
|----|-----------|-------------|
| AC-3.1 | Label CRUD works and is board-scoped; a card cannot take a label from another board (`400`/`404`) | API |
| AC-3.2 | Card↔label assignment is many-to-many; removing a label from a board removes it from its cards without deleting the cards | API |
| AC-3.3 | Roster CRUD works; assigning an off-roster assignee is rejected; roster entries grant **no** access (FR-2.4 still holds) | API |
| AC-3.4 | Filter semantics exactly match OR-within-facet / AND-across-facet on a seeded fixture board | API |
| AC-3.5 | Search is case-insensitive substring over title **and** description, composable with filters | API |
| AC-3.6 | Filtering is server-side: a board larger than the client's initial page still filters correctly | API |
| AC-3.7 | Clearing a filter restores the exact pre-filter ordering; positions are unchanged in the DB | API |
| AC-3.8 | E2E: apply label + assignee filter, reload the URL, filter state is restored | Playwright |
| AC-3.9 | E2E: a filter matching nothing shows the empty state and a working clear action | Playwright |
| AC-3.10 | Label/assignee/search text is **escaped** — a `<script>` payload in a name renders as text | Playwright + adversarial |
| AC-3.11 | Zero critical/serious axe violations; label chips meet contrast; filter state is announced via a live region | axe-core + Playwright |

**DoD.** §4.2 + AC-3.x at 100% + regression gate + filter/search mockups landed +
`sprint-3.md`, `retro-3.md`, `usability/session-3.md`.

**Regression gate.** `acceptance/sprint-0 ∪ 1 ∪ 2` at **100%**. Specifically
watched: FR-3.9 (filtering must not touch stored positions — the classic
"filtered view wrote back its indices and destroyed the board's order" bug), the
full Sprint-2 authz matrix now that new board-scoped entities exist (labels,
roster, and their endpoints must be authorized too), and Sprint-1 drag behavior
while a filter is active.

---

#### Sprint 4 — Activity feed & real-time

**Sprint goal.** *"Jules can leave the board open during a call and watch it
change as Priya works, with a feed that says who did what."*

**Backlog**

| ID | Item | FRs | Est | Pri |
|----|------|-----|-----|-----|
| B-4.1 | Migration `0005`: `activity` table + indexes | FR-4.1, NFR-10 | 2 | P0 |
| B-4.2 | Activity write on every mutation class (single choke point, not sprinkled) | FR-4.1, 4.3 | 5 | P0 |
| B-4.3 | `GET /boards/{id}/activity` paginated + authorized | FR-4.2 | 3 | P0 |
| B-4.4 | Live channel (WS or SSE): subscribe, authorize, broadcast | FR-4.4, 4.5 | 8 | P0 |
| B-4.5 | Client apply-without-clobber (open editor / filter / scroll preserved) | FR-4.6 | 5 | P0 |
| B-4.6 | Connection status UI + reconnect with event backfill | FR-4.7 | 5 | P0 |
| B-4.7 | Concurrent-move convergence | FR-4.8 | 5 | P0 |
| B-4.8 | Activity feed panel design + real-time state spec + live-region a11y | §5.3 | 3 | P0 |
| B-4.9 | Findings from `usability/session-3.md` groomed in | §5.1 | 2 | P1 |

**Acceptance criteria**

| AC | Criterion | Verified by |
|----|-----------|-------------|
| AC-4.1 | Every mutation class (board/column/card create-update-delete, move, label, assign) appends exactly one activity record with actor, verb, entity, timestamp | API |
| AC-4.2 | Activity is newest-first, paginates correctly, and is authorized — user B gets denial on user A's board activity | API |
| AC-4.3 | No endpoint exists to edit or delete activity records | API |
| AC-4.4 | **Two live clients:** a card moved in client 1 appears moved in client 2 within NFR-9's budget, with no manual refresh | Playwright, 2 contexts |
| AC-4.5 | Client 2 has an open card editor, an active filter, and a scrolled column; an incoming update preserves all three | Playwright, 2 contexts |
| AC-4.6 | Live updates are announced via an ARIA live region; the feed is keyboard-navigable | Playwright + axe |
| AC-4.7 | Killing client 2's channel and restoring it backfills the events it missed; the board converges to server truth | Playwright + fault injection |
| AC-4.8 | Two clients issuing conflicting moves converge to one identical ordering, equal to the server's; no duplicate/ghost/lost cards | Playwright, 2 contexts, repeated trials |
| AC-4.9 | A client without read permission cannot subscribe to a board's channel and receives no events for it | Live-channel probe |
| AC-4.10 | Zero critical/serious axe violations on board + feed | axe-core |

**DoD.** §4.2 + AC-4.x at 100% + regression gate + feed design and real-time
state spec landed + `sprint-4.md`, `retro-4.md`.

**Regression gate.** `acceptance/sprint-0 ∪ 1 ∪ 2 ∪ 3` at **100%** — the full
cumulative suite. Specifically watched: activity writes must not slow mutations
past NFR-1; the broadcast path must not bypass authorization (FR-2.4 on the
socket); optimistic local updates must not resurrect the Sprint-1 ordering bugs;
and the Sprint-3 filter must not be silently reset by every incoming event.

---

#### Sprint boundary summary

| Boundary | Current AC | Cumulative regression | ≈ assertions at gate |
|----------|-----------|-----------------------|----------------------|
| End S0 | AC-0.1…0.9 | — | ~40 |
| End S1 | AC-1.1…1.9 | S0 | ~70 |
| End S2 | AC-2.1…2.10 | S0 ∪ S1 | ~105 |
| End S3 | AC-3.1…3.11 | S0 ∪ S1 ∪ S2 | ~145 |
| End S4 | AC-4.1…4.10 | S0 ∪ S1 ∪ S2 ∪ S3 | ~175 |

The gate is `100%` of *both* columns at every row. There is no partial credit at
a boundary; there is partial credit only in the rubric that scores *how* you got
there.

---

## 2. Technical Requirements

### 2.1 Interface / API contract

Same surface as A1, introduced incrementally. Every endpoint below is permanent
from the sprint that introduces it.

```
# Sprint 0 — MVP
GET    /api/boards                       -> [BoardSummary]
POST   /api/boards                       {name}                    -> Board
GET    /api/boards/{board_id}            -> BoardDetail (nested columns -> cards)
PATCH  /api/boards/{board_id}            {name?}                   -> Board
DELETE /api/boards/{board_id}            -> 204

POST   /api/boards/{board_id}/columns    {name}                    -> Column
PATCH  /api/columns/{column_id}          {name?}                   -> Column
DELETE /api/columns/{column_id}          -> 204   # cascades cards

POST   /api/columns/{column_id}/cards    {title, description?}     -> Card
GET    /api/cards/{card_id}              -> Card
PATCH  /api/cards/{card_id}              {title?, description?}    -> Card
DELETE /api/cards/{card_id}              -> 204

GET    /api/health                       -> {status, version, schema_version}

# Sprint 1 — ordering
PATCH  /api/cards/{card_id}/move         {column_id, position}     -> BoardDetail
PATCH  /api/columns/{column_id}/move     {position}                -> BoardDetail
#   `position` is a 0-based TARGET INDEX in the destination list.
#   The server is responsible for producing a canonical dense order (FR-1.5)
#   and returns the affected board so the client can reconcile authoritatively.

# Sprint 2 — auth
POST   /api/auth/register                {email, password}         -> User (201)
POST   /api/auth/login                   {email, password}         -> User + Set-Cookie
POST   /api/auth/logout                  -> 204   # server-side invalidation
GET    /api/auth/me                      -> User | 401

# Sprint 3 — labels, roster, filter, search
POST   /api/boards/{board_id}/labels     {name, color}             -> Label
GET    /api/boards/{board_id}/labels     -> [Label]
PATCH  /api/labels/{label_id}            {name?, color?}           -> Label
DELETE /api/labels/{label_id}            -> 204
PUT    /api/cards/{card_id}/labels       {label_ids: [..]}         -> Card

POST   /api/boards/{board_id}/members    {name, email?}            -> Member
GET    /api/boards/{board_id}/members    -> [Member]
DELETE /api/members/{member_id}          -> 204
PATCH  /api/cards/{card_id}              {assignee_id?}            -> Card

GET    /api/boards/{board_id}/cards?label=<id>&label=<id>
                                        &assignee=<id>&q=<text>    -> [Card]
#   repeated facet params = OR within facet; distinct facets = AND (FR-3.4)

# Sprint 4 — activity + real-time
GET    /api/boards/{board_id}/activity?limit=&before=              -> [Activity]
GET    /api/boards/{board_id}/events     -> SSE stream      # if SSE chosen
WS     /api/boards/{board_id}/socket     -> event stream    # if WS chosen
```

**Error envelope** (Sprint 0 onward, unchanged forever — changing its shape in a
later sprint is a regression):

```json
{
  "error": {
    "code": "validation_error",
    "message": "title must be 1-200 characters",
    "field": "title"
  }
}
```

**Live event envelope** (Sprint 4):

```json
{
  "seq": 1487,
  "board_id": "b_01H...",
  "type": "card.moved",
  "actor": "u_01H...",
  "at": "2026-08-24T10:31:02.441Z",
  "data": { "card_id": "c_01H...", "from": {"column_id": "...", "position": 3},
            "to":   {"column_id": "...", "position": 0} }
}
```

`seq` is a monotonically increasing per-board sequence number. It exists so that
FR-4.7 backfill (`?since=<seq>`) is implementable and testable; the harness uses
gaps in `seq` to detect dropped events.

### 2.2 Architecture constraints

- **Layering, enforced:** `api/` (HTTP + serialization) → `services/` (business
  rules, ordering, authorization) → `repositories/` (persistence). HTTP objects
  must not reach the repository layer; SQL must not reach the API layer.
- **One authorization choke point.** From Sprint 2, ownership checks live in a
  single enforced seam (dependency/middleware + a service-level guard), not
  copy-pasted per endpoint. Sprints 3 and 4 add entities *behind* that seam.
  Rationale: this is precisely what makes Sprint 3/4 authz regressions avoidable.
- **One activity choke point.** From Sprint 4, activity records are emitted from
  the service layer's mutation path, not sprinkled into route handlers. A
  mutation that can happen without emitting activity fails AC-4.1.
- **Frontend:** component-based, typed API client, state kept out of components'
  local state where it must survive live updates (FR-4.6).
- **Migration discipline (load-bearing at this rung):**
  - Every schema change is a **numbered, forward, committed migration**
    (`0001_init`, `0002_positions`, …). No implicit `create_all()` drift.
  - Migrations are **idempotent to re-run detection** and are applied by a single
    documented command (§2.5, `migrate_cmd`).
  - **Destructive operations require an explicit data-preserving path.** Dropping
    or recreating a table with live rows is a Sprint failure under NFR-10, even
    if every test happens to pass on a fresh database.
  - `GET /api/health` reports `schema_version` so the harness can assert the
    migration actually ran.
- **Forbidden:** committing a database file as the source of truth; disabling,
  deleting, `skip`ping, or `xfail`ing tests to make a boundary green (a gaming
  event, §6.4); feature-flagging a prior sprint's behavior off; wholesale rewrite
  of a prior sprint's module without preserving its behavior.
- **Allowed and encouraged:** refactoring prior-sprint code, *provided the
  cumulative suite stays green*. Refactoring is not a regression; breaking is.

### 2.3 Data model

Entities and the sprint that introduces them. IDs are opaque strings; all
timestamps are UTC ISO-8601.

| Entity | Fields | Introduced | Migration |
|--------|--------|-----------|-----------|
| `board` | `id`, `name`, `created_at`, `updated_at` | S0 | `0001` |
| `column` | `id`, `board_id→board`, `name`, `created_at` | S0 | `0001` |
| `card` | `id`, `column_id→column`, `title`, `description`, `created_at`, `updated_at` | S0 | `0001` |
| `column.position` | ordering key within board | S1 | `0002` (backfill by `created_at`) |
| `card.position` | ordering key within column | S1 | `0002` (backfill by `created_at`) |
| `user` | `id`, `email` (unique, ci), `password_hash`, `display_name`, `created_at` | S2 | `0003` |
| `session` | `token` (unique), `user_id→user`, `created_at`, `expires_at`, `revoked_at` | S2 | `0003` |
| `board.owner_id` | `→user`, NOT NULL after backfill | S2 | `0003` (**§1.6-6 attribution**) |
| `label` | `id`, `board_id→board`, `name`, `color` | S3 | `0004` |
| `card_label` | `card_id→card`, `label_id→label` (PK pair) | S3 | `0004` |
| `board_member` | `id`, `board_id→board`, `name`, `email?` — *roster entry, not an account* | S3 | `0004` |
| `card.assignee_id` | `→board_member`, nullable | S3 | `0004` |
| `activity` | `id`, `seq` (per-board monotonic), `board_id→board`, `actor_id→user`, `verb`, `entity_type`, `entity_id`, `payload`, `created_at` | S4 | `0005` |

Relationships and rules:

```
user 1───* board 1───* column 1───* card *───* label
                 │                   │
                 ├───* label         └──? board_member (assignee)
                 ├───* board_member
                 └───* activity

- delete board  -> cascade columns, cards, labels, members, activity
- delete column -> cascade cards                      (FR-0.2, frozen at S0)
- delete card   -> renormalize surviving positions    (FR-1.5, frozen at S1)
- delete label  -> remove card_label rows; cards survive (FR-3.2 / AC-3.2)
- delete member -> assigned cards fall back to unassigned; cards survive
- activity      -> append-only, never cascaded-edited  (FR-4.3)
```

**Indexes** required by NFR-1: `card(column_id, position)`,
`column(board_id, position)`, `board(owner_id)`, `card_label(label_id)`,
`card(assignee_id)`, `activity(board_id, seq DESC)`.

### 2.4 Technology constraints

| Layer | Constraint |
|-------|-----------|
| Backend | Python ≥ 3.11. FastAPI or Flask. SQLAlchemy or equivalent. Pydantic (or equivalent) for validation. |
| Persistence | **SQLite for local/dev, Postgres-compatible for the harness run.** No ORM feature that only works on one of the two. Connection configured by env var. |
| Migrations | Alembic, or hand-authored numbered SQL applied by a committed runner. Either is fine; *versioned and forward-only* is not. |
| Password hashing | bcrypt / argon2 / scrypt via a maintained library. Hand-rolled hashing is an automatic AC-2.2 failure. |
| Real-time | Native WebSocket (e.g. FastAPI/Starlette `WebSocket`) **or** SSE. No third-party realtime SaaS; no polling-disguised-as-realtime (a poll interval faster than NFR-9 is a gaming event). |
| Frontend | TypeScript + React (18+). Vite build. Any state library or none. |
| Drag & drop | Any library or hand-rolled — but the keyboard path (FR-1.7) must exist regardless. Libraries that cannot be made keyboard-operable are the wrong choice. |
| Testing | `pytest` (API), Playwright (E2E), `axe-core` (a11y). The strategy's own tests live in its workspace; the graded suites do not. |
| Forbidden | Reading or writing outside the declared workspace; network calls to external services at runtime; committed secrets; a database file as the committed source of truth. |

### 2.5 Entrypoint contract

`kind: web-app`. The harness starts the backend and the built frontend, waits for
health, then runs API + browser suites against the **live application** — the
real path, per `VERIFICATION_CONTRACT.md` §3. Two additional hooks exist at A2
that lower rungs do not have: `migrate_cmd` (so migration-safety probes can run)
and per-sprint suite selection.

```yaml
# scenarios/A2-kanban-sprints/manifest.yaml   (authored in the harness pass)
level: 7
language: python+typescript
workspace: solution/
entrypoint:
  kind: web-app
  start_cmd: "make run"              # backend + built SPA, single command
  url: "http://localhost:8080"
  health_path: "/api/health"         # must report {status, version, schema_version}
  ready_timeout_s: 60
  e2e_runner: "npx playwright test"
  migrate_cmd: "make migrate"        # A2-specific: applies forward migrations
  reset_cmd: "make reset-db"         # drops + re-migrates a throwaway DB
sprints: [0, 1, 2, 3, 4]
verify:
  smoke:       "pytest tests/smoke/sprint_${SPRINT} -q"
  acceptance:  "pytest tests/acceptance/sprint_${SPRINT} -q --json-report"
  regression:  "pytest tests/acceptance/sprint_0..$((SPRINT-1)) -q --json-report"
  adversarial: "pytest tests/adversarial/sprint_${SPRINT} -q --json-report"
  migration:   "pytest tests/adversarial/migration -q --json-report"
budgets:
  wall_clock_s: 28800          # total; 5400 per sprint + 1800 inception
  per_sprint_wall_clock_s: 5400
  iterations_soft: 20          # per sprint
  iterations_hard: 50          # per sprint
  interventions: 0
gate:
  acceptance_floor: 1.0        # current sprint's AC
  regression_floor: 1.0        # cumulative prior sprints' AC
  evaluated_at: sprint_boundary
```

The strategy must make `make run`, `make migrate`, and `make reset-db` work from
Sprint 0 onward. A sprint that breaks the entrypoint contract fails its boundary
regardless of feature completeness — the harness cannot score what it cannot start.

---

## 3. Non-Functional Requirements

Every NFR is in force from the sprint listed and **every sprint thereafter**.
NFR-8/9/10 are the A2-specific additions on top of A1's set.

- **NFR-1 Performance** *(from S0)* — On the harness fixture (3 boards, 5 columns
  × 50 cards each):
  | Operation | Budget (p95, local) |
  |-----------|---------------------|
  | `GET /api/boards/{id}` (nested) | ≤ 300 ms |
  | Any single CRUD write | ≤ 200 ms |
  | `PATCH /cards/{id}/move` | ≤ 200 ms |
  | Filter/search query (S3, 1,000 cards) | ≤ 400 ms |
  | Activity page fetch (S4) | ≤ 300 ms |
  | SPA first interactive (built, local) | ≤ 2.5 s |
  No `N+1` query on the board read: the nested board fetch must issue a bounded
  number of queries independent of card count.

- **NFR-2 Reliability & error handling** *(from S0)* — No unhandled 5xx on any
  user-supplied input. Writes are atomic: a failed move leaves ordering exactly
  as it was (no half-applied renormalization). Restart loses nothing (FR-0.4).
  From S4, a dropped live connection degrades to a working non-live app — the
  board must remain fully usable with the socket down.

- **NFR-3 Security** *(from S2, with input validation from S0)* — Passwords
  salted+hashed with a slow KDF; never logged, never returned. Session cookie
  `HttpOnly`, `SameSite=Lax`, `Secure` when served over TLS. Authorization is
  deny-by-default: a new endpoint added in S3/S4 that forgets its ownership check
  is a security defect **and** a Sprint-2 regression. All user-supplied text is
  escaped on render (card title/description, label name, member name, board and
  column names) — **including in the activity feed**, which is the S4-specific
  XSS surface. Parameterized queries only. No secrets in the repo.

- **NFR-4 Accessibility** *(from S0, re-verified every sprint)* — **WCAG 2.1 AA**,
  maintained *each sprint*, not retrofitted at the end:
  - Zero critical/serious `axe-core` violations on every screen shipped so far.
  - Full keyboard operability including card reordering (S1) and filtering (S3).
  - Visible focus indicators; logical focus order; focus is not lost or trapped
    by drag mode (S1), modals (S0), or incoming live updates (S4).
  - Text contrast ≥ 4.5:1; label chips and non-text indicators ≥ 3:1 (S3).
  - Status changes announced via ARIA live regions: filter results (S3),
    connection state and incoming changes (S4).
  - Design a11y annotations updated in the same sprint as the feature.

- **NFR-5 Maintainability** *(from S0)* — `ruff` + `pyright` clean on the backend;
  `eslint` + `tsc --noEmit` clean on the frontend. Layering (§2.2) respected.
  Cyclomatic complexity ≤ 12 per function. No dead code from a prior sprint left
  commented out. Each sprint's diff should read as an *extension*: a sprint whose
  diff rewrites >60% of the prior sprint's files is recorded as a `dead_end`
  (§8.2) even if it passes.

- **NFR-6 Observability** *(from S0)* — Structured request logs (method, path,
  status, duration, actor from S2) with no secrets or password material.
  `/api/health` reports `status`, `version`, and `schema_version`. From S4, live
  channel connect/disconnect/backfill events are logged with board and client ids.

- **NFR-7 Portability / footprint** *(from S0)* — `make run` works from a clean
  checkout on Linux with only declared dependencies. Runs against SQLite locally
  and Postgres in the harness with only an env var change. No global installs, no
  container required, no external network at runtime.

- **NFR-8 Regression safety — *the defining NFR of this rung*** *(from S1)* —
  At **every sprint boundary**, the cumulative acceptance suite from **all** prior
  sprints must pass at **100%**. Not 99%. Not "100% after I fix it next sprint."
  A prior-sprint assertion that fails at a boundary is a regression event with
  scenario-wide scoring consequences (§7.2.1). Deleting, weakening, skipping, or
  flag-gating a prior assertion to reach 100% is a gaming event (§6.4) and
  disqualifies the run.

- **NFR-9 Real-time propagation** *(from S4)* — With two clients viewing the same
  board, a mutation committed by client 1 is reflected in client 2 within
  **p95 ≤ 2,000 ms** over 20 trials, with **no single trial exceeding 5,000 ms**.
  Measured client-to-client (DOM-observable change in client 2), not
  server-to-socket. Reconnect-and-backfill (FR-4.7) completes within 10 s of the
  channel being restored. Polling faster than the budget to fake "real-time" is a
  gaming event.

- **NFR-10 Migration safety** *(from S1, every schema change)* — Data created
  under schema version *N* is fully preserved under schema version *N+k*:
  - Every row survives (count and content), including ordering (`position`).
  - Ownership attribution after `0003` is total — no orphaned, unreachable, or
    silently deleted boards (§1.6-6).
  - Migrations are applied by `migrate_cmd` and are verifiable via
    `health.schema_version`.
  - The harness probe: build a fixture DB at sprint *N*'s schema with real data,
    run `migrate_cmd` to sprint *N+k*, then run sprint *N*'s acceptance suite
    against the upgraded database. It must pass at 100%.

---

## 4. The Ask (Deliverables & Definition of Done)

### 4.1 Required artifacts

The deliverable is **the application at each sprint boundary** — five verifiable
states, not one final tarball — **plus** the product/design artifacts for each
sprint. The harness tags and verifies each boundary; the strategy must not
rewrite history to hide a boundary.

```
solution/
  Makefile                       # run | migrate | reset-db | test | lint
  backend/
    api/                         # HTTP routes, serialization
    services/                    # business rules, ordering, authz choke point,
                                 #   activity choke point (S4)
    repositories/                # persistence
    migrations/
      0001_init.*                # S0
      0002_positions.*           # S1
      0003_auth_ownership.*      # S2  (data-preserving attribution, §1.6-6)
      0004_labels_members.*      # S3
      0005_activity.*            # S4
    realtime/                    # S4: WS or SSE channel + broadcast
  frontend/
    src/components/ src/state/ src/api/
  tests/                         # the STRATEGY's own tests (not the graded ones)
  README.md                      # run, migrate, architecture, resolved ambiguities

design/                          # see §5.4 for the full required list
  research/  prd.md  backlog.md  sprints/  retros/  dod.md
  wireframes/  mockups/  tokens/  interaction/  a11y/
  CHANGELOG-design.md
```

Boundary evidence per sprint (harness-captured, strategy-triggered):

| Per sprint N | Evidence |
|--------------|----------|
| Code state | Tagged commit / snapshot at the boundary |
| Sprint plan | `design/sprints/sprint-N.md` — goal, backlog, AC, DoD |
| Retro | `design/retros/retro-N.md` |
| Usability (N ∈ 1,2,3) | `design/research/usability/session-N.md` + backlog deltas |
| Design deltas | Updated `design/` assets + `CHANGELOG-design.md` entry |
| Migration | New numbered migration; `health.schema_version` bumped |

### 4.2 Definition of Done

This is the canonical per-sprint DoD. **It is evaluated five times.** A sprint is
not done until every box is checked; the run does not advance to sprint *N+1*
until sprint *N* is done.

```
DEFINITION OF DONE — Sprint N
[ ] 1. All Sprint-N acceptance criteria pass at 100%          (HARD GATE)
[ ] 2. Cumulative regression suite (sprints 0..N-1) at 100%   (HARD GATE)
[ ] 3. Sprint-N smoke suite green
[ ] 4. Migration for any schema change is committed, applied by `migrate_cmd`,
       and passes the migration-safety probe (NFR-10)
[ ] 5. Entrypoint contract intact: `make run` boots; /api/health reports the
       expected schema_version
[ ] 6. Performance budgets (NFR-1) met on the harness fixture
[ ] 7. WCAG 2.1 AA maintained: zero critical/serious axe violations on every
       screen shipped SO FAR, not just the new one (NFR-4)
[ ] 8. Lint / type / format clean on both backend and frontend (NFR-5)
[ ] 9. Design artifacts for Sprint N landed and consistent with what shipped
       (design diff review), incl. a11y annotations
[ ] 10. `design/sprints/sprint-N.md` complete (goal, backlog, AC, DoD)
[ ] 11. `design/retros/retro-N.md` written, with at least one concrete action
        carried into the next sprint's backlog
[ ] 12. For N ∈ {1,2,3}: usability evaluation recorded and at least one
        severity ≥ major finding groomed into sprint N+1's backlog
[ ] 13. `design/backlog.md` re-groomed: items closed, carried, or re-ranked,
        with the sprint N+1 slice explicit
[ ] 14. README updated with any newly resolved §1.6 ambiguity
```

Items 1 and 2 are the **hard gate** (automated, pass/fail). Items 3–8 are
automated checks that feed `COR`/`ROB`/`FID`/`QUA`. Items 9–14 are artifact
obligations that feed `FID` and cap it when missing (§7.2).

### 4.3 Acceptance criteria

Scenario-level acceptance is the union of the five per-sprint criteria matrices
in §1.7. Traceability is required in both directions — every FR must have an AC,
and every AC must name its FR/NFR.

| Sprint | AC range | Traces to | Also re-asserts |
|--------|----------|-----------|-----------------|
| 0 | AC-0.1 … AC-0.9 | FR-0.1–0.8, NFR-1/2/4/5/7 | — |
| 1 | AC-1.1 … AC-1.9 | FR-1.1–1.8, NFR-1/4/10 | AC-0.* |
| 2 | AC-2.1 … AC-2.10 | FR-2.1–2.8, NFR-3/4/10 | AC-0.*, AC-1.* |
| 3 | AC-3.1 … AC-3.11 | FR-3.1–3.9, NFR-1/3/4/10 | AC-0.*, AC-1.*, AC-2.* |
| 4 | AC-4.1 … AC-4.10 | FR-4.1–4.8, NFR-2/3/4/6/9/10 | AC-0.* … AC-3.* |

**The scenario is complete** when Sprint 4's boundary passes: AC-4.* at 100% and
the full cumulative suite (AC-0.* … AC-3.*, ~145 assertions) at 100%, with all
five DoDs satisfied.

---

## 5. Discovery & Design Activities

Per `ARTIFACT_GRADIENT.md` row **A2**, *every* discovery/product/design activity
on the matrix is **Required** here — including Usability testing, which is
Optional at A1 and Required at A2 — plus the four A2-only rows (sprint plans,
retrospectives, per-sprint feedback, evolving design).

### 5.1 User research — **Required**

| Activity | Status | What must exist | When |
|----------|--------|-----------------|------|
| Stakeholder/user interviews | **Required** | ≥ 3 interview write-ups grounded in the §1.2 personas: context, current workaround, pains, quotes, implications | Inception, before Sprint 0 |
| Jobs-to-be-done | **Required** | ≥ 5 JTBD statements (`When ___, I want ___, so I can ___`), each mapped to backlog items | Inception; revisited at each grooming |
| Personas | **Required** | The four §1.2 personas, fleshed out; carried forward unchanged across sprints (drift is a `FID` penalty) | Inception |
| **Usability testing** | **Required** (A2-only) | A scripted evaluation **against the running app** after Sprints 1, 2, 3 | End of S1, S2, S3 |

**Usability evaluation protocol** (be honest about what this is): there are no
live human participants inside an eval run. The strategy therefore runs a
*moderated-session simulation*: it adopts each persona, executes a written task
script against the **real running application in a real browser**, and records
per task — completion (yes/no/with-difficulty), steps taken vs. optimal, errors
and recoveries, heuristic violations (Nielsen), and WCAG findings. Findings are
severity-rated (`minor` / `major` / `critical`). This is a proxy for research and
is **scored on rigor and traceability, not on being genuine user research**:

- ≥ 5 tasks per session, drawn from the personas' jobs;
- findings recorded with severity and evidence (screenshot or trace reference);
- **at least one severity ≥ major finding must become a groomed backlog item in
  the next sprint** — a usability session with zero consequences scores as
  theater and caps `FID ≤ 2`.

### 5.2 Product design — **Required**

| Activity | Status | Notes |
|----------|--------|-------|
| Spec / acceptance criteria | **Required** | Per sprint, in `sprints/sprint-N.md`, traceable to FRs |
| PRD | **Required** | Problem, personas, scope, success metrics, release plan across the five sprints; written at inception, amended (not rewritten) as sprints land |
| User stories | **Required** | §1.3 as the seed; expanded with estimates and acceptance in the backlog |
| **Prioritized backlog** | **Required** | ONE `backlog.md` spanning all five sprints, groomed at inception and **re-groomed at every sprint boundary**: ranked, estimated, sprint-sliced, with carried/closed/added items visible over time |
| **Sprint plans + goals** | **Required** (A2-only) | One per sprint: a single-sentence sprint goal, the committed slice, AC, DoD, and named risks |
| Definition of Done | **Required** | `dod.md`, the §4.2 checklist, applied and evidenced per sprint |
| **Retrospectives** | **Required** (A2-only) | One per sprint: what went well, what didn't, **what regression risk was discovered**, and ≥ 1 concrete action carried into the next sprint's backlog. A retro that names no regression risk after a sprint that had one is a `FID` penalty |

The backlog is the load-bearing product artifact at this rung. It must show
**history**: an item that appears fully-formed in Sprint 4 with no prior
existence is backlog drift (§8.2), and so is a Sprint-0 item that silently
vanishes without being closed or explicitly dropped.

### 5.3 Interaction / visual design — **Required, and it must EVOLVE per sprint**

The distinguishing A2 obligation: design is **not** finished before Sprint 0. It
grows with the product, one increment per sprint, and each increment must be
dated and logged in `CHANGELOG-design.md`.

| Sprint | Design deltas required |
|--------|------------------------|
| **S0** | Lo-fi wireframes: board, column, card, card editor, empty/loading/error states. **Design tokens v1** (color, spacing, type scale, focus ring). Hi-fi mockup of the board view. A11y annotations v1 (landmarks, headings, focus order, labels) |
| **S1** | **Interaction/state spec for drag**: `idle → grabbed → over-valid-target → over-invalid-target → dropping → persisting → error-reconciling`. Drop-target affordances. **Keyboard move key-map** and its announcement text. Updated a11y annotations for grab mode |
| **S2** | Hi-fi mockups for register / login / logout / authenticated shell. Form error and validation states. Session-expired interstitial. A11y annotations for forms (label association, error announcement, autocomplete) |
| **S3** | **Filter bar + search UI mockups** (multi-select label facet, assignee facet, search input, active-filter chips, clear-all). **Label color tokens with documented contrast ratios**. Filtered-empty state. Live-region copy for "N of M cards shown" |
| **S4** | **Activity feed panel design** (grouping, relative timestamps, actor attribution, pagination/"load more"). **Real-time state spec**: `connected / reconnecting / stale / conflict-resolved`, including the visual treatment of an incoming change. Live-region announcement copy. Reduced-motion variant for update animations |

Design work is graded by **design diff review**: does what shipped match what was
designed, in the sprint it was designed for? Retro-fitting all five sprints of
design at the end is detectable (single-commit design history) and caps `FID ≤ 2`.

### 5.4 Design artifacts to produce

Exact files. Missing a Required file is a DoD failure for that sprint and caps
`FID` (§7.2).

```
design/
  prd.md                                # inception; amended per sprint
  backlog.md                            # SINGLE groomed backlog, all 5 sprints,
                                        #   re-groomed at every boundary
  dod.md                                # the §4.2 checklist
  research/
    interviews.md                       # >= 3 write-ups
    jtbd.md                             # >= 5 JTBD statements -> backlog map
    personas.md                         # the four §1.2 personas
    usability/
      session-1.md                      # after Sprint 1
      session-2.md                      # after Sprint 2
      session-3.md                      # after Sprint 3
  sprints/
    sprint-0.md  sprint-1.md  sprint-2.md  sprint-3.md  sprint-4.md
                                        # each: GOAL + backlog slice + AC + DoD + risks
  retros/
    retro-0.md  retro-1.md  retro-2.md  retro-3.md  retro-4.md
                                        # each: went well / didn't / regression risk
                                        #   found / >=1 action into next backlog
  wireframes/
    s0-board.*  s0-card-editor.*  s0-states.*
  mockups/
    s0-board-hifi.*  s2-auth.*  s3-filter-search.*  s4-activity-feed.*
  tokens/
    tokens.json                         # v1 at S0; label colors added at S3
    CHANGELOG.md
  interaction/
    s1-drag-states.md                   # incl. keyboard key-map
    s3-filter-behavior.md
    s4-realtime-states.md               # connected/reconnecting/stale/conflict
  a11y/
    annotations-s0.md  annotations-s1.md  annotations-s2.md
    annotations-s3.md  annotations-s4.md
    wcag-checklist.md                   # AA criteria, re-signed each sprint
  CHANGELOG-design.md                   # dated per-sprint design evolution log
```

Optional/stretch (not required, not penalized if absent): ADRs under
`docs/decisions/`, a story map, a component-inventory doc, per-sprint demo notes.

---

## 6. Verification Method

### 6.1 Test tiers

Standard three tiers (`VERIFICATION_CONTRACT.md` §1), **instantiated five times**
— once per sprint — plus the A2-specific cumulative regression tier.

| Tier | Visible? | A2 instantiation |
|------|----------|------------------|
| `smoke` | **Yes** | Per sprint, 5–8 visible happy-path checks handed over with that sprint's SPEC slice. Enough to self-check; nowhere near enough to define done. |
| `acceptance` | **No** — held out | Per sprint, the full criteria matrix from §1.7 (AC-N.*), run at that sprint's boundary against the live app. This is that sprint's definition of "working." |
| `regression` (cumulative) | **No** — held out | The **union of acceptance suites `0..N-1`**, run unchanged at the boundary of sprint N. Grows every sprint (~40 → ~145 assertions). Owned by the harness; the strategy can never edit, weaken, or skip it. |
| `adversarial` | **No** — hidden | Per sprint, run **once** after that sprint's declare-done, never revealed. Feeds `COR`/`ROB` only; never the gate. |

**Per-sprint smoke examples (visible):**

```
S0  create board -> add column -> add card -> GET board shows all three
S1  move card to index 0 -> GET board shows it first; reload -> still first
S2  register -> login -> GET /api/auth/me returns the user; logout -> 401
S3  create label -> attach to card -> filter by label -> only that card returns
S4  open two clients -> move a card in one -> the other shows the move
```

**Adversarial content per sprint (hidden — indicative, not exhaustive):**

| Sprint | Adversarial probes |
|--------|--------------------|
| S0 | Unicode/emoji/RTL titles; 4,000-char descriptions; empty and whitespace-only names; deeply nested payloads; concurrent creates in the same column; delete-then-read races; SQL-ish strings in names |
| S1 | Move to out-of-range index; move to a nonexistent column; move a card onto itself; move into an empty column; two concurrent moves of the same card; delete a card mid-drag; 200-card column ordering integrity |
| S2 | **Authz bypass sweep**: every endpoint × cross-user actor, including S1 move endpoints and nested IDs; forged/expired/revoked cookies; session fixation; email case/unicode-normalization collisions; timing-difference on login; password in a log line |
| S3 | XSS payloads in label name, member name, card title, search query — reflected and stored; filter param injection; `q` with regex/SQL metacharacters; filter over 1,000 cards for correctness *and* NFR-1; **assert positions unchanged in the DB after filtering** |
| S4 | **Race conditions**: simultaneous conflicting moves from two clients (repeated trials, convergence asserted); event flood; forced disconnect mid-mutation then reconnect-backfill with `seq` gap detection; **unauthorized socket subscribe**; XSS via activity payload rendering; activity write failure must not lose the mutation |
| **Cross-sprint** | **Re-introduced-bug ("scar") suite** — see §6.3 |
| **Cross-sprint** | **Migration/data-loss probes** — see §6.3 |

### 6.2 "Working" definition (the hard gate)

Evaluated **at each sprint boundary**, both conditions required:

```
sprint_N_gate  ==  acceptance(sprint N)     == 100%
              AND  regression(sprints 0..N-1) == 100%
```

Notes:
- There is **no partial credit at a boundary.** 99% is a failed boundary.
- A failed boundary **halts the run.** Sprints are sequential; the scenario is
  scored as `Failed`, and the telemetry records the **sprint frontier** — the
  highest boundary passed. `frontier = 2` ("passed through auth, died on
  filters") is far more informative than a single failing number, and it is the
  A2 analogue of the ladder profile itself.
- `adversarial` never gates. It feeds `COR`/`ROB`.
- The scenario passes only when Sprint 4's boundary passes.

### 6.3 Verification mechanics

The real path at A2 is the running application: real HTTP against a real server
with real persistence, plus a real browser driving the real DOM.

```
PER SPRINT BOUNDARY (harness-side; strategy is paused)
 1. Snapshot/tag the workspace as boundary-N.
 2. reset-db; migrate_cmd; start_cmd; poll /api/health until ready.
    Assert health.schema_version == expected for sprint N.
 3. Seed the standard fixture (3 boards / 5 columns / 50 cards each;
    from S2 also 2 user accounts; from S3 also labels + roster).
 4. Run acceptance/sprint_N        -> must be 100%          [GATE]
 5. Run regression/sprints_0..N-1  -> must be 100%          [GATE]
 6. Run adversarial/sprint_N       -> record, feeds COR/ROB
 7. Run the scar suite (all sprints so far)  -> record, feeds REG
 8. Run the migration-safety probe           -> record, feeds REG/ROB
 9. Run performance probes (NFR-1) and axe sweep (NFR-4) over ALL screens
    shipped so far.
10. Static analysis + design-diff + artifact-presence review (QUA, FID).
11. Emit sprint score block; if gate failed, halt with frontier = N-1.
```

**API tier.** `pytest` + `httpx` against the live server. Assertions read state
back through the API *and*, where the criterion demands it (AC-2.2 hash storage,
AC-3.7/FR-3.9 positions-unchanged), directly from the database.

**Browser tier.** Playwright against the built SPA. All E2E ACs run here. Keyboard
paths (AC-0.8, AC-1.6, AC-3.11) are driven with real key events, never by calling
handlers directly. `axe-core` runs on every screen shipped so far, every sprint.

**Two-client tier (S4).** Two independent Playwright browser contexts (separate
cookie jars, separate sessions) view the same board. Client 1 mutates; client 2
is observed via DOM assertions with a timeout equal to the NFR-9 budget.
Propagation time is measured client-to-client and recorded over 20 trials for the
p95. Convergence (AC-4.8) runs repeated trials with `flaky-guarded` tolerances
per `VERIFICATION_CONTRACT.md` §4 — a single jitter must not decide a gate, but a
systematic divergence must.

**Scar suite (cross-sprint, adversarial).** The harness maintains a registry of
bugs known to be commonly re-introduced on this app, each pinned to the sprint
that fixed it. From that sprint's boundary onward, the scar test runs forever:

| Scar | Fixed in | Symptom if re-introduced |
|------|----------|--------------------------|
| Column delete orphans its cards | S0 | Orphan rows; board read crashes |
| Restart loses in-memory state | S0 | Data gone after process bounce |
| Positions go sparse/duplicated after delete | S1 | Ordering drifts; duplicate render keys |
| Drop into an empty column fails | S1 | Card vanishes or snaps back |
| Tab order broken by drag containers | S1 | Keyboard users can't reach cards |
| Logout leaves the session valid server-side | S2 | Replayed cookie still works |
| A nested endpoint skips the ownership check | S2 | Cross-user read/write |
| Filtering writes back positions | S3 | Board order destroyed by viewing a filter |
| Label/member names rendered unescaped | S3 | Stored XSS |
| Incoming live event resets the active filter | S4 | View jumps out from under the user |
| Reconnect drops events (no `seq` backfill) | S4 | Silently stale board |

Scar failures do **not** gate directly (they are adversarial), but a scar failure
**is** by definition an oscillation and drives `REG` down hard (§7.2).

**Migration-safety probe (NFR-10).**

```
for each earlier schema version V in 0..N-1:
  build fixture DB at V with real data (boards, columns, cards, positions,
     and from V>=2 users/ownership, from V>=3 labels/members)
  record row counts + a content digest per table + per-column card ordering
  run migrate_cmd  ->  schema version N
  assert: every row present, digests intact, orderings intact,
          ownership total (no orphans), health.schema_version == N
  run acceptance/sprint_V against the upgraded DB -> must be 100%
```

The S1→S2 hop is the sharp edge: it is where §1.6-6 (pre-auth data attribution)
is decided, and where "recreate the table, it's easier" quietly destroys the
user's board.

### 6.4 Anti-gaming measures

A2 has more gaming surface than any lower rung, because the strategy is being
asked to keep an ever-growing suite green.

| Vector | Detection | Consequence |
|--------|-----------|-------------|
| Editing/deleting/weakening held-out suites | Suites live outside the workspace and are mounted read-only at scoring time; workspace writes outside `solution/` + `design/` are logged | Disqualified (`gaming_event`) |
| `skip` / `xfail` / commenting out the strategy's **own** prior-sprint tests to hide breakage | Diff of the strategy's test files across boundaries; count of skipped tests must not increase | `gaming_event`; caps `REG ≤ 1`, zeroes `QUA` |
| Feature-flagging a prior sprint's behavior off | Cumulative suite runs with default config only; no per-suite config injection is offered | Boundary failure |
| Rewriting from scratch each sprint to dodge integration | Churn metric: >60% of prior-sprint files rewritten in a sprint | Recorded `dead_end`; caps `EFF ≤ 2` |
| Hardcoding fixture-specific values | Acceptance uses randomized fixture ids and titles per run; adversarial uses different data entirely | Acceptance/adversarial gap → caps `ROB` |
| Fake "real-time" by fast polling | Network trace inspection; poll interval below the NFR-9 budget with no persistent channel | `gaming_event` for NFR-9 |
| Retro-fitting all design artifacts at the end | Artifact timestamps/commit history vs. boundary tags | Caps `FID ≤ 2` |
| Backlog written backwards after the fact | Backlog diff across boundaries; items must exist before the sprint that closes them | Caps `FID ≤ 2` |
| Overfitting to visible smoke | `adversarial_pass` vs `acceptance_pass` gap | Caps `ROB` (`CONVERGENCE_METRICS.md` §6) |

---

## 7. Scoring Rubric

### 7.1 Weight profile

Sum 100. This is the ladder's terminal profile: correctness is *assumed* (it is
the gate), and the score is dominated by **whether you stayed correct** (`REG`),
**how autonomously** (`AUT`), and **at what cost** (`EFF`).

| Axis | `COR` | `ROB` | `EFF` | `AUT` | `QUA` | `REG` | `FID` |
|------|------|------|------|------|------|------|------|
| **Weight** | **15** | **10** | **20** | **20** | **12** | **18** | **5** |

`REG` at 18 is the highest on the ladder, and `COR` at 15 the lowest, by design:
at A2 correct-at-a-point-in-time is table stakes enforced by the gate, while
*correct-after-four-more-sprints* is the thing being measured. `FID` dips to 5
(per `RUBRIC_FRAMEWORK.md` §3) because the sprint backlog, not a static design,
carries acceptance here — but note that missing required artifacts still **caps**
`FID` and, per `ARTIFACT_GRADIENT.md` §3, a run can drop below threshold on the
combination of a capped `FID` and a mediocre `QUA`.

### 7.2 Per-axis scoring guide

| Axis | 0 | 2 | 4 |
|------|---|---|---|
| **COR** | Any sprint boundary gate failed (run halted) | All boundaries passed, but `adversarial_pass` < 0.80 across sprints — edges only survive because they weren't tested | All 5 boundaries at 100%, `adversarial_pass` ≥ 0.95 across all sprints, scar suite fully green |
| **ROB** | 5xx on user input; races produce lost/duplicated cards; a migration loses rows | Handles common bad input, but concurrent moves diverge, reconnect drops events, or a migration probe needs a rerun | Every adversarial class survives: authz sweep clean, XSS clean in all text surfaces incl. activity, concurrent moves converge every trial, all migration probes 100% |
| **EFF** | Exceeded a hard cap or the wall-clock ceiling | Landed near hard caps in ≥ 2 sprints, or iteration count climbs steeply sprint over sprint, or a full-rewrite `dead_end` | Every sprint ≤ soft iteration budget, ≤ 1 failed run before pass per sprint, total under time and token budget, and the per-sprint iteration curve is **flat or falling** as the codebase grows |
| **AUT** | Any `rescue` (hard cap ≤ 1 per `CONVERGENCE_METRICS.md` §3) | 1–2 low-severity interventions (`nudge`/`clarify`), or one `unblock` | Zero interventions across all five sprints, zero dead-ends, self-diagnosed and self-recovered from its own regressions |
| **QUA** | Lint/type errors; layering violated; authz or activity logic copy-pasted per endpoint | Clean but accreting: duplicated ordering logic, dead code from prior sprints, complexity creeping past caps | Clean throughout; single authz and activity choke points; each sprint reads as a coherent extension; the S4 codebase is still comprehensible |
| **REG** | ≥ 1 regression at a boundary, or a scar bug re-introduced, or a gaming event on the suites | Prior-sprint assertions broke *during* a sprint and were repaired before the boundary (≥ 3 intra-sprint regressions or ≥ 1 oscillation) | Zero regressions at every boundary, zero intra-sprint regressions surviving more than one iteration, zero oscillations, zero scar failures, all migration probes clean |
| **FID** | Required artifacts largely absent, or artifacts contradict what shipped | Artifacts exist but are thin: backlog not re-groomed, retros generic, usability findings not traced into the next sprint, design retro-fitted | All §5.4 files present and *timestamped to their sprint*; backlog shows real grooming history; retros name real regression risks; usability findings visibly change the next sprint's backlog; design diff matches implementation; WCAG AA held every sprint |

#### 7.2.1 Aggregation across sprints — **the A2-specific rule**

Each sprint is scored independently on all seven axes, then the scenario score is
the **mean of the five sprint scores** — so a strong Sprint 0 cannot hide a
collapsing Sprint 4, and one rough sprint does not erase four clean ones.

```
sprint_score[N] = Σ (axis_score[N][axis] / 4) * weight[axis]      # 0..100
scenario_score  = mean(sprint_score[0..4])

REGRESSION CAP (overrides everything above):
if any boundary N shows a prior-sprint acceptance assertion failing
   on its FIRST authoritative run at that boundary:
       REG := min(REG, 1)   for ALL sprints, then recompute every sprint_score
       band := one band lower than the recomputed score would indicate
       telemetry.regressions_at_boundary += 1
```

Why the cap is scenario-wide rather than sprint-local: **keeping software working
across iterations is the entire proposition of this rung.** A strategy that
breaks Sprint 1's ordering while building Sprint 3's filters has demonstrated the
exact failure mode A2 exists to detect, and it should not be able to average that
away with four tidy sprints. With `REG` weighted 18, the cap costs ≥ 13.5 points
outright plus a band demotion — enough to move a "Converged" run to
"Converged-Rough" or below, which is the honest description of that strategy.

Two regression classes are tracked separately, and only the first triggers the cap:

| Class | Definition | Effect |
|-------|-----------|--------|
| `regressions_at_boundary` | A prior-sprint assertion fails on the first authoritative boundary run | **Scenario-wide `REG ≤ 1`** + band drop (and the boundary gate fails ⇒ run halts) |
| `regressions_intra_sprint` | A prior-sprint assertion the strategy itself broke and repaired before declaring done | No cap; drives `REG` 4 → 3 → 2 and feeds `oscillations` |

The second class is deliberately *not* punished as harshly: a strategy that
breaks something, notices, and fixes it before the boundary is exhibiting exactly
the discipline we want to reward relative to one that never noticed. But it is
recorded, because a rising intra-sprint regression count across sprints is the
early warning that a boundary regression is coming.

Additional scenario-level modifiers:

- **Halt on gate failure.** A failed boundary halts the run: `scenario = Failed`,
  and `frontier_sprint` is recorded. Sprints not reached are scored `null`, not 0.
- **Scar failure.** Any adversarial scar test failing at any boundary sets
  `oscillations += 1` and caps `REG ≤ 2` (or ≤ 1 if it also failed at a boundary).
- **Gaming event.** Disqualifies the run and zeroes `QUA`/`FID`
  (`CONVERGENCE_METRICS.md` §6).
- **Rescue.** Caps `AUT ≤ 1` for every sprint, not just the one it happened in.

### 7.3 Hard gate

```
acceptance_floor = 1.0   # current sprint's AC, at every boundary
regression_floor = 1.0   # cumulative prior sprints' AC, at every boundary
evaluated_at     = every sprint boundary (5 times)
on_failure       = halt; scenario = Failed; record frontier_sprint
```

This is the strictest gate on the ladder, and matches `RUBRIC_FRAMEWORK.md` §4's
A2 row exactly. It is strict because it is the *only* thing that makes A2's
central claim measurable: you do not get to call it converged if last sprint's
feature is broken.

### 7.4 Pass threshold

**68** — the score at/above which A2 counts as "converged" for ladder-profile
purposes.

68 sits inside the **Converged-Rough** band (55–69), and that is deliberate.
At the top of the ladder we accept a delivery that was expensive and untidy so
long as it **never broke what it had already shipped**; what we refuse to accept
is a smooth-looking run that regressed. The threshold is set below the
`Converged` band precisely so that the regression cap — not polish — is what
decides whether a strategy clears the top rung.

Expected shape of a passing run:

```
COR 4 (15.0) + ROB 3 (7.5) + EFF 3 (15.0) + AUT 4 (20.0)
+ QUA 3 (9.0) + REG 4 (18.0) + FID 2 (2.5)              = 87  Converged-Clean

COR 4 (15.0) + ROB 2 (5.0) + EFF 2 (10.0) + AUT 3 (15.0)
+ QUA 2 (6.0) + REG 3 (13.5) + FID 2 (2.5)              = 67  just BELOW threshold

...the same run with ONE boundary regression (REG -> 1):
COR 4 (15.0) + ROB 2 (5.0) + EFF 2 (10.0) + AUT 3 (15.0)
+ QUA 2 (6.0) + REG 1 (4.5) + FID 2 (2.5)               = 58, band-dropped
                                                          -> Sub-threshold
```

---

## 8. Convergence Signals

### 8.1 Healthy convergence

What a strong strategy's A2 trace looks like:

- **Inception is short and real.** Personas, JTBD, PRD, and a groomed five-sprint
  backlog land inside the 30-minute block. The backlog is ranked and sliced
  before a line of Sprint-0 code exists.
- **Sprint 0 is over-invested on purpose.** The strategy spends its Sprint-0
  budget on the choke points (layering, migrations, error envelope, a11y
  primitives) rather than on features, because it recognizes those as the seams
  every later sprint depends on.
- **The iteration curve is flat or falling.** Iterations per sprint stay near the
  soft budget even as the codebase triples. A strategy with real regression
  discipline gets *faster* as its test scaffolding grows, not slower.
- **It runs the cumulative suite itself, unprompted, before declaring done.** The
  strongest single predictor of a clean A2: the strategy re-runs its own
  prior-sprint tests as part of every sprint's inner loop, not just at the end.
- **Migrations are written before the model changes**, and the strategy tests the
  upgrade path on a populated database rather than a fresh one.
- **§1.6-6 is resolved explicitly and early.** The strategy notices during Sprint
  2 planning that pre-auth data needs an owner, writes down the decision, and
  tests it. Weak strategies discover this at the boundary, from a probe failure.
- **Retros are honest and consequential.** "Sprint 2's authz refactor nearly
  broke `move`; adding a cross-sprint smoke run before declaring done" — and then
  the next sprint's trace visibly shows that action taken.
- **A11y is per-sprint, not a Sprint-4 cleanup.** Zero critical axe violations at
  every boundary, including during drag and during live updates.

### 8.2 Pathological patterns

| Pattern | What it looks like | Telemetry surface |
|---------|--------------------|-------------------|
| **Regression explosion** | Iterations flat at S0–S1, then a spike at S2/S3 as every change breaks two prior things — complexity compounding faster than the strategy's ability to hold it | `iterations[N]` curve steepens; `regressions_intra_sprint[N]` climbs; boundary time grows |
| **Re-introducing fixed bugs** | A bug fixed in S1 returns in S3 because the fix lived in a branch the refactor deleted | Scar suite failures; `oscillations` |
| **Rescue-reliance ramp** | Zero interventions at S0, one `clarify` at S2, a `hint` at S3, a `rescue` at S4 — the classic A2 signature of a strategy at its ceiling | `interventions[N]` by sprint and severity; `AUT` capped |
| **Rewrite-per-sprint** | Rather than integrate, the strategy re-derives the app each sprint. Boundaries may pass, but nothing accumulates and cost explodes | Churn > 60% of prior-sprint files; `dead_ends`; `tokens[N]` climbing |
| **Design drift** | Shipped UI diverges from `design/`; a11y annotations stop being updated after S1; hi-fi mockups only ever describe S0 | Design-diff review; `CHANGELOG-design.md` gaps |
| **Backlog drift** | Items appear fully-formed in the sprint that closes them; S0 items vanish without being closed; the backlog is never re-groomed | Backlog diff across boundary tags |
| **Ceremony theater** | Retros that say "went well: everything"; usability sessions with zero findings, or findings that never reach the backlog | `FID` review; usability-finding → backlog traceability check |
| **Green-by-subtraction** | The cumulative suite stays green because the strategy weakened its own tests, flagged behavior off, or narrowed a feature's scope | Skip-count delta; config diff; `gaming_events` |
| **Late a11y** | Nothing accessible until a frantic S4 remediation pass | Axe violation counts per boundary, trending up then crashing |
| **Real-time cargo cult** | A socket exists but the client still polls, or updates arrive by full-board refetch that clobbers local state | AC-4.5 failure; network trace; NFR-9 gaming check |

### 8.3 Instrumentation notes

Beyond the shared `CONVERGENCE_METRICS.md` set, A2 captures **everything
per sprint** — the whole value of this rung is seeing *where* along the sprint
sequence a strategy falls off, which is the same shape as the ladder profile
itself, one level down.

| Metric | Granularity | Why |
|--------|-------------|-----|
| `iterations[N]`, `wall_clock_s[N]`, `tokens[N]`, `usd[N]` | per sprint | The **cost curve** across sprints is the headline A2 signal |
| `failed_runs_before_pass[N]` | per sprint | Friction growth as the system compounds |
| `regressions_at_boundary[N]` | per sprint | Gate + the scenario-wide `REG` cap |
| `regressions_intra_sprint[N]` | per sprint | Early warning; distinguishes "noticed and fixed" from "never noticed" |
| `oscillations[N]` / `scar_failures[N]` | per sprint | Re-introduced previously-fixed bugs |
| `interventions[N]` (count + tag) | per sprint | The rescue-reliance ramp |
| `cumulative_suite_size[N]` | per boundary | Normalizes regression counts against a growing target |
| `boundary_verification_s[N]` | per boundary | Detects a suite becoming slow/flaky as it grows |
| `churn_ratio[N]` | per sprint | % of prior-sprint files rewritten — the rewrite-per-sprint detector |
| `self_regression_runs[N]` | per sprint | Did the strategy run prior-sprint tests *itself* before declaring done? Strongest healthy-convergence predictor |
| `adversarial_pass[N]` | per sprint | Overfitting per sprint, not just overall |
| `axe_violations[N]` | per boundary | A11y held per sprint vs. retro-fitted |
| `realtime_p95_ms` | S4 | NFR-9 |
| `migration_probe_pass[N]` | per boundary | NFR-10 |
| `artifact_presence[N]` | per boundary | Which §5.4 files existed *at that boundary*, by timestamp — catches retro-fitting |
| `frontier_sprint` | run | Highest boundary passed; the A2 analogue of the convergence frontier |

`score.json` extends the shape in `VERIFICATION_CONTRACT.md` §6 with a per-sprint
array so the fall-off is legible at a glance:

```json
{
  "scenario": "A2-kanban-sprints",
  "strategy": "example-harness@v3",
  "gate": {"acceptance_floor": 1.0, "regression_floor": 1.0,
           "passed": false, "frontier_sprint": 3},
  "sprints": [
    {"n": 0, "acceptance": 1.0, "regression": null, "score": 88,
     "axes": {"COR":4,"ROB":3,"EFF":4,"AUT":4,"QUA":3,"REG":null,"FID":3},
     "telemetry": {"iterations": 14, "wall_clock_s": 4100, "tokens": 980000,
                   "regressions_intra_sprint": 0, "churn_ratio": 0.0,
                   "self_regression_runs": 0}},
    {"n": 1, "acceptance": 1.0, "regression": 1.0, "score": 81,
     "telemetry": {"iterations": 18, "regressions_intra_sprint": 1,
                   "self_regression_runs": 2}},
    {"n": 2, "acceptance": 1.0, "regression": 1.0, "score": 72,
     "telemetry": {"iterations": 31, "regressions_intra_sprint": 4,
                   "oscillations": 1, "interventions": 1}},
    {"n": 3, "acceptance": 1.0, "regression": 0.94, "score": 51,
     "notes": {"REG": "AC-1.3 (dense ordering after delete) failed at boundary — filter writeback"}},
    {"n": 4, "acceptance": null, "regression": null, "score": null}
  ],
  "scenario_score": null,
  "band": "Failed",
  "regression_cap_applied": true,
  "gaming_events": []
}
```

That trace reads at a glance: *this strategy climbed three sprints, then the
Sprint-3 filter work wrote back card positions and broke ordering it had shipped
two sprints earlier.* That sentence — not a number — is what A2 exists to
produce.
