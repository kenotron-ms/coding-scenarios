# Lane integration_e2e

## Outcome

Wire together the backend and frontend into a runnable application by implementing the entrypoint scripts, seed data, README, and smoke E2E tests. The app must start from a clean checkout via `solution/run.sh`, pass the health check, and pass the full smoke suite (S1–S6).

This lane depends on `backend_core` and `frontend_core` being complete, and `design_artifacts` providing the DECISIONS.md.

Concrete files to create (all under `scenarios/L6-kanban-app/`):

- `solution/run.sh` — starts both the FastAPI backend (uvicorn) and the Vite dev server (or serves the built SPA); exits non-zero if either fails to bind; idempotent
- `solution/seed.py` — creates alice@example.com and bob@example.com (password `password123`) idempotently; used by acceptance tests
- `solution/README.md` — how to run, how to test, architecture summary (≤1 page)
- `tests/smoke/test_smoke_e2e.py` (or `tests/smoke_e2e/smoke.spec.ts`) — E2E smoke tests S5 and S6 using Playwright

## Steps

1. Read `scenarios/L6-kanban-app/REQUIREMENTS.md` §2.5 (entrypoint contract) fully.

2. Implement `solution/run.sh`:
   ```bash
   #!/usr/bin/env bash
   set -e
   
   # Kill any existing processes on our ports
   fuser -k ${API_PORT:-8000}/tcp 2>/dev/null || true
   fuser -k ${PORT:-5173}/tcp 2>/dev/null || true
   
   # Start the backend
   cd "$(dirname "$0")/backend"
   DATABASE_URL="${DATABASE_URL:-sqlite:///./kanban.db}" \
   SECRET_KEY="${SECRET_KEY:-dev-secret-key-change-in-production}" \
   API_PORT="${API_PORT:-8000}" \
   uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8000}" &
   BACKEND_PID=$!
   
   # Wait for backend health
   for i in $(seq 1 30); do
     if curl -sf "http://localhost:${API_PORT:-8000}/api/health" > /dev/null 2>&1; then
       break
     fi
     sleep 1
   done
   
   # Start the frontend (dev mode with proxy, or serve built dist)
   cd "$(dirname "$0")/frontend"
   npm run dev -- --port "${PORT:-5173}" --host &
   FRONTEND_PID=$!
   
   wait $BACKEND_PID $FRONTEND_PID
   ```
   Make it executable: `chmod +x solution/run.sh`

3. Implement `solution/seed.py`:
   ```python
   """Idempotent seed script: creates alice@example.com and bob@example.com."""
   import os, sys
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
   from app.db import engine, SessionLocal
   from app.models import Base, User
   from app.auth import hash_password
   import uuid
   from datetime import datetime
   
   Base.metadata.create_all(engine)
   
   SEED_USERS = [
       ("alice@example.com", "password123"),
       ("bob@example.com", "password123"),
   ]
   
   with SessionLocal() as session:
       for email, password in SEED_USERS:
           existing = session.query(User).filter(User.email == email.lower()).first()
           if not existing:
               user = User(
                   id=str(uuid.uuid4()),
                   email=email.lower(),
                   password_hash=hash_password(password),
                   created_at=datetime.utcnow(),
               )
               session.add(user)
       session.commit()
   print("Seed complete.")
   ```

4. Implement `solution/README.md` covering:
   - Prerequisites (Python ≥3.11, Node ≥20)
   - Setup commands: `pip install -r solution/backend/requirements.txt && npm --prefix solution/frontend ci`
   - Run: `./solution/run.sh`
   - Seed: `python solution/seed.py`
   - Test: `pytest tests/smoke/ -q && npx playwright test tests/smoke_e2e`
   - Architecture: backend (FastAPI + SQLAlchemy + SQLite), frontend (React 18 + TypeScript + Vite + Zustand + @dnd-kit), communication (HTTP REST API only), ordering (fractional REAL positions with midpoint insertion), session (HttpOnly SameSite=Lax cookie)
   - Key design decisions: references solution/DECISIONS.md

