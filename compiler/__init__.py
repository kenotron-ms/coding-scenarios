"""Deterministic goal-plan compiler.

Turns a ``plan.json``-shaped spec into a ``goal_plan_smoke``-family parent
``.dot`` pipeline. No LLM anywhere in this code path -- same spec in, byte-
identical DOT out.

Public API::

    from compiler import compile_plan, load_plan, build_plan, PlanValidationError

    dot_source = compile_plan(load_plan("plan.json"))
"""

from __future__ import annotations

from .generator import compile_plan
from .plan import Lane, Plan, PlanValidationError, build_plan, load_plan

__all__ = [
    "Lane",
    "Plan",
    "PlanValidationError",
    "build_plan",
    "compile_plan",
    "load_plan",
]
