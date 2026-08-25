"""The compiled, reusable Template (public class).

``Template(source)`` tokenizes and parses **once**, at construction (FR-8). Each
:meth:`render` walks the already-built AST with a fresh renderer, so repeated
renders with different contexts are independent and never re-parse.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from .filters import builtin_filters
from .parser import parse
from .renderer import RenderConfig, Renderer

if TYPE_CHECKING:
    from .environment import Environment


class Template:
    """A compiled template: parse once, render many.

    Args:
        source: the template text.
        autoescape: HTML-escape interpolated values after filters (default
            ``False``, the pinned default).
        strict_undefined: raise on a missing name instead of the lenient policy
            (default ``False``, the pinned default).
        environment: optional owning :class:`Environment` supplying the loader
            (for ``{% include %}``) and the shared filter registry.

    Raises:
        TemplateSyntaxError: at construction, if ``source`` is malformed.
    """

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
        self._body: list[object] = parse(source)

    @property
    def body(self) -> list[object]:
        """The compiled AST body (internal contract shared within the package)."""
        return self._body

    def render(self, context: Mapping[str, object] | None = None) -> str:
        """Render the template against ``context`` (``None`` means ``{}``)."""
        return Renderer(self._config()).render(self._body, context)

    def _config(self) -> RenderConfig:
        env = self._environment
        filters: dict[str, Callable[..., object]]
        compile_partial: Callable[[str], list[object]] | None
        if env is not None:
            filters = env.filter_map()
            compile_partial = env.compile_partial
        else:
            filters = builtin_filters()
            compile_partial = None
        return RenderConfig(
            filters=filters,
            autoescape=self.autoescape,
            strict_undefined=self.strict_undefined,
            compile_partial=compile_partial,
        )
