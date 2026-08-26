"""Lexer: tokenises a template source string into a flat list of Tokens.

Token kinds
-----------
TEXT            Literal text between tags.
BLOCK_START     The ``{%`` opener (value is the stripped inner content).
BLOCK_END       The ``%}`` closer (value is ``"%}"``) — consumed by parser.
INTERP_START    The ``{{`` opener (value is the stripped inner content).
INTERP_END      The ``}}`` closer (value is ``"}}"``).
EOF             Sentinel at end of stream.

Position rules (NFR-2)
----------------------
- ``line`` and ``col`` are 1-based.
- A tab counts as one column.
- ``\\r\\n`` counts as one newline; ``\\r`` alone also counts as one newline.
- The position of ``{{`` or ``{%`` is the position of the first ``{``.
- Unterminated ``{{`` or ``{%`` raises :class:`TemplateSyntaxError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .errors import TemplateSyntaxError


class Token(NamedTuple):
    """A single lexer token with source position."""

    kind: str   # TEXT | BLOCK_START | INTERP_START | EOF
    value: str
    line: int
    col: int


def tokenize(source: str) -> list[Token]:
    """Tokenise *source* into a list of :class:`Token` objects.

    Args:
        source: The raw template source string.

    Returns:
        A flat list of tokens ending with an EOF token.

    Raises:
        TemplateSyntaxError: For unterminated ``{{`` or ``{%``.
    """
    tokens: list[Token] = []
    pos = 0
    n = len(source)
    line = 1
    col = 1

    def _advance_pos(start: int, end: int) -> tuple[int, int]:
        """Return (line, col) after consuming source[start:end]."""
        ln = line
        cl = col
        for ch in source[start:end]:
            if ch == "\n":
                ln += 1
                cl = 1
            elif ch == "\r":
                # \r\n handled by skipping \n after \r; bare \r counts too
                ln += 1
                cl = 1
            else:
                cl += 1
        return ln, cl

    while pos < n:
        # Look for the next tag opener
        brace2 = source.find("{{", pos)
        percent = source.find("{%", pos)

        # Find the nearest opener
        if brace2 == -1 and percent == -1:
            # Rest is plain text
            if pos < n:
                tokens.append(Token("TEXT", source[pos:], line, col))
                line, col = _advance_pos(pos, n)
            break

        if brace2 == -1:
            next_tag = percent
            tag_type = "block"
        elif percent == -1:
            next_tag = brace2
            tag_type = "interp"
        else:
            if brace2 <= percent:
                next_tag = brace2
                tag_type = "interp"
            else:
                next_tag = percent
                tag_type = "block"

        # Emit text before the tag
        if next_tag > pos:
            tokens.append(Token("TEXT", source[pos:next_tag], line, col))
            line, col = _advance_pos(pos, next_tag)

        tag_line = line
        tag_col = col

        if tag_type == "interp":
            # Find closing "}}"
            close = source.find("}}", next_tag + 2)
            if close == -1:
                raise TemplateSyntaxError(
                    "unterminated '{{'", tag_line, tag_col
                )
            inner = source[next_tag + 2 : close].strip()
            tokens.append(Token("INTERP_START", inner, tag_line, tag_col))
            pos = close + 2
            line, col = _advance_pos(next_tag, pos)
        else:
            # Find closing "%}"
            close = source.find("%}", next_tag + 2)
            if close == -1:
                raise TemplateSyntaxError(
                    "unterminated '{%'", tag_line, tag_col
                )
            inner = source[next_tag + 2 : close].strip()
            tokens.append(Token("BLOCK_START", inner, tag_line, tag_col))
            pos = close + 2
            line, col = _advance_pos(next_tag, pos)

    tokens.append(Token("EOF", "", line, col))
    return tokens
