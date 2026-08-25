# RUBRICS — reusable scoring lenses

> Named, reusable rubrics for scoring the ideas in `IDEAS.md`. **Definitions only — no results.**
> Each scoring *run* is a dated artifact in `scores/` recording the date + which rubric it used,
> so we can re-score over time and run different rubrics. Rubrics are stable; results are snapshots
> (ideas, team state, and twin availability all drift).

## How to use
1. Pick a rubric from the registry below.
2. Score the ideas at *idea-maturity* (no fleshing-out — rubric first, flesh-out second).
3. Write the run to `scores/<YYYY-MM-DD>-<rubric-id>.md`, noting the rubric and any input snapshots
   (e.g. team-interest state) used.

## Registry

| Rubric | id | Judges |
|---|---|---|
| **Dev-Machine Fit** | `dev-machine-fit` | How good a candidate an idea is to feed to the greenfield, **Python-only** dev-machine pipeline. |

---

## Rubric: Dev-Machine Fit — `dev-machine-fit`

*"How good a candidate is this idea to feed to my dev machine?"* — greenfield, **Python-only** (today),
admissions gate → plan → feature specs → implement → validate with **reality-check**.

**Admissions gate (pass/fail, judged from the idea entry as-is — no fleshing-out):**
- **A. Clear intent** — goal stateable crisply enough to drive a plan.
- **B. Evident scope** — *clearly* implies ≥3 user stories → pass · clearly tiny → fail · borderline → pass + `scope:uncertain`.

**Language is a FLAG, not a gate** (changed 2026-06-26 — the machine is Python-only *today*, but we score the
idea's *intrinsic* value so we can see what the constraint blocks and how much another language would unlock).
Score every idea fully, then tag a **`python:` flag**:
- `python: full` — completable entirely in Python (CLI / service / library / pipeline).
- `python: core+shell` — Python core, but **can't be *completed* in Python** — needs a non-Python shell
  (React/mobile UI, hardware, game engine). **Highlight these — partially blocked.**
- `python: none` — not Python at all (e.g. .NET, a platform SDK). **Fully blocked today.**

**Scored 0–3 each:**
1. **Greenfield fit** — net-new build vs. extending something existing.
2. **Python-nativeness** — how much of the *value* is deliverable in pure Python (penalize big non-Python shells: React, native mobile, hardware, game engine).
3. **Scope richness** — beyond the floor, how cleanly it fans into many independent features.
4. **Reality-check validatability** — can success be auto-verified (deterministic, testable behavior + acceptance tests)? Aesthetic/subjective output scores low.
5. **Self-contained / mockable** — buildable & validatable without real proprietary services, special hardware, or live accounts — **or** with a DTU twin.

**Modifier:** Team value **+0 / +1 / +2** (snapshot of team interests at scoring time — record the snapshot in the run).

**Annotations:**
- `TWIN-GATED(minimal|full): <twin>` — ⑤ low *because* of a missing DTU twin (signal to maybe build the twin).
- `scope:uncertain` — borderline-B.

**Score = 0–15 (five dims) + team (0–2) → 0–17.** Score the **best buildable slice** that passes gates A+B;
② Python-nativeness already reflects the language flag (high = `full`, low = `core+shell`/`none`).

**Known caveats (apply on every run):**
- **Only score actual ideas-to-build.** A *derived* "building block" that turns out to be an **existing
  capability** (e.g. a "generative eval harness" = just *use `evaluation` mode*) is **not an idea** —
  **leave it out of the run entirely** (it lives in `BUILDING-BLOCKS.md`, not the scores).
- Score the slice you'd actually feed the machine, not the sprawling whole.
- **Language is scored, not gated** (see flag above) — surface `core+shell` and `none` ideas in a
  **Language reality** section so the cost of Python-only is visible.

### Report format — every run is identical and self-contained

A scoring run is a **standalone snapshot**. It **must not reference other runs** — "supersedes",
"since run 1", "extends", "delta" are forbidden; restate everything needed. Use these sections, in order:

1. **Header** — `# Scoring run — <date> — rubric: <id>` + one line: "self-contained snapshot scoring every idea".
2. **Team-interest snapshot** — source + date + the signal behind the team modifier.
3. **Top candidates** — table with per-dimension scores + notes (the strong band).
4. **Build-first shortlist** — the no-twin-needed ranking.
5. **TWIN-GATED** — table: twin · cost · unlocks.
6. **Language reality** — what Python-only blocks: the `core+shell` and `none` ideas, with the language they'd need.
7. **Other gate notes** — `scope:uncertain`, etc. (Do not list non-ideas.)
8. **Full scores (every idea)** — complete table sorted by total desc: idea · `python:` · ①②③④⑤ · team · total · flags.
