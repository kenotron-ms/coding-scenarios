# Lane sprint2_auth

## Outcome

Implement Sprint 2 (Auth & Multi-user) of the L7 Kanban application, building on Sprints 0 and 1 already in `scenarios/L7-kanban-sprints/solution/`. This sprint adds user registration/login/logout, server-side sessions with HttpOnly cookies, board ownership, and authorization enforcement on every endpoint. All Sprint 0 and Sprint 1 behavior must remain 100% intact when accessed as an authenticated user.

Concrete changes (repo-relative paths under `scenarios/L7-kanban-sprints/solution/`):

- `backend/migrations/0003_auth_ownership.sql` (or .py): creates `user` and `session` tables; adds `owner_id` to `board`; attributes all pre-auth boards to a seeded owner (ambiguity 1.6-6 resolution)
- `backend/api/auth.py`: register, login, logout, me endpoints
- `backend/services/auth_service.py`: password hashing (bcrypt/argon2/scrypt), session management
- `backend/repositories/user_repo.py`, `session_repo.py`
- `backend/api/middleware.py` (or equivalent): session authentication middleware returning 401 on unauthenticated requests
- `backend/services/authz.py` (single choke point): ownership check — a request for a board owned by a different user returns the chosen denial code (404 or 403, consistent everywhere)
- All existing board/column/card routes updated to require authentication and pass through the authz choke point
- `frontend/src/`: register screen, login screen, logout button, authenticated shell, session-expired flow
- `tests/smoke/sprint_2/`: Playwright smoke tests — register -> login -> GET /api/auth/me returns user; logout -> 401
- `design/sprints/sprint-2.md`, `design/retros/retro-2.md`, `design/research/usability/session-2.md`
- `design/mockups/s2-auth.md`
- `design/a11y/annotations-s2.md`
- `design/CHANGELOG-design.md` updated

Key implementation requirements:

- `POST /api/auth/register {email, password}`: email unique case-insensitive, password >= 8 chars, stored only as salted hash (bcrypt/argon2/scrypt — never plaintext, never returned). Returns User (201).
- `POST /api/auth/login {email, password}`: establishes server-side session, sets `HttpOnly; SameSite=Lax` cookie. Returns User.
- `POST /api/auth/logout`: invalidates session server-side. Replaying the old cookie yields 401.
- `GET /api/auth/me`: returns User or 401.
- All board/column/card endpoints now require authenticated session; unauthenticated requests get 401.
- Authorization: user B's request for user A's board/column/card returns the chosen denial code (404 or 403), consistently, without leaking existence if 404 chosen.
- Pre-auth data (boards from Sprints 0-1): attributed to a seeded `legacy@local` account (or first registered account) by migration 0003. No data loss. Every board still exists with intact ordering, owned by exactly one account.
- `health.schema_version` reports `3` after migration 0003.
- Session cookie: `HttpOnly`, `SameSite=Lax`. Not readable from `document.cookie`.
- Sprint 0 and Sprint 1 regression gate: all prior smoke tests still pass when run as an authenticated user.
- WCAG 2.1 AA on auth screens: form errors programmatically associated with inputs, zero critical/serious axe violations.

## Steps

1. **Migration 0003**: Write `backend/migrations/0003_auth_ownership.sql`:
   - Create `user` table: `id, email (unique, lowercase), password_hash, display_name, created_at`
   - Create `session` table: `token (unique), user_id -> user, created_at, expires_at, revoked_at`
   - Add `owner_id` column to `board` (nullable initially, then backfill, then NOT NULL)
   - Seed a `legacy@local` system user; set all existing boards' `owner_id` to this user
   - Bump schema_version to 3

2. **Password hashing**: Use `bcrypt` (via `passlib[bcrypt]` or `bcrypt` package). Never store plaintext. Never log or return password material.

3. **Session management**: Generate cryptographically random session tokens (e.g., `secrets.token_urlsafe(32)`). Store in `session` table with expiry (e.g., 24 hours). On logout, set `revoked_at`. Session middleware reads cookie, looks up session, rejects if revoked or expired.

4. **Auth endpoints**: Implement `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` in `backend/api/auth.py`. Login sets `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax; Path=/`.

5. **Auth middleware**: Add middleware (FastAPI dependency or Starlette middleware) that reads the session cookie, validates it, and injects the current user into the request context. Returns 401 for all `/api/` routes except `/api/auth/*` and `/api/health` when unauthenticated.

6. **Authorization choke point**: Implement `services/authz.py` with a single `require_board_owner(board_id, current_user)` function that fetches the board and raises an HTTP exception (404 or 403, documented choice) if the board doesn't belong to the current user. All board/column/card service methods call this. New Sprint 3/4 entities will also go through this seam.

7. **Update all existing routes**: Add the auth dependency to all board/column/card routes. The behavior is unchanged once authenticated — auth is a gate, not a rewrite.

8. **Frontend - auth screens**: Add register page (`/register`), login page (`/login`), logout button in the app shell. On 401 response, redirect to login (session-expired flow). After login, return user to where they were.

9. **Smoke tests**: Write `tests/smoke/sprint_2/test_sprint2.spec.ts` covering: register -> login -> GET /api/auth/me returns user; logout -> subsequent authenticated request returns 401.

10. **Design artifacts**: Create `design/sprints/sprint-2.md`, `design/retros/retro-2.md` (must note the pre-auth data attribution decision and the authz refactor regression risk), `design/research/usability/session-2.md` (>= 5 tasks on auth flows, >= 1 major finding groomed into Sprint 3), `design/mockups/s2-auth.md`, `design/a11y/annotations-s2.md`, update `design/CHANGELOG-design.md`.

11. **Regression check**: Before declaring done, run Sprint 0 and Sprint 1 smoke tests with an authenticated session to confirm no regressions.

12. **Verify**: Start server, run Sprint 2 smoke tests headlessly, confirm exit 0.

## Done when

The following command exits 0 (run from repo root):

```bash
cd scenarios/L7-kanban-sprints/solution && make migrate && make run &SERVER_PID=$!; sleep 5; npx playwright test tests/smoke/sprint_2 --reporter=line; STATUS=$?; kill $SERVER_PID 2>/dev/null; exit $STATUS
```

This verifies:
- Migration 0003 applied (schema_version = 3)
- App starts on port 8080
- Sprint 2 smoke tests pass: register, login, /me, logout -> 401

## Final step (REQUIRED)

After all work is complete and the Done-when check passes with exit 0, write the file `artifacts/sprint2_auth.done` containing exactly `sprint2_auth:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action taken.
