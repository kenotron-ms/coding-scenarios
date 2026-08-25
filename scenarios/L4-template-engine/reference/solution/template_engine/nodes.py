"""AST node types -- data only, no rendering logic (leaf module).

Two families live here:

* **Template nodes** (:class:`TextNode`, :class:`OutputNode`, :class:`IfNode`,
  :class:`ForNode`, :class:`IncludeNode`) -- the compiled template tree the
  renderer walks.
* **Expression nodes** (:class:`Literal`, :class:`Path`, :class:`Compare`,
  :class:`BoolOp`, :class:`Not`) -- the bounded expression grammar (REQUIREMENTS
  Sec.2.1), parsed once at compile time and evaluated by the renderer.

Every node carries the 1-based ``line``/``col`` that originated in the lexer, so
positions never have to be recomputed by re-scanning the source (Sec.2.2).
"""

from __future__ import annotations

from dataclasses import dataclass


# --- expression nodes ------------------------------------------------------


@dataclass(frozen=True)
class Literal:
    """A literal value: string, int, float, ``true``/``false``/``none``."""

    value: object


@dataclass(frozen=True)
class Path:
    """A name followed by zero or more attribute/item accessors.

    ``steps`` is a tuple of ``("attr", name)`` or ``("item", key)`` where a key
    is an ``int`` (sequence index / literal int) or ``str`` (mapping key).
    """

    name: str
    steps: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class Compare:
    """A single comparison ``left <op> right`` (op in == != < <= > >=)."""

    left: object
    op: str
    right: object


@dataclass(frozen=True)
class BoolOp:
    """A short-circuiting ``and``/``or`` chain over two-or-more operands."""

    op: str  # "and" | "or"
    values: tuple[object, ...]


@dataclass(frozen=True)
class Not:
    """Logical negation of an operand."""

    operand: object


# --- template nodes --------------------------------------------------------


@dataclass(frozen=True)
class TextNode:
    """Literal template text, emitted verbatim and never escaped."""

    text: str
    line: int
    col: int


@dataclass(frozen=True)
class OutputNode:
    """An interpolation ``{{ expr | filter... }}``."""

    expr: object
    filters: tuple[tuple[str, tuple[object, ...]], ...]
    line: int
    col: int


@dataclass(frozen=True)
class IfNode:
    """An ``if`` / ``elif`` / ``else`` chain.

    ``branches`` is a list of ``(condition_expr, body)`` pairs -- the ``if`` and
    each ``elif`` arm; ``else_body`` is the optional ``else`` body.
    """

    branches: list[tuple[object, list[object]]]
    else_body: list[object] | None
    line: int
    col: int


@dataclass(frozen=True)
class ForNode:
    """A ``for var in expr`` loop whose body renders in a child scope."""

    var: str
    expr: object
    body: list[object]
    line: int
    col: int


@dataclass(frozen=True)
class IncludeNode:
    """An ``{% include "name" %}`` partial, resolved via the environment."""

    name: str
    line: int
    col: int


# Convenience alias for the compiled template body.
Body = list[object]

__all__ = [
    "Body",
    "BoolOp",
    "Compare",
    "ForNode",
    "IfNode",
    "IncludeNode",
    "Literal",
    "Not",
    "OutputNode",
    "Path",
    "TextNode",
]
