"""Public exception hierarchy for the template engine.

All exceptions that cross the public API must be one of these three types.
"""

from __future__ import annotations


class TemplateError(Exception):
    """Base class for all template engine errors."""


class TemplateSyntaxError(TemplateError):
    """Raised at template construction time for malformed syntax.

    Attributes
    ----------
    msg : str
        Human-readable description of the error.
    line : int
        1-based line number of the offending construct.
    col : int
        1-based column number of the first character of the offending
        construct (the ``{`` of ``{{`` or ``{%``). Tabs count as 1 column;
        ``\\r`` is not counted.
    """

    def __init__(self, msg: str, line: int, col: int) -> None:
        super().__init__(f"{msg} (line {line}, col {col})")
        self.msg = msg
        self.line = line
        self.col = col


class TemplateRuntimeError(TemplateError):
    """Raised during template rendering for runtime failures.

    Wraps any exception that would otherwise cross the public API
    (KeyError, AttributeError, RecursionError, etc.).
    """
