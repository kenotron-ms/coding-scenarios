"""Walk a compiled AST + a context and produce the output string.

The renderer consumes the AST only (REQUIREMENTS Sec.2.2): it never sees raw
source and never re-invokes the lexer or parser. It evaluates the bounded
expression grammar, enforces the sandbox (no ``_``-prefixed access), applies the
undefined policy (strict raises, lenient yields :data:`UNDEFINED`), and wraps
every internal failure into :class:`TemplateRuntimeError` so no foreign
exception escapes the public API (NFR-2, NFR-3).
"""

from __future__ import annotations

import html
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .errors import TemplateError, TemplateRuntimeError
from .nodes import (
    BoolOp,
    Compare,
    ForNode,
    IfNode,
    IncludeNode,
    Literal,
    Not,
    OutputNode,
    Path,
    TextNode,
)
from .runtime import UNDEFINED

_COMPARATORS: dict[str, Callable[[object, object], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,  # type: ignore[operator]
    "<=": lambda a, b: a <= b,  # type: ignore[operator]
    ">": lambda a, b: a > b,  # type: ignore[operator]
    ">=": lambda a, b: a >= b,  # type: ignore[operator]
}


@dataclass
class RenderConfig:
    """Everything the renderer needs from the environment, passed by value.

    ``compile_partial`` maps an include name to its compiled body (or raises
    :class:`TemplateRuntimeError`); ``None`` means no loader is configured.
    """

    filters: dict[str, Callable[..., object]]
    autoescape: bool
    strict_undefined: bool
    compile_partial: Callable[[str], list[object]] | None


class _Scope:
    """A base mapping plus a stack of overlay frames for loop bindings."""

    def __init__(self, base: Mapping[str, object]) -> None:
        self._base = base
        self._frames: list[dict[str, object]] = []

    def push(self, frame: dict[str, object]) -> None:
        self._frames.append(frame)

    def pop(self) -> None:
        self._frames.pop()

    def lookup(self, name: str) -> tuple[bool, object]:
        for frame in reversed(self._frames):
            if name in frame:
                return True, frame[name]
        if name in self._base:
            return True, self._base[name]
        return False, None


class Renderer:
    """Renders a compiled template body against a context."""

    def __init__(self, config: RenderConfig) -> None:
        self._config = config

    def render(self, body: list[object], context: Mapping[str, object] | None) -> str:
        scope = _Scope(context if context is not None else {})
        out: list[str] = []
        self._render_nodes(body, scope, out, ())
        return "".join(out)

    # -- node dispatch ----------------------------------------------------

    def _render_nodes(
        self,
        nodes: list[object],
        scope: _Scope,
        out: list[str],
        includes: tuple[str, ...],
    ) -> None:
        for node in nodes:
            if isinstance(node, TextNode):
                out.append(node.text)
            elif isinstance(node, OutputNode):
                out.append(self._render_output(node, scope))
            elif isinstance(node, IfNode):
                self._render_if(node, scope, out, includes)
            elif isinstance(node, ForNode):
                self._render_for(node, scope, out, includes)
            elif isinstance(node, IncludeNode):
                self._render_include(node, scope, out, includes)

    def _render_output(self, node: OutputNode, scope: _Scope) -> str:
        value = self._eval(node.expr, scope)
        for name, args in node.filters:
            fn = self._config.filters.get(name)
            if fn is None:
                raise TemplateRuntimeError(f"unknown filter {name!r}")
            try:
                value = fn(value, *args)
            except TemplateError:
                raise
            except Exception as exc:  # wrap per NFR-2
                raise TemplateRuntimeError(f"filter {name!r} failed: {exc}") from exc
        text = "" if value is UNDEFINED else str(value)
        if self._config.autoescape:
            text = html.escape(text, quote=True)
        return text

    def _render_if(
        self, node: IfNode, scope: _Scope, out: list[str], includes: tuple[str, ...]
    ) -> None:
        for condition, body in node.branches:
            if bool(self._eval(condition, scope)):
                self._render_nodes(body, scope, out, includes)
                return
        if node.else_body is not None:
            self._render_nodes(node.else_body, scope, out, includes)

    def _render_for(
        self, node: ForNode, scope: _Scope, out: list[str], includes: tuple[str, ...]
    ) -> None:
        iterable = self._eval(node.expr, scope)
        if iterable is UNDEFINED:
            items: list[object] = []
        else:
            try:
                items = list(iterable)  # type: ignore[arg-type]
            except TypeError as exc:
                raise TemplateRuntimeError(
                    f"loop target for {node.var!r} is not iterable"
                ) from exc
        total = len(items)
        for index, item in enumerate(items):
            frame: dict[str, object] = {
                node.var: item,
                "loop": {
                    "index": index + 1,
                    "index0": index,
                    "first": index == 0,
                    "last": index == total - 1,
                    "length": total,
                },
            }
            scope.push(frame)
            try:
                self._render_nodes(node.body, scope, out, includes)
            finally:
                scope.pop()

    def _render_include(
        self,
        node: IncludeNode,
        scope: _Scope,
        out: list[str],
        includes: tuple[str, ...],
    ) -> None:
        if self._config.compile_partial is None:
            raise TemplateRuntimeError(
                f"cannot include {node.name!r}: no loader is configured"
            )
        if node.name in includes:
            chain = " -> ".join([*includes, node.name])
            raise TemplateRuntimeError(f"include cycle detected: {chain}")
        body = self._config.compile_partial(node.name)
        self._render_nodes(body, scope, out, (*includes, node.name))

    # -- expression evaluation -------------------------------------------

    def _eval(self, expr: object, scope: _Scope) -> object:
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Path):
            return self._resolve(expr, scope)
        if isinstance(expr, Not):
            return not bool(self._eval(expr.operand, scope))
        if isinstance(expr, BoolOp):
            return self._eval_boolop(expr, scope)
        if isinstance(expr, Compare):
            return self._eval_compare(expr, scope)
        return expr  # pragma: no cover - defensive; parser never emits this

    def _eval_boolop(self, expr: BoolOp, scope: _Scope) -> object:
        value: object = UNDEFINED
        for operand in expr.values:
            value = self._eval(operand, scope)
            truthy = bool(value)
            if expr.op == "and" and not truthy:
                return value
            if expr.op == "or" and truthy:
                return value
        return value

    def _eval_compare(self, expr: Compare, scope: _Scope) -> bool:
        left = self._eval(expr.left, scope)
        right = self._eval(expr.right, scope)
        try:
            return _COMPARATORS[expr.op](left, right)
        except TypeError as exc:
            raise TemplateRuntimeError(
                f"cannot compare {left!r} {expr.op} {right!r}"
            ) from exc

    def _resolve(self, path: Path, scope: _Scope) -> object:
        found, value = scope.lookup(path.name)
        if not found:
            if self._config.strict_undefined:
                raise TemplateRuntimeError(f"undefined variable {path.name!r}")
            return UNDEFINED
        for kind, key in path.steps:
            if value is UNDEFINED:
                return UNDEFINED
            value = self._access(value, kind, key, path)
        return value

    def _access(self, value: object, kind: str, key: object, path: Path) -> object:
        if kind == "attr":
            assert isinstance(key, str)
            if key.startswith("_"):
                raise TemplateRuntimeError(
                    f"access to attribute {key!r} is not allowed"
                )
            if isinstance(value, Mapping) and key in value:
                return value[key]
            if hasattr(value, key):
                return getattr(value, key)
            return self._missing(path, key)
        if isinstance(value, Mapping):
            if key in value:
                return value[key]
            return self._missing(path, key)
        try:
            return value[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            if self._config.strict_undefined:
                raise TemplateRuntimeError(
                    f"cannot resolve {key!r} on {path.name!r}"
                ) from exc
            return UNDEFINED

    def _missing(self, path: Path, key: object) -> object:
        if self._config.strict_undefined:
            raise TemplateRuntimeError(
                f"undefined path: {path.name!r} has no {key!r}"
            )
        return UNDEFINED
