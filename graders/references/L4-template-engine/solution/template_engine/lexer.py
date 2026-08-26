"""Source -> token stream, with 1-based line/column on every token.

The lexer is the single origin of position metadata (REQUIREMENTS Sec.2.2): a
token records the position of the **first character** of its construct -- the
``{`` of ``{{`` / ``{%`` for tags, or the first character for a text run. The
parser and renderer carry those positions forward and never re-scan the source.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import TemplateSyntaxError


@dataclass(frozen=True)
class Token:
    """A lexical token.

    ``kind`` is one of ``text``, ``var`` (``{{ ... }}``), ``block``
    (``{% ... %}``), or ``eof``. ``value`` is the raw inner text of a tag (the
    characters between the delimiters, not yet stripped) or the literal text.
    """

    kind: str
    value: str
    line: int
    col: int


def line_col(source: str, offset: int) -> tuple[int, int]:
    """Return the 1-based ``(line, column)`` of ``offset`` into ``source``.

    Columns count characters (a tab is one column). ``\\n`` and ``\\r\\n`` both
    end a line; because the column is measured from the preceding ``\\n``, the
    ``\\r`` of a ``\\r\\n`` is not counted (NFR-2).
    """
    newline = source.rfind("\n", 0, offset)
    line = source.count("\n", 0, offset) + 1
    col = offset - newline if newline != -1 else offset + 1
    return line, col


def tokenize(source: str) -> list[Token]:
    """Split ``source`` into a flat list of tokens ending with an ``eof`` token.

    Raises:
        TemplateSyntaxError: if a ``{{`` or ``{%`` tag is never closed. The
            reported position is the opening ``{`` of the unterminated tag.
    """
    tokens: list[Token] = []
    n = len(source)
    i = 0
    text_start = 0
    text_buf: list[str] = []

    def flush_text() -> None:
        if text_buf:
            line, col = line_col(source, text_start)
            tokens.append(Token("text", "".join(text_buf), line, col))
            text_buf.clear()

    while i < n:
        ch = source[i]
        if ch == "{" and i + 1 < n and source[i + 1] in "{%":
            flush_text()
            is_var = source[i + 1] == "{"
            closer = "}}" if is_var else "%}"
            end = source.find(closer, i + 2)
            line, col = line_col(source, i)
            if end == -1:
                opener = "{{" if is_var else "{%"
                raise TemplateSyntaxError(f"unterminated '{opener}' tag", line, col)
            inner = source[i + 2 : end]
            tokens.append(Token("var" if is_var else "block", inner, line, col))
            i = end + 2
            text_start = i
        else:
            if not text_buf:
                text_start = i
            text_buf.append(ch)
            i += 1

    flush_text()
    eof_line, eof_col = line_col(source, n)
    tokens.append(Token("eof", "", eof_line, eof_col))
    return tokens
