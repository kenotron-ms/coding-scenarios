# L8 — Markdown Vault Editor (Tauri + SSH) — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> discovery/design obligations fixed by the **L8 row** of
> `framework/ARTIFACT_GRADIENT.md`.
>
> **Hand-curated capstone — extends the designed ladder.** L0–L7 form a
> systematically-graded ladder; **L8 is a bespoke top rung** chosen because it
> concentrates several *new* classes of difficulty that the web-app rungs never
> touch: a **native desktop shell (Tauri)**, **remote and security-sensitive
> I/O over SSH**, integration with **OS-level config (`~/.ssh/config`)**, a
> **hard cold-boot performance budget**, and a **WYSIWYM editing experience** as
> the product's soul. Its rubric weight profile and pass threshold extend the
> trajectory table in `RUBRIC_FRAMEWORK.md §3` rather than continuing it
> mechanically — see §7 for rationale. Proposed parameters (perf budget number,
> weight profile, pass threshold) are flagged as tunable.

## 0. Scenario Summary
- **Level:** L8
- **Codename / dir:** `L8-markdown-editor`
- **One-liner:** A Tauri desktop app — a lightning-fast, WYSIWYM Markdown
  reader/editor that opens "vaults" of Markdown files **over SSH** (optionally
  via Tailscale), discovers hosts by reading the user's SSH config, remembers
  vaults it has seen before, and renders Mermaid diagrams and syntax-highlighted
  code. Markdown for the agentic era: a human front-end to vaults that AI agents
  also read and write.
- **New difficulty introduced:** First **native desktop application** that
  integrates with the **operating system** and **remote systems**. Distinct from
  L6/L7 (a browser web app) along four axes at once: (1) a native shell
  (Tauri: Rust core + system webview, cross-platform packaging); (2) **remote,
  secure file I/O over SSH/SFTP** with real key/agent handling and host-key
  verification; (3) reading and honoring **system configuration**
  (`~/.ssh/config`, Tailscale); (4) a **desktop-grade non-functional bar** —
  sub-second cold boot and a lossless WYSIWYM editor. Security and performance
  are load-bearing, not incidental.
- **Estimated reference solution size:** 5,000–12,000 LoC across Rust
  (Tauri core/commands) + TypeScript (editor SPA); 60–120 files.
- **Time budget:** Multi-session / multi-day. A single supervised run targets a
  working slice; the full P0 surface is a **~2–4 day** budget for a strong
  strategy (tunable — this rung is meant to stress sustained convergence).
- **Iteration budget:** soft 60, hard 150 edit→verify cycles.
- **Intervention budget:** 0. `clarify`-type interventions on the deliberately-open
  transport/editor-engine ambiguities (§1.6) are low severity and do not, by
  themselves, cap Autonomy. Any `hint`/`rescue` on the SSH/security surface is a
  strong negative signal.

## 1. Product Requirements

### 1.1 Problem statement
Markdown power-users keep their knowledge in "vaults" — trees of `.md` files —
that increasingly live on **remote machines** (dev boxes, servers, homelab) and
are increasingly **co-edited by AI agents**. Today they either sync those files
locally (slow, conflict-prone, leaks copies), edit them in a terminal (no
diagrams, no WYSIWYM), or run a heavyweight web app (slow to boot, browser tab
tax). They want a **native, beautiful, instant** editor that reaches remote
vaults **directly over SSH** — no sync — with a modern rendered editing
experience, and that behaves well when an agent changes a file underneath them.

### 1.2 Target users / personas — **Required**
- **Ken — the remote-first power user.** *Goals:* open a vault on any of his
  SSH hosts in one keystroke and start writing in a rendered view immediately;
  never manage credentials in-app. *Frustrations:* sync tools that duplicate
  files and conflict; editors that reflow/mangle his Markdown on save; slow cold
  starts that break flow. *Key tasks:* pick a host from his SSH config, open a
  known vault, edit a note with headings/lists/code/diagrams, save back over SSH.
- **Ada — the keyboard-driven writer.** *Goals:* fully keyboard-navigable
  editing, fast formatting via Markdown shortcuts, no mouse. *Frustrations:*
  WYSIWYG editors that fight her muscle memory or lose semantic structure.
- **Atlas — the agent (agentic-era stakeholder).** A non-human "user": an AI
  agent reads and writes the same vault files out-of-band. The app must **detect
  external changes** and offer reload/merge rather than silently overwriting an
  agent's edits — the human and the agent share one source of truth on disk.

