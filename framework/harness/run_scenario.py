#!/usr/bin/env python3
"""Reference grader for the coding-scenarios eval ladder.

Grades ONE produced solution against ONE scenario and emits score.json, per
`framework/GRADING.md` and `framework/VERIFICATION_CONTRACT.md`.

Scope: this reference runner drives the deterministic entrypoint kinds
(`python-module`, `cli`) directly via pytest tiers. For `http-service`,
`web-app`, and `desktop-app` it shells to the scenario's declared `verify`
commands (which own their servers/browsers/fixtures). The automated axes
(COR/ROB/REG/EFF/AUT) are computed here; QUA/FID (graded portion) are left
`null` with `judge_pending` for the grader agent (GRADING.md §6). QUA also
carries a provisional value from the static-analysis floor.

Usage:
  python framework/harness/run_scenario.py \
      --scenario scenarios/L0-roman-numerals \
      --solution graders/references/L0-roman-numerals/solution \
      [--telemetry telemetry.json] [--strategy name] --out runs/<dt>/L0/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

TIERS = ("smoke", "acceptance", "adversarial")


def load_yaml(p: Path) -> dict:
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def run_tier(scenario: Path, tier: str, solution: Path, out: Path) -> dict | None:
    """Run a pytest tier against the solution; return {total, passed} or None."""
    if not (scenario / "tests" / tier).exists():
        return None
    xml = out.resolve() / f"{tier}.xml"
    env = {**os.environ, "SOLUTION_DIR": str(solution.resolve()), "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [
        sys.executable, "-m", "pytest", f"tests/{tier}",   # relative to cwd=scenario
        "-q", "-p", "no:cacheprovider", f"--junitxml={xml}",
    ]
    subprocess.run(cmd, cwd=scenario.resolve(), env=env, capture_output=True, text=True, check=False)
    if not xml.exists():
        return {"total": 0, "passed": 0, "error": "no junit xml produced"}
    total = passed = 0
    root = ET.parse(xml).getroot()
    for suite in root.iter("testsuite"):
        t = int(suite.get("tests", 0))
        f = int(suite.get("failures", 0))
        e = int(suite.get("errors", 0))
        s = int(suite.get("skipped", 0))
        total += t
        passed += t - f - e - s
    return {"total": total, "passed": passed}


def frac(r: dict | None) -> float:
    if not r or not r.get("total"):
        return 0.0
    return r["passed"] / r["total"]


def static_floor(solution: Path, tools: list[str]) -> tuple[bool | None, list[str]]:
    """Run available static-analysis tools; floor passes only if all present pass."""
    notes: list[str] = []
    ran = False
    ok = True
    for tool in tools:
        exe = tool.split()[0]
        if not shutil.which(exe):
            notes.append(f"{exe}: not installed (skipped)")
            continue
        ran = True
        if exe == "ruff":
            cmd = ["ruff", "check", str(solution)]
        elif exe == "pyright":
            cmd = ["pyright", str(solution)]
        else:
            cmd = tool.split() + [str(solution)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            ok = False
            notes.append(f"{exe}: FAILED")
        else:
            notes.append(f"{exe}: ok")
    return (ok if ran else None), notes


def run_probes(solution: Path, rubric: dict) -> dict:
    """Evaluate named gate-authority probes (GRADING.md §1/§4) -> {id: bool}.

    Supported kinds:
      absent_import: passes iff the solution never imports `module` (e.g. L1's
                     "stdlib csv is forbidden" -> check:L1-CSVLIB-none).
    """
    checks: dict[str, bool] = {}
    for p in rubric.get("probes", []):
        pid, kind = p.get("id"), p.get("kind")
        if kind == "absent_import":
            mod = re.escape(p["module"])
            pat = re.compile(rf"^\s*(import\s+{mod}\b|from\s+{mod}\b)", re.M)
            hit = any(pat.search(f.read_text(errors="ignore")) for f in solution.rglob("*.py"))
            checks[pid] = not hit
        else:  # unknown probe kind -> conservatively fail (do not silently pass a gate)
            checks[pid] = False
    return checks


# --- axis scorers (defaults; anchors per scenario §7.2) --------------------

def cor_score(acc: float, adv: float) -> int:
    if acc >= 1.0:
        return 4 if adv >= 0.95 else 3 if adv >= 0.80 else 2
    return 2 if acc >= 0.8 else 1 if acc >= 0.5 else 0


def rob_score(adv: float) -> int:
    return 4 if adv >= 0.95 else 3 if adv >= 0.80 else 2 if adv >= 0.60 else 1 if adv >= 0.40 else 0


def eff_score(t: dict | None, b: dict) -> int | None:
    if not t:
        return None
    it, wall, tok = t.get("iterations", 1e9), t.get("wall_clock_s", 1e9), t.get("tokens", 1e9)
    frb = t.get("failed_runs_before_pass", 0)
    soft, hard = b.get("iterations_soft", 1e9), b.get("iterations_hard", 1e9)
    wc, tb = b.get("wall_clock_s", 1e9), b.get("token_budget", 1e18)
    if it <= soft and wall <= wc and tok <= tb and frb <= 1:
        return 4
    if it <= hard and wall <= 1.5 * wc and tok <= 1.5 * tb:
        return 3
    if it <= hard:
        return 2
    return 1


_SEV = {"rescue": 1, "hint": 2, "unblock": 3, "clarify": 3, "nudge": 4}


def aut_score(t: dict | None) -> int | None:
    if not t:
        return None
    iv = t.get("interventions", [])
    if not iv:
        return 4
    worst = min(_SEV.get(i.get("tag", "nudge"), 4) for i in iv)
    if len(iv) > 3:
        worst = max(1, worst - 1)
    return worst


def qua_provisional(floor_ok: bool | None) -> int | None:
    if floor_ok is None:
        return None
    return 3 if floor_ok else 1  # provisional; grader agent sets the final 0-4


def band_of(score: int) -> str:
    return ("Converged-Clean" if score >= 85 else "Converged" if score >= 70
            else "Converged-Rough" if score >= 55 else "Sub-threshold")


def eval_gate(expr: str, ns: dict) -> bool:
    expr = re.sub(r"check:([A-Za-z0-9_\-]+)",
                  lambda m: str(bool(ns.get("checks", {}).get(m.group(1), False))), expr)
    return bool(eval(expr, {"__builtins__": {}}, ns))  # noqa: S307 (restricted ns)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, type=Path)
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--telemetry", type=Path)
    ap.add_argument("--strategy", default="unknown")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    manifest = load_yaml(a.scenario / "manifest.yaml")
    rubric = load_yaml(a.scenario / "rubric.yaml")
    telemetry = load_yaml(a.telemetry) if a.telemetry else None

    results = {t: run_tier(a.scenario, t, a.solution, a.out) for t in TIERS}
    acc, adv = frac(results["acceptance"]), frac(results["adversarial"])

    warnings = []
    dens = rubric.get("denominators", {})
    for tier in ("acceptance", "adversarial"):
        declared, actual = dens.get(tier), (results[tier] or {}).get("total")
        if declared is not None and actual is not None and declared != actual:
            warnings.append(
                f"denominator drift: {tier} declared {declared} but ran {actual}")

    floor_ok, floor_notes = static_floor(a.solution, rubric.get("static_floor", {}).get("python", []))

    probes = run_probes(a.solution, rubric)
    ns = {
        "acceptance_pass": acc, "adversarial_pass": adv,
        "p0_pass": acc,           # L0-L5 have no P0 subset; equals acceptance
        "regression_pass": 1.0 if manifest.get("regression", {}).get("strategy") == "none" else acc,
        "perf_ok": None, "security_ok": None, "checks": probes,
    }
    gate_expr = rubric.get("gate", "acceptance_pass == 1.0")
    passed = eval_gate(gate_expr, ns)

    weights = rubric.get("weights", {})
    axes = {
        "COR": cor_score(acc, adv), "ROB": rob_score(adv),
        "EFF": eff_score(telemetry, manifest.get("budgets", {})),
        "AUT": aut_score(telemetry), "QUA": qua_provisional(floor_ok),
        "REG": None, "FID": None,
    }
    covered = {k: v for k, v in axes.items() if v is not None and k in weights}
    weight_covered = sum(weights[k] for k in covered)
    raw = sum((v / 4) * weights[k] for k, v in covered.items())
    score = 0 if not passed else round(raw)
    band = "Failed" if not passed else band_of(round(raw))

    out = {
        "scenario": rubric.get("scenario") or manifest.get("scenario"),
        "strategy": a.strategy,
        "gate": {"expression": gate_expr, **{k: ns[k] for k in
                 ("acceptance_pass", "p0_pass", "regression_pass")}, "passed": passed},
        "denominators": dens,
        "results": {"acceptance_pass": round(acc, 4), "adversarial_pass": round(adv, 4),
                    "smoke": results["smoke"], "acceptance": results["acceptance"],
                    "adversarial": results["adversarial"], "static_floor_pass": floor_ok},
        "axes": axes, "weights": weights,
        "weight_covered": weight_covered,
        "score": score, "band": band,
        "pass_threshold": rubric.get("pass_threshold"),
        "converged": bool(passed and round(raw) >= (rubric.get("pass_threshold") or 101)),
        "telemetry": telemetry,
        "judge_pending": [k for k in ("QUA", "FID") if k in weights and axes[k] is None
                          or (k == "QUA" and axes.get("QUA") is not None)],
        "notes": {"static_floor": floor_notes, "QUA": "provisional from static floor; run grader agent for final"},
        "warnings": warnings,
    }
    (a.out / "score.json").write_text(json.dumps(out, indent=2))

    print(f"scenario={out['scenario']} strategy={a.strategy}")
    print(f"  acceptance={acc:.2%} adversarial={adv:.2%} gate={'PASS' if passed else 'FAIL'}")
    print(f"  axes={axes}")
    print(f"  score={score} band={band} threshold={out['pass_threshold']} converged={out['converged']}")
    if warnings:
        print("  WARNINGS: " + "; ".join(warnings))
    print(f"  -> {a.out / 'score.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
