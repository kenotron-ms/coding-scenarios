"""Parse the bounded expression grammar into expression nodes.

This module owns tokenizing and parsing the *inside* of ``{{ ... }}`` and the
condition of ``{% if/elif ... %}`` (REQUIREMENTS Sec.2.1). It never evaluates --
evaluation is the renderer's job -- so parsing happens exactly once, at compile
time. All syntax errors report the tag's opening position (``line``/``col``),
per the NFR-2 pinning rule that a tag-level error points at the ``{``.
"""

from __future__ import annotations

import re
from typing import NoReturn

from .errors import TemplateSyntaxError
from .nodes import BoolOp, Compare, Literal, Not, Path

_TOKEN_RE = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<FLOAT>\d+\.\d+)
    | (?P<INT>\d+)
    | (?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<OP>==|!=|<=|>=|<|>)
    | (?P<PIPE>\|)
    | (?P<DOT>\.)
    | (?P<LBRACKET>\[)
    | (?P<RBRACKET>\])
    | (?P<LPAREN>\()
    | (?P<RPAREN>\))
    | (?P<COMMA>,)
    | (?P<NAME>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)

_BOOL_KEYWORDS = {"and", "or", "not"}
_LITERAL_KEYWORDS = {"true": True, "false": False, "none": None}

# A parsed filter: its name and a tuple of already-evaluated literal arguments.
FilterSpec = tuple[str, tuple[object, ...]]


def _unquote(raw: str) -> str:
    """Strip the surrounding quotes from a string literal and unescape it."""
    body = raw[1:-1]
    out: list[str] = []
    k = 0
    simple = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
    while k < len(body):
        ch = body[k]
        if ch == "\\" and k + 1 < len(body):
            out.append(simple.get(body[k + 1], body[k + 1]))
            k += 2
        else:
            out.append(ch)
            k += 1
    return "".join(out)


def _lex(text: str, line: int, col: int) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    length = len(text)
    while pos < length:
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise TemplateSyntaxError(
                f"malformed expression near {text[pos]!r}", line, col
            )
        pos = match.end()
        kind = match.lastgroup or ""
        if kind == "WS":
            continue
        tokens.append((kind, match.group()))
    return tokens


class _Parser:
    """Recursive-descent parser: or > and > not > comparison > operand."""

    def __init__(self, tokens: list[tuple[str, str]], line: int, col: int) -> None:
        self.tokens = tokens
        self.pos = 0
        self.line = line
        self.col = col

    def _peek(self) -> tuple[str, str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("EOF", "")

    def _next(self) -> tuple[str, str]:
        tok = self._peek()
        self.pos += 1
        return tok

    def _fail(self, msg: str) -> NoReturn:
        raise TemplateSyntaxError(msg, self.line, self.col)

    # -- grammar ----------------------------------------------------------

    def parse_expr(self) -> object:
        return self._parse_or()

    def _parse_or(self) -> object:
        values = [self._parse_and()]
        while self._peek() == ("NAME", "or"):
            self._next()
            values.append(self._parse_and())
        return values[0] if len(values) == 1 else BoolOp("or", tuple(values))

    def _parse_and(self) -> object:
        values = [self._parse_not()]
        while self._peek() == ("NAME", "and"):
            self._next()
            values.append(self._parse_not())
        return values[0] if len(values) == 1 else BoolOp("and", tuple(values))

    def _parse_not(self) -> object:
        if self._peek() == ("NAME", "not"):
            self._next()
            return Not(self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> object:
        left = self._parse_operand()
        if self._peek()[0] == "OP":
            op = self._next()[1]
            right = self._parse_operand()
            return Compare(left, op, right)
        return left

    def _parse_operand(self) -> object:
        kind, value = self._peek()
        if kind == "STRING":
            self._next()
            return Literal(_unquote(value))
        if kind == "INT":
            self._next()
            return Literal(int(value))
        if kind == "FLOAT":
            self._next()
            return Literal(float(value))
        if kind == "NAME":
            if value in _LITERAL_KEYWORDS:
                self._next()
                return Literal(_LITERAL_KEYWORDS[value])
            if value in _BOOL_KEYWORDS:
                self._fail(f"unexpected keyword {value!r} in expression")
            return self._parse_path()
        if kind == "EOF":
            self._fail("empty or incomplete expression")
        self._fail(f"unexpected token {value!r} in expression")

    def _parse_path(self) -> Path:
        name = self._next()[1]
        steps: list[tuple[str, object]] = []
        while True:
            kind, _ = self._peek()
            if kind == "DOT":
                self._next()
                attr_kind, attr = self._next()
                if attr_kind != "NAME":
                    self._fail("expected a name after '.'")
                steps.append(("attr", attr))
            elif kind == "LBRACKET":
                self._next()
                index_kind, index = self._next()
                if index_kind == "INT":
                    key: object = int(index)
                elif index_kind == "STRING":
                    key = _unquote(index)
                else:
                    self._fail("expected an integer or string index inside '[]'")
                if self._next()[0] != "RBRACKET":
                    self._fail("expected ']' to close an index")
                steps.append(("item", key))
            else:
                break
        return Path(name, tuple(steps))

    def _parse_literal_arg(self) -> object:
        kind, value = self._next()
        if kind == "STRING":
            return _unquote(value)
        if kind == "INT":
            return int(value)
        if kind == "FLOAT":
            return float(value)
        if kind == "NAME" and value in _LITERAL_KEYWORDS:
            return _LITERAL_KEYWORDS[value]
        self._fail("filter arguments must be literals")

    def parse_filters(self) -> tuple[FilterSpec, ...]:
        filters: list[FilterSpec] = []
        while self._peek()[0] == "PIPE":
            self._next()
            name_kind, name = self._next()
            if name_kind != "NAME" or name in _BOOL_KEYWORDS:
                self._fail("expected a filter name after '|'")
            args: list[object] = []
            if self._peek()[0] == "LPAREN":
                self._next()
                if self._peek()[0] != "RPAREN":
                    args.append(self._parse_literal_arg())
                    while self._peek()[0] == "COMMA":
                        self._next()
                        args.append(self._parse_literal_arg())
                if self._next()[0] != "RPAREN":
                    self._fail("expected ')' after filter arguments")
            filters.append((name, tuple(args)))
        return tuple(filters)

    def expect_end(self) -> None:
        if self.pos != len(self.tokens):
            self._fail("unexpected trailing tokens in expression")


def parse_expression(text: str, line: int, col: int) -> object:
    """Parse a standalone expression (a condition or a ``for`` iterable)."""
    parser = _Parser(_lex(text, line, col), line, col)
    node = parser.parse_expr()
    parser.expect_end()
    return node


def parse_output(text: str, line: int, col: int) -> tuple[object, tuple[FilterSpec, ...]]:
    """Parse an interpolation body: an expression plus an optional filter chain."""
    parser = _Parser(_lex(text, line, col), line, col)
    expr = parser.parse_expr()
    filters = parser.parse_filters()
    parser.expect_end()
    return expr, filters
