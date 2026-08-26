# Lane lane_editor_frontend

## Outcome
Implement the TypeScript frontend SPA for the L8 Markdown vault editor under `scenarios/L8-markdown-editor/src/`. This includes the WYSIWYM editor (source-faithful rendered editing), Mermaid/code rendering with sanitization, file tree, host picker, vault switcher, and the typed IPC client layer. No secrets cross the IPC boundary.

Required files (repo-relative):
- `scenarios/L8-markdown-editor/package.json` — npm manifest with TypeScript, chosen framework (Svelte/React/Solid), editor engine (Milkdown/TipTap), Mermaid, DOMPurify, eslint, tsc
- `scenarios/L8-markdown-editor/tsconfig.json` — strict TypeScript config (no `any` on IPC boundary)
- `scenarios/L8-markdown-editor/src/main.ts` — SPA entry point
- `scenarios/L8-markdown-editor/src/ipc/client.ts` — typed IPC client wrapping all Tauri commands
- `scenarios/L8-markdown-editor/src/editor/document-model.ts` — isolated document model + Markdown serializer (lossless round-trip)
- `scenarios/L8-markdown-editor/src/editor/editor.ts` (or `.svelte`/`.tsx`) — WYSIWYM editor component
- `scenarios/L8-markdown-editor/src/components/FileTree.ts` (or framework equivalent) — file tree component
- `scenarios/L8-markdown-editor/src/components/HostPicker.ts` (or framework equivalent) — host picker component

## Steps

1. Initialize the frontend project under `scenarios/L8-markdown-editor/`:
   - `package.json`: choose a lightweight framework for boot speed (Svelte recommended for minimal bundle; React or Solid also acceptable — document rationale in a comment). Include: `typescript`, chosen framework, `@milkdown/core` (or `@tiptap/core`), `mermaid`, `dompurify`, `@types/dompurify`, `eslint`, `@typescript-eslint/parser`, `vite` (or equivalent bundler).
   - `tsconfig.json`: `"strict": true`, `"noImplicitAny": true`, `"noUncheckedIndexedAccess": true`. No `any` on IPC boundary types.
   - `.eslintrc.json` or `eslint.config.js`: enforce no-`any` on IPC types, no raw `innerHTML` without sanitization.

2. Implement `src/ipc/client.ts` — typed IPC client:
   - Import `invoke` from `@tauri-apps/api/core`.
   - Define TypeScript interfaces for all IPC types (matching Rust structs): `SshHostEntry`, `SessionHandle`, `DirEntry`, `FileContent`, `VaultRecord`, `TailscaleStatus`, `HostKeyDecision`, `WriteError`, `SshError`.
   - Export typed async functions for each command: `listHosts()`, `connect(hostAlias)`, `verifyHostKey(host, fingerprint, decision)`, `listDir(sessionId, path)`, `readFile(sessionId, path)`, `writeFile(sessionId, path, content, baseMtime)`, `watchFile(sessionId, path)`, `listVaults()`, `rememberVault(name, hostAlias, remotePath)`, `tailscaleStatus()`.
   - NO `any` types on function signatures or return types.
   - No raw Tauri `invoke` calls outside this module (all IPC goes through this client).

3. Implement `src/editor/document-model.ts` — isolated document model and Markdown (de)serializer:
   - `parseMarkdown(source: string): EditorDocument` — parse CommonMark + GFM into an internal AST.
   - `serializeDocument(doc: EditorDocument): string` — serialize back to Markdown with MINIMAL DIFF guarantee: regions the user did not touch are byte-preserved; no whole-file reflow or re-wrapping.
   - The serializer must be lossless for unedited regions — this is NFR-4 and a grading gate.
   - Export the `EditorDocument` type and both functions. This module must be independently testable.
   - Include at least basic unit tests in `src/editor/document-model.test.ts` verifying round-trip identity on a sample document.

