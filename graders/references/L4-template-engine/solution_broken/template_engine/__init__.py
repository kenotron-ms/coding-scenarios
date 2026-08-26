"""L4 broken mutant -- deliberately WRONG. Proves the grader discriminates.

An "interpolation-only" engine: it substitutes ``{{ name }}`` by a naive regex
and emits ``{% ... %}`` block tags as literal text. It has **no** parser/AST, so
conditionals, loops, includes, filters, autoescape, strict-undefined, and
position-accurate ``TemplateSyntaxError`` all do the wrong thing. It must FAIL the
acceptance gate (``acceptance_pass < 0.95``) and score 0 / Failed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

_VAR = re.compile(r"{{\s*(.*?)\s*}}")


class TemplateError(Exception):
    """Base error (present only so imports succeed)."""


class TemplateSyntaxError(TemplateError):
    """Never actually raised by this mutant -- malformed templates render as text."""

    def __init__(self, msg: str, line: int, col: int) -> None:
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.col = col


class TemplateRuntimeError(TemplateError):
    """Never actually raised by this mutant."""


class Template:
    def __init__(
        self,
        source: str,
        *,
        autoescape: bool = False,
        strict_undefined: bool = False,
        environment: Environment | None = None,
    ) -> None:
        self.source = source
        self.autoescape = autoescape
        self.strict_undefined = strict_undefined
        self._environment = environment

    def render(self, context: Mapping[str, object] | None = None) -> str:
        ctx = context or {}

        def sub(match: re.Match[str]) -> str:
            key = match.group(1).split("|")[0].strip()
            return str(ctx.get(key, ""))

        return _VAR.sub(sub, self.source)


class Environment:
    def __init__(
        self,
        loader: object | None = None,
        filters: Mapping[str, Callable[..., object]] | None = None,
        autoescape: bool = False,
        strict_undefined: bool = False,
    ) -> None:
        self._loader = loader
        self.autoescape = autoescape
        self.strict_undefined = strict_undefined

    def add_filter(self, name: str, fn: Callable[..., object]) -> None:
        pass

    def from_string(self, source: str) -> Template:
        return Template(source, environment=self)

    def get_template(self, name: str) -> Template:
        loader = self._loader
        if isinstance(loader, Mapping):
            source = loader.get(name, "")
        elif callable(loader):
            source = loader(name)
        else:
            source = ""
        return Template(str(source), environment=self)

    def render(self, name: str, context: Mapping[str, object] | None = None) -> str:
        return self.get_template(name).render(context)


__all__ = [
    "Environment",
    "Template",
    "TemplateError",
    "TemplateRuntimeError",
    "TemplateSyntaxError",
]
