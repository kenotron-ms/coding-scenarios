---
title: GitHub Actions drives a hosted compute backend — capsule pipeline
type: design
status: draft
created: 2026-08-19
---

# GitHub Actions drives a hosted compute backend — the capsule pipeline port

**Goal.** Run the capsule pipeline (issue → capsule PR → merge → fix PR) the same way
it runs today, but move the **compute** off the GitHub Actions runner and onto a
**hosted compute backend**. GitHub keeps events, issues, PRs, and review; the backend
becomes the engine.

This note is the surgical spec for the two adapted workflows.

## Shape of the workflows

Each workflow is: **prepare inputs → run the engine → classify from artifacts → push a
branch / open a PR → comment on the issue → upload evidence.** Only the middle "run the
engine" step is runner-local machinery. Everything on either side is GitHub plumbing we
keep verbatim.

- **specify** runs `capsule.dot`; results (`capsule_out` + `.ai/` findings) are read by
  the unchanged classify / PR / comment steps.
- **implement** runs `task-runner.dot`; today the engine commits into the local tree and
  "the branch push is the retrieval."

## The port — delete / replace / keep

**Delete** the runner-local engine machinery (obsolete when compute is remote):
- the engine snapshot/detach step,
- `setup-python` and `install uv`,
- the provider-key preflight and the dual-provider bundle mount — provider selection is
  the hosted backend's concern now.

**Replace** the single `attractor run …` step with a **submit → poll → retrieve** step
(`submit_compute.py`). It lands results at the exact local paths the downstream plumbing
already reads, so nothing downstream changes:
- **specify:** `$RUNNER_TEMP/capsule-run/out` (capsule_out) and `$GITHUB_WORKSPACE/.ai/`.
  A workspace-resident shim runs the repo's `capsule.dot` and exports `.ai/` findings
  into `capsule_out` so one fetch retrieves everything.
- **implement:** the compute happens remotely, so the local tree is not mutated. The shim
  adds an **Export node** that writes `git diff base..task/<id>` to `capsule_out`; the
  workflow re-applies that diff into its checkout and the existing "push branch + open
  PR" step runs unchanged.

**Keep** verbatim: checkout, base-SHA capture, issue materialization, secret scrubbing,
classify, the capsule PR / fix PR creation, issue comments, and evidence upload.

## Submit contract

`submit_compute.py` is stdlib-only (runs on a bare runner, no extra install). It:
uploads dynamic inputs, submits a run, polls to a terminal status, auto-answers any
human-gate prompts (the unattended analog of auto-approve), and pulls `capsule_out` +
the event log back.

Auth is a **bearer token**: `COMPUTE_URL` (repo variable) + `COMPUTE_TOKEN` (repo
secret), sent as `Authorization: Bearer <token>`.

Config surface on the target repo:
- `COMPUTE_URL` (variable) — the backend base URL
- `COMPUTE_TOKEN` (secret) — the bearer token
- `CAPSULE_PR_TOKEN` (secret) — PAT for `gh pr create` (falls back to `github.token`)

Provider keys are no longer runner secrets — the hosted backend mounts providers.

## First-run risks (pending a live run with a token)

1. `.ai/` retrieval round-trip on the specify path.
2. Exact shape of the data-listing response (the client's flattener is tolerant).
3. Human-gate auto-answer text per graph (`--gate-answer`, default `A`).
4. Dynamic inputs uploaded and accepted as container-readable paths.
5. **Token lifetime** — a short-lived token expires quickly; a static service token or a
   per-job-minted one is needed for durable automation. Open item.

## Sequence

Port and prove **specify first, watch it**, then implement — not both at once. Validate
on a throwaway repo before pointing at a real one.
