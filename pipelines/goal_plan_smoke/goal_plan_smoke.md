# Goal Plan Smoke

This guide describes the canonical `goal_plan_smoke` member of the Goal Plan
Attractor family. It is the identity-stable history-anchor artifact for the
local-only `history_anchor` repository identity mode. Keep this document
stable: it deliberately contains no run-specific commit, source, descriptor,
plan-blob, or other content-address identity values.

## Static graph

The compiled member is a fixed, reviewed parent graph rather than a runtime
scheduler. Its visible control flow contains:

- Wave 1: concurrent `lane_a` and `lane_b` child pipelines;
- parent collection, independent candidate verification, ownership checks, and
  stable sequential integration;
- aggregate verification after each accepted merge;
- Wave 2: `lane_c`, gated on both Wave 1 lanes and the green aggregate;
- bounded integration-correction and coherence routes;
- a one-HEAD final lane sweep and post-sweep aggregate gate; and
- an optional delivery child followed by cleanup and an explicit terminal
  carrier.

Each bounded lane runs in its own Git worktree and headless child Attractor
process. The parent graph owns dependencies, supervision, verification,
integration, recovery, and terminal selection. The plan describes and audits
the compiled graph; runtime does not discover or schedule lanes from plan data.

## Prerequisites

A run requires all of the following before the parent graph starts:

- Linux process supervision as required by schema version 1;
- a canonical Git target repository and an approved, immutable compiled
  `goal_plan_smoke` directory;
- a harness-owned, immutable launch descriptor stored in an external launch
  control root;
- an externally installed trusted bootstrap, Git, interpreter or executable,
  and Attractor runner addressed by absolute, authenticated argv prefixes;
- the compiled `anthropic` provider and its required credentials; and
- external, pairwise-disjoint launch-control, state, worktree, and (when
  delivery is enabled) delivery-state roots, all outside the target repository
  and its Git common directory.

The descriptor and compiled source are deployment inputs. The target checkout
cannot create, replace, repair, or select the launch descriptor or trusted
runtime.

## Trusted verification route

1. The external bootstrap authenticates its own installed identity, the launch
   descriptor, the descriptor-bound Git and interpreter identities, and the
   exact committed plan blob. It then requires the checked-out plan bytes to
   match that blob before reading plan-controlled trust fields.
2. It extracts the runtime and supervisor from exact Git blobs, installs them
   atomically under the external state root, fsyncs and seals the files
   non-writable, and rereads them to verify their byte identities.
3. The bootstrap rehydrates only an absent trusted-runtime bundle, rejects a
   present mismatching bundle, changes OS CWD to the canonical target
   repository, and hands off with the exact parent argv through `execve`,
   without a shell or target-repository runtime import.
4. The parent independently observes supervisor results, child exit truth,
   verifier evidence, worktree ownership, source immutability, and Git state.
   Worker or artifact self-reports never certify success.
5. After final proof, cleanup recomputes current authority and reconciles
   identity-valid processes and recorded worktrees before publishing the final
   status through exactly one carrier.

## Terminals

The graph has four explicit terminal states:

- `COMPLETE` — the final integrated result and all required proof gates pass;
- `RESIDUALS_READY` — named evidence-backed residuals remain without fabricated
  success or automatic partial delivery;
- `INFRA_FAILURE` — infrastructure, trust, process, source, or verification
  integrity failed; and
- `ABORTED` — an approved abort or unrecoverable run stop was recorded.

Harness failures before the parent starts are distinct from graph terminals:
`PRELAUNCH_INFRASTRUCTURE_BLOCKED` and
`RECOVERY_INFRASTRUCTURE_BLOCKED` are reported through external evidence with
exit code 78. They must not be converted into a plausible graph success.
