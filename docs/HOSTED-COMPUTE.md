# How to configure and run it

This is the plumbing. The human flow (issues and PRs) is in the top-level
[README](../README.md). This page is what you set up once and how the parts fit.

The idea is a compute swap. The capsule graphs normally run in a GitHub Actions runner. Here
the runner does no model work. It packages the issue, submits to a hosted backend over a
bearer token, waits, and pulls the result back. GitHub keeps events, issues, PRs, and review.
The backend is the engine. The design rationale and first-run risks are in
[docs/designs/gh-actions-hosted-compute.md](designs/gh-actions-hosted-compute.md).

## Secrets

Set these under Settings > Secrets and variables > Actions.

| Name | Value |
|------|-------|
| `COMPUTE_URL` | the hosted backend base URL, a secret so it stays out of public logs |
| `COMPUTE_TOKEN` | bearer token for the backend |
| `CAPSULE_PR_TOKEN` | a PAT for `gh pr create`, or rely on the default token |

The names are deliberately neutral so the backend's product name stays out of public YAML.
Put the URL and token the backend owner gave you into `COMPUTE_URL` and `COMPUTE_TOKEN`.

Until `COMPUTE_TOKEN` is set, the submit step fails fast by design. Everything up to the
backend call still exercises the wiring.

## Labels

Two labels trigger the pipeline. Create both.

- `ready:spec` starts the defect specify lane.
- `ready:feature-spec` starts the feature specify lane.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `backend-smoke.yml` | manual (Actions, run workflow) | auth precheck plus a minimal submit, to confirm the token works |
| `capsule-specify.yml` | label `ready:spec` on an issue | runs `capsule.dot`, opens a defect capsule PR |
| `feature-specify.yml` | label `ready:feature-spec` on an issue | runs `feature-capsule.dot`, opens a feature capsule PR |
| `capsule-implement.yml` | a capsule PR is merged | runs `task-runner.dot`, opens a fix PR |

The implement workflow is unified. Merging any capsule PR, defect or feature, fires it, and it
runs `task-runner.dot` against whichever capsule the merge carried. There is no separate
feature-implement workflow.

Smoke-test the token before the first real run.

## The feature criteria comment

A feature run needs binding acceptance criteria, and the issue body is never trusted for them.
Post them as a comment from a repository OWNER, MEMBER, or COLLABORATOR, in this exact shape,
then add the `ready:feature-spec` label.

```markdown
## Acceptance criteria (feature-capsule)

Owned-by: @your-login
Scope: IN -- ... OUT -- ...

AC-1: <one testable behavior through a public surface>
AC-2: <another>
AC-3 [guard]: <a criterion that already holds at base and must keep holding>
```

`author_association` is computed server-side by GitHub, so a filer cannot forge a maintainer
comment. Issue #11 (`format_price()`) is a worked example.

## Submit and retrieve

`submit_compute.py` is the client that stands in for the in-runner engine. It builds a params
object from a workspace-resident shim (`shim-specify.dot`, `shim-feature-specify.dot`, or
`shim-implement.dot`), submits to the backend, polls to completion while auto-answering gates,
then fetches the pipeline's `capsule_out` tree and the event log back to the runner. The
specify workflows commit the returned capsule into the PR. The implement workflow re-applies
the returned fix diff and opens the fix PR. Events land in a separate meta directory that the
secret gate keeps out of the uploaded artifact.

## Layout

```
.github/workflows/        capsule-specify.yml, feature-specify.yml, capsule-implement.yml,
                          backend-smoke.yml            (adapted, compute on the backend)
.github/capsule-pipeline/
    submit_compute.py     bearer-token submit/retrieve client (ours)
    shim-*.dot            workspace-resident shims: shim-specify, shim-feature-specify,
                          shim-implement (ours)
    capsule.dot, feature-capsule.dot, task-runner.dot,
    scrub_secrets.py, capsule_pair_fence.sh, verify_shipped_gate.sh, vendor/
                                                       (from amplifier-bundle-attractor, public)
    proposals/            shipped capsules for the sample scenarios
src/, tests/              the buggy sample project
docs/                     this guide, the explainer, scenarios, and the design docs
```

## Visibility and who can run it

This repo is private, and stays private as long as the backend (Resolve) is private. It is
tied to the backend, not to the pipeline. The pipeline itself is public.

The graphs are public. They are vendored unmodified from
[microsoft/amplifier-bundle-attractor](https://github.com/microsoft/amplifier-bundle-attractor),
which is public. Only where the compute runs is private here.

So this approach works on public repos too. You can wire these workflows into a public
repository and run the whole flow, as long as you have access to the backend (`COMPUTE_URL`
and `COMPUTE_TOKEN`). That is true for teammates today. The private piece is the backend
token, not the method.

To apply this to another repo, see [AGENTS.md](../AGENTS.md).