### 1.3 User stories — **Required**
- As Ken, I want the app to list my SSH hosts from `~/.ssh/config`, so that I can
  connect without retyping connection details.
- As Ken, I want to open a remote directory as a "vault" and browse its Markdown
  tree, so that I can navigate my notes.
- As Ken, I want to open, edit, and save a `.md` file directly over SSH, so that
  I never keep a local copy.
- As Ken, I want the app to remember vaults I've opened before and restore my
  last session, so that reopening is one action.
- As any user, I want a WYSIWYM editing surface that renders headings, lists,
  tables, task lists, **Mermaid diagrams**, and **syntax-highlighted code**,
  while saving back **clean, minimally-diffed Markdown**.
- As Ada, I want to do everything from the keyboard with clear focus and screen
  reader support.
- As Ken, I want the app to be interactive **within a fraction of a second** of
  launching, so that it feels native.
- As Ken (with Atlas in the loop), I want to be warned when a file changed on the
  remote while I was editing, so that I don't clobber an agent's changes.
- As Ken, I optionally want to reach hosts over **Tailscale** (MagicDNS names)
  when my machine is on the tailnet.

### 1.4 Functional requirements
- **FR-1 Host discovery** — Parse `~/.ssh/config` and present `Host` entries as
  connection targets, honoring `HostName`, `User`, `Port`, `IdentityFile`,
  `ProxyJump`, and `Include`. Wildcard/`Match` blocks handled sensibly
  (documented, §1.6).
- **FR-2 SSH/SFTP connect** — Connect to a chosen host and authenticate using
  **ssh-agent and/or the identity from config/known keys** — never by storing a
  password in the app. Surface auth/connection failures with actionable messages.
- **FR-3 Host-key verification** — Verify the server host key against
  `~/.ssh/known_hosts`; on an unknown/changed key, **prompt the user** (TOFU) and
  never silently auto-accept. (Security-critical; part of the gate, §6/§7.)
- **FR-4 Vault open & browse** — Open a remote directory as a vault; list and
  navigate its Markdown tree (folders + `.md` files); lazy-load large trees.
- **FR-5 Vault memory** — Persist previously-opened vaults (host alias + remote
  path + display name + last-opened) and offer quick reopen; restore the last
  session on launch. **No secrets** are persisted (only host aliases/paths).
- **FR-6 Render** — Render CommonMark + GFM (tables, task lists, strikethrough,
  autolinks), **Mermaid** diagrams, and **syntax-highlighted** fenced code
  blocks; resolve vault-relative image paths over SSH.
- **FR-7 WYSIWYM editing** — Edit in a rendered, source-anchored surface (not a
  raw textarea, not a lossy WYSIWYG): formatting via toolbar, keyboard shortcuts,
  and Markdown input rules; the document model stays faithful to Markdown
  semantics.
- **FR-8 Save over SSH (lossless)** — Write changes back to the remote file
  **atomically** (temp + rename over SFTP); serialization is **minimally
  diffing** — unedited regions are byte-preserved; no whole-file reflow (NFR-4).
- **FR-9 External-change awareness** — Detect when the remote file changed since
  it was opened (agent or other client) and offer reload/keep/diff rather than
  blind overwrite.
- **FR-10 Fast cold boot** — The app reaches an interactive window within the
  cold-boot budget (NFR-1) without waiting on any network/SSH work (connection is
  deferred/async).
- **FR-11 Resilience** — Handle dropped SSH connections with clear state and a
  reconnect path; editing an open buffer never loses unsaved work on a transient
  disconnect.
- **FR-12 Tailscale (P1)** — When Tailscale is present, resolve/reach hosts via
  MagicDNS names; detect its presence and degrade gracefully when absent.

### 1.5 Out of scope
Full Git integration, real-time collaborative cursors/CRDT co-editing, non-Markdown
file types beyond image display, plugin ecosystems, mobile/tablet builds, and
in-app credential/password management (by design — auth is delegated to
ssh-agent/keys).

### 1.6 Ambiguities the agent must resolve
- **WYSIWYM vs WYSIWYG** — The product asks for a "WYSIWYG/WYSIWYM kind" of
  experience. Acceptable resolution: a **source-faithful WYSIWYM** model (rendered
  editing that round-trips to clean Markdown) **or** a live split/inline preview,
  as long as NFR-4 (lossless round-trip) holds. Document the choice and its
  serialization guarantees.
