"""Built-in filter registry (imports errors + runtime only).

Filters are plain callables ``fn(value, *args) -> value``. The renderer wraps a
filter that raises into a :class:`TemplateRuntimeError`, so these keep to the
happy path and let real failures (e.g. ``len`` of an int) propagate to that
wrapper (REQUIREMENTS FR-5, Sec.2.1 semantics table).
"""

from __future__ import annotations

from collections.abc import Callable

from .runtime import UNDEFINED


def do_upper(value: object) -> str:
    """``str(value).upper()``."""
    return str(value).upper()


def do_lower(value: object) -> str:
    """``str(value).lower()``."""
    return str(value).lower()


def do_length(value: object) -> int:
    """``len(value)``; the renderer wraps the ``TypeError`` for a length-less value."""
    return len(value)  # type: ignore[arg-type]


def do_default(value: object, fallback: object) -> object:
    """Return ``fallback`` when ``value`` is undefined or ``None``.

    A defined-but-falsy value (``0``, ``""``, ``[]``) passes through unchanged.
    """
    if value is UNDEFINED or value is None:
        return fallback
    return value


def builtin_filters() -> dict[str, Callable[..., object]]:
    """Return a fresh mapping of the four built-in filters."""
    return {
        "upper": do_upper,
        "lower": do_lower,
        "length": do_length,
        "default": do_default,
    }


__all__ = ["builtin_filters", "do_default", "do_length", "do_lower", "do_upper"]
