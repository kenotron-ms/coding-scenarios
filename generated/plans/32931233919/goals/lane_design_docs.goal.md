# Lane lane_design_docs

## Outcome
Create all required design and discovery artifacts under `scenarios/L8-markdown-editor/design/` as specified in REQUIREMENTS.md §5.4. These documents constrain the implementation lanes and must be written first so security and performance choices are grounded in an explicit model.

The following files must exist (repo-relative paths):
- `scenarios/L8-markdown-editor/design/personas.md` — Ken, Ada, Atlas personas with goals, frustrations, key tasks, JTBD
- `scenarios/L8-markdown-editor/design/prd.md` — Product Requirements Document covering the full FR/NFR surface
- `scenarios/L8-markdown-editor/design/backlog.md` — Prioritized P0/P1 backlog with Definition of Done
- `scenarios/L8-markdown-editor/design/interaction-specs.md` — Editing model, keyboard map, host-picker/vault-switcher flow, conflict flow, connection states, perceived-performance/motion spec
- `scenarios/L8-markdown-editor/design/security-model.md` — Threat model: SSH trust model, secret handling policy, host-key verification policy (TOFU), webview/CSP design, Markdown/Mermaid sanitization strategy
- `scenarios/L8-markdown-editor/design/performance-budget.md` — Cold-boot (≤800 ms cold / ≤400 ms warm), first-render (≤300 ms after bytes arrive), idle memory ceiling (≤250 MB), measurement method
- `scenarios/L8-markdown-editor/design/a11y-annotations.md` — WCAG 2.1 AA annotations for main views: keyboard navigation, ARIA roles/labels, focus management, contrast ratios
- `scenarios/L8-markdown-editor/design/wireframes/` — directory with at least one lo-fi wireframe file (e.g., `main-layout.md` or `main-layout.svg`)
- `scenarios/L8-markdown-editor/design/hifi/` — directory with at least one hi-fi mockup description file

## Steps

1. Create the directory `scenarios/L8-markdown-editor/design/` and subdirectories `wireframes/` and `hifi/`.

2. Write `personas.md` with three personas:
   - Ken (remote-first power user): goals, frustrations, key tasks, JTBD
   - Ada (keyboard-driven writer): goals, frustrations, key tasks, JTBD
   - Atlas (agentic stakeholder — AI agent co-editing vault): goals, key tasks

3. Write `prd.md` covering:
   - Problem statement (remote vault editing without local sync)
   - User stories from REQUIREMENTS.md §1.3
   - All FRs (FR-1 through FR-12) with acceptance criteria references
   - All NFRs (NFR-1 through NFR-8)
   - Ambiguity resolutions (§1.6): WYSIWYM model chosen (source-faithful with rendered editing), SSH transport choice (russh or ssh2 Rust crate), editor engine choice (TipTap or Milkdown), conflict policy (detect + prompt, never silent overwrite), known_hosts/config location per platform

4. Write `backlog.md` with a prioritized P0/P1 table:
   - P0 items: FR-1,2,3,4,5,6,7,8,10; NFR-1,3,4,5
   - P1 items: FR-9,11,12; NFR-2 polish; Windows target; theming
   - Definition of Done checklist matching REQUIREMENTS.md §4.3

5. Write `interaction-specs.md` covering:
   - Editing model: WYSIWYM with source-anchored rendering (chosen engine, e.g., Milkdown/ProseMirror)
   - Keyboard map: all editing shortcuts, navigation shortcuts (tree, host picker, vault switcher)
   - Host-picker flow: list SSH config hosts → select → connect (async) → show connection state
   - Vault-switcher flow: browse tree → open file → edit → save
   - Conflict flow (FR-9): detect remote mtime change → modal with Reload/Keep/Diff options
   - Connection states: disconnected / connecting / connected / error / reconnecting
   - Perceived-performance spec: skeleton screens, optimistic UI, no blocking on SSH during boot

6. Write `security-model.md` as a threat model covering:
   - SSH trust model: auth delegated to ssh-agent/key files; no passwords stored or accepted by app
   - Secret handling policy: no passwords/private keys cross IPC boundary or land in logs/state
   - Host-key verification (TOFU): unknown/changed key → user prompt → explicit accept/reject; never auto-accept
   - Webview/CSP: strict Content-Security-Policy (no inline scripts, no remote scripts); Tauri capabilities minimally scoped
   - Markdown→HTML sanitization: DOMPurify or equivalent; `<script>`, `javascript:` hrefs, event handlers stripped
   - Mermaid sanitization: render in sandboxed iframe or via server-side rendering; no script injection
   - SFTP path handling: no path traversal; validate paths stay within vault root
   - Threat table: at minimum cover credential theft, host impersonation, XSS via document content, SFTP path traversal

7. Write `performance-budget.md` covering:
   - Cold boot ≤800 ms: definition (process start → interactive window, no SSH blocking), measurement method (tauri-driver timing), reference hardware spec
   - Warm boot ≤400 ms: definition (second launch with warm OS cache)
   - First render ≤300 ms: definition (bytes arrive from SSH → rendered in editor)
   - Idle memory ≤250 MB: measurement method
   - Budget defense strategy: lazy SSH connection, minimal frontend bundle, system webview advantage
   - Continuous tracking: measure at each build snapshot

8. Write `a11y-annotations.md` covering:
   - WCAG 2.1 AA compliance plan
   - Keyboard navigation map for all main views (host picker, file tree, editor toolbar, editor body)
   - ARIA roles and labels for custom components
   - Focus management: focus trap in modals, focus restoration after close
   - Contrast ratios ≥4.5:1 for text, ≥3:1 for UI components
   - Screen reader support for the editing surface (live regions for save status, connection status)

9. Write `wireframes/main-layout.md` — a text/ASCII description of the main window layout: sidebar (file tree + vault switcher), editor area, toolbar, status bar with connection state.

10. Write `hifi/main-layout.md` — a description of the hi-fi design: color palette, typography, spacing, component states (connected/disconnected/editing/saving).

## Done when
The following shell command exits 0:
```
test -f scenarios/L8-markdown-editor/design/security-model.md && \
test -f scenarios/L8-markdown-editor/design/performance-budget.md && \
test -f scenarios/L8-markdown-editor/design/personas.md && \
test -f scenarios/L8-markdown-editor/design/prd.md && \
test -f scenarios/L8-markdown-editor/design/interaction-specs.md && \
test -f scenarios/L8-markdown-editor/design/a11y-annotations.md && \
test -f scenarios/L8-markdown-editor/design/backlog.md
```

## Final step (REQUIRED)
After all design files are written and the check above passes, write the file `artifacts/lane_design_docs.done` containing exactly the text `lane_design_docs:ok` and nothing else (no trailing newline variations — just that string). This marker file is how the batch orchestrator confirms this lane finished; it must be the LAST action.