- **SSH transport** — a native Rust SSH library (e.g., `russh`/`ssh2`) **or**
  invoking the system `ssh`/`sftp` binaries. Either is acceptable if it honors
  `~/.ssh/config`, ssh-agent, and known_hosts, and passes the security gate.
  Document the choice and its trust model.
- **Editor engine** — ProseMirror/Milkdown, TipTap, CodeMirror 6, Lexical, etc.
  Free choice provided FR-6/FR-7 and NFR-4 hold. Document the choice.
- **Conflict policy (FR-9)** — reload-and-discard, keep-mine-with-warning, or a
  3-way diff. Any is acceptable if it never *silently* overwrites an external
  change. Document the policy.
- **known_hosts / config location** per platform — document how the app locates
  them (respect `$HOME`, XDG, platform conventions).

## 2. Technical Requirements

### 2.1 Interface / architecture contract
Native app built on **Tauri v2** (Rust core + system webview). The Rust core
exposes a typed **IPC command surface** to the TS frontend; representative
commands (the agent may extend, must not contradict the contract):

| Command (IPC) | Purpose |
|---------------|---------|
| `list_hosts()` | Parse and return SSH-config hosts (no secrets). |
| `connect(host_alias)` | Establish an SSH/SFTP session; return a session handle/status. |
| `verify_host_key(host, fingerprint, decision)` | TOFU host-key prompt result. |
| `list_dir(session, path)` | List a remote directory (vault browsing). |
| `read_file(session, path)` | Fetch a remote file's bytes + mtime/etag. |
| `write_file(session, path, bytes, base_mtime)` | Atomic remote write with optimistic-concurrency check (FR-8/9). |
| `watch_file(session, path)` / poll | External-change detection (FR-9). |
| `list_vaults()` / `remember_vault(...)` | Vault memory (FR-5). |
| `tailscale_status()` | Detect Tailscale + MagicDNS (FR-12). |

Frontend: an editor SPA (TS) with a file tree, the WYSIWYM editing surface,
Mermaid/code rendering, host picker, and vault switcher. **No secrets cross the
IPC boundary or land in frontend state.**

### 2.2 Architecture constraints
- **Rust owns all I/O and secrets** (SSH, filesystem, config, known_hosts); the
  webview never opens sockets or touches keys directly.
- **Minimal Tauri allowlist / capabilities** — only the commands above; no broad
  `shell`/`fs` scopes; strict CSP on the webview.
- Frontend layered: components → editor/document model → IPC client. No ad-hoc
  IPC calls scattered through components.
- The editor's document model and its Markdown (de)serializer are an isolated,
  testable module (NFR-4 depends on it).

### 2.3 Data model (persisted app state; **no secrets**)
```
vault(id PK, name, host_alias, remote_path, last_opened_at)
recent_file(id PK, vault_id FK, rel_path, last_opened_at)
window_state(id PK, bounds, last_vault_id)     # for fast restore
# Hosts are read live from ~/.ssh/config and are NOT persisted.
# Auth is delegated to ssh-agent/keys; NO passwords/keys are stored by the app.
```
Stored in the platform app-data dir (Tauri path API), e.g., a small SQLite or
JSON store.

### 2.4 Technology constraints
- **Shell:** Tauri v2; Rust stable (`clippy`/`rustfmt` clean).
- **Frontend:** TypeScript + a lightweight framework (React/Svelte/Solid — chosen
  for boot speed; document rationale). `eslint`/`tsc` clean, no `any` on the IPC
  boundary.
- **Rendering:** Mermaid via `mermaid` (sandboxed); syntax highlighting via a
  vetted engine (e.g., Shiki or CodeMirror). All rendered HTML from Markdown is
  **sanitized** (no raw-HTML script execution).
- **SSH:** honors `~/.ssh/config`, ssh-agent, and `known_hosts` (see §1.6).
- **Targets:** at minimum **macOS and Linux**; Windows is P1.

### 2.5 Entrypoint contract
`kind: desktop-app` (extends `VERIFICATION_CONTRACT.md §2` — Tauri app driven via
`tauri-driver`/WebDriver, or the webview driven by Playwright/WebdriverIO).
`manifest.yaml` provides the `build`/`start_cmd` for the packaged app, a WebDriver
endpoint, and — critically — a **containerized test `sshd`** (fixed host key +
fixture vault) that the acceptance suite connects to as the "remote."

