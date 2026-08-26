"""AST node dataclasses for the template engine.

All nodes are pure data containers — no rendering logic lives here.
Positions (line, col) originate in the lexer and are propagated here
by the parser; they are never recomputed from source text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------


@dataclass
class LiteralExpr:
    """A literal value: string, int, float, true, false, or none."""

    value: Any
    line: int
    col: int


@dataclass
class PathExpr:
    """A variable path like ``user.address.city`` or ``items[0]``.

    ``parts`` is a list of steps:
    - A ``str`` step means attribute/key access (dotted).
    - An ``int`` step means integer index access.
    - A ``str`` step that comes from a bracket string literal is still a str.
    """

    root: str
    parts: list[str | int]
    line: int
    col: int


@dataclass
class BinaryExpr:
    """A binary operation: comparison or boolean and/or."""

    op: str  # '==', '!=', '<', '<=', '>', '>=', 'and', 'or'
    left: Any
    right: Any
    line: int
    col: int


@dataclass
class NotExpr:
    """A boolean ``not`` expression."""

    operand: Any
    line: int
    col: int


# ---------------------------------------------------------------------------
# Template nodes
# ---------------------------------------------------------------------------


@dataclass
class TextNode:
    """A literal text segment emitted verbatim."""

    text: str
    line: int
    col: int


@dataclass
class OutputNode:
    """An interpolation tag ``{{ expr | filter... }}``."""

    expr: Any  # expression node
    filters: list[tuple[str, list[Any]]]  # list of (name, [literal_args])
    line: int
    col: int


@dataclass
class IfNode:
    """An ``{% if %} ... {% elif %} ... {% else %} ... {% endif %}`` block.

    ``branches`` is a list of ``(condition_expr, body_nodes)`` tuples, one per
    ``if``/``elif`` arm.  ``else_body`` holds the nodes for the optional
    ``{% else %}`` arm (empty list if absent).
    """

    branches: list[tuple[Any, list[Any]]]
    else_body: list[Any]
    line: int
    col: int


@dataclass
class ForNode:
    """A ``{% for var in expr %} ... {% endfor %}`` loop."""

    var: str
    expr: Any  # expression node
    body: list[Any]
    line: int
    col: int


@dataclass
class IncludeNode:
    """A ``{% include "name" %}`` partial-include tag."""

    name: str
    line: int
    col: int