5. Implement Playwright E2E smoke tests for S5 and S6. Create `tests/smoke_e2e/smoke.spec.ts`:
   ```typescript
   import { test, expect } from '@playwright/test';
   
   const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
   const API_URL = process.env.API_URL || 'http://localhost:8000/api';
   
   // Helper: register and login a test user
   async function loginUser(page, email: string, password: string) {
     await page.goto(`${BASE_URL}/login`);
     await page.fill('[name="email"]', email);
     await page.fill('[name="password"]', password);
     await page.click('[type="submit"]');
     await page.waitForURL('**/boards');
   }
   
   test.describe('Smoke S5: create board, column, card visible in DOM', () => {
     test('create board -> add column -> add card -> card visible', async ({ page }) => {
       // Register a fresh user for this test
       const email = `smoke5-${Date.now()}@example.com`;
       await page.goto(`${BASE_URL}/register`);
       await page.fill('[name="email"]', email);
       await page.fill('[name="password"]', 'password123');
       await page.click('[type="submit"]');
       await page.waitForURL('**/boards');
       
       // Create a board
       await page.click('[data-testid="create-board-button"]');
       await page.fill('[name="board-title"]', 'Test Board');
       await page.keyboard.press('Enter');
       await page.click('[data-testid="board-card"]');
       await page.waitForURL('**/boards/**');
       
       // Add a column "To Do"
       await page.click('[data-testid="add-column-button"]');
       await page.fill('[name="column-title"]', 'To Do');
       await page.keyboard.press('Enter');
       
       // Add a card "First card"
       const toDoColumn = page.locator('[data-testid="column"]').filter({ hasText: 'To Do' });
       await toDoColumn.locator('[data-testid="add-card-button"]').click();
       await page.fill('[name="card-title"]', 'First card');
       await page.keyboard.press('Enter');
       
       // Assert card is visible in the column
       await expect(toDoColumn.locator('[data-testid="card"]').filter({ hasText: 'First card' })).toBeVisible();
     });
   });
   
   test.describe('Smoke S6: drag card to another column, persists after reload', () => {
     test('drag card from To Do to Done, reload, card still in Done', async ({ page }) => {
       const email = `smoke6-${Date.now()}@example.com`;
       await page.goto(`${BASE_URL}/register`);
       await page.fill('[name="email"]', email);
       await page.fill('[name="password"]', 'password123');
       await page.click('[type="submit"]');
       await page.waitForURL('**/boards');
       
       // Create board with two columns and one card via API for reliability
       const resp = await page.request.post(`${API_URL}/boards`, {
         data: { title: 'Drag Test Board' }
       });
       const board = await resp.json();
       
       const colResp1 = await page.request.post(`${API_URL}/boards/${board.id}/columns`, {
         data: { title: 'To Do' }
       });
       const toDoCol = await colResp1.json();
       
       await page.request.post(`${API_URL}/boards/${board.id}/columns`, {
         data: { title: 'Done' }
       });
       
       const cardResp = await page.request.post(`${API_URL}/columns/${toDoCol.id}/cards`, {
         data: { title: 'First card' }
       });
       const card = await cardResp.json();
       
       await page.goto(`${BASE_URL}/boards/${board.id}`);
       
       // Drag "First card" from "To Do" to "Done"
       const cardEl = page.locator(`[data-testid="card"][data-card-id="${card.id}"]`);
       const doneColumn = page.locator('[data-testid="column"]').filter({ hasText: 'Done' });
       
       const cardBox = await cardEl.boundingBox();
       const doneBox = await doneColumn.boundingBox();
       
       await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
       await page.mouse.down();
       await page.mouse.move(doneBox.x + doneBox.width / 2, doneBox.y + doneBox.height / 2, { steps: 10 });
       await page.mouse.up();
       
       // Wait for optimistic update
       await expect(doneColumn.locator('[data-testid="card"]').filter({ hasText: 'First card' })).toBeVisible({ timeout: 3000 });
       
       // Reload and verify persistence
       await page.reload();
       await expect(page.locator('[data-testid="column"]').filter({ hasText: 'Done' }).locator('[data-testid="card"]').filter({ hasText: 'First card' })).toBeVisible();
     });
   });
   ```

6. Create `playwright.config.ts` at `scenarios/L6-kanban-app/`:
   ```typescript
   import { defineConfig } from '@playwright/test';
   export default defineConfig({
     testDir: './tests',
     use: {
       baseURL: process.env.BASE_URL || 'http://localhost:5173',
       screenshot: 'only-on-failure',
     },
     webServer: undefined,  // harness starts the server
   });
   ```

7. Verify the full setup works:
   - `cd scenarios/L6-kanban-app && pip install -r solution/backend/requirements.txt`
   - `cd scenarios/L6-kanban-app/solution/frontend && npm ci`
   - Start the app: `./solution/run.sh &`
   - Wait for health: `curl http://localhost:8000/api/health`
   - Run seed: `python solution/seed.py`
   - Run smoke API tests: `pytest tests/smoke/ -q`
   - Stop the app

8. Verify `solution/run.sh` is executable and starts both processes without interactive input.

9. Verify `solution/seed.py` is idempotent (running twice does not error or duplicate users).

10. Verify `solution/README.md` exists and covers run/test/architecture.

## Done when

The following command exits 0:

```bash
test -f scenarios/L6-kanban-app/solution/run.sh && \
test -f scenarios/L6-kanban-app/solution/seed.py && \
test -x scenarios/L6-kanban-app/solution/run.sh && \
test -f scenarios/L6-kanban-app/solution/README.md && \
grep -q 'alice@example.com' scenarios/L6-kanban-app/solution/seed.py && \
grep -q 'bob@example.com' scenarios/L6-kanban-app/solution/seed.py
```

## Final step (REQUIRED)

After all the above files exist and the check above passes, write the file `artifacts/integration_e2e.done` containing exactly `integration_e2e:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
