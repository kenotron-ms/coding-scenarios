# goal_lane_impl.dot — real-work lane brick

Real-work sibling of `goal_lane.dot`. Same bounded child-convergence shape,
but the attempt does **real work** against a referenced goal instead of
writing a fixed marker string.

## What changed vs `goal_lane.dot`

| Concern | `goal_lane.dot` (marker) | `goal_lane_impl.dot` (real work) |
|---|---|---|
| Attempt | `Attempt` writes `$marker_content` to `$marker_file` | `Implement` reads `$goal_condition_file` and implements the goal stated there (modeled on `idea_to_pr.dot`'s `Implement`) |
| Verify | `ChildVerify` runs a marker-equality envelope | `Verify` (independent LLM judge) re-runs the goal's own machine check + `CheckVerdict` (deterministic file gate) — modeled on `idea_to_pr.dot`'s `SelfEvaluate → CheckRubric` |
| Commit | `Candidate` stages one marker file | `Candidate` stages all work (`git add -A`) |
| Budget / diagnose / retry backstop | `Orient → ReserveAttempt → … → Diagnose → RepeatCheck → Postmortem`, `BudgetExhausted`, `InfraExit`, `BlockedExit` | **reproduced verbatim** so the parent graph consumes it unchanged |

## Seam (pinned)

- Reads `$goal_condition_file` — the `/goal`-style stop condition to implement.
- Writes `$lane_result_path` as `{"result": "candidate", "candidate_sha": "<sha>"}`
  and prints the `lane.result` / `lane.candidate_sha` line, exactly like
  `goal_lane.dot`'s `Candidate` node.
- Keeps `goal_lane.dot`'s budget-ledger params (`$runtime_py_dir`,
  `$ledger_path`, `$ledger_lock_path`, `$run_id`, `$max_attempts`,
  `$evidence_path`, `$lane_id`). `$marker_file` / `$marker_content` are
  ignored if a parent still passes them.

## Contract (identical to `goal_lane.dot`)

- `lane.result` = `candidate` | `blocked`
- `lane.candidate_sha` (set only on candidate)
- `lane.blocker_reason` (set only on blocked)

This brick never certifies its own final success — it hands back a candidate
commit plus evidence, and the parent (`goal_plan_smoke.dot`) independently
re-verifies. Behavioral end-to-end proof is the orchestrator's job at
integration; this brick's bar is: structurally correct, lints with zero ERROR
diagnostics via `compiler.validate`.
