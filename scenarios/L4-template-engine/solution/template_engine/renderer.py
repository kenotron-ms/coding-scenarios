"""Renderer for the template engine.

Walks a compiled AST and produces a string. Never re-invokes the lexer or
parser. All exceptions that cross the public API are TemplateRuntimeError.

Ambiguity resolution #1 — lenient-undefined value:
    A missing name in lenient mode yields an *Undefined* sentinel object.
    - Interpolation: renders as empty string "".
    - Conditions: falsy (Undefined is falsy).
    - Loops: treated as empty iterable (no iterations).
    - ``default`` filter: intercepts it (returns the fallback).
    - Strict mode: raises TemplateRuntimeError on first access.
    This is uniform across all three contexts.

Security: path resolution refuses _-prefixed and dunder attribute/key access,
raising TemplateRuntimeError. eval/exec/compile/__import__ are not used.
"""

from __future__ import annotations

import html
from typing import Any, Iterator

from .ast_nodes import (
    BinOpNode, FilterNode, ForNode, IfNode, IncludeNode,
    InterpolationNode, LiteralNode, NameNode, PathNode, TemplateNode,
    TextNode, UnaryOpNode,
)
from .exceptions import TemplateRuntimeError


# ---------------------------------------------------------------------------
# Undefined sentinel
# ---------------------------------------------------------------------------

class _Undefined:
    """Sentinel for a missing variable in lenient mode."""

    def __bool__(self) -> bool:
        return False

    def __iter__(self) -> Iterator[Any]:
        return iter([])

    def __str__(self) -> str:
        return ""

    def __repr__(self) -> str:
        return "Undefined"


UNDEFINED = _Undefined()


# ---------------------------------------------------------------------------
# Built-in filters
# ---------------------------------------------------------------------------

def _filter_upper(value: Any) -> str:
    return str(value).upper()


def _filter_lower(value: Any) -> str:
    return str(value).lower()


