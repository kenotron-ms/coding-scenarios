"""Exception taxonomy for the template engine (leaf module).

Every exception the library raises derives from :class:`TemplateError`, so a
consumer's error handling can be a single ``except TemplateError`` rather than a
guessing game about ``KeyError`` vs ``AttributeError`` vs ``RecursionError``
(REQUIREMENTS US-4, FR-9, NFR-2).
"""

from __future__ import annotations


class TemplateError(Exception):
    """Base class for every exception this library raises."""


class TemplateSyntaxError(TemplateError):
    """A malformed template, detected at construction (compile) time.

    Carries the 1-based ``line`` and ``col`` of the offending construct so a
    template author can locate the fault without bisecting the source.

    Args:
        msg: human-readable description naming the offending construct.
        line: 1-based line of the offending construct.
        col: 1-based column of the offending construct.
    """

    def __init__(self, msg: str, line: int, col: int) -> None:
        super().__init__(f"{msg} (line {line}, column {col})")
        self.msg = msg
        self.line = line
        self.col = col


class TemplateRuntimeError(TemplateError):
    """A failure raised during :meth:`Template.render`.

    Covers unknown filter, filter failure, missing include, include cycle,
    strict-undefined access, non-iterable loop target, and sandboxed
    (``_``-prefixed) attribute access. Internal ``KeyError`` / ``AttributeError``
    / ``IndexError`` / ``TypeError`` / ``RecursionError`` are wrapped into this
    type so no foreign exception crosses the public API (NFR-2).
    """
