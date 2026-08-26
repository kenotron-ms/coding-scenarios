"""Exception hierarchy for the template engine.

All exceptions raised by this library inherit from :class:`TemplateError`.
No other exception type may cross the public API boundary.
"""


class TemplateError(Exception):
    """Base class for every exception raised by the template engine."""


class TemplateSyntaxError(TemplateError):
    """Raised at template construction time when the source is malformed.

    Attributes:
        msg: Human-readable description naming the offending construct.
        line: 1-based line number of the offending construct.
        col: 1-based column number of the offending construct.
    """

    def __init__(self, msg: str, line: int, col: int) -> None:
        """Initialise with a message and source position.

        Args:
            msg: Human-readable description of the error.
            line: 1-based line number.
            col: 1-based column number.
        """
        super().__init__(f"{msg} (line {line}, col {col})")
        self.msg = msg
        self.line = line
        self.col = col


class TemplateRuntimeError(TemplateError):
    """Raised during rendering.

    Covers: unknown filter, filter failure, missing include, include cycle,
    strict-undefined access, non-iterable loop target, sandboxed attribute
    access, and any other runtime failure.
    """
