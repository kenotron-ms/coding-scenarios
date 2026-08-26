# Lane sprint_2_auth

## Outcome

Deliver Sprint 2 (Auth & multi-user) of the L7 Kanban application, building on Sprints 0 and 1. The application must gain user registration/login/logout, server-side sessions with HttpOnly cookies, per-board ownership, authorization enforcement on every endpoint, and a data-preserving migration that attributes pre-auth boards to an owner. All Sprint 2 acceptance criteria (AC-2.1 through AC-2.10) must pass, AND the cumulative regression suite from Sprints 0 and 1 (AC-0.* ∪ AC-1.*) must still pass 100% when run as an authenticated user.

Concrete files that must exist at the end (in addition to all Sprint 0–1 files):

- `scenarios/L7-kanban-sprints/solution/backend/migrations/0003_auth_ownership.sql` (or `.py`) — adds user, session, board.owner_id; attributes pre-auth rows
- `scenarios/L7-kanban-sprints/solution/tests/sprint_2/` — strategy-owned tests for Sprint 2
- `scenarios/L7-kanban-sprints/design/sprints/sprint-2.md`
- `scenarios/L7-kanban-sprints/design/retros/retro-2.md`
- `scenarios/L7-kanban-sprints/design/research/usability/session-1.md` — usability session from end of Sprint 1
- `scenarios/L7-kanban-sprints/design/mockups/s2-auth.md`
- `scenarios/L7-kanban-sprints/design/a11y/annotations-s2.md`
- `scenarios/L7-kanban-sprints/design/CHANGELOG-design.md` updated with Sprint 2 entry

## Steps

1. **Sprint 2 design artifacts first**: Author `design/mockups/s2-auth.md` (hi-fi mockups for register/login/logout/authenticated shell, form error and validation states, session-expired interstitial). Author `design/a11y/annotations-s2.md` (label association, error announcement, autocomplete attributes for auth forms). Update `design/CHANGELOG-design.md` with a Sprint 2 entry. Confirm `design/research/usability/session-1.md` exists (authored at end of Sprint 1) and that ≥1 severity ≥ major finding from it is groomed into this sprint's backlog.

2. **Resolve §1.6-6 explicitly**: Decide and document in `design/sprints/sprint-2.md` how pre-auth boards will be attributed (options: bind to first account registered, create a seeded `legacy@local` owner, or explicit one-time claim flow). This decision is load-bearing — no data loss is acceptable.

3. **Migration 0003**: Create `solution/backend/migrations/0003_auth_ownership.sql` (or Alembic equivalent) that:
   - Creates `user` table: `id`, `email` (unique, case-insensitive), `password_hash`, `display_name`, `created_at`
   - Creates `session` table: `token` (unique), `user_id→user`, `created_at`, `expires_at`, `revoked_at`
   - Adds `board.owner_id → user`, NOT NULL after backfill
   - Implements the §1.6-6 attribution strategy: every pre-auth board/column/card is preserved and attributed to exactly one user account (no orphaned boards)
   - Migration is forward-only, data-preserving, applied by `make migrate`
   - After migration, `health.schema_version` reports the new version

4. **Backend — auth endpoints**: Implement:
   - `POST /api/auth/register {email, password}` → User (201); email unique case-insensitive; password min 8 chars; stored only as salted hash (bcrypt/argon2/scrypt — never hand-rolled); duplicate email → 400 with error envelope; weak password → 400
   - `POST /api/auth/login {email, password}` → User + Set-Cookie (HttpOnly; SameSite=Lax); establishes server-side session
   - `POST /api/auth/logout` → 204; **invalidates session server-side** — replaying the old cookie afterwards yields 401
   - `GET /api/auth/me` → User | 401

5. **Backend — session middleware and authorization**: Implement a single authorization choke point (not copy-pasted per endpoint):
   - Session middleware: all board/column/card endpoints now require an authenticated session; unauthenticated requests → 401
   - Ownership authorization: a request from user B for a board owned by user A (read/write/move/delete on board or any of its columns/cards) is denied with the chosen denial code (404 or 403, pick one, apply consistently everywhere — document in README)
   - The denial must not leak existence: "board owned by someone else" and "board that does not exist" return identical responses if 404 is chosen
   - Add `board(owner_id)` index for NFR-1

6. **Frontend — auth screens**: Add register/login/logout screens and an authenticated shell to the SPA:
   - Session-expired flow that returns the user to login without silently losing their place
   - Form errors programmatically associated with their inputs (aria-describedby)
   - Session cookie is HttpOnly — not readable from document.cookie
   - Zero critical/serious axe violations on auth screens

7. **Verify Sprint 0/1 behavior unchanged post-auth**: Run the full Sprint 0 and Sprint 1 test suites as an authenticated user. The regression gate specifically watches: drag/move endpoints still work identically behind auth (the most common L7 regression is an authz refactor that quietly breaks `move`), and dense ordering survives migration 0003.

8. **Strategy tests**: Write `solution/tests/sprint_2/` covering AC-2.1 through AC-2.10. Include the authz matrix test (AC-2.4): enumerate every read/write/move/delete endpoint and assert user B receives the chosen denial code on user A's resources. Run Sprint 0 and Sprint 1 tests to confirm no regression.

9. **Sprint plan and retro**: Write `design/sprints/sprint-2.md` (sprint goal, backlog slice, AC-2.1–2.10, DoD, named risks including §1.6-6 attribution, authz refactor breaking move) and `design/retros/retro-2.md` (what went well, what didn't, regression risk discovered, ≥1 concrete action into Sprint 3's backlog). Update `design/backlog.md`.

10. **Usability session 2**: After Sprint 2 is complete, run a moderated-session simulation. Write `design/research/usability/session-2.md` (≥5 tasks covering auth flows, ≥1 severity ≥ major finding groomed into Sprint 3's backlog).

## Done when

The following command exits 0:
```
bash -c "test -f scenarios/L7-kanban-sprints/solution/backend/migrations/0003_auth_ownership.sql && test -f scenarios/L7-kanban-sprints/design/sprints/sprint-2.md && test -f scenarios/L7-kanban-sprints/design/retros/retro-2.md && test -f scenarios/L7-kanban-sprints/design/research/usability/session-1.md"
```

This passes when:
- `solution/backend/migrations/0003_auth_ownership.sql` exists (the auth + ownership migration)
- `design/sprints/sprint-2.md` exists
- `design/retros/retro-2.md` exists
- `design/research/usability/session-1.md` exists (Sprint 1 usability session)

Additionally verify that the auth endpoints work, the authz matrix is enforced on every endpoint, and Sprints 0+1 tests still pass as authenticated.

## Final step (REQUIRED)

After all the work above is done and the verifier check passes, write the file `artifacts/sprint_2_auth.done` containing exactly `sprint_2_auth:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished — it must be the LAST action taken.