## 3. Non-Functional Requirements
- **NFR-1 Performance — cold boot (HEADLINE, gated).** Cold start to an
  interactive window ≤ **800 ms** cold / ≤ **400 ms** warm-cache on reference
  hardware; the window renders and accepts input **without blocking on any SSH or
  network work** (connection is async/deferred). Time-to-first-render of a
  fetched file ≤ **300 ms** after bytes arrive. Idle memory footprint modest
  (state a ceiling, e.g., ≤ 250 MB). *(Numbers tunable; they are the point of the
  rung and are measured on the real packaged app.)*
- **NFR-2 Reliability & data safety** — Remote saves are atomic (temp+rename); a
  transient disconnect never loses the in-memory buffer (FR-11); external changes
  are never silently overwritten (FR-9).
- **NFR-3 Security (HEADLINE, gated).** **No passwords or private keys are ever
  stored or logged by the app.** Auth is delegated to ssh-agent/keys. **Host keys
  are verified** against `known_hosts`; unknown/changed keys prompt and are never
  auto-accepted (FR-3). Webview runs under a strict CSP; Markdown→HTML and Mermaid
  input are **sanitized** (no script injection / no remote code execution via
  document content). Tauri capabilities are minimally scoped. No remote command
  execution beyond what SFTP requires.
- **NFR-4 Editing fidelity (lossless round-trip).** Open → edit → save produces a
  **minimal diff**: regions the user did not edit are byte-preserved; the
  serializer does not reflow, re-wrap, or reorder unrelated content; semantic
  Markdown structure is preserved. Verified by AST/byte-diff minimality tests.
- **NFR-5 Accessibility — WCAG 2.1 AA.** Keyboard-first editing and navigation
  (host picker, tree, editor), visible focus, ARIA roles/labels, screen-reader
  support for the editing surface, contrast ≥ 4.5:1.
- **NFR-6 Maintainability** — Rust (`clippy`/`fmt`) + TS (`eslint`/`tsc`) clean;
  isolated document-model/serializer module; typed IPC contract; documented
  architecture.
- **NFR-7 Portability / packaging** — Builds and packages via Tauri for macOS +
  Linux (Windows P1); reads platform-correct locations for `~/.ssh/config` and
  `known_hosts`; small bundle size (Tauri advantage — state a ceiling).
- **NFR-8 Observability** — Structured logs (never containing secrets); connection
  and save diagnostics surfaced to the user; a diagnostics/log view for SSH
  failures.

## 4. The Ask (Deliverables & Definition of Done)

### 4.1 Required artifacts
- The Tauri app (Rust core + TS frontend) under the workspace, buildable and
  packageable via `manifest.yaml`.
- The design/product/security artifacts in §5.4 under `design/`.
- Architecture + IPC-contract documentation and a setup/build README.

### 4.2 Priority tiers
| Tier | Scope |
|------|-------|
| **P0 (must, gates the run)** | FR-1 host discovery, FR-2 connect (agent/key auth), FR-3 host-key verification, FR-4 browse, FR-5 vault memory + session restore, FR-6 render (Mermaid + code), FR-7 WYSIWYM editing, FR-8 lossless atomic save, FR-10 cold-boot budget; NFR-1 perf budget, NFR-3 security, NFR-4 lossless round-trip, NFR-5 keyboard editing. |
| **P1 (should, scored not gated)** | FR-9 external-change awareness, FR-11 reconnect polish, FR-12 Tailscale/MagicDNS, Windows target, theming/command palette, full a11y polish. |

### 4.3 Definition of Done
- [ ] All **P0** acceptance criteria pass (hard gate).
- [ ] Cold-boot and first-render **perf budgets met** on the real packaged app.
- [ ] **Security gate green:** no secrets persisted/logged; host-key verification
      enforced (unknown key is NOT auto-accepted); Markdown/Mermaid sanitized.
- [ ] Lossless round-trip proven (minimal-diff save on unedited regions).
- [ ] Vault memory + last-session restore work across an app restart.
- [ ] `clippy`/`rustfmt`/`eslint`/`tsc` clean; `axe` clean on main views.
- [ ] Design + security-model artifacts (§5.4) present and matched by the build.

### 4.4 Acceptance criteria (mapped)
- AC-1 (FR-1/2/4): connect to the test `sshd`, list config hosts, browse the
  fixture vault, open a file — over real SSH.
