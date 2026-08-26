"""Environment: composition root for the template engine.

Owns the loader, filter registry, autoescape/strictness defaults, and the
compiled-template cache.

Dependency order: imports :mod:`parser`, :mod:`renderer`, and :mod:`filters`.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .errors import TemplateRuntimeError
from .filters import BUILTIN_FILTERS
from .parser import parse
from .renderer import render_ast


class Template:
    """A compiled template that can be rendered many times.

    Tokenisation and parsing happen at construction time.  ``render()``
    only walks the already-built AST.

    Ambiguity resolutions
    ---------------------
    A-1: Lenient undefined → empty string on interpolation, falsy in
         conditions, empty iteration in loops.
    A-2: Strict verbatim whitespace preservation.
    A-3: ``autoescape`` default is ``False``.

    Args:
        source: The raw template source string.
        autoescape: HTML-escape interpolated values when ``True``
            (default: ``False``, pinned).
        strict_undefined: Raise :class:`TemplateRuntimeError` on undefined
            names when ``True`` (default: ``False``).
        environment: The owning :class:`Environment`, or ``None``.

    Raises:
        TemplateSyntaxError: If *source* contains a syntax error.
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
        self._strict = strict_undefined
        self._env = environment
        # Parse at construction time (FR-8)
        self._ast = parse(source)

    def render(self, context: Mapping[str, Any] | None = None) -> str:
        """Render the template with *context*.

        Args:
            context: Variable bindings.  ``None`` is equivalent to ``{}``.

        Returns:
            The rendered string.

        Raises:
            TemplateRuntimeError: On any runtime failure.
        """
        if context is None:
            ctx: dict[str, Any] = {}
        else:
            ctx = dict(context)  # shallow copy — do not mutate caller's mapping

        return render_ast(
            self._ast,
            ctx,
            self._env,
            self._autoescape,
            self._strict,
            [],
        )


class Environment:
    """Composition root: loader + filter registry + defaults + template cache.

    Ambiguity resolution A-3: ``autoescape`` defaults to ``False``.

    Args:
        loader: A ``Mapping[str, str]`` of name → source, or a callable
            ``(name) -> source``.  ``None`` means no loader.
        filters: Additional filters to register on top of the built-ins.
        autoescape: HTML-escape interpolated values (default: ``False``,
            choice A-3a).
        strict_undefined: Raise on undefined names (default: ``False``).
    """

    def __init__(
        self,
        loader: Mapping[str, str] | Callable[[str], str] | None = None,
        filters: Mapping[str, Callable[..., Any]] | None = None,
        autoescape: bool = False,
        strict_undefined: bool = False,
    ) -> None:
        self.loader = loader
        self._autoescape = autoescape
        self._strict = strict_undefined
        # Build filter registry: built-ins plus any user-supplied filters
        self._filters: dict[str, Any] = dict(BUILTIN_FILTERS)
        if filters:
            self._filters.update(filters)
        self._cache: dict[str, Template] = {}

    def add_filter(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a filter function under *name*.

        A user filter may shadow a built-in.

        Args:
            name: The filter name used in templates.
            fn: The callable to invoke.
        """
        self._filters[name] = fn

    def from_string(self, source: str) -> Template:
        """Compile *source* and return a :class:`Template` bound to this env.

        Args:
            source: The raw template source string.

        Returns:
            A compiled :class:`Template` inheriting this environment's
            settings.

        Raises:
            TemplateSyntaxError: If *source* contains a syntax error.
        """
        return Template(
            source,
            autoescape=self._autoescape,
            strict_undefined=self._strict,
            environment=self,
        )

    def get_template(self, name: str) -> Template:
        """Return a compiled :class:`Template` for *name*, cached per env.

        Each name is compiled at most once per environment instance.

        Args:
            name: The template name to look up via the loader.

        Returns:
            A compiled :class:`Template`.

        Raises:
            TemplateRuntimeError: If the loader is ``None`` or the name is
                not found.
            TemplateSyntaxError: If the loaded source contains a syntax error.
        """
        if name in self._cache:
            return self._cache[name]

        source = self._load(name)
        tmpl = Template(
            source,
            autoescape=self._autoescape,
            strict_undefined=self._strict,
            environment=self,
        )
        self._cache[name] = tmpl
        return tmpl

    def render(self, name: str, context: Mapping[str, Any] | None = None) -> str:
        """Compile (or retrieve from cache) and render the named template.

        Args:
            name: The template name.
            context: Variable bindings.

        Returns:
            The rendered string.

        Raises:
            TemplateRuntimeError: On loader or runtime failure.
            TemplateSyntaxError: On syntax error in the template source.
        """
        return self.get_template(name).render(context)

    def _load(self, name: str) -> str:
        """Load template source by name using the configured loader.

        Args:
            name: The template name.

        Returns:
            The template source string.

        Raises:
            TemplateRuntimeError: If no loader is configured or name not found.
        """
        if self.loader is None:
            raise TemplateRuntimeError(
                "no loader configured; cannot resolve template name"
            )
        try:
            if callable(self.loader) and not isinstance(self.loader, dict):
                return self.loader(name)
            return self.loader[name]  # type: ignore[index]
        except (KeyError, Exception) as exc:
            raise TemplateRuntimeError(
                f"template {name!r} not found"
            ) from exc
