# plan-batch

**A planner attractor: one GitHub issue in, a compiler-accepted `plan.json`
out -- or nothing at all, with a residual note saying why.**

Entry pipeline: [`plan-batch.dot`](./plan-batch.dot)

---

## Purpose

`plan-batch` reads a single GitHub issue and emits a `plan.json` describing a
**goal-batch decomposition** of that issue -- the lanes, waves, dependency
order and per-lane machine-checkable verifiers that the deterministic
[goal-plan compiler](../../compiler/README.md) turns into a runnable parent
`.dot`.

The hard part is not writing JSON. The hard part is that an LLM writing a
schema-constrained document is a noisy operator: it will produce something
plausible-looking that the compiler rejects on a cross-field rule it did not
internalise. So this pipeline is shaped as an attractor rather than a
prompt-and-hope: the compiler itself is the gate, and the graph loops until
the compiler accepts -- or aborts honestly.

**It does not run the plan.** Compiling and executing the generated parent
`.dot` is the consuming workflow's job (and, downstream of that, the
[`goal_plan_smoke`](../goal_plan_smoke/) family's). This pipeline's entire
output contract is one file.

---

## Input: `$goal` is the GitHub issue

This pipeline runs inside a GitHub Actions job via the
[`microsoft/amplifier-app-actions`](https://github.com/microsoft/amplifier-app-actions)
action.

**The action provides no param channel.** The only runtime-variable input that
reaches the graph is the built-in `$goal` substitution, which the action sets
to a formatted GitHub issue context block: event type, issue `#number`,
`owner/repo`, Title, Body, Labels, Author. Both LLM nodes (`AuthorPlan`,
`RevisePlan`) consume `$goal` directly.

Everything else is fixed in the graph. Where a knob would genuinely be useful
-- the authoring-attempt cap -- it is written as a shell default
(`${plan_max_attempts:-4}`), which resolves to `4` today and would pick up a
real param for free if a param channel ever appears. This works because the
engine leaves an unresolvable `${key:-default}` token literal for `/bin/sh` to
expand.

**Required env:**

| Variable | Used for |
|---|---|
| `ANTHROPIC_API_KEY` | LLM provider auth (`model_stylesheet` pins `claude-sonnet-4-6` / `anthropic`). |
| `GH_TOKEN` | Read the issue and post the rendered plan back to it (used by the surrounding workflow, not by this graph's own nodes). |
| `GITHUB_WORKSPACE` | Set by the runner. Every tool node re-anchors to it explicitly (see *cwd* below). |

---

## Output contract

| Outcome | Workspace artifacts | Context |
|---|---|---|
| Converged | `plan.json` at the **workspace root**, proven to compile | `plan.result="accepted"`, `plan.path="plan.json"` |
| Aborted | `plan-batch-residual.md` at the workspace root, and **`plan.json` deliberately removed** | `plan.result="aborted"`, `plan.residual="plan-batch-residual.md"` |

The path is the fixed relative path `plan.json` (resolving against
`$GITHUB_WORKSPACE`); the consuming workflow relocates it afterwards. All
intermediate pipeline state lives under `/tmp/plan-batch/` -- absolute,
cwd-independent, and it keeps the checked-out repo clean for the workflow
steps that commit.

> **Consume the artifact, not the exit status.** On abort, the pipeline
> removes `plan.json` on purpose: a plan the compiler rejects must not be
> shipped downstream by a job that merely "completed". So the workflow's own
> gate should be `test -f plan.json`, which is the same evidence-based routing
> doctrine this graph uses internally, applied at the job boundary.

`plan.json`'s schema is **not** restated here -- [`compiler/README.md`](../../compiler/README.md)
is the integration contract and the single source of truth. Both LLM nodes are
prompted to read it from the checkout at run time.

---

## The attractor shape

```
Start
  |
  v
ResetPlanState  (idempotency: wipe stale plan.json / counter / error line)
  |
  v
AuthorPlan  (box, LLM) --------- outcome=fail --------------.
  |  must_write=/tmp/plan-batch/plan.json                    |
  v                                                          |
InstallPlan  (deterministic: JSON-check, copy into workspace)|
  |          |                                               |
  |          `-- install_failed ------------------------.    |
  | installed                                            |   |
  v                                                      v   v
CompilerGate  -- plan_rejected ---------------------> CheckAttempts
  |  python3 -m compiler plan.json -o /tmp/plan-check.dot  |    |
  | plan_ok                                     revise_ok  |    | attempts_exhausted
  v                                                        v    v
MarkAccepted --> Exit                                RevisePlan  Abort --> MarkAborted --> Exit
                                                           |     (removes plan.json,
                                                           |      writes residual note)
                                                           `--> InstallPlan  [loop_restart]
```

Built in the order [`docs/primer.md` §3](../../docs/primer.md) prescribes:

1. **Name the sink.** `plan.json` at the workspace root such that
   `python3 -m compiler plan.json -o /tmp/plan-check.dot` exits `0`. That
   command, run by a machine, is what proves this pipeline is done. Nothing
   else counts.
2. **Build the gate.** `CompilerGate` is a `shape=parallelogram` tool node
   that runs exactly that command and routes on `context.tool.last_line`
   derived from its **real exit code**. It never asks an LLM whether the plan
   is valid, and it is deliberately stricter than exit-0: it removes any stale
   `/tmp/plan-check.dot` first, then requires a non-empty generated parent
   `.dot` **and** a non-empty `plan.json` before printing `plan_ok`. This is
   the independent verification [`docs/RUBRIC.md` §2](../../docs/RUBRIC.md)
   demands, applied to the one claim that matters.
3. **Build the loop.** Rejection routes
   `CompilerGate -> CheckAttempts -> RevisePlan -> InstallPlan -> CompilerGate`,
   carrying the compiler's own named error.
4. **Only then the work nodes.** `AuthorPlan` and `RevisePlan` are the only
   LLM nodes in the graph.

### The three-question test ([RUBRIC §1](../../docs/RUBRIC.md))

- **Is there a cycle?** Yes -- `InstallPlan -> CompilerGate -> CheckAttempts ->
  RevisePlan -> InstallPlan`, closed by `loop_restart="true"` on `RevisePlan`'s
  forward edge.
- **Is the exit gated on evidence?** Yes -- `MarkAccepted` is reachable only
  through `CompilerGate`'s `plan_ok`, which requires compiler exit 0 plus real
  artifacts on disk.
- **Would it still land if an LLM node had a bad day?** Yes. A malformed,
  hallucinated, or entirely absent plan cannot reach `MarkAccepted`. It loops
  with the compiler's named reason; after the cap it aborts with `plan.json`
  removed.

---

## The self-correction loop

**Feedback is curated, not accumulated sludge** ([primer §4.4](../../docs/primer.md)).
Two files carry it, with different jobs:

| File | Role |
|---|---|
| `/tmp/plan-batch/last_error.txt` | **One line.** The compiler's own `error: invalid plan spec: <reason>`, or a named reason for a non-compiler failure (no artifact produced / not valid JSON). This is what drives the next attempt. Overwritten each round -- it cannot silt up. |
| `/tmp/plan-batch/history.log` | Append-only, one line per attempt. Read by `RevisePlan` **only** to answer "am I repeating myself?" ([primer §4.9](../../docs/primer.md), regime detection). |

`RevisePlan` is a **separate node** from `AuthorPlan` on purpose. Re-running
the original prompt is a coin re-flip -- same distribution, new sample. The
repair node is prompted against the compiler's exact named error and told to
change only what that error requires. If `history.log` shows the same
rejection twice, its prompt escalates: stop patching the symptom, re-cut the
decomposition so the violated constraint is satisfied by construction. That is
[primer §4.7](../../docs/primer.md) -- an attractor absorbs model drift, not a
wrong plan shape.

**Failure classes are differentiated** ([primer §4.6](../../docs/primer.md)):

| Class | Route | Why |
|---|---|---|
| Compiler rejected the spec | `CheckAttempts -> RevisePlan` | Model drift. Fixable with the named reason. |
| Artifact unusable (missing / not JSON) | `CheckAttempts -> RevisePlan` | Model failure, different reason text. `InstallPlan` catches unparseable JSON before the compiler does, because `python3 -m compiler` raises a raw `JSONDecodeError` traceback on it rather than the clean named error the loop feeds on. |
| LLM node hard-failed (incl. `must_write=` violation) | `condition="outcome=fail"` -> `CheckAttempts` | Model failure. Enters the bounded loop. |
| A deterministic gate crashed outright | `condition="outcome=fail"` -> `Abort` | Infrastructure, not model drift. Spending revision budget on a broken tool is exactly what [primer §4.7](../../docs/primer.md) warns against. |

### The bound is a decision point, not a fuse

`CheckAttempts` increments a counter file and routes: `revise_ok` while under
the cap, `attempts_exhausted` at it. Budget: `attempts.txt` starts at `0`, so
**1 initial authoring pass + 3 revisions = 4 authoring attempts** before the
cap trips.

This is an explicit context counter, **not** `default_max_retry` --
`max_retry` bounds a single node's own execution attempts, it does not limit
how many times the graph traverses a back-edge.

Hitting the cap routes to `Abort`, which:

1. **Removes `plan.json` from the workspace.** This is the point of the node.
2. Writes `plan-batch-residual.md` containing the attempt count, the last
   named compiler reason verbatim, the full attempt history, and next steps.

A human gets a diagnosis, not a shrug -- and no rejected plan escapes.

---

## Doctrine notes and foot-guns respected

Audited against [`docs/RUBRIC.md` §3](../../docs/RUBRIC.md) /
[`docs/primer.md` §6](../../docs/primer.md):

- **§3.1 -- no `shape=diamond` anywhere.** There is no LLM judgment gate in
  this graph at all. Every gate is a deterministic `parallelogram` routing on
  `context.tool.last_line`. The compiler is the judge: free, exhaustive and
  incorruptible.
- **§3.2 -- FAIL does not traverse plain edges.** Every node that can FAIL has
  an explicit `condition="outcome=fail"` edge (see the failure-class table
  above). No branch can silently dead-end.
- **§3.4 -- nothing reads `$last_response`.** Every routing decision reads an
  exit code or a file, so the 200-char truncation under
  `default_fidelity="summary:high"` cannot affect routing. This is also *why*
  the LLM nodes write a file and print a short marker instead of emitting
  multi-KB JSON as prose: a `plan.json` sent through the response channel
  would be truncated away.
- **§3.5 -- all routing is on `context.tool.last_line`**, never `tool.output`.
  Each `tool_command` prints exactly one label to stdout; every diagnostic
  goes to a file or stderr.
- **§3.8 -- cwd is never trusted.** Tool nodes resolve cwd via
  `context.target_dir -> graph.source_dir -> process cwd`, which is not
  guaranteed to be `$GITHUB_WORKSPACE` when this graph is fetched from a
  `git+https://` URL. Every tool node re-anchors with
  `PB_WS=${GITHUB_WORKSPACE:-$PWD}`. Agent nodes are never asked to write a
  relative path -- they write the fixed absolute path
  `/tmp/plan-batch/plan.json`, and the engine's `must_write=` fail-closed
  artifact contract (existence + freshness + non-trivial content) asserts the
  write actually happened rather than trusting the node's own success line.
  The workspace write itself is performed by the deterministic `InstallPlan`
  node, never by an LLM.
- **§3.9 / §4 idempotency -- checkpoints do not resume.** `ResetPlanState`
  wipes a stale `plan.json`, attempt counter and error line at the start of
  every run. Without it, a reused CI checkout carrying a valid `plan.json`
  from a previous run would sail through the gate without this run's planner
  ever succeeding -- the same class of bug fixed by `idea_to_pr.dot`'s
  `ResetFixState`.
- **Tier discipline ([primer §4.1](../../docs/primer.md)).** Two LLM nodes,
  both there for judgment (how to cut an issue into independently verifiable
  lanes). Everything else is deterministic shell. There is deliberately no
  "Report" box node -- summarising a known outcome is typing, not judgment --
  so the terminals are `parallelogram` context stamps.
- **`max_pipeline_duration="45m"` carries a unit suffix.** A bare integer here
  is **milliseconds**.

### Deliberate deviation, recorded

The runtime brief suggested the authoring node *emit the plan.json content as
its response* and have a downstream node capture it. That was not done, and
the reason is §3.4: under this graph's fidelity, `last_response` truncates to
200 characters, so a multi-KB plan sent through the response channel would
arrive mutilated. The equivalent guarantee is obtained without that hazard by
having the LLM write a **fixed absolute** path (cwd-independent, so the
original cwd concern does not apply) and asserting the write with
`must_write=`, while the deterministic `InstallPlan` node still performs the
workspace write. The invariant the brief was protecting -- *no LLM node is
trusted to have placed the file the workflow consumes* -- holds.

---

## Consuming workflow

`.github/workflows/plan-batch.yml` drives this pipeline and is responsible for
everything after the artifact exists:

1. Run `plan-batch.dot` via `microsoft/amplifier-app-actions` on an issue
   event, with `$goal` set to the issue context block.
2. Gate on `test -f plan.json` (see the output-contract note above). If it is
   absent, surface `plan-batch-residual.md` and stop.
3. Relocate the artifact to `generated/plans/<run_id>/plan.json`.
4. Compile the committed plan into its parent `.dot`
   (`python3 -m compiler generated/plans/<run_id>/plan.json -o ...`).
5. Render the graph to Mermaid via
   [`scripts/dot_to_mermaid.py`](../../scripts/dot_to_mermaid.py).
6. Post the rendered plan back to the originating issue with `GH_TOKEN`.

Steps 4-6 are intentionally outside this pipeline: they are deterministic
transport with nothing to converge on, and the primer is explicit that a model
should never be used as a format translator.

---

## Running it locally

`plan-batch` only needs `$goal` and a checkout of this repo, so it runs
outside Actions on the `attractor run` CLI (from `amplifier-bundle-attractor`)
with `GITHUB_WORKSPACE` pointed at the checkout:

```bash
cd /path/to/attractor-pipelines
GITHUB_WORKSPACE="$PWD" \
attractor run "$PWD/pipelines/plan-batch/plan-batch.dot" \
  --cwd "$PWD" \
  --param goal="$(gh issue view 412 --json number,title,body,labels,author -q '.')"
```

`--cwd` must match the directory the `.dot` path resolves from -- a known
constraint of the engine CLI for agent pipelines. Setting `GITHUB_WORKSPACE`
explicitly is what makes the tool nodes' `PB_WS=${GITHUB_WORKSPACE:-$PWD}`
re-anchoring land on the checkout rather than on whatever cwd the engine hands
the subprocess.

Then verify the sink directly -- which is the same check the gate ran:

```bash
python3 -m compiler plan.json -o /tmp/plan-check.dot && echo ACCEPTED
```

Remote source (no local checkout needed by the caller):

```
git+https://github.com/kenotron-ms/attractor-pipelines@main#subdirectory=pipelines/plan-batch/plan-batch.dot
```

---

## Related

- [`compiler/README.md`](../../compiler/README.md) -- the authoritative
  `plan.json` schema and the compiler's invocation contract. **Read this
  before hand-authoring a plan.**
- [`pipelines/goal_plan_smoke/`](../goal_plan_smoke/) -- the hand-authored
  exemplar of the parent `.dot` family this plan compiles into.
- [`docs/primer.md`](../../docs/primer.md) /
  [`docs/RUBRIC.md`](../../docs/RUBRIC.md) -- the doctrine and the checklist
  this pipeline was built and reviewed against.
- [`pipelines/idea_to_pr/idea_to_pr.dot`](../idea_to_pr/idea_to_pr.dot) -- the
  proven pipeline whose `parallelogram` gate / counter-backstop / context-stamp
  terminal idioms this one copies.