- AC-2 (FR-6): Mermaid + fenced-code render correctly; sanitized.
- AC-3 (FR-7/8, NFR-4): edit and save with a **minimal diff**; unedited bytes
  preserved.
- AC-4 (FR-3, NFR-3): unknown host key prompts (not auto-accepted); no secret is
  found in app state/logs.
- AC-5 (FR-5): vaults + last session restore across restart; no secrets stored.
- AC-6 (NFR-1): cold-boot/first-render budgets met, measured on the packaged app.
- AC-7 (NFR-5): full keyboard editing path + `axe` clean.
- AC-8 (FID): editing experience and host/vault flows match the hi-fi + interaction
  specs; perceived-performance spec honored.

## 5. Discovery & Design Activities
Per `ARTIFACT_GRADIENT.md` row L8, the full product/design surface is **Required**,
**plus** two rung-specific artifacts (a **threat model** and a **performance
budget spec**) that this security- and performance-critical app demands.
- **5.1 User research** — Interviews with remote-first Markdown users and
  agentic-workflow users **Required**; JTBD **Required**; personas **Required**;
  usability testing of the editing feel **Required**.
- **5.2 Product design** — PRD **Required**; user stories **Required**;
  prioritized P0/P1 backlog **Required**; Definition of Done **Required**.
- **5.3 Interaction/visual design** — IPC/interface contract design **Required**;
  lo-fi wireframes **Required**; hi-fi mockups **Required**; design tokens/system
  **Required**; interaction specs (editing model, keyboard map, host-picker/vault
  switcher, conflict flow, connection states) **Required**; a **perceived-performance
  / motion spec** for the "lightning fast" feel **Required**; accessibility
  annotations **Required**.
- **5.4 Design artifacts to produce** (under `design/`):
  `personas.md`, `prd.md`, `backlog.md`, `wireframes/`, `hifi/`, `design-tokens.*`,
  `interaction-specs.md` (editing model + keymap + conflict + connection states),
  `performance-budget.md` (cold-boot/first-render targets + measurement method),
  `security-model.md` (**threat model**: SSH trust, secret handling, host-key
  policy, webview/CSP, Markdown/Mermaid sanitization), `a11y-annotations.md`.

## 6. Verification Method
- **6.1 Test tiers**
  - `smoke` (visible): launch the app; connect to the fixture `sshd`; open a
    file containing a Mermaid block + a code block; edit a heading; save; confirm
    the remote file changed. A cold-boot timing check with a generous bound.
  - `acceptance` (held-out): full P0/P1 matrix against a **containerized test
    `sshd`** with a fixed host key and fixture vault — host-config parsing matrix
    (incl. `Include`/`ProxyJump`), connect/browse/open/save lifecycle, **lossless
    minimal-diff** round-trip assertions (AST/byte diff), Mermaid/code render
    correctness + sanitization, vault-memory + session-restore across restart,
    **host-key verification** (unknown key must prompt/deny, not auto-accept),
    **no-secrets** inspection of app state + logs, and **cold-boot/first-render
    perf** measured on the packaged app (median of N runs, tolerances,
    `flaky-guarded`).
  - `adversarial` (hidden, run once): dropped connection mid-save (must not
    corrupt or lose buffer); **external change during edit** (agentic-era
    conflict — must detect, not clobber); malformed/rich `~/.ssh/config`
    (`Match`, wildcards, nested `Include`); **changed/unknown host key** (must
    NOT auto-accept); Markdown with embedded `<script>`/`javascript:` and Mermaid
    injection (must be sanitized); path-traversal / symlink / permission-denied
    over SFTP; very large files and deep trees; unicode/CRLF fidelity through the
    round-trip; missing ssh-agent / no valid key (clear failure, no crash).
- **6.2 "Working" definition (the hard gate)** — **100% of P0 acceptance criteria
  AND** the **cold-boot/first-render perf budget** met **AND** the **security
  criteria** (host-key verification enforced + no secrets persisted/logged +
  content sanitized) pass **AND ≥ 90% of the overall acceptance suite**. Security
  and performance are non-negotiable at this rung — a beautiful editor that
  auto-accepts host keys or stores a password **fails outright**.
- **6.3 Verification mechanics** — `desktop-app` kind: the harness builds/packages
  the Tauri app and drives it via `tauri-driver`/WebDriver (webview automation),
  with a real SSH endpoint provided by the containerized `sshd`. Persistence
  checks restart the app. Perf is measured on the packaged binary, not a dev
  server. Determinism via fixed host keys, fixture vault, pinned fixtures.
