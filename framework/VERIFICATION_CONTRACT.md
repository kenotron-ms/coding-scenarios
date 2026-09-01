# Verification Contract

How "working" is defined, isolated, and measured — identically across every
rung. This is the contract that makes scores trustworthy: the agent under test
never sees the code that judges it, and the harness invokes every solution the
same way.

## 1. Test tiers and visibility

Each scenario ships three tiers with different visibility to the agent under test:

| Tier | Visible to agent? | Purpose | Feeds |
|------|-------------------|---------|-------|
| `smoke` | **Yes** — provided with the SPEC | Fast signal / a few worked examples so the agent can self-check the happy path. Small (≈3–8 cases). | Agent's own loop; not scored directly. |
| `acceptance` | **No** — held out, revealed only to the harness | The authoritative definition of "working." Broad behavioral coverage of every `FR`/`NFR`. | Hard gate + `COR`/`ROB`/`FID`/`REG`. |
| `adversarial` | **No** — hidden, run **once** after the strategy declares done | Anti-overfitting: nasty edge cases and inputs the agent could not have coded to. | `COR`/`ROB` only; never the gate. |

Rationale: `smoke` gives the strategy a legitimate feedback loop; `acceptance`
prevents "passes because it was shown the answers"; `adversarial` detects
strategies that overfit to whatever tests they *can* see.

### Visibility enforcement
- `smoke` lives in the agent's workspace. `acceptance`/`adversarial` live outside
  it and are mounted only by the harness at scoring time.
- If a strategy reads or writes outside its declared workspace to discover held-out
  tests, the run is **disqualified** (recorded as a gaming event).

## 2. Entrypoint contract (`manifest.yaml`)

Every scenario declares how the harness builds, runs, and verifies the solution.
The agent's job is to satisfy the entrypoint; the harness owns everything else.

```yaml
# scenarios/L*/manifest.yaml  (authored in the harness pass; specified here)
level: 2
language: python
workspace: solution/            # where the agent writes; only this is agent-visible
entrypoint:
  kind: python-module           # python-module | cli | http-service | web-app | desktop-app
  target: solution.lru_cache    # import path / command / server module
  # kind-specific fields:
  #   cli:          command, args_schema
  #   http-service: start_cmd, base_url, health_path, ready_timeout_s
  #   web-app:      start_cmd, url, e2e_runner
build:
  setup: ["pip install -r solution/requirements.txt"]
verify:
  smoke:       "pytest tests/smoke -q"
  acceptance:  "pytest tests/acceptance -q --json-report"
  adversarial: "pytest tests/adversarial -q --json-report"
budgets:
  wall_clock_s: 900
  iterations_soft: 15
  iterations_hard: 40
  interventions: 0
gate:
  acceptance_floor: 1.0         # fraction of acceptance assertions required
```

### Entrypoint kinds and how each is verified
| Kind | Invocation | Verification style |
|------|-----------|--------------------|
| `python-module` | import the module | unit + property tests (`pytest`, `hypothesis`) |
| `cli` | subprocess with argv/stdin | golden-file / exit-code / stdout-stderr assertions |
| `http-service` | start server, poll health | live HTTP requests, DB/state assertions, concurrency probes |
| `web-app` | start backend+frontend | API tests + browser E2E (Playwright) against real DOM |
| `desktop-app` | build/package native app; drive webview via WebDriver | Tauri app via `tauri-driver`/WebDriver against a real endpoint (e.g. containerized `sshd`); perf + security checks on the packaged binary (A3) |

The **kind climbs the ladder** (module → cli → service → web-app → desktop-app), which is a
large part of what makes higher rungs harder: the *real path* being verified
gets further from a pure function.

## 3. "Working" is a real-path definition

Per the verification-driven principle: the acceptance tier must exercise the
**real production path**, not a mock of it.

- L0–L2: the real path *is* the function/class → unit/property tests are the real path.
- L3: run the actual built CLI as a subprocess; assert real stdout/exit codes.
- L5: hit a real running server over real HTTP against real persistence.
- A1–A2: drive the real UI in a real browser plus real API calls.

Mock-only evidence is never sufficient at L3+ and is not accepted as acceptance
verification. This mirrors the harness we are trying to prove out: strategies
that only satisfy mocks must score poorly on `COR`.

## 4. Determinism requirements

Acceptance/adversarial suites must be deterministic so scores are reproducible:
- Time, randomness, network, and clock are controlled (injected/faked at the
  seam, or pinned via fixtures) — e.g., L2 eviction/TTL uses a fake clock; L5
  uses a fixed seed and a throwaway DB per run.
- Any inherently timing-sensitive assertion (e.g., concurrency at L5) uses
  tolerances and repeated trials, and is marked `flaky-guarded` so a single
  jitter doesn't decide the gate.

## 5. Run protocol (per scenario, per strategy)

```
1. Provision clean workspace, install nothing but declared deps.
2. Hand SPEC + smoke tests to the strategy under test. Start telemetry.
3. Strategy iterates (edit → run smoke → repeat) until it declares "done"
   or hits a budget cap.
4. Harness runs acceptance (hard gate) — record pass fraction.
5. Harness runs adversarial once — record, feed COR/ROB.
6. For L4+: run cumulative regression suite (prior features/sprints).
7. Compute telemetry-derived axes (EFF, AUT) against budgets.
8. Score QUA/FID (automated floor + LLM/human graded portion).
9. Emit score.json (per-axis 0–4, weighted 0–100, band, gate result, telemetry).
```

## 6. `score.json` shape (harness output, specified here)

```json
{
  "scenario": "L2-lru-cache",
  "strategy": "example-harness@v3",
  "gate": {"acceptance_floor": 1.0, "acceptance_pass": 1.0, "passed": true},
  "axes": {"COR": 4, "ROB": 3, "EFF": 3, "AUT": 4, "QUA": 3, "REG": null, "FID": null},
  "weights": {"COR": 45, "ROB": 20, "EFF": 12, "AUT": 10, "QUA": 13},
  "score": 82,
  "band": "Converged",
  "telemetry": {"iterations": 9, "wall_clock_s": 410, "tokens": 61000,
                "usd": 0.74, "failed_runs_before_pass": 3, "interventions": 0,
                "regressions_introduced": 0, "adversarial_pass": 0.92},
  "gaming_events": [],
  "notes": {"QUA": "clear interface, missing docstrings on 2 methods"}
}
```
