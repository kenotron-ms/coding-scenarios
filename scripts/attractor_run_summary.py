#!/usr/bin/env python3
"""Render a human-readable summary of a goal_plan_smoke run from its state/logs.

Reads the on-disk artifacts a goal_plan run leaves under `--state` (the
`state_root`) and `--logs` (the `--logs-root` per-node dir) and prints a
Markdown report to stdout. Used by the `execute-plan` GitHub Actions workflow
to surface *why* a run ended (COMPLETE / RESIDUALS_READY / INFRA_FAILURE /
ABORTED) directly in the run's Step Summary, job log, and issue comment -- so
operators never have to download and dig through the run artifact.

Purely defensive: every file read is guarded; missing/renamed/partial state
degrades to a thinner report, never a crash. It is an observability helper, so
it must not itself become a failure source in CI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Lines in a lane's child stderr / a node's output that are worth surfacing.
ERROR_MARKERS = (
    "Error at ",
    "no_matching_edge",
    "Traceback",
    "MERGE_CONFLICT",
    "AGGREGATE_FAIL",
    "AGGREGATE_INFRA",
    "BUDGET:",
    "INFRA",
    "FileNotFoundError",
    "\u2717",  # cross mark
    "postmortem",
)

# Node output.txt files that are pure routing/terminal noise -- never worth
# tailing (the terminal is already in the header; carriers/cleanup just echo it).
_BORING_NODES = {
    "Start",
    "Admit",
    "CheckAbortRequested",
    "CheckPlanCorrespondence",
    "Residuals",
    "ResidualsCarrier",
    "ResidualsCleanup",
    "CompleteCarrier",
    "InfraCarrier",
    "AbortedCarrier",
    "PreTerminalCleanup",
}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 - defensive: never crash CI on bad/missing state
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - defensive: never crash CI on bad/missing state
        return ""


def _lane_names(state: Path) -> list[str]:
    names: set[str] = set()
    for sub in ("results", "lane-results"):
        d = state / sub
        if d.is_dir():
            for f in d.glob("*.json"):
                names.add(f.stem)
    return sorted(names)


def _interesting_lines(text: str, limit: int = 8) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(m in line for m in ERROR_MARKERS):
            hits.append(s)
            if len(hits) >= limit:
                break
    return hits


def _fence(lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "(no output)"
    return "```\n" + body + "\n```"


def build(state: Path, logs: Path, run_id: str, terminal: str, pr_url: str) -> str:
    out: list[str] = []
    emoji = {"COMPLETE": "\u2705", "RESIDUALS_READY": "\u26a0\ufe0f"}.get(
        terminal, "\u274c"
    )
    out.append(f"## {emoji} Attractor batch `{run_id}` \u2014 `{terminal}`")
    out.append("")
    out.append(f"- **Terminal:** `{terminal}`")
    out.append(f"- **PR:** {pr_url if pr_url else 'none'}")
    out.append("")

    lanes = _lane_names(state)

    # --- Lanes table -----------------------------------------------------
    if lanes:
        out.append("### Lanes")
        out.append("| Lane | Process | Result | Note |")
        out.append("|------|---------|--------|------|")
        for lane in lanes:
            res = _read_json(state / "results" / f"{lane}.json") or {}
            proc = res.get("verdict", "?")
            code = res.get("normalized_exit_code")
            proc_cell = f"{proc} ({code})" if code is not None else str(proc)
            lr = _read_json(state / "lane-results" / f"{lane}.json")
            if lr is None:
                result_cell = "\u2014 (no candidate)"
                note = ""
            else:
                result_cell = str(lr.get("result", "?"))
                note = lr.get("blocker_reason") or ""
            out.append(f"| `{lane}` | {proc_cell} | {result_cell} | {note} |")
        out.append("")

    # --- Integration journal --------------------------------------------
    journal = _read_json(state / "integration-journal.json")
    entries = (journal or {}).get("entries") or []
    if entries:
        out.append("### Integration")
        out.append("| Seq | Lane | Result | Rolled back |")
        out.append("|-----|------|--------|-------------|")
        for e in sorted(entries, key=lambda x: x.get("sequence", 0)):
            r = e.get("result", "?")
            mark = "\u2705" if r == "ACCEPTED" else "\u274c"
            rb = "yes" if e.get("rolled_back") else "no"
            out.append(
                f"| {e.get('sequence', '?')} | `{e.get('lane_id', '?')}` | {mark} {r} | {rb} |"
            )
        out.append("")

    # --- Why did it end this way ----------------------------------------
    reasons: list[str] = []
    for e in entries:
        r = e.get("result")
        if r and r != "ACCEPTED":
            reasons.append(
                f"**`{e.get('lane_id', '?')}`** \u2014 {r} during integration "
                f"(seq {e.get('sequence', '?')}): candidate was verified on its own but "
                f"could not be merged on top of the already-integrated lane(s)."
            )
    for lane in lanes:
        lr = _read_json(state / "lane-results" / f"{lane}.json")
        if lr and lr.get("result") == "blocked":
            reasons.append(
                f"**`{lane}`** \u2014 blocked ({lr.get('blocker_reason', 'no reason recorded')})."
            )
        if lr is None:
            res = _read_json(state / "results" / f"{lane}.json") or {}
            code = res.get("normalized_exit_code")
            if code not in (0, None):
                reasons.append(
                    f"**`{lane}`** \u2014 lane process exited {code} and produced no candidate "
                    f"(its goal verification did not pass)."
                )
    if terminal != "COMPLETE":
        out.append(f"### Why `{terminal}`")
        if reasons:
            out.extend(f"- {r}" for r in reasons)
        else:
            out.append(
                "- No single blocker was auto-detected; see the node/lane logs below."
            )
        out.append("")

    # --- Key error excerpts ---------------------------------------------
    excerpts: list[str] = []

    # Per-lane child stderr (where a lane's own goal-verify failure is printed).
    for lane in lanes:
        hits = _interesting_lines(_read_text(state / "logs" / f"{lane}.stderr"))
        if hits:
            excerpts.append(
                f"<details><summary>lane <code>{lane}</code> \u2014 stderr</summary>\n\n{_fence(hits)}\n</details>"
            )

    # Per-node output.txt for decisive nodes.
    if logs.is_dir():
        for node_dir in sorted(p for p in logs.iterdir() if p.is_dir()):
            node = node_dir.name
            if node in _BORING_NODES:
                continue
            text = _read_text(node_dir / "output.txt")
            if not text.strip():
                continue
            decisive = node.startswith(("Integrate", "Correction", "ParentVerify"))
            has_err = any(m in text for m in ERROR_MARKERS)
            clean = text.strip() in {"PASS", "ACCEPTED", "candidate"}
            if (decisive and not clean) or has_err:
                tail = [ln for ln in text.splitlines() if ln.strip()][-8:]
                excerpts.append(
                    f"<details><summary>node <code>{node}</code></summary>\n\n{_fence(tail)}\n</details>"
                )

    if excerpts:
        out.append("### Key errors")
        out.extend(excerpts)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", required=True, help="goal_plan state_root dir")
    ap.add_argument("--logs", required=True, help="pipeline-runner --logs-root dir")
    ap.add_argument("--run-id", default=os.environ.get("RUN_ID", "unknown"))
    ap.add_argument("--terminal", default="unknown")
    ap.add_argument("--pr-url", default="")
    args = ap.parse_args()
    try:
        report = build(
            Path(args.state), Path(args.logs), args.run_id, args.terminal, args.pr_url
        )
        print(report, end="")
    except Exception as exc:  # noqa: BLE001 - the summarizer must never fail the CI job
        print(
            f"## Attractor batch `{args.run_id}` - `{args.terminal}`\n\n_(summary error: {exc})_\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