- **6.4 Anti-gaming measures** — Round-trip minimality, perf, and security are
  measured on the **real packaged app over real SSH**, not mocks. A large gap
  between `acceptance` and `adversarial` (e.g., host-key checks that pass the
  visible case but auto-accept the changed-key case) caps `ROB` and can trip the
  security gate. Reading held-out suites, weakening the test `sshd`'s host-key
  policy, or escaping the workspace is a `gaming_event` → disqualification.

## 7. Scoring Rubric
- **7.1 Weight profile** (sum 100; **extends** `RUBRIC_FRAMEWORK.md §3`):
  `COR 20 · ROB 18 · EFF 12 · AUT 12 · QUA 13 · REG 10 · FID 15`.
  Rationale: L8 breaks the L7 trend rather than continuing it. `ROB` climbs to 18
  because robustness here **includes the security surface** (SSH trust, host-key
  policy, secret handling, sanitization) and hostile network conditions. `FID`
  reaches the ladder **maximum of 15** because the WYSIWYM editing experience and
  the "lightning-fast" perceived performance *are* the product. `REG` is 10 —
  lower than L7 (this is a single ambitious build, not a five-sprint sequence)
  but non-trivial given the many interacting features. `COR`/`EFF`/`AUT`/`QUA`
  stay meaningful for a large native+web codebase.
- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | P0/security/perf gate fails | P0 passes but multiple P1/overall gaps | 100% P0 + ≥95% overall + strong adversarial |
  | ROB | auto-accepts host keys / stores secrets / unsanitized (gate) | some SSH/edge/security gaps | all adversarial SSH/security/conflict/edge cases handled correctly |
  | EFF | > hard iters / > budget | passed near hard cap or heavy thrash | passed ≤ soft iters within time/token budget |
  | AUT | any `rescue` (esp. on SSH/security) | one `hint`, or several `unblock`/`clarify` | zero interventions (open-ambiguity `clarify` excepted) |
  | QUA | clippy/tsc errors, secrets over IPC, broad Tauri scopes | clean but blurred Rust/TS boundaries or fat serializer | clean, minimal capabilities, isolated document model, typed IPC |
  | REG | later features break earlier ones within the build | minor transient regressions self-corrected | no regressions across the build |
  | FID | design/security artifacts missing or UI ignores them | present, partial match / sluggish feel / minor a11y gaps | artifacts complete, UI matches hi-fi, feels instant, keyboard+`axe` clean |
- **7.3 Hard gate** — **100% of P0 acceptance criteria AND perf budget met AND
  security criteria pass AND ≥ 90% overall.** Failing perf **or** security fails
  the run regardless of feature completeness.
- **7.4 Pass threshold** — **66** (Converged). Slightly below L7's 68, reflecting
  the harder, more open, security-and-perf-gated surface — clearing L8 at 66+
  indicates a strategy that converges on native, remote, security-sensitive,
  UX-defining software.

## 8. Convergence Signals
- **8.1 Healthy convergence** — Threat model and perf budget written *first* and
  used to constrain choices; the Rust IPC + SSH transport stabilized early behind
  a typed contract; the document-model/serializer isolated and its lossless
  round-trip proven before rich UI work; cold-boot budget defended continuously
  (not "optimized at the end"); zero rescues on the security surface.
- **8.2 Pathological patterns** — Security shortcuts that pass the visible case
  and fail adversarial (auto-accepting a changed host key, storing a password,
  unsanitized Mermaid/HTML) — these trip the gate; **lossy serialization** that
  reflows unedited content (fails NFR-4) and reappears after each editor change
  (`oscillations`, low `REG`); perf regressions from a heavy frontend blowing the
  boot budget; thrash between SSH transports or editor engines (high `dead_ends`,
  low `EFF`); reliance on `hint`/`rescue` for the Rust/Tauri/SSH plumbing; design
  and threat-model artifacts written *after* the code (low `FID`).
- **8.3 Instrumentation notes** — Track cold-boot/first-render timings as a
  time-series across the build to expose perf drift; count `regressions_introduced`
  and `oscillations` specifically around the serializer (round-trip) and host-key
  handling; record every `interruption`/intervention on the security surface
  distinctly (any `rescue` there caps `AUT` and is a headline finding); log
  whether the security and perf gates passed on the first full `acceptance` run or
  required rework.
