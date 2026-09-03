"""Lexer (tokenizer) for the template engine.

Splits source text into a flat list of Tokens. Position metadata
(1-based line/col) is recorded at the start of every token.

Ambiguity resolution #2 — whitespace control:
    Strict verbatim preservation (option a). Block tags do NOT consume
    surrounding whitespace or newlines. A template with no block tags is
    byte-exact. Trim markers ({%- ... -%}) are NOT supported.
"""

from __future__ import annotations

import re
from typing import Iterator

from .tokens import Token, TokenKind

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Matches {{ ... }} or {% ... %} or literal text in between.
_BLOCK_RE = re.compile(
    r"(\{\{|\}\}|\{%|%\})",
)

# Inner token patterns (used inside {{ }} and {% %} regions)
_INNER_TOKENS: list[tuple[TokenKind, re.Pattern[str]]] = [
    (TokenKind.FLOAT,   re.compile(r"\d+\.\d+")),
    (TokenKind.INTEGER, re.compile(r"\d+")),
    (TokenKind.STRING,  re.compile(r'"[^"]*"|\'[^\']*\'')),
    (TokenKind.EQ,      re.compile(r"==")),
    (TokenKind.NEQ,     re.compile(r"!=")),
    (TokenKind.LTE,     re.compile(r"<=")),
    (TokenKind.GTE,     re.compile(r">=")),
    (TokenKind.LT,      re.compile(r"<")),
    (TokenKind.GT,      re.compile(r">")),
    (TokenKind.DOT,     re.compile(r"\.")),
    (TokenKind.LBRACKET, re.compile(r"\[")),
    (TokenKind.RBRACKET, re.compile(r"\]")),
    (TokenKind.PIPE,    re.compile(r"\|")),
    (TokenKind.LPAREN,  re.compile(r"\(")),
    (TokenKind.RPAREN,  re.compile(r"\)")),
    (TokenKind.COMMA,   re.compile(r",")),
    (TokenKind.NAME,    re.compile(r"[A-Za-z_][A-Za-z0-9_]*")),
]

_KEYWORDS: dict[str, TokenKind] = {
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "in": TokenKind.IN,
    "true": TokenKind.BOOL,
    "false": TokenKind.BOOL,
    "none": TokenKind.NONE,
}


class LexerError(Exception):
    """Internal error — caller converts to TemplateSyntaxError."""
    def __init__(self, msg: str, line: int, col: int) -> None:
        super().__init__(msg)
        self.line = line
        self.col = col


def _pos_after(source: str, offset: int) -> tuple[int, int]:
    """Return (line, col) for *offset* in *source* (1-based).

    \r is ignored (not counted). Tabs count as 1 column.
    """
    line = 1
    col = 1
    for i, ch in enumerate(source):
        if i == offset:
            break
        if ch == "\r":
            continue
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return line, col


def tokenize(source: str) -> list[Token]:
    """Tokenize *source* and return a list of Tokens ending with EOF."""
    tokens: list[Token] = []
    pos = 0
    length = len(source)

    # Track line/col incrementally for efficiency
    line = 1
    col = 1

    def advance(n: int) -> None:
        nonlocal pos, line, col
        for _ in range(n):
            if pos >= length:
                break
            ch = source[pos]
            pos += 1
            if ch == "\r":
                pass  # \r not counted
            elif ch == "\n":
                line += 1
                col = 1
            else:
                col += 1

    def current_pos() -> tuple[int, int]:
        return line, col

    while pos < length:
        # Are we at the start of a tag?
        if source[pos] == "{" and pos + 1 < length and source[pos + 1] in ("{", "%"):
            tag_line, tag_col = current_pos()
            tag_open = source[pos : pos + 2]
            if tag_open == "{{":
                tokens.append(Token(TokenKind.VAR_START, "{{", tag_line, tag_col))
                advance(2)
                tokens.extend(_lex_inner(source, pos, tag_line, tag_col, "}}"))
                # advance past inner tokens
                end_pos = _find_close(source, pos, "}}")
                if end_pos == -1:
                    raise LexerError("Unclosed '{{'", tag_line, tag_col)
                # advance to end_pos
                while pos < end_pos:
                    advance(1)
                close_line, close_col = current_pos()
                tokens.append(Token(TokenKind.VAR_END, "}}", close_line, close_col))
                advance(2)
            else:  # {%
                tokens.append(Token(TokenKind.BLOCK_START, "{%", tag_line, tag_col))
                advance(2)
                tokens.extend(_lex_inner(source, pos, tag_line, tag_col, "%}"))
                end_pos = _find_close(source, pos, "%}")
                if end_pos == -1:
                    raise LexerError("Unclosed '{%'", tag_line, tag_col)
                while pos < end_pos:
                    advance(1)
                close_line, close_col = current_pos()
                tokens.append(Token(TokenKind.BLOCK_END, "%}", close_line, close_col))
                advance(2)
        else:
            # Collect literal text until the next tag or end
            text_start = pos
            text_line, text_col = current_pos()
            text_chars: list[str] = []
            while pos < length:
                if source[pos] == "{" and pos + 1 < length and source[pos + 1] in ("{", "%"):
                    break
                ch = source[pos]
                if ch != "\r":
                    text_chars.append(ch)
                advance(1)
            text = "".join(text_chars)
            if text:
                tokens.append(Token(TokenKind.TEXT, text, text_line, text_col))

    tokens.append(Token(TokenKind.EOF, "", line, col))
    return tokens


def _find_close(source: str, start: int, close: str) -> int:
    """Return the index of *close* in *source* starting at *start*, or -1."""
    idx = source.find(close, start)
    return idx


def _lex_inner(
    source: str, start: int, tag_line: int, tag_col: int, close: str
) -> list[Token]:
    """Lex the content between an opening tag delimiter and its closing one."""
    end = source.find(close, start)
    if end == -1:
        raise LexerError(f"Unclosed tag", tag_line, tag_col)
    inner = source[start:end]

    tokens: list[Token] = []
    i = 0
    # Compute starting position in source for accurate line/col
    src_offset = start

    # We need absolute line/col for each inner token.
    # Walk source[start:end] character by character.
    inner_line, inner_col = _pos_after(source, start)

    while i < len(inner):
        # Skip whitespace
        if inner[i] in " \t\n\r":
            ch = inner[i]
            if ch == "\n":
                inner_line += 1
                inner_col = 1
            elif ch != "\r":
                inner_col += 1
            i += 1
            continue

        tok_line = inner_line
        tok_col = inner_col

        matched = False
        for kind, pattern in _INNER_TOKENS:
            m = pattern.match(inner, i)
            if m:
                value = m.group(0)
                # Reclassify keywords
                if kind == TokenKind.NAME:
                    kind = _KEYWORDS.get(value, kind)
                tokens.append(Token(kind, value, tok_line, tok_col))
                # Advance inner_line/inner_col
                for ch in value:
                    if ch == "\n":
                        inner_line += 1
                        inner_col = 1
                    elif ch != "\r":
                        inner_col += 1
                i += len(value)
                matched = True
                break

        if not matched:
            raise LexerError(
                f"Unexpected character {inner[i]!r} in template tag",
                tok_line, tok_col
            )

    return tokens
