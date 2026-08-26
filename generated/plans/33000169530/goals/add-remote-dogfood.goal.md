# Lane add-remote-dogfood

## Outcome

Create the file `REMOTE_DOGFOOD.md` at the repository root. The file must contain exactly one line with the text `remote-ok` and nothing else (no trailing blank lines beyond the single newline that terminates the line).

## Steps

1. At the repository root, create the file `REMOTE_DOGFOOD.md`.
2. Write exactly the single line `remote-ok` into the file (i.e., the file contents are `remote-ok\n`).
3. Do not add any other content, headers, or blank lines.
4. Stage and commit the file (the lane runner will handle the git operations, but ensure the file is present and correct in the working tree).

## Done when

The following command exits 0:

```
test -f REMOTE_DOGFOOD.md && grep -qx 'remote-ok' REMOTE_DOGFOOD.md
```

`grep -qx 'remote-ok'` matches the entire line exactly — the file must contain a line whose full content is `remote-ok` with no extra characters.

## Final step (REQUIRED)

After the work is done and the check above passes, write the file `artifacts/add-remote-dogfood.done` containing exactly the text `add-remote-dogfood:ok` and nothing else. This marker is how the batch orchestrator confirms the lane finished, so it must be the LAST action performed.

```bash
mkdir -p artifacts
printf 'add-remote-dogfood:ok' > artifacts/add-remote-dogfood.done
```
