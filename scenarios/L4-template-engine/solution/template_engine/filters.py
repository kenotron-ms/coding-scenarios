"""Built-in filter registry for the template engine.

Imports only :mod:`errors`.

Built-in filters
----------------
upper(v)            ``str(v).upper()``
lower(v)            ``str(v).lower()``
length(v)           ``len(v)``; raises :class:`TemplateRuntimeError` if no length
default(v, fallback) Returns *fallback* when *v* is undefined (sentinel) or
                    ``None``; passes through defined-but-falsy values unchanged.
"""

from __future__ import annotations

from typing import Any

from .errors import TemplateRuntimeError

# Sentinel used by the renderer to signal "undefined / not found".
UNDEFINED = object()


def _filter_upper(v: Any) -> str:
    """Return ``str(v).upper()``."""
    return str(v).upper()


def _filter_lower(v: Any) -> str:
    """Return ``str(v).lower()``."""
    return str(v).lower()


def _filter_length(v: Any) -> int:
    """Return ``len(v)``.

    Raises:
        TemplateRuntimeError: If *v* has no ``__len__``.
    """
    try:
        return len(v)
    except TypeError as exc:
        raise TemplateRuntimeError(
            f"object of type {type(v).__name__!r} has no length"
        ) from exc


def _filter_default(v: Any, fallback: Any = "") -> Any:
    """Return *fallback* when *v* is the undefined sentinel or ``None``.

    Defined-but-falsy values (``0``, ``""``, ``[]``) pass through unchanged.

    Args:
        v: The value to test.
        fallback: The replacement when *v* is undefined or ``None``.

    Returns:
        *fallback* if *v* is undefined or ``None``, otherwise *v*.
    """
    if v is UNDEFINED or v is None:
        return fallback
    return v


#: The built-in filter registry mapping name -> callable.
BUILTIN_FILTERS: dict[str, Any] = {
    "upper": _filter_upper,
    "lower": _filter_lower,
    "length": _filter_length,
    "default": _filter_default,
}
