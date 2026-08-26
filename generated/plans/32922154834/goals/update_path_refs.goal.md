# Lane update_path_refs

## Outcome

Update every doc, script, and source-code comment in the repository that references the old `scenarios/L*/reference/` paths so they point to the new `graders/references/L*/` location. After this lane, no file under `framework/` or the top-level `README.md` should contain a path of the form `scenarios/L[0-4].../reference/`.

Files known to need updating (from the pre-move state; verify each still contains old paths):

| File | What to change |
|---|---|
| `framework/harness/run_scenario.py` | Usage comment in the module docstring cites `scenarios/L0-roman-numerals/reference/solution` — update to `graders/references/L0-roman-numerals/solution` |
| `README.md` | Usage example cites `scenarios/L1-csv-parser/reference/solution` — update to `graders/references/L1-csv-parser/solution` |
| `scenarios/L0-roman-numerals/EVALUATION.md` | Any prose or code blocks referencing `reference/solution/` or `reference/solution_broken/` should be updated to note the new location `graders/references/L0-roman-numerals/` |
| `scenarios/L1-csv-parser/EVALUATION.md` | Same treatment — update path references |
| `scenarios/L2-lru-cache/EVALUATION.md` | Same treatment |
| `scenarios/L3-log-analyzer/EVALUATION.md` | Same treatment — includes a code block with `--solution scenarios/L3-log-analyzer/reference/solution` |
| `scenarios/L4-template-engine/EVALUATION.md` | Same treatment — includes a code block with `--solution scenarios/L4-template-engine/reference/solution` |

For each file, replace occurrences of `scenarios/L<N>-<name>/reference/` with `graders/references/L<N>-<name>/`. Prose that says "reference/solution/" in a relative sense (e.g. "its grader passes on `reference/solution/`") should be updated to say "grader passes on `graders/references/L<N>-<name>/solution/`" to keep the paths unambiguous and accurate.

Do NOT change anything inside files that now live under `graders/references/` themselves (internal comments in reference solution source files that mention `reference/solution/` are self-referential and acceptable to leave as-is, since those files are not agent-visible).

## Steps

1. For `framework/harness/run_scenario.py`: find the module docstring usage example and replace `scenarios/L0-roman-numerals/reference/solution` with `graders/references/L0-roman-numerals/solution`.

2. For `README.md`: find the usage example block and replace `scenarios/L1-csv-parser/reference/solution` with `graders/references/L1-csv-parser/solution`.

3. For each `scenarios/L{0,1,2,3,4}-*/EVALUATION.md`:
   - Replace any shell command `--solution scenarios/L<N>-<name>/reference/solution` with `--solution graders/references/L<N>-<name>/solution`.
   - Replace prose references like `` `reference/solution/` `` with `` `graders/references/L<N>-<name>/solution/` `` and `` `reference/solution_broken/` `` with `` `graders/references/L<N>-<name>/solution_broken/` ``.

4. After edits, run the verification grep (see Done when) to confirm no old-pattern paths remain in the target files.

5. Stage all changed files.

## Done when

The following command exits 0 (meaning: no occurrences of the old path pattern remain in framework scripts or top-level README):

```bash
! grep -rn 'scenarios/L[0-4][^/]*/reference/' --include='*.py' --include='*.md' --include='*.yaml' --include='*.yml' framework/ README.md 2>/dev/null | grep -v '^Binary'
```

Exit 0 from this command means grep found zero matches (the `!` negates grep's exit code), confirming all old path references have been removed from the framework and README.

## Final step (REQUIRED)

After the work is done and the check above passes, write the file `artifacts/update_path_refs.done` containing exactly the text `update_path_refs:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
