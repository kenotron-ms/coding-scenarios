# Lane lane_integration

## Outcome
Wire together the Rust core (lane_rust_core) and TypeScript frontend (lane_editor_frontend) into a complete, buildable Tauri v2 application. Produce `manifest.yaml`, `tauri.conf.json`, and a containerized test `sshd` fixture with a fixture vault. This lane runs after all wave-1 lanes are integrated.

Required files (repo-relative):
- `scenarios/L8-markdown-editor/manifest.yaml` — scenario manifest with `kind: desktop-app`, `build` command, `start_cmd`, budgets
- `scenarios/L8-markdown-editor/tauri.conf.json` — Tauri v2 config: minimal capabilities, strict CSP, app metadata
- `scenarios/L8-markdown-editor/fixtures/sshd/sshd_config` — containerized sshd config for acceptance tests
- `scenarios/L8-markdown-editor/fixtures/sshd/Dockerfile` — Docker image for the test sshd
- `scenarios/L8-markdown-editor/fixtures/vault/README.md` — fixture vault root file (with Mermaid block + code block for AC-1/2 tests)
- `scenarios/L8-markdown-editor/fixtures/vault/notes/sample.md` — additional fixture file for browse/open/edit/save tests

## Steps

1. Create `scenarios/L8-markdown-editor/tauri.conf.json` — Tauri v2 configuration:
   - `productName`: "markdown-vault-editor"
   - `version`: "0.1.0"
   - `identifier`: "com.example.markdown-vault-editor"
   - `build.frontendDist`: "../dist" (or wherever Vite outputs)
   - `build.devUrl`: "http://localhost:1420" (or Vite dev port)
   - `app.windows`: one window, `"title": "Markdown Vault Editor"`, `"width": 1280`, `"height": 800`
   - `app.security.csp`: strict CSP — e.g., `"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src ipc: http://ipc.localhost"` — no `unsafe-eval`, no remote script sources
   - `plugins`: only the plugins actually used (e.g., `shell` disabled, `fs` disabled — all file I/O goes through custom commands)
   - Tauri capabilities file at `src-tauri/capabilities/default.json`: list only the custom IPC commands; no broad `core:default` or `shell:allow-execute` scopes

2. Create `scenarios/L8-markdown-editor/manifest.yaml` — scenario manifest:
   ```yaml
   kind: desktop-app
   scenario: L8-markdown-editor
   build:
     command: "cd scenarios/L8-markdown-editor && npm install && npm run build && cd src-tauri && cargo build --release"
   start_cmd: "scenarios/L8-markdown-editor/src-tauri/target/release/markdown-vault-editor"
   webdriver_endpoint: "http://localhost:4444"
   test_sshd:
     image: "scenarios/L8-markdown-editor/fixtures/sshd"
     port: 2222
     host_key: "fixtures/sshd/host_key"
     fixture_vault: "fixtures/vault"
   budgets:
     wall_clock_s: 28800
     iterations_soft: 60
     iterations_hard: 150
     token_budget: 3000000
   regression:
     strategy: workspace-snapshots
   ```

3. Create the fixture sshd under `scenarios/L8-markdown-editor/fixtures/sshd/`:
   - `Dockerfile`: based on `alpine` or `debian:slim`; installs `openssh-server`; copies in a **fixed host key pair** (`host_key` + `host_key.pub`) so the host key is deterministic across test runs; creates a test user `vaultuser` with a fixed authorized key; exposes port 22; sets `PermitRootLogin no`, `PasswordAuthentication no`, `PubkeyAuthentication yes`.
   - `sshd_config`: minimal sshd config for the test container.
   - `host_key` + `host_key.pub`: generate a fixed ED25519 key pair (commit the public key; the private key is for the sshd only — never the client). These are test-only keys, not real secrets.
   - `authorized_keys`: the test client's public key (for acceptance tests to authenticate).
   - `README.md`: documents how to build and run the fixture sshd.

4. Create the fixture vault under `scenarios/L8-markdown-editor/fixtures/vault/`:
   - `README.md`: a Markdown file containing:
     - A heading
     - A paragraph
     - A Mermaid diagram block (e.g., a simple flowchart)
     - A fenced code block with syntax highlighting (e.g., Python or JavaScript)
     - A task list
     - A table
   - `notes/` subdirectory with `sample.md`: a simple note for browse/open/edit/save lifecycle tests.
   - `notes/agent-edited.md`: a file for external-change detection tests (FR-9).

5. Connect Rust and frontend build:
   - Ensure `src-tauri/Cargo.toml` has `tauri-build` as a build dependency and a `build.rs` that calls `tauri_build::build()`.
   - Ensure `package.json` has a `"build"` script (e.g., `"vite build"`) and a `"dev"` script.
   - Add a top-level `scenarios/L8-markdown-editor/README.md` (build/setup instructions): how to install Rust + Tauri CLI, `npm install`, `cargo tauri build`, and how to run the fixture sshd.

6. Verify Tauri capabilities are minimal:
   - `src-tauri/capabilities/default.json` must list only the custom commands from `commands.rs`.
   - Must NOT include `core:default`, `shell:allow-execute`, `fs:allow-read-dir`, or any broad scope.
   - This is part of NFR-3 (security gate): minimal Tauri allowlist.

7. Verify CSP is strict:
   - The CSP in `tauri.conf.json` must not include `unsafe-eval` or `unsafe-inline` for scripts.
   - `style-src 'unsafe-inline'` is acceptable for CSS-in-JS frameworks but must be documented.

8. Smoke-test the build (if Tauri CLI is available in the environment):
   - Run `cd scenarios/L8-markdown-editor && npm install && npm run build` and confirm it succeeds.
   - If Tauri CLI is not available, document the build steps clearly in README.md and ensure all config files are syntactically valid JSON/YAML.

## Done when
The following shell command exits 0:
```
test -f scenarios/L8-markdown-editor/manifest.yaml && \
test -f scenarios/L8-markdown-editor/tauri.conf.json && \
grep -q 'build' scenarios/L8-markdown-editor/manifest.yaml && \
test -f scenarios/L8-markdown-editor/fixtures/sshd/sshd_config && \
test -f scenarios/L8-markdown-editor/fixtures/vault/README.md
```

## Final step (REQUIRED)
After all integration files are written and the check above passes, write the file `artifacts/lane_integration.done` containing exactly the text `lane_integration:ok` and nothing else. This marker file is how the batch orchestrator confirms this lane finished; it must be the LAST action.
