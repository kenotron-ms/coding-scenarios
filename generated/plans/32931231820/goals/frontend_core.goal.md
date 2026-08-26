# Lane frontend_core

## Outcome

Implement the complete React/TypeScript frontend for the L6 Kanban application under `scenarios/L6-kanban-app/solution/frontend/`. The frontend must implement all SPA routes from §2.1, all UI requirements from §1.4, the §2.2 architecture constraints, WCAG 2.1 AA accessibility (NFR-4), and pass `tsc --noEmit` under `strict: true`.

This lane depends on `backend_core` being complete (the backend API contract is implemented and the types are known).

Concrete files to create (all under `scenarios/L6-kanban-app/solution/frontend/`):

- `package.json` — React 18+, TypeScript, Vite, React Router, Zustand, @dnd-kit/core + @dnd-kit/sortable + @dnd-kit/utilities, @axe-core/react (dev), eslint; ≤15 direct runtime deps
- `package-lock.json` — locked dependencies
- `vite.config.ts` — proxy `/api` to `http://localhost:8000`, serve on port 5173
- `tsconfig.json` — strict: true, target ES2020+
- `.eslintrc.cjs` — eslint config
- `src/main.tsx` — React root, BrowserRouter, error boundary
- `src/App.tsx` — route definitions (login, register, boards, board detail, card detail modal, 404)
- `src/types/api.ts` — TypeScript types for all API request/response shapes (User, Board, Column, Card, MoveCardRequest, etc.)
- `src/api/client.ts` — THE ONLY place fetch is called; typed functions for every API endpoint; handles credentials: 'include' for cookies; parses error envelope; throws typed errors
- `src/store/authStore.ts` — Zustand store for auth state (user, loading, login/logout/register actions)
- `src/store/boardStore.ts` — Zustand store for board state (boards, current board with columns and cards, optimistic update with snapshot/rollback, move actions)
- `src/styles/tokens.css` — imports `../../../design/tokens.css` (or copies/re-exports the design tokens); this is the CSS custom properties file consumed by components
- `src/routes/Login.tsx` — login form with validation, redirect if authenticated
- `src/routes/Register.tsx` — registration form with validation, redirect if authenticated
- `src/routes/BoardList.tsx` — board list with empty state, loading state, error state, create board form
- `src/routes/BoardDetail.tsx` — board detail with columns, cards, drag-and-drop, keyboard move, column reorder
- `src/components/Board.tsx` — board container component
- `src/components/Column.tsx` — column component with card list, drag target, keyboard interactions
- `src/components/Card.tsx` — card component with drag handle, keyboard pick-up, data-testid and data-card-id
- `src/components/CardDetail.tsx` — card detail modal with focus trap, Esc to close, focus return
- `src/components/EmptyState.tsx` — reusable empty state component
- `src/components/ErrorState.tsx` — reusable error state with retry
- `src/components/LoadingState.tsx` — reusable loading affordance

## Steps

1. Read `scenarios/L6-kanban-app/REQUIREMENTS.md` §1.4, §2.1, §2.2, §2.4 and the design artifacts from `scenarios/L6-kanban-app/design/` (tokens, interaction-specs, a11y-annotations).

2. Initialize the frontend project:
   ```bash
   cd scenarios/L6-kanban-app/solution
   npm create vite@latest frontend -- --template react-ts
   cd frontend
   npm install react-router-dom zustand @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
   npm install -D @types/react @types/react-dom eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser eslint-plugin-react-hooks
   ```

3. Configure `vite.config.ts` with proxy:
   ```ts
   server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }, port: 5173 }
   ```

4. Implement `src/types/api.ts` with strict TypeScript types matching the backend schemas exactly. No `any`. Include: `User`, `Board`, `BoardDetail` (with nested columns and cards), `Column`, `Card`, `ApiError`, `MoveCardRequest`, `MoveCardResponse`, `MoveColumnRequest`.

5. Implement `src/api/client.ts`:
   - Base URL from env or default to `/api`
   - All requests use `credentials: 'include'`
   - Parse `{"error": {...}}` envelope and throw typed `ApiError`
   - Export typed functions: `authApi.register`, `authApi.login`, `authApi.logout`, `authApi.me`, `boardsApi.list`, `boardsApi.create`, `boardsApi.get`, `boardsApi.update`, `boardsApi.delete`, `columnsApi.create`, `columnsApi.update`, `columnsApi.delete`, `columnsApi.move`, `cardsApi.create`, `cardsApi.update`, `cardsApi.delete`, `cardsApi.move`
   - No fetch calls anywhere else in the codebase

6. Implement `src/store/authStore.ts` with Zustand:
   - State: `user: User | null`, `loading: boolean`, `error: string | null`
   - Actions: `login`, `register`, `logout`, `checkAuth` (calls /api/auth/me on app init)
   - Persists auth state across reloads via checkAuth on mount

