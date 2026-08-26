"""Command-line entry point for the goal-plan compiler.

Usage::

    python -m compiler PLAN_JSON [-o OUTPUT_DOT]

Reads a ``plan.json``-shaped spec, compiles it into a ``goal_plan_smoke``-family
parent ``.dot``, and writes it to ``-o`` (or stdout if omitted). Exits non-zero
with a named error message on an invalid plan.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .generator import compile_plan
from .plan import PlanValidationError, load_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m compiler",
        description="Compile a plan.json-shaped spec into a goal_plan_smoke-family parent .dot",
    )
    parser.add_argument("plan_json", help="path to the plan.json-shaped spec")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="write the generated .dot here (default: stdout)",
    )
    args = parser.parse_args(argv)

    try:
        plan = load_plan(args.plan_json)
        dot_source = compile_plan(plan)
    except PlanValidationError as e:
        print(f"error: invalid plan spec: {e}", file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(dot_source, encoding="utf-8")
    else:
        sys.stdout.write(dot_source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
