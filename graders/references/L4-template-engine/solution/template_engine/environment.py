"""Environment: the composition root (loader + filters + defaults + cache).

An :class:`Environment` owns the partial loader, the filter registry (built-ins
plus user filters), the autoescape/strictness defaults, and the compiled-template
cache. Templates it produces inherit its filters, loader, and defaults
(REQUIREMENTS FR-10). The autoescape default is ``False`` (Sec.1.6 A-3
resolution (a): matching ``Template``'s pinned default).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .errors import TemplateError, TemplateRuntimeError
from .filters import builtin_filters
from .template import Template

Loader = Mapping[str, str] | Callable[[str], str]


class Environment:
    """Loader + filters + defaults + a per-environment compiled-template cache.

    Args:
        loader: a ``{name: source}`` mapping, a ``(name) -> source`` callable, or
            ``None`` (includes then raise :class:`TemplateRuntimeError`).
        filters: extra filters merged over (and able to shadow) the built-ins.
        autoescape: default autoescape for templates this environment creates.
        strict_undefined: default undefined strictness for those templates.
    """

    def __init__(
        self,
        loader: Loader | None = None,
        filters: Mapping[str, Callable[..., object]] | None = None,
        autoescape: bool = False,
        strict_undefined: bool = False,
    ) -> None:
        self._loader = loader
        self._filters: dict[str, Callable[..., object]] = builtin_filters()
        if filters:
            self._filters.update(filters)
        self.autoescape = autoescape
        self.strict_undefined = strict_undefined
        self._cache: dict[str, Template] = {}

    def add_filter(self, name: str, fn: Callable[..., object]) -> None:
        """Register (or override) a filter by name."""
        self._filters[name] = fn

    def filter_map(self) -> dict[str, Callable[..., object]]:
        """Return a copy of the filter registry for a template to render with."""
        return dict(self._filters)

    def from_string(self, source: str) -> Template:
        """Compile ``source`` into a :class:`Template` bound to this environment."""
        return Template(
            source,
            autoescape=self.autoescape,
            strict_undefined=self.strict_undefined,
            environment=self,
        )

    def get_template(self, name: str) -> Template:
        """Return the compiled template for ``name``, compiling it at most once."""
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        template = Template(
            self._resolve_source(name),
            autoescape=self.autoescape,
            strict_undefined=self.strict_undefined,
            environment=self,
        )
        self._cache[name] = template
        return template

    def render(self, name: str, context: Mapping[str, object] | None = None) -> str:
        """Fetch ``name`` (cached) and render it against ``context``."""
        return self.get_template(name).render(context)

    def compile_partial(self, name: str) -> list[object]:
        """Return the compiled body of an included partial (used by the renderer)."""
        return self.get_template(name).body

    def _resolve_source(self, name: str) -> str:
        loader = self._loader
        if loader is None:
            raise TemplateRuntimeError(
                f"cannot load {name!r}: no loader is configured"
            )
        if isinstance(loader, Mapping):
            try:
                return loader[name]
            except KeyError as exc:
                raise TemplateRuntimeError(f"template {name!r} not found") from exc
        try:
            source = loader(name)
        except TemplateError:
            raise
        except Exception as exc:  # wrap foreign loader failures per NFR-2
            raise TemplateRuntimeError(f"loader failed for {name!r}: {exc}") from exc
        if source is None:
            raise TemplateRuntimeError(f"template {name!r} not found")
        return source
