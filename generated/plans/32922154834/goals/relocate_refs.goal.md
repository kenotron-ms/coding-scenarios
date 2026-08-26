# Lane relocate_refs

## Outcome

Move all five `reference/` subtrees from inside the scenario directories to a new top-level `graders/references/` directory, so no reference solution lives within the scenario tree an agent can access.

Specifically, perform these git-tracked moves (preserving history):

| Old path | New path |
|---|---|
| `scenarios/L0-roman-numerals/reference/` | `graders/references/L0-roman-numerals/` |
| `scenarios/L1-csv-parser/reference/` | `graders/references/L1-csv-parser/` |
| `scenarios/L2-lru-cache/reference/` | `graders/references/L2-lru-cache/` |
| `scenarios/L3-log-analyzer/reference/` | `graders/references/L3-log-analyzer/` |
| `scenarios/L4-template-engine/reference/` | `graders/references/L4-template-engine/` |

Also update `.gitignore` so the new location is explicitly kept (the existing `!scenarios/**/reference/**` keep-rule must be replaced or supplemented with `!graders/references/**` since the files have moved).

Do NOT delete any files — only move them. All reference solution files must exist at their new paths after the move.

## Steps

1. Create the destination directory: `mkdir -p graders/references`
2. Use `git mv` (or equivalent) to move each scenario's `reference/` directory:
   - `git mv scenarios/L0-roman-numerals/reference graders/references/L0-roman-numerals`
   - `git mv scenarios/L1-csv-parser/reference graders/references/L1-csv-parser`
   - `git mv scenarios/L2-lru-cache/reference graders/references/L2-lru-cache`
   - `git mv scenarios/L3-log-analyzer/reference graders/references/L3-log-analyzer`
   - `git mv scenarios/L4-template-engine/reference graders/references/L4-template-engine`
3. Edit `.gitignore`: replace the line `!scenarios/**/reference/**        # keep reference solutions` with two lines:
   ```
   !graders/references/**            # keep reference solutions (moved from scenario tree)
   !scenarios/**/reference/**        # keep reference solutions (legacy — no longer populated)
   ```
   (Keeping the old line is harmless and avoids breaking any cached tooling; adding the new line ensures the new location is tracked.)
4. Stage all changes (`git add -A` or equivalent) — do not commit; the harness commits.

## Done when

The following command exits 0:

```bash
bash -c "test ! -d scenarios/L0-roman-numerals/reference && test ! -d scenarios/L1-csv-parser/reference && test ! -d scenarios/L2-lru-cache/reference && test ! -d scenarios/L3-log-analyzer/reference && test ! -d scenarios/L4-template-engine/reference && test -f graders/references/L0-roman-numerals/solution/roman.py && test -f graders/references/L1-csv-parser/solution/csvparse.py && test -f graders/references/L2-lru-cache/solution/lru.py && test -f graders/references/L3-log-analyzer/solution/loganalyze.py && test -d graders/references/L4-template-engine/solution/template_engine"
```

That is: none of the five old `reference/` directories exist under `scenarios/`, AND the key reference files exist at their new locations under `graders/references/`.

## Final step (REQUIRED)

After the work is done and the check above passes, write the file `artifacts/relocate_refs.done` containing exactly the text `relocate_refs:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
