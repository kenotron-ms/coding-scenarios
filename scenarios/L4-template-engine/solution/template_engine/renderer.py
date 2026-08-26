"""Renderer: walks an AST and produces a string.

Imports only :mod:`nodes`, :mod:`errors`, and :mod:`filters`.
Never imports :mod:`lexer` or :mod:`parser`.

Ambiguity resolutions applied here
-----------------------------------
A-1 (undefined in lenient mode): missing name → empty string on interpolation,
    falsy in conditions, empty iteration in loops.
A-2 (whitespace): strict verbatim preservation — all text emitted exactly as
    written.
A-3 (autoescape default): ``False`` — consistent with ``Template``'s pinned
    default.

Security
--------
- Path components beginning with ``_`` are refused (raises
  :class:`TemplateRuntimeError`).
- ``eval``, ``exec``, ``compile``, and ``__import__`` are never called.
- All ``KeyError``, ``AttributeError``, ``IndexError``, ``TypeError``, and
  ``RecursionError`` are wrapped in :class:`TemplateRuntimeError`.
"""

from __future__ import annotations

import html
from typing import Any

from .errors import TemplateRuntimeError
from .filters import BUILTIN_FILTERS, UNDEFINED
from .nodes import (
    BinaryExpr,
    ForNode,
    IfNode,
    IncludeNode,
    LiteralExpr,
    NotExpr,
    OutputNode,
    PathExpr,
    TextNode,
)


class _LoopContext:
    """Exposes loop metadata inside a ``{% for %}`` body."""

    __slots__ = ("index", "index0", "first", "last", "length")

    def __init__(self, index0: int, length: int) -> None:
        self.index0 = index0
        self.index = index0 + 1
        self.first = index0 == 0
        self.last = index0 == length - 1
        self.length = length


def _resolve_path(
    root: str,
    parts: list[str | int],
    context: dict[str, Any],
    strict: bool,
) -> Any:
    """Resolve a path expression against *context*.

    Resolution order for dotted access: mapping key first, then attribute.
    Integer parts always use item access.

    Args:
        root: The root variable name.
        parts: Subsequent access steps (str = key/attr, int = index).
        context: The current render context.
        strict: If ``True``, raise on undefined; otherwise return UNDEFINED.

    Returns:
        The resolved value or :data:`~filters.UNDEFINED` in lenient mode.

    Raises:
        TemplateRuntimeError: For sandboxed access or strict-undefined.
    """
    if root.startswith("_"):
        raise TemplateRuntimeError(
            f"access to private name {root!r} is not allowed"
        )

    if root not in context:
        if strict:
            raise TemplateRuntimeError(f"undefined variable {root!r}")
        return UNDEFINED

    value = context[root]

    for step in parts:
        if isinstance(step, str):
            if step.startswith("_"):
                raise TemplateRuntimeError(
                    f"access to private attribute {step!r} is not allowed"
                )
            # Mapping key first, then attribute
            try:
                if isinstance(value, dict):
                    if step in value:
                        value = value[step]
                    else:
                        # Try attribute
                        try:
                            value = getattr(value, step)
                        except AttributeError:
                            if strict:
                                raise TemplateRuntimeError(
                                    f"undefined key/attribute {step!r}"
                                )
                            return UNDEFINED
                else:
                    # Non-dict: try mapping protocol first, then attribute
                    try:
                        value = value[step]
                    except (KeyError, TypeError, IndexError):
                        try:
                            value = getattr(value, step)
                        except AttributeError:
                            if strict:
                                raise TemplateRuntimeError(
                                    f"undefined attribute {step!r}"
                                )
                            return UNDEFINED
            except TemplateRuntimeError:
                raise
            except Exception as exc:
                raise TemplateRuntimeError(str(exc)) from exc
        else:
            # Integer index
            try:
                value = value[step]
            except (KeyError, IndexError, TypeError) as exc:
                if strict:
                    raise TemplateRuntimeError(
                        f"index {step!r} not found"
                    ) from exc
                return UNDEFINED

    return value


def _eval_expr(
    expr: Any,
    context: dict[str, Any],
    strict: bool,
) -> Any:
    """Evaluate an expression node against *context*.

    Args:
        expr: An AST expression node.
        context: The current render context.
        strict: Strict-undefined mode flag.

    Returns:
        The evaluated value.

    Raises:
        TemplateRuntimeError: On any evaluation failure.
    """
    if isinstance(expr, LiteralExpr):
        return expr.value

    if isinstance(expr, PathExpr):
        return _resolve_path(expr.root, expr.parts, context, strict)

    if isinstance(expr, NotExpr):
        val = _eval_expr(expr.operand, context, strict)
        if val is UNDEFINED:
            return True  # undefined is falsy, so not undefined is truthy
        return not val

    if isinstance(expr, BinaryExpr):
        if expr.op == "and":
            left = _eval_expr(expr.left, context, strict)
            if left is UNDEFINED:
                left = ""
            if not left:
                return left
            right = _eval_expr(expr.right, context, strict)
            if right is UNDEFINED:
                return ""
            return right
        if expr.op == "or":
            left = _eval_expr(expr.left, context, strict)
            if left is UNDEFINED:
                left = ""
            if left:
                return left
            right = _eval_expr(expr.right, context, strict)
            if right is UNDEFINED:
                return ""
            return right

        left = _eval_expr(expr.left, context, strict)
        right = _eval_expr(expr.right, context, strict)
        if left is UNDEFINED:
            left = ""
        if right is UNDEFINED:
            right = ""

        try:
            if expr.op == "==":
                return left == right
            if expr.op == "!=":
                return left != right
            if expr.op == "<":
                return left < right
            if expr.op == "<=":
                return left <= right
            if expr.op == ">":
                return left > right
            if expr.op == ">=":
                return left >= right
        except TypeError as exc:
            raise TemplateRuntimeError(
                f"comparison error: {exc}"
            ) from exc

    raise TemplateRuntimeError(f"unknown expression node: {type(expr).__name__}")


