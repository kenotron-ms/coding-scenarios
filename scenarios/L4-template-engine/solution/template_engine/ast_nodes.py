"""AST node definitions for the template engine.

Every node carries position metadata (line, col) originating from the lexer.
The renderer consumes these nodes; it never re-invokes the lexer or parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """Abstract base for all AST nodes."""
    line: int
    col: int


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------

@dataclass
class NameNode(Node):
    """A simple identifier: {{ name }}"""
    name: str


@dataclass
class LiteralNode(Node):
    """A literal value: string, int, float, bool, or None."""
    value: Any


@dataclass
class PathNode(Node):
    """Chained attribute/index access: a.b[0].c

    steps: list of (kind, key) where kind is 'attr' or 'index'.
    The root is a NameNode.
    """
    root: NameNode
    steps: list[tuple[str, Any]]  # ('attr', 'name') | ('index', expr_node)


@dataclass
class FilterNode(Node):
    """value | filter_name(args...)"""
    expr: Any          # expression node
    name: str
    args: list[Any]    # literal argument nodes


@dataclass
class BinOpNode(Node):
    """Binary comparison or boolean operation."""
    op: str            # '==' '!=' '<' '<=' '>' '>=' 'and' 'or'
    left: Any
    right: Any


@dataclass
class UnaryOpNode(Node):
    """Unary 'not' operation."""
    op: str            # 'not'
    operand: Any


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------

@dataclass
class TextNode(Node):
    """Literal text to output verbatim."""
    text: str


@dataclass
class InterpolationNode(Node):
    """{{ expr }} — interpolate expression."""
    expr: Any


@dataclass
class IfNode(Node):
    """{% if %} ... {% elif %} ... {% else %} ... {% endif %}"""
    condition: Any
    body: list[Any]
    elif_clauses: list[tuple[Any, list[Any]]]  # (condition, body) pairs
    else_body: list[Any]


@dataclass
class ForNode(Node):
    """{% for var in expr %} ... {% endfor %}"""
    var: str
    iterable: Any
    body: list[Any]


@dataclass
class IncludeNode(Node):
    """{% include "name" %}"""
    template_name: str


@dataclass
class TemplateNode(Node):
    """Root node: the whole template."""
    body: list[Any]