def _filter_length(value: Any) -> int:
    try:
        return len(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TemplateRuntimeError(f"Filter 'length' error: {exc}") from exc


def _filter_default(value: Any, fallback: Any = "") -> Any:
    """Return *fallback* when value is Undefined or None; pass through otherwise."""
    if isinstance(value, _Undefined) or value is None:
        return fallback
    return value


BUILTIN_FILTERS: dict[str, Any] = {
    "upper": _filter_upper,
    "lower": _filter_lower,
    "length": _filter_length,
    "default": _filter_default,
}


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer:
    """Walks an AST and renders it to a string."""

    def __init__(
        self,
        *,
        autoescape: bool = False,
        strict_undefined: bool = False,
        filters: dict[str, Any] | None = None,
        environment: Any | None = None,  # Environment, typed loosely to avoid cycle
    ) -> None:
        self._autoescape = autoescape
        self._strict_undefined = strict_undefined
        self._filters: dict[str, Any] = dict(BUILTIN_FILTERS)
        if filters:
            self._filters.update(filters)
        self._environment = environment

    def render(self, node: TemplateNode, context: dict[str, Any]) -> str:
        """Render *node* with *context* and return the result string."""
        try:
            parts: list[str] = []
            self._render_body(node.body, context, parts)
            return "".join(parts)
        except TemplateRuntimeError:
            raise
        except RecursionError as exc:
            raise TemplateRuntimeError(f"Recursion error (include cycle?): {exc}") from exc
        except Exception as exc:
            raise TemplateRuntimeError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Body / statement dispatch
    # ------------------------------------------------------------------

    def _render_body(
        self, body: list[Any], ctx: dict[str, Any], out: list[str]
    ) -> None:
        for node in body:
            self._render_node(node, ctx, out)

    def _render_node(self, node: Any, ctx: dict[str, Any], out: list[str]) -> None:
        match node:
            case TextNode():
                out.append(node.text)
            case InterpolationNode():
                self._render_interpolation(node, ctx, out)
            case IfNode():
                self._render_if(node, ctx, out)
            case ForNode():
                self._render_for(node, ctx, out)
            case IncludeNode():
                self._render_include(node, ctx, out)
            case _:
                raise TemplateRuntimeError(
                    f"Unknown AST node type: {type(node).__name__}"
                )

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    def _render_interpolation(
        self, node: InterpolationNode, ctx: dict[str, Any], out: list[str]
    ) -> None:
        value = self._eval_expr(node.expr, ctx)
        text = str(value)
        if self._autoescape:
            text = html.escape(text, quote=True)
        out.append(text)

    # ------------------------------------------------------------------
    # If
    # ------------------------------------------------------------------

    def _render_if(self, node: IfNode, ctx: dict[str, Any], out: list[str]) -> None:
        if self._eval_truthy(node.condition, ctx):
            self._render_body(node.body, ctx, out)
            return
        for elif_cond, elif_body in node.elif_clauses:
            if self._eval_truthy(elif_cond, ctx):
                self._render_body(elif_body, ctx, out)
                return
        if node.else_body:
            self._render_body(node.else_body, ctx, out)

    # ------------------------------------------------------------------
    # For
    # ------------------------------------------------------------------

    def _render_for(self, node: ForNode, ctx: dict[str, Any], out: list[str]) -> None:
        iterable = self._eval_expr(node.iterable, ctx)
        if isinstance(iterable, _Undefined):
            return  # empty iterable in lenient mode

        try:
            items = list(iterable)
        except TypeError as exc:
            raise TemplateRuntimeError(
                f"Cannot iterate over {type(iterable).__name__}: {exc}"
            ) from exc

        length = len(items)
        # Save outer bindings
        outer_loop = ctx.get("loop")
        outer_var = ctx.get(node.var)
        has_outer_var = node.var in ctx

        for idx, item in enumerate(items):
            loop_obj = {
                "index": idx + 1,
                "index0": idx,
                "first": idx == 0,
                "last": idx == length - 1,
                "length": length,
            }
            ctx["loop"] = loop_obj
            ctx[node.var] = item
            self._render_body(node.body, ctx, out)

        # Restore outer bindings
        if outer_loop is None:
            ctx.pop("loop", None)
        else:
            ctx["loop"] = outer_loop

        if not has_outer_var:
            ctx.pop(node.var, None)
        else:
            ctx[node.var] = outer_var  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Include
    # ------------------------------------------------------------------

    def _render_include(
        self, node: IncludeNode, ctx: dict[str, Any], out: list[str]
    ) -> None:
        if self._environment is None:
            raise TemplateRuntimeError(
                "{% include %} requires an Environment with a loader"
            )
        try:
            tmpl = self._environment.get_template(node.template_name)
        except Exception as exc:
            raise TemplateRuntimeError(
                f"Cannot load template {node.template_name!r}: {exc}"
            ) from exc
        # Render with current context (pass a copy to avoid cross-contamination)
        result = tmpl._render_with_context(ctx)
        out.append(result)

    # ------------------------------------------------------------------
    # Expression evaluation
    # ------------------------------------------------------------------

    def _eval_expr(self, node: Any, ctx: dict[str, Any]) -> Any:
        match node:
            case LiteralNode():
                return node.value
            case NameNode():
                return self._lookup_name(node.name, ctx, node.line, node.col)
            case PathNode():
                return self._eval_path(node, ctx)
            case FilterNode():
                return self._eval_filter(node, ctx)
            case BinOpNode():
                return self._eval_binop(node, ctx)
            case UnaryOpNode():
                return self._eval_unary(node, ctx)
            case _:
                raise TemplateRuntimeError(
                    f"Unknown expression node: {type(node).__name__}"
                )

    def _eval_truthy(self, node: Any, ctx: dict[str, Any]) -> bool:
        value = self._eval_expr(node, ctx)
        return bool(value)

    def _lookup_name(
        self, name: str, ctx: dict[str, Any], line: int, col: int
    ) -> Any:
        if name in ctx:
            return ctx[name]
        if self._strict_undefined:
            raise TemplateRuntimeError(
                f"Undefined variable {name!r} (line {line}, col {col})"
            )
        return UNDEFINED

    def _eval_path(self, node: PathNode, ctx: dict[str, Any]) -> Any:
        value = self._lookup_name(node.root.name, ctx, node.line, node.col)
        for step_kind, step_key in node.steps:
            if isinstance(value, _Undefined):
                return value  # propagate undefined
            if step_kind == "attr":
                value = self._resolve_attr(value, step_key, node.line, node.col)
            else:  # index
                idx = self._eval_expr(step_key, ctx)
                value = self._resolve_index(value, idx, node.line, node.col)
        return value

    def _resolve_attr(self, obj: Any, name: str, line: int, col: int) -> Any:
        """Resolve attribute access: mapping key first, then attribute.

        Refuses _-prefixed and dunder names.
        """
        if name.startswith("_"):
            raise TemplateRuntimeError(
                f"Access to private/dunder attribute {name!r} is forbidden "
                f"(line {line}, col {col})"
            )
        # Mapping key first
        try:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        except Exception:
            pass
        # Then attribute
        try:
            return getattr(obj, name)
        except AttributeError:
            pass
        # Not found
        if self._strict_undefined:
            raise TemplateRuntimeError(
                f"Attribute {name!r} not found (line {line}, col {col})"
            )
        return UNDEFINED

    def _resolve_index(self, obj: Any, idx: Any, line: int, col: int) -> Any:
        """Resolve bracket index access."""
        if isinstance(idx, str) and idx.startswith("_"):
            raise TemplateRuntimeError(
                f"Access to private/dunder key {idx!r} is forbidden "
                f"(line {line}, col {col})"
            )
        try:
            return obj[idx]
        except (KeyError, IndexError, TypeError) as exc:
            if self._strict_undefined:
                raise TemplateRuntimeError(
                    f"Index {idx!r} not found: {exc} (line {line}, col {col})"
                ) from exc
            return UNDEFINED

    def _eval_filter(self, node: FilterNode, ctx: dict[str, Any]) -> Any:
        value = self._eval_expr(node.expr, ctx)
        fn = self._filters.get(node.name)
        if fn is None:
            raise TemplateRuntimeError(
                f"Unknown filter {node.name!r}"
            )
        args = [self._eval_expr(a, ctx) for a in node.args]
        try:
            return fn(value, *args)
        except TemplateRuntimeError:
            raise
        except Exception as exc:
            raise TemplateRuntimeError(
                f"Filter {node.name!r} raised an error: {exc}"
            ) from exc

    def _eval_binop(self, node: BinOpNode, ctx: dict[str, Any]) -> Any:
        if node.op == "and":
            left = self._eval_expr(node.left, ctx)
            if not left:
                return left
            return self._eval_expr(node.right, ctx)
        if node.op == "or":
            left = self._eval_expr(node.left, ctx)
            if left:
                return left
            return self._eval_expr(node.right, ctx)

        left = self._eval_expr(node.left, ctx)
        right = self._eval_expr(node.right, ctx)
        try:
            match node.op:
                case "==": return left == right
                case "!=": return left != right
                case "<":  return left < right   # type: ignore[operator]
                case "<=": return left <= right  # type: ignore[operator]
                case ">":  return left > right   # type: ignore[operator]
                case ">=": return left >= right  # type: ignore[operator]
                case _:
                    raise TemplateRuntimeError(f"Unknown operator {node.op!r}")
        except TemplateRuntimeError:
            raise
        except Exception as exc:
            raise TemplateRuntimeError(
                f"Operator {node.op!r} error: {exc}"
            ) from exc

    def _eval_unary(self, node: UnaryOpNode, ctx: dict[str, Any]) -> Any:
        operand = self._eval_expr(node.operand, ctx)
        if node.op == "not":
            return not operand
        raise TemplateRuntimeError(f"Unknown unary operator {node.op!r}")
