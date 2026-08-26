# Lane backend_core

## Outcome

Implement the complete Python/FastAPI backend for the L6 Kanban application under `scenarios/L6-kanban-app/solution/backend/`. The backend must implement every endpoint in the §2.1 API contract, the §2.3 data model, the §2.2 architecture constraints, and pass the smoke test suite.

Concrete files to create (all under `scenarios/L6-kanban-app/`):

- `solution/backend/requirements.txt` — pinned dependencies (fastapi, uvicorn, pydantic, sqlalchemy, passlib[bcrypt], itsdangerous or starlette sessions, python-multipart, aiofiles; ≤12 direct runtime deps)
- `solution/backend/app/__init__.py`
- `solution/backend/app/main.py` — app factory, health endpoint, error handlers, structured JSON request logging with correlation id, CORS/proxy config
- `solution/backend/app/db.py` — SQLite setup via SQLAlchemy, `DATABASE_URL`/`KANBAN_DB` env var, auto-schema creation on startup
- `solution/backend/app/models.py` — SQLAlchemy ORM models for users, boards, columns, cards, card_labels matching §2.3 schema exactly (column names pinned)
- `solution/backend/app/schemas.py` — Pydantic request/response schemas for all entities and operations
- `solution/backend/app/auth.py` — password hashing (bcrypt), server-side session via HttpOnly SameSite=Lax cookie (itsdangerous or starlette SessionMiddleware), `get_current_user` dependency, CSRF defense
- `solution/backend/app/ordering.py` — THE SINGLE WRITER of position values; implements fractional position scheme: new item gets max_position+1.0, move uses midpoint insertion, rebalance when gap<0.001; exports `append_position(session, parent_id, parent_type)`, `move_position(session, item, target_parent_id, target_index)`, `rebalance_if_needed(session, parent_id, parent_type)`
- `solution/backend/app/api/__init__.py`
- `solution/backend/app/api/auth.py` — POST /api/auth/register, POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me
- `solution/backend/app/api/boards.py` — GET /api/boards, POST /api/boards, GET /api/boards/{board_id}, PATCH /api/boards/{board_id}, DELETE /api/boards/{board_id}, POST /api/boards/{board_id}/columns
- `solution/backend/app/api/columns.py` — PATCH /api/columns/{column_id}, DELETE /api/columns/{column_id}, POST /api/columns/{column_id}/move, POST /api/columns/{column_id}/cards
- `solution/backend/app/api/cards.py` — PATCH /api/cards/{card_id}, DELETE /api/cards/{card_id}, POST /api/cards/{card_id}/move
- `tests/smoke/__init__.py`
- `tests/smoke/test_smoke.py` — smoke tests S1–S4 (API-only; S5/S6 are E2E)

## Steps

1. Read `scenarios/L6-kanban-app/REQUIREMENTS.md` §2.1, §2.2, §2.3, §2.4, §2.5 fully.

2. Create `solution/backend/requirements.txt` with pinned versions:
   ```
   fastapi>=0.111.0,<0.112
   uvicorn[standard]>=0.29.0,<0.30
   pydantic>=2.7.0,<3
   sqlalchemy>=2.0.0,<3
   passlib[bcrypt]>=1.7.4,<2
   itsdangerous>=2.1.0,<3
   python-multipart>=0.0.9,<0.1
   ```

3. Implement `app/db.py`: use SQLAlchemy with `create_engine`, read `DATABASE_URL` env (default `sqlite:///./kanban.db`), set `connect_args={"check_same_thread": False}` for SQLite, create all tables on startup via `Base.metadata.create_all(engine)`.

4. Implement `app/models.py` with exact column names from §2.3. Use `uuid.uuid4()` for ids stored as TEXT. Use `datetime.utcnow()` for timestamps. Add `updated_at` auto-update on boards and cards.

5. Implement `app/ordering.py` as the ONLY writer of position values:
   - `get_max_position(session, parent_id, parent_type) -> float`: returns max position in parent or 0.0
   - `append_position(session, parent_id, parent_type) -> float`: returns max+1.0
   - `reorder_items(session, items_in_new_order)`: assigns positions 1.0, 2.0, 3.0, ... (full rebalance)
   - `move_item(session, item, target_parent_id, target_index, item_type)`: implements the §2.1 move semantics — removes from source, inserts at target_index in destination using midpoint between neighbors; if gap<0.001 triggers rebalance; returns updated item and affected_column_ids. All done in one transaction with row-level locking.
   - NEVER called from route handlers directly for position arithmetic — route handlers call these functions.

6. Implement `app/auth.py`:
   - `hash_password(plain: str) -> str` using passlib bcrypt
   - `verify_password(plain: str, hashed: str) -> bool`
   - `SessionMiddleware` with `SECRET_KEY` from env (default a clearly-marked dev key), `HttpOnly=True`, `SameSite="lax"`, `Secure=False` (dev)
   - `get_current_user(request: Request, session: Session) -> User` dependency: reads user_id from session cookie, returns User or raises 401
   - CSRF: SameSite=Lax is the primary defense; document in DECISIONS.md

7. Implement all API routes. Authorization pattern for every board-scoped endpoint:
   - Resolve the resource by id from DB
   - If not found OR owner_id != current_user.id: return 404 (uniform per §1.6f)
   - Never trust client-supplied board_id or owner_id
   - Cards: resolve card→column→board→owner_id chain

8. Implement `GET /api/boards/{board_id}` to return fully nested response (board + columns ordered by position + cards per column ordered by position) in ONE query or bounded queries (no N+1).

9. Implement `POST /api/cards/{card_id}/move` with exact §2.1 semantics:
   - target_index is 0-based insertion index AFTER removal from source
   - Clamp target_index to [0, len(destination_after_removal)]
   - Same position no-op returns 200 without mutation
   - Cross-board move rejected with 404
   - Atomic: transaction wraps both parent updates

10. Implement `POST /api/columns/{column_id}/move` similarly for column reorder within board.

11. Error envelope: all errors return `{"error": {"code": "...", "message": "...", "field": "..."}}` with appropriate status codes. Never return stack traces or SQL in responses.

12. `GET /api/health` returns `{"status": "ok"}` only after schema is ready.

13. Write `tests/smoke/test_smoke.py` covering S1–S4:
    - S1: GET /api/health → 200 {"status":"ok"}
    - S2: register → login → GET /api/auth/me returns user → logout → me is 401
    - S3: POST /api/boards → appears in GET /api/boards
    - S4: create column, create card → both appear correctly nested and ordered in GET /api/boards/{id}

14. Run `cd scenarios/L6-kanban-app && pip install -r solution/backend/requirements.txt && python -m pytest tests/smoke/ -q` and fix until passing.

15. Run `ruff check solution/backend/` and `pyright solution/backend/` and fix all errors.

## Done when

The following command exits 0:

```bash
test -f scenarios/L6-kanban-app/solution/backend/requirements.txt && \
test -f scenarios/L6-kanban-app/solution/backend/app/main.py && \
test -f scenarios/L6-kanban-app/solution/backend/app/models.py && \
test -f scenarios/L6-kanban-app/solution/backend/app/ordering.py && \
test -f scenarios/L6-kanban-app/solution/backend/app/auth.py && \
cd scenarios/L6-kanban-app && \
pip install -q -r solution/backend/requirements.txt && \
python -m pytest tests/smoke/ -q --tb=short 2>&1 | grep -qE '(passed|no tests ran)'
```

## Final step (REQUIRED)

After all the above files exist and the smoke tests pass, write the file `artifacts/backend_core.done` containing exactly `backend_core:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
