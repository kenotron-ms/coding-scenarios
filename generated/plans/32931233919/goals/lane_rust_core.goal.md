# Lane lane_rust_core

## Outcome
Implement the Tauri v2 Rust backend for the L8 Markdown vault editor under `scenarios/L8-markdown-editor/src-tauri/`. This is the security-critical core: all SSH/SFTP I/O, host-key verification, vault memory, and IPC command surface live here. The webview never touches SSH or secrets directly.

Required files (repo-relative):
- `scenarios/L8-markdown-editor/src-tauri/Cargo.toml` — Tauri v2 workspace manifest with SSH dependency (ssh2 or russh crate)
- `scenarios/L8-markdown-editor/src-tauri/src/main.rs` — Tauri app entry point, command registration
- `scenarios/L8-markdown-editor/src-tauri/src/ssh/mod.rs` — SSH/SFTP session management
- `scenarios/L8-markdown-editor/src-tauri/src/ssh/config.rs` — `~/.ssh/config` parser (Host, HostName, User, Port, IdentityFile, ProxyJump, Include)
- `scenarios/L8-markdown-editor/src-tauri/src/ssh/hostkey.rs` — known_hosts verification + TOFU prompt logic
- `scenarios/L8-markdown-editor/src-tauri/src/commands.rs` — all IPC Tauri commands
- `scenarios/L8-markdown-editor/src-tauri/src/vault.rs` — vault memory persistence (SQLite or JSON store, no secrets)

## Steps

1. Initialize the Tauri v2 Rust project under `scenarios/L8-markdown-editor/src-tauri/`:
   - `Cargo.toml` with: `tauri = { version = "2", features = [...] }`, `ssh2` (or `russh`) for SSH/SFTP, `serde`/`serde_json`, `tokio`, `rusqlite` (or `serde_json` for JSON store), `log`/`tracing`.
   - `src/main.rs`: Tauri `Builder::default()` with `.invoke_handler(tauri::generate_handler![...])` registering all commands.

2. Implement `src/ssh/config.rs` — SSH config parser:
   - Parse `~/.ssh/config` (and `Include` directives recursively, up to a safe depth).
   - Extract `Host` blocks: `HostName`, `User`, `Port`, `IdentityFile`, `ProxyJump`.
   - Handle wildcard `Host *` and `Match` blocks sensibly (document behavior in code comments).
   - Return a `Vec<SshHostEntry>` with no secrets (no passwords).
   - Platform-correct config location: `$HOME/.ssh/config` on Linux/macOS; `%USERPROFILE%\.ssh\config` on Windows.

3. Implement `src/ssh/hostkey.rs` — host-key verification:
   - On connect, read `~/.ssh/known_hosts` and verify the server's host key fingerprint.
   - If the key matches known_hosts: proceed silently.
   - If the key is unknown (new host): emit a Tauri event to the frontend requesting TOFU confirmation; block the connection until the user responds.
   - If the key has CHANGED (possible MITM): emit a strong warning event; block connection; never auto-accept.
   - On user acceptance: append the key to known_hosts.
   - NEVER auto-accept an unknown or changed key — this is a security gate requirement.

4. Implement `src/ssh/mod.rs` — SSH/SFTP session:
   - `connect(host_alias)`: resolve host from config, authenticate via ssh-agent first, then identity file; never prompt for password.
   - Session pool: store active sessions keyed by session handle (UUID or similar).
   - `list_dir(session_id, path)`: SFTP readdir, return `Vec<DirEntry>` (name, kind, size, mtime).
   - `read_file(session_id, path)`: SFTP read, return bytes + mtime (as etag for optimistic concurrency).
   - `write_file(session_id, path, bytes, base_mtime)`: atomic write — write to a temp path, verify mtime matches base_mtime (optimistic concurrency check for FR-9), then SFTP rename. If mtime changed, return a conflict error instead of overwriting.
   - `watch_file(session_id, path)`: poll mtime periodically (e.g., every 5 s), emit a Tauri event if changed.
   - `tailscale_status()`: check if `tailscaled` is running (via socket or process check); return presence + MagicDNS availability.
   - Handle disconnects: return typed error; never lose the in-memory buffer.

5. Implement `src/commands.rs` — Tauri IPC commands (annotated with `#[tauri::command]`):
   - `list_hosts()` → `Vec<SshHostEntry>` (no secrets)
   - `connect(host_alias: String)` → `Result<SessionHandle, SshError>`
   - `verify_host_key(host: String, fingerprint: String, decision: HostKeyDecision)` → `Result<(), SshError>`
   - `list_dir(session_id: String, path: String)` → `Result<Vec<DirEntry>, SshError>`
   - `read_file(session_id: String, path: String)` → `Result<FileContent, SshError>` (bytes + mtime)
   - `write_file(session_id: String, path: String, content: Vec<u8>, base_mtime: u64)` → `Result<(), WriteError>`
   - `watch_file(session_id: String, path: String)` → `Result<WatchHandle, SshError>`
   - `list_vaults()` → `Vec<VaultRecord>`
   - `remember_vault(name: String, host_alias: String, remote_path: String)` → `Result<VaultId, DbError>`
   - `tailscale_status()` → `TailscaleStatus`
   - Ensure NO secret (password, private key bytes) appears in any command input/output type. All types derive `Serialize`/`Deserialize`.

6. Implement `src/vault.rs` — vault memory (FR-5):
   - Persist to Tauri's app-data dir (use `tauri::api::path::app_data_dir`).
   - Schema: `vault(id, name, host_alias, remote_path, last_opened_at)`, `recent_file(id, vault_id, rel_path, last_opened_at)`, `window_state(id, bounds, last_vault_id)`.
   - Use SQLite via `rusqlite` or a JSON file — no secrets stored.
   - `list_vaults()`, `remember_vault()`, `update_last_opened()`, `get_last_session()` functions.

7. Security invariants to enforce in code:
   - No `String` field named `password`, `passphrase`, `private_key`, `key_data` in any serialized type.
   - Structured logging with `tracing` — never log SSH key material, passwords, or file content.
   - Tauri capabilities in `tauri.conf.json` (created in lane_integration): only the commands above; no broad `shell`/`fs` plugin scopes.
   - `clippy` clean: run `cargo clippy -- -D warnings` and fix all warnings.
   - `rustfmt` clean: run `cargo fmt --check`.

8. Ensure `src/main.rs` contains (at minimum) the function names `list_hosts`, `verify_host_key`, and `write_file` registered as Tauri commands (the verifier greps for these).

## Done when
The following shell command exits 0:
```
test -f scenarios/L8-markdown-editor/src-tauri/src/main.rs && \
test -f scenarios/L8-markdown-editor/src-tauri/Cargo.toml && \
grep -q 'list_hosts' scenarios/L8-markdown-editor/src-tauri/src/main.rs && \
grep -q 'verify_host_key' scenarios/L8-markdown-editor/src-tauri/src/main.rs && \
grep -q 'write_file' scenarios/L8-markdown-editor/src-tauri/src/main.rs
```

## Final step (REQUIRED)
After all Rust source files are written and the check above passes, write the file `artifacts/lane_rust_core.done` containing exactly the text `lane_rust_core:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished; it must be the LAST action.
