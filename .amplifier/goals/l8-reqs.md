# Goal — lane `l8-reqs`: make L8 (markdown-editor) GRADEABLE

## Outcome
Edit **only** `scenarios/L8-markdown-editor/REQUIREMENTS.md` so its perf+security gate
`p0_pass == 1.0 and acceptance_pass >= 0.90 and perf_ok and security_ok` becomes
**computable**, WITHOUT building a runnable grader (Tauri/ssh infra is out of scope).

## Exit
Complete when **either** every item below reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items
ending FAIL or BLOCKED are residuals, not failures of the goal.
Terminal states: `PASS` / `FAIL-<reason>` / `BLOCKED-<reason>` / `PENDING-HUMAN-<reason>`.

## Items (all inside `scenarios/L8-markdown-editor/REQUIREMENTS.md`)
1. **§0 budgets** — replace the vague "multi-session / multi-day, tunable" with the
   concrete values already fixed in `framework/GRADING.md §9` for L8: wall_clock_s 28800,
   iterations soft 60 / hard 150, token_budget 3M. State them as the scenario's budgets.
2. **Regression mechanism** — in §6 (and §8) declare L8's regression strategy explicitly
   as **`workspace-snapshots`** (per `framework/GRADING.md §5`): prior acceptance re-run at
   mid-build snapshots. Make the `REG` axis well-defined.
3. **P0-tag acceptance** — in §4/§6, mark which acceptance criteria are **P0** (the gate's
   `p0_pass` set) vs **P1**, so `p0_pass == 1.0` is computable. §4.2 already tiers the FRs
   P0/P1; extend that to the acceptance criteria list so each acceptance item carries a
   priority.
4. **Name the gate authorities** — in §6/§7, explicitly name the checks that make
   `perf_ok` and `security_ok` true: the cold-boot/first-render budget checks (perf) and
   the host-key-verification + no-secrets-persisted + content-sanitization checks
   (security), tagged as `gate_authority` per `framework/GRADING.md §1/§4`. The concrete
   perf numbers already live in NFR-1 (≤800 ms cold / ≤400 ms warm) — reference them.
5. **Consistency** — confirm §7 stays coherent (L8 pass_threshold stays **66** — do NOT
   change it; the threshold/band reconciliation is the orchestrator's job on OTHER files).
   Confirm the gate expression in §6.2/§7.3 now has computable `p0_pass`, `perf_ok`,
   `security_ok`.

## Ground rules
- **Work ONLY in this worktree**: `/home/ken/workspace/coding-scenarios.gb/l8-reqs`,
  branch `gb/l8-reqs`. Do NOT touch the main checkout or sibling worktrees.
- **OWN only** `scenarios/L8-markdown-editor/REQUIREMENTS.md`. Do NOT edit `framework/`
  (GRADING §9 already has the numbers — just restate them), `README.md`, or any other
  scenario. If you think another file needs a change, record it as a `residual`.
- **Do NOT change L8's pass_threshold (66)** — that overlaps the orchestrator's
  threshold/band work; changing it here causes a collision.
- **Commit** your edit to your branch. Do NOT push to origin. **NEVER merge to main.**
- **Time bound**: honor the wall-clock; exceeding it is terminal `BUDGET`.
- **DONE.json** (gitignored) in the worktree root as your **final act**:
  `{lane:"l8-reqs", session_id:<your own>, verdict:<COMPLETE|BLOCKED|PARTIAL>, branch,
  head:<sha>, pushed:false, items:[...], residuals:[...], pending_human:[...],
  suite:"n/a — documentation edit; consistency verified by reading §0/§4/§6/§7"}`.

## KNOWN
- This is a documentation edit, not code. No tests to run. The success criterion is that
  a grader reading L8 could compute `p0_pass`, `perf_ok`, `security_ok`, and a `REG` value
  from the spec. Keep the existing L8 voice and section structure (§0–§8).