7. Implement `src/store/boardStore.ts` with Zustand:
   - State: `boards: Board[]`, `currentBoard: BoardDetail | null`, `loading`, `error`
   - Optimistic update pattern: before each mutation, snapshot current state; apply optimistic change; on API failure, restore snapshot and set error message
   - Actions: `fetchBoards`, `createBoard`, `updateBoard`, `deleteBoard`, `fetchBoard`, `createColumn`, `updateColumn`, `deleteColumn`, `moveColumn`, `createCard`, `updateCard`, `deleteCard`, `moveCard`
   - `moveCard` updates both source and destination columns optimistically using the §2.1 move semantics (target_index after removal)
   - `moveColumn` updates column order optimistically

8. Implement drag-and-drop using `@dnd-kit`:
   - Use `DndContext`, `SortableContext`, `useSortable` for cards within columns
   - Use `DndContext` with custom sensors for column reorder
   - Add `KeyboardSensor` with custom coordinates for keyboard move (FR-26)
   - On `onDragEnd`: call `boardStore.moveCard` or `boardStore.moveColumn`
   - Keyboard move: Space/Enter picks up, Arrow keys move, Escape cancels, Space/Enter drops
   - Announce each move via `aria-live="polite"` region

9. Implement accessibility requirements (NFR-4, all a11y-* requirements):
   - Board: `role="main"`, `aria-label="Board: {title}"`
   - Columns: `role="list"`, `aria-label="{title} column, {n} cards"`, `data-testid="column"`, `data-column-id`
   - Cards: `role="listitem"`, `aria-label="{title}"`, `data-testid="card"`, `data-card-id`
   - Board list: `data-testid="board-list"`, each board item `data-testid="board-card"`, `data-board-id`
   - `aria-live="polite"` region for keyboard move announcements
   - Card detail: focus trap (Tab cycles within modal), Esc closes, focus returns to invoking card
   - Every form control has associated `<label>`; validation errors use `aria-describedby`
   - `prefers-reduced-motion`: wrap transitions in `@media (prefers-reduced-motion: no-preference)`
   - Skip-to-content link if there is persistent navigation

10. Implement all view states:
    - Loading: spinner/skeleton while data is in flight (never blank)
    - Empty: purpose-built empty state with CTA for no boards, no columns, no cards
    - Error: recoverable error view with retry button; redirect to /login on 401
    - Populated: the main view

11. Implement optimistic UI with rollback (FR-30):
    - Card create: add card to column immediately; on failure, remove it and show toast
    - Card move: update both columns immediately; on failure, restore both and show toast
    - Column reorder: update column order immediately; on failure, restore and show toast
    - Inline rename: update title immediately; on failure, restore original and show toast
    - Post-rollback state must equal server state (verified by reload)

12. Implement input validation client-side (FR-34):
    - Board title: 1–120 chars after trim
    - Column title: 1–80 chars after trim
    - Card title: 1–200 chars after trim
    - Card description: 0–5000 chars
    - Show field-level errors immediately; do not submit if invalid
    - Never use `dangerouslySetInnerHTML` for user text (FR-35)

13. Implement SPA routes with auth guards (FR-5):
    - `/login` and `/register`: redirect to `/boards` if authenticated
    - `/boards`, `/boards/:boardId`, `/boards/:boardId/cards/:cardId`: redirect to `/login` if not authenticated
    - Never flash board data before redirect

14. Run `npm run build` and fix all TypeScript errors. Run `npx tsc --noEmit` under strict:true. Run `npx eslint src/` and fix all errors.

15. Ensure `src/styles/tokens.css` imports the design tokens (either by importing `../../../design/tokens.css` via Vite alias, or by copying the CSS custom properties). The tokens must be consumed by component styles.

## Done when

The following command exits 0:

```bash
test -f scenarios/L6-kanban-app/solution/frontend/src/api/client.ts && \
test -f scenarios/L6-kanban-app/solution/frontend/src/types/api.ts && \
test -f scenarios/L6-kanban-app/solution/frontend/src/store/boardStore.ts && \
test -f scenarios/L6-kanban-app/solution/frontend/src/store/authStore.ts && \
test -f scenarios/L6-kanban-app/solution/frontend/src/styles/tokens.css && \
cd scenarios/L6-kanban-app/solution/frontend && \
npm ci --silent && \
npx tsc --noEmit 2>&1 | tee /tmp/tsc_out.txt; \
lines=$(wc -l < /tmp/tsc_out.txt); \
test $lines -eq 0
```

## Final step (REQUIRED)

After all the above files exist and `tsc --noEmit` passes with zero output, write the file `artifacts/frontend_core.done` containing exactly `frontend_core:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
