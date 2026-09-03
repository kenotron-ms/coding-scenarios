"""template_engine — a small, dependency-free text/HTML template engine.

Public API
----------
Template
    Compile a template from source and render it with a context dict.
Environment
    Manage a collection of templates with shared configuration (loader,
    filters, autoescape, undefined handling).
TemplateError
    Base exception for all template errors.
TemplateSyntaxError
    Raised at construction time for malformed template syntax. Carries
    accurate 1-based ``line`` and ``col`` pointing at the offending construct.
TemplateRuntimeError
    Raised during rendering. Wraps all lower-level exceptions (KeyError,
    AttributeError, RecursionError, …) so nothing else crosses the public API.

Ambiguity choices (documented here and in relevant docstrings)
--------------------------------------------------------------
1. **Lenient-undefined value** (SPEC §Ambiguities #1):
   A missing name in lenient mode yields an *Undefined* sentinel.
   - Interpolation → empty string "".
   - Conditions → falsy (no branch taken).
   - Loops → treated as empty iterable (zero iterations).
   - ``default`` filter → intercepts it and returns the fallback.
   - Strict mode → raises TemplateRuntimeError on first access.
   This behaviour is uniform across all three contexts.

2. **Whitespace control** (SPEC §Ambiguities #2):
   Strict verbatim preservation (option a). Block tags do NOT consume
   surrounding whitespace or newlines. A template with no block tags is
   byte-exact. Trim markers ({%- … -%}) are not supported.

3. **Environment autoescape default** (SPEC §Ambiguities #3):
   ``False`` (option a, matching ``Template``'s pinned default). An explicit
   setting always wins over an inherited one; ``Template(source)`` with no
   argument does not escape.
"""

from __future__ import annotations

from .exceptions import TemplateError, TemplateSyntaxError, TemplateRuntimeError
from .lexer import LexerError, tokenize
from .parser import ParseError, Parser
from .renderer import Renderer
from .ast_nodes import TemplateNode

__all__ = [
    "Template",
    "Environment",
    "TemplateError",
    "TemplateSyntaxError",
    "TemplateRuntimeError",
]


class Template:
    """A compiled template.

    Parameters
    ----------
    source:
        The template source string.
    autoescape:
        When True, every interpolated value is HTML-escaped before output.
        Literal template text is never escaped.
    strict_undefined:
        When True, referencing an undefined variable raises
        TemplateRuntimeError. When False (default), undefined variables
        render as empty string / falsy / empty iterable (see module docstring,
        Ambiguity #1).
    environment:
        The Environment this template belongs to. Provides the loader for
        ``{% include %}`` and any registered filters.

    Compile once, render many
    -------------------------
    Tokenization and parsing happen at construction time. ``render()`` only
    walks the built AST — no re-parsing — and leaks no state between calls.
    """

    def __init__(
        self,
        source: str,
        *,
        autoescape: bool = False,
        strict_undefined: bool = False,
        environment: "Environment | None" = None,
    ) -> None:
        self._source = source
        self._autoescape = autoescape
        self._strict_undefined = strict_undefined
        self._environment = environment

        # Compile at construction time
        self._ast: TemplateNode = self._compile(source)

        # Build renderer (shared config, no state)
        filters = environment._filters if environment is not None else None
        self._renderer = Renderer(
            autoescape=autoescape,
            strict_undefined=strict_undefined,
            filters=filters,
            environment=environment,
        )

    def _compile(self, source: str) -> TemplateNode:
        """Tokenize and parse *source*, raising TemplateSyntaxError on error."""
        try:
            tokens = tokenize(source)
        except LexerError as exc:
            raise TemplateSyntaxError(str(exc), exc.line, exc.col) from exc

        try:
            parser = Parser(tokens)
            return parser.parse()
        except ParseError as exc:
            raise TemplateSyntaxError(str(exc), exc.line, exc.col) from exc

    def render(self, context: dict | None = None) -> str:
        """Render the template with the given *context* and return a string.

        Leaks no state between calls. All exceptions are wrapped as
        TemplateRuntimeError.
        """
        ctx: dict = dict(context) if context else {}
        return self._renderer.render(self._ast, ctx)

    def _render_with_context(self, ctx: dict) -> str:
        """Render sharing the caller's context dict (used by include)."""
        return self._renderer.render(self._ast, ctx)


class Environment:
    """A shared configuration container for a set of templates.

    Parameters
    ----------
    loader:
        A dict mapping template names to source strings, or any object with a
        ``get_source(name: str) -> str`` method. The engine performs no I/O of
        its own; the loader is consumer-supplied.
    filters:
        A dict of extra filter functions to register. These may shadow
        built-ins. Keys are filter names; values are callables.
    autoescape:
        Default autoescape setting for templates created via this environment.
        (Ambiguity #3: defaults to False.)
    strict_undefined:
        Default strict_undefined setting for templates created via this
        environment.

    Template caching
    ----------------
    ``get_template(name)`` compiles each template once per name and caches the
    result. Subsequent calls return the cached Template without re-parsing.
    """

    def __init__(
        self,
        loader: dict[str, str] | object | None = None,
        filters: dict[str, object] | None = None,
        autoescape: bool = False,
        strict_undefined: bool = False,
    ) -> None:
        self._loader = loader
        self._filters: dict[str, object] = dict(filters) if filters else {}
        self._autoescape = autoescape
        self._strict_undefined = strict_undefined
        self._cache: dict[str, Template] = {}

    def add_filter(self, name: str, fn: object) -> None:
        """Register a filter function under *name*.

        A user filter may shadow a built-in. Unknown or raising filters
        produce TemplateRuntimeError at render time.
        """
        self._filters[name] = fn

    def from_string(self, source: str) -> Template:
        """Compile and return a Template from a source string.

        The template inherits this environment's settings.
        """
        return Template(
            source,
            autoescape=self._autoescape,
            strict_undefined=self._strict_undefined,
            environment=self,
        )

    def get_template(self, name: str) -> Template:
        """Return the compiled Template for *name*, loading and caching it.

        Raises TemplateRuntimeError if the loader is absent or the template
        cannot be found.
        """
        if name in self._cache:
            return self._cache[name]

        source = self._load_source(name)
        tmpl = Template(
            source,
            autoescape=self._autoescape,
            strict_undefined=self._strict_undefined,
            environment=self,
        )
        self._cache[name] = tmpl
        return tmpl

    def render(self, name: str, context: dict | None = None) -> str:
        """Load, compile (once), and render the named template."""
        return self.get_template(name).render(context)

    def _load_source(self, name: str) -> str:
        """Load template source for *name* from the loader."""
        if self._loader is None:
            raise TemplateRuntimeError(
                f"No loader configured; cannot load template {name!r}"
            )
        if isinstance(self._loader, dict):
            if name not in self._loader:
                raise TemplateRuntimeError(
                    f"Template {name!r} not found in loader"
                )
            return self._loader[name]
        # Duck-typed loader object
        try:
            return self._loader.get_source(name)  # type: ignore[union-attr]
        except Exception as exc:
            raise TemplateRuntimeError(
                f"Loader error for {name!r}: {exc}"
            ) from exc
