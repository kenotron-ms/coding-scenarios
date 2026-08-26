# Lane create-smoke-marker

## Outcome

Create the file `BATCH_SMOKE.md` at the repository root. The file must contain the exact line:

    batch delivery verified

## Steps

1. Create (or overwrite) the file `BATCH_SMOKE.md` at the repository root.
2. Ensure the file contains the exact line `batch delivery verified` (the line must be present verbatim, with no extra leading/trailing whitespace on that line).

A minimal valid file contents example:

```
batch delivery verified
```

## Done when

The following command exits 0 when run from the repository root:

```
grep -q "batch delivery verified" BATCH_SMOKE.md
```

This is the machine check that proves the deliverable exists with the required content.

## Final step (REQUIRED)

After the work is done and the check above passes, write the file `artifacts/create-smoke-marker.done` containing exactly the text:

    create-smoke-marker:ok

and nothing else (no trailing newline beyond what is standard, no extra content). This marker file is how the batch orchestrator confirms the lane finished — it must be the LAST action taken.