def render_ast(
    nodes: list[Any],
    context: dict[str, Any],
    env: Any,  # Environment | None
    autoescape: bool,
    strict: bool,
    render_stack: list[str],
) -> str:
    """Render a list of AST nodes to a string.

    Args:
        nodes: The AST node list to render.
        context: The current render context (a shallow copy for mutation safety).
        env: The :class:`~environment.Environment` instance, or ``None``.
        autoescape: Whether to HTML-escape interpolated values.
        strict: Strict-undefined mode.
        render_stack: Stack of template names currently being rendered (for
            cycle detection in includes).

    Returns:
        The rendered string.

    Raises:
        TemplateRuntimeError: On any runtime failure.
    """
    parts: list[str] = []

    for node in nodes:
        if isinstance(node, TextNode):
            parts.append(node.text)

        elif isinstance(node, OutputNode):
            try:
                value = _eval_expr(node.expr, context, strict)
            except TemplateRuntimeError:
                raise
            except Exception as exc:
                raise TemplateRuntimeError(str(exc)) from exc

            # Apply filters
            filter_registry = _get_filter_registry(env)
            for fname, fargs in node.filters:
                fn = filter_registry.get(fname)
                if fn is None:
                    raise TemplateRuntimeError(
                        f"unknown filter {fname!r}"
                    )
                try:
                    value = fn(value, *fargs)
                except TemplateRuntimeError:
                    raise
                except Exception as exc:
                    raise TemplateRuntimeError(
                        f"filter {fname!r} raised: {exc}"
                    ) from exc

            # Undefined in lenient mode: emit empty string
            if value is UNDEFINED:
                parts.append("")
                continue

            str_value = str(value)
            if autoescape:
                str_value = html.escape(str_value, quote=True)
            parts.append(str_value)

        elif isinstance(node, IfNode):
            rendered = False
            for cond_expr, body in node.branches:
                try:
                    cond = _eval_expr(cond_expr, context, strict)
                except TemplateRuntimeError:
                    raise
                except Exception as exc:
                    raise TemplateRuntimeError(str(exc)) from exc
                if cond is UNDEFINED:
                    cond = ""  # lenient: undefined is falsy
                if cond:
                    parts.append(
                        render_ast(body, context, env, autoescape, strict, render_stack)
                    )
                    rendered = True
                    break
            if not rendered and node.else_body:
                parts.append(
                    render_ast(node.else_body, context, env, autoescape, strict, render_stack)
                )

        elif isinstance(node, ForNode):
            try:
                iterable = _eval_expr(node.expr, context, strict)
            except TemplateRuntimeError:
                raise
            except Exception as exc:
                raise TemplateRuntimeError(str(exc)) from exc

            if iterable is UNDEFINED:
                iterable = []  # lenient: undefined iterates empty

            try:
                items = list(iterable)
            except TypeError as exc:
                raise TemplateRuntimeError(
                    f"cannot iterate over {type(iterable).__name__!r}"
                ) from exc

            length = len(items)
            # Save outer bindings
            outer_var = context.get(node.var, UNDEFINED)
            outer_loop = context.get("loop", UNDEFINED)

            for idx, item in enumerate(items):
                child_ctx = context.copy()
                child_ctx[node.var] = item
                child_ctx["loop"] = _LoopContext(idx, length)
                parts.append(
                    render_ast(node.body, child_ctx, env, autoescape, strict, render_stack)
                )

            # Restore outer bindings
            if outer_var is UNDEFINED:
                context.pop(node.var, None)
            else:
                context[node.var] = outer_var
            if outer_loop is UNDEFINED:
                context.pop("loop", None)
            else:
                context["loop"] = outer_loop

        elif isinstance(node, IncludeNode):
            if env is None:
                raise TemplateRuntimeError(
                    "no environment configured; cannot resolve include"
                )
            loader = getattr(env, "loader", None)
            if loader is None:
                raise TemplateRuntimeError(
                    "no loader configured; cannot resolve include"
                )

            name = node.name
            if name in render_stack:
                cycle = " -> ".join(render_stack + [name])
                raise TemplateRuntimeError(
                    f"include cycle detected: {cycle}"
                )

            try:
                tmpl = env.get_template(name)
            except TemplateRuntimeError:
                raise
            except Exception as exc:
                raise TemplateRuntimeError(
                    f"could not load template {name!r}: {exc}"
                ) from exc

            render_stack.append(name)
            try:
                result = render_ast(
                    tmpl._ast,
                    context.copy(),
                    env,
                    tmpl._autoescape,
                    tmpl._strict,
                    render_stack,
                )
            finally:
                render_stack.pop()
            parts.append(result)

        else:
            raise TemplateRuntimeError(
                f"unknown AST node type: {type(node).__name__}"
            )

    return "".join(parts)


def _get_filter_registry(env: Any) -> dict[str, Any]:
    """Return the active filter registry (env's registry or built-ins)."""
    if env is not None and hasattr(env, "_filters"):
        return env._filters
    return BUILTIN_FILTERS