4. Implement `src/editor/editor.ts` (or `.svelte`/`.tsx`) — WYSIWYM editor component:
   - Use the chosen editor engine (Milkdown, TipTap, or CodeMirror 6).
   - Render headings, lists, tables, task lists, strikethrough, autolinks (CommonMark + GFM).
   - Render **Mermaid diagrams**: detect fenced code blocks with `mermaid` language tag; render via `mermaid.render()` in a sandboxed context; sanitize the output with DOMPurify before inserting into DOM.
   - Render **syntax-highlighted code**: fenced code blocks with language tag → Shiki or CodeMirror syntax highlighting.
   - **Sanitization (security gate)**: all Markdown→HTML output passes through DOMPurify with a strict config (no `<script>`, no `javascript:` hrefs, no event handler attributes). This is `L8-SEC-sanitize`.
   - Formatting toolbar: bold, italic, heading levels, code, link, bullet list, numbered list, task list, table insert.
   - Keyboard shortcuts: standard Markdown shortcuts (e.g., `**` for bold, `#` for heading) + formatting shortcuts (Ctrl+B, Ctrl+I, etc.).
   - Emit `onChange(doc: EditorDocument)` events for the parent to track dirty state.

5. Implement `src/components/FileTree.ts` (or framework equivalent):
   - Display the remote directory tree (folders + `.md` files) from `listDir()` results.
   - Lazy-load: only fetch children when a folder is expanded.
   - Keyboard navigable: arrow keys to move focus, Enter to open, Space to expand/collapse.
   - ARIA roles: `role="tree"`, `role="treeitem"`, `aria-expanded`, `aria-selected`.

6. Implement `src/components/HostPicker.ts` (or framework equivalent):
   - On mount, call `listHosts()` and display the list of SSH config hosts.
   - On host selection, call `connect(hostAlias)` and show connection state (connecting / connected / error).
   - Handle host-key verification: listen for Tauri events from the Rust core requesting TOFU confirmation; show a modal with the fingerprint and Accept/Reject buttons; call `verifyHostKey()` with the user's decision.
   - Show actionable error messages for auth failures, unknown hosts, connection timeouts.

7. Implement `src/components/VaultSwitcher.ts` (or framework equivalent):
   - Call `listVaults()` on mount; show previously-opened vaults with host alias, path, last-opened time.
   - Quick-reopen: select a vault → connect to its host → open its root in the file tree.
   - `rememberVault()` called after successfully opening a new vault.

8. Implement `src/app.ts` (or main component):
   - Boot sequence: show the window immediately (cold-boot budget); defer all SSH/network work.
   - Restore last session on launch: call `listVaults()` → find last-used vault → reconnect async → reopen last file async. Show skeleton/loading state while connecting; never block the window.
   - External-change detection (FR-9): listen for `watch_file` events; on change detected, show a non-blocking toast/modal: "File changed externally — Reload / Keep mine / Show diff".
   - Connection resilience (FR-11): on SSH disconnect, show reconnect UI; preserve the in-memory editor buffer; attempt reconnect on user action.

9. Accessibility (NFR-5, AC-7):
   - All interactive elements keyboard-reachable via Tab/Shift-Tab.
   - Visible focus indicators on all focusable elements.
   - ARIA labels on icon buttons and custom controls.
   - Live regions for connection status and save status.
   - Contrast ≥4.5:1 for text.

10. Linting and type-checking:
    - Add `"typecheck": "tsc --noEmit"` and `"lint": "eslint src/"` scripts to `package.json`.
    - The verifier runs `npm run typecheck` and `npm run lint`; both must exit 0 with no errors.

## Done when
The following shell command exits 0:
```
test -f scenarios/L8-markdown-editor/src/main.ts && \
test -f scenarios/L8-markdown-editor/src/editor/document-model.ts && \
test -f scenarios/L8-markdown-editor/src/ipc/client.ts && \
test -f scenarios/L8-markdown-editor/package.json
```

## Final step (REQUIRED)
After all frontend source files are written and the check above passes, write the file `artifacts/lane_editor_frontend.done` containing exactly the text `lane_editor_frontend:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished; it must be the LAST action.
