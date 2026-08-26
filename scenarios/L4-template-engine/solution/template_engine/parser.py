"""Parser: converts a token list into an AST.

Imports only :mod:`lexer`, :mod:`nodes`, and :mod:`errors` — never
:mod:`renderer` or :mod:`environment`.

Grammar implemented
-------------------
::

    template      := (TEXT | interpolation | block)*
    interpolation := '{{' expr ('|' filter)* '}}'
    block         := if_block | for_block | include
    if_block      := '{% if' expr '%}' template
                     ('{% elif' expr '%}' template)*
                     ('{% else %}' template)?
                     '{% endif %}'
    for_block     := '{% for' NAME 'in' expr '%}' template '{% endfor %}'
    include       := '{% include' STRING '%}'

    expr          := or_expr
    or_expr       := and_expr ('or' and_expr)*
    and_expr      := not_expr ('and' not_expr)*
    not_expr      := 'not' not_expr | comparison
    comparison    := operand (('=='|'!='|'<'|'<='|'>'|'>=') operand)?
    operand       := literal | path
    path          := NAME ('.' NAME | '[' (INT | STRING) ']')*
    literal       := STRING | INT | FLOAT | 'true' | 'false' | 'none'
    filter        := NAME ('(' literal (',' literal)* ')')?

Positions are carried from lexer tokens onto AST nodes; the parser never
re-scans the source.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import TemplateSyntaxError
from .lexer import Token, tokenize
from .nodes import (
    BinaryExpr,
    ForNode,
    IfNode,
    IncludeNode,
    LiteralExpr,
    NotExpr,
    OutputNode,
    PathExpr,
    TextNode,
)

# ---------------------------------------------------------------------------
# Mini-tokeniser for the *content* inside {{ ... }} and {% ... %} tags
# ---------------------------------------------------------------------------

_TOK_RE = re.compile(
    r"""
    (?P<FLOAT>  -?[0-9]+\.[0-9]+ )       |
    (?P<INT>    -?[0-9]+          )       |
    (?P<STRING> '(?:[^'\\]|\\.)*' | "(?:[^"\\]|\\.)*" ) |
    (?P<NAME>   [A-Za-z_][A-Za-z0-9_]* ) |
    (?P<OP>     ==|!=|<=|>=|<|>|\||\(|\)|\[|\]|\.|,|= ) |
    (?P<WS>     \s+               )
    """,
    re.VERBOSE,
)


def _lex_inner(text: str, base_line: int, base_col: int) -> list[tuple[str, str]]:
    """Tokenise the stripped content of a tag into ``(kind, value)`` pairs.

    Whitespace tokens are discarded.
    """
    result: list[tuple[str, str]] = []
    for m in _TOK_RE.finditer(text):
        kind = m.lastgroup
        if kind == "WS":
            continue
        result.append((kind, m.group()))  # type: ignore[arg-type]
    return result


def _unescape_string(s: str) -> str:
    """Remove surrounding quotes and interpret escape sequences."""
    quote = s[0]
    inner = s[1:-1]
    return inner.replace(f"\\{quote}", quote).replace("\\n", "\n").replace("\\t", "\t")


# ---------------------------------------------------------------------------
# Expression parser (operates on inner tokens)
# ---------------------------------------------------------------------------


class _ExprParser:
    """Recursive-descent expression parser for template expressions."""

    def __init__(self, tokens: list[tuple[str, str]], line: int, col: int) -> None:
        self._tokens = tokens
        self._pos = 0
        self._line = line
        self._col = col

    def _peek(self) -> tuple[str, str] | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> tuple[str, str]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str, value: str | None = None) -> tuple[str, str]:
        tok = self._peek()
        if tok is None or tok[0] != kind or (value is not None and tok[1] != value):
            expected = f"{kind}({value!r})" if value else kind
            raise TemplateSyntaxError(
                f"expected {expected}", self._line, self._col
            )
        return self._consume()

    def parse_expr(self) -> Any:
        """Parse a full expression (entry point)."""
        return self._parse_or()

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while self._peek() == ("NAME", "or"):
            self._consume()
            right = self._parse_and()
            left = BinaryExpr("or", left, right, self._line, self._col)
        return left

    def _parse_and(self) -> Any:
        left = self._parse_not()
        while self._peek() == ("NAME", "and"):
            self._consume()
            right = self._parse_not()
            left = BinaryExpr("and", left, right, self._line, self._col)
        return left

    def _parse_not(self) -> Any:
        if self._peek() == ("NAME", "not"):
            self._consume()
            operand = self._parse_not()
            return NotExpr(operand, self._line, self._col)
        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        left = self._parse_operand()
        tok = self._peek()
        if tok and tok[0] == "OP" and tok[1] in ("==", "!=", "<", "<=", ">", ">="):
            op = self._consume()[1]
            right = self._parse_operand()
            return BinaryExpr(op, left, right, self._line, self._col)
        return left

    def _parse_operand(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise TemplateSyntaxError(
                "empty or malformed expression", self._line, self._col
            )
        kind, value = tok
        if kind == "STRING":
            self._consume()
            return LiteralExpr(_unescape_string(value), self._line, self._col)
        if kind == "INT":
            self._consume()
            return LiteralExpr(int(value), self._line, self._col)
        if kind == "FLOAT":
            self._consume()
            return LiteralExpr(float(value), self._line, self._col)
        if kind == "NAME" and value in ("true", "false", "none"):
            self._consume()
            mapping = {"true": True, "false": False, "none": None}
            return LiteralExpr(mapping[value], self._line, self._col)
        if kind == "NAME":
            return self._parse_path()
        raise TemplateSyntaxError(
            f"unexpected token {value!r}", self._line, self._col
        )

    def _parse_path(self) -> Any:
        root_tok = self._expect("NAME")
        root = root_tok[1]
        parts: list[str | int] = []
        while True:
            tok = self._peek()
            if tok and tok[0] == "OP" and tok[1] == ".":
                self._consume()
                attr_tok = self._expect("NAME")
                parts.append(attr_tok[1])
            elif tok and tok[0] == "OP" and tok[1] == "[":
                self._consume()
                idx_tok = self._peek()
                if idx_tok is None:
                    raise TemplateSyntaxError(
                        "expected index inside '['", self._line, self._col
                    )
                if idx_tok[0] == "INT":
                    self._consume()
                    parts.append(int(idx_tok[1]))
                elif idx_tok[0] == "STRING":
                    self._consume()
                    parts.append(_unescape_string(idx_tok[1]))
                else:
                    raise TemplateSyntaxError(
                        f"expected INT or STRING inside '[', got {idx_tok[1]!r}",
                        self._line,
                        self._col,
                    )
                self._expect("OP", "]")
            else:
                break
        return PathExpr(root, parts, self._line, self._col)

    def parse_filter(self) -> tuple[str, list[Any]]:
        """Parse a single filter: NAME ('(' literal (',' literal)* ')')?"""
        name_tok = self._expect("NAME")
        name = name_tok[1]
        args: list[Any] = []
        if self._peek() == ("OP", "("):
            self._consume()
            while self._peek() != ("OP", ")"):
                tok = self._peek()
                if tok is None:
                    raise TemplateSyntaxError(
                        "unterminated filter argument list", self._line, self._col
                    )
                kind, value = tok
                if kind == "STRING":
                    self._consume()
                    args.append(_unescape_string(value))
                elif kind == "INT":
                    self._consume()
                    args.append(int(value))
                elif kind == "FLOAT":
                    self._consume()
                    args.append(float(value))
                elif kind == "NAME" and value in ("true", "false", "none"):
                    self._consume()
                    args.append({"true": True, "false": False, "none": None}[value])
                else:
                    raise TemplateSyntaxError(
                        f"expected literal in filter args, got {value!r}",
                        self._line,
                        self._col,
                    )
                if self._peek() == ("OP", ","):
                    self._consume()
            self._expect("OP", ")")
        return name, args

    def remaining(self) -> int:
        """Return number of unconsumed tokens."""
        return len(self._tokens) - self._pos


def _parse_expr_from_text(text: str, line: int, col: int) -> Any:
    """Parse an expression from the stripped content of an interpolation tag."""
    inner_tokens = _lex_inner(text, line, col)
    if not inner_tokens:
        raise TemplateSyntaxError("empty expression", line, col)
    ep = _ExprParser(inner_tokens, line, col)
    expr = ep.parse_expr()
    if ep.remaining() > 0:
        raise TemplateSyntaxError(
            f"unexpected token after expression: {ep._tokens[ep._pos][1]!r}",
            line,
            col,
        )
    return expr


def _parse_interp_tag(content: str, line: int, col: int) -> OutputNode:
    """Parse the content of a ``{{ ... }}`` tag into an OutputNode."""
    if not content:
        raise TemplateSyntaxError("empty expression", line, col)
    # Split on '|' to find filters, but only at top level (no nested parens)
    # We use the inner tokeniser to split correctly.
    inner_tokens = _lex_inner(content, line, col)
    if not inner_tokens:
        raise TemplateSyntaxError("empty expression", line, col)

    # Find pipe positions (not inside parentheses)
    pipe_positions: list[int] = []
    depth = 0
    for i, (k, v) in enumerate(inner_tokens):
        if k == "OP" and v == "(":
            depth += 1
        elif k == "OP" and v == ")":
            depth -= 1
        elif k == "OP" and v == "|" and depth == 0:
            pipe_positions.append(i)

    # Split token list at pipes
    if pipe_positions:
        expr_tokens = inner_tokens[: pipe_positions[0]]
        filter_token_slices: list[list[tuple[str, str]]] = []
        for i, pipe_pos in enumerate(pipe_positions):
            start = pipe_pos + 1
            end = pipe_positions[i + 1] if i + 1 < len(pipe_positions) else len(inner_tokens)
            filter_token_slices.append(inner_tokens[start:end])
    else:
        expr_tokens = inner_tokens
        filter_token_slices = []

    # Parse expression
    if not expr_tokens:
        raise TemplateSyntaxError("empty expression before filter", line, col)
    ep = _ExprParser(expr_tokens, line, col)
    expr = ep.parse_expr()
    if ep.remaining() > 0:
        raise TemplateSyntaxError(
            f"unexpected token in expression: {ep._tokens[ep._pos][1]!r}", line, col
        )

    # Parse filters
    filters: list[tuple[str, list[Any]]] = []
    for fslice in filter_token_slices:
        if not fslice:
            raise TemplateSyntaxError("empty filter name", line, col)
        fp = _ExprParser(fslice, line, col)
        fname, fargs = fp.parse_filter()
        if fp.remaining() > 0:
            raise TemplateSyntaxError(
                f"unexpected token in filter: {fp._tokens[fp._pos][1]!r}", line, col
            )
        filters.append((fname, fargs))

    return OutputNode(expr, filters, line, col)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


class _Parser:
    """Recursive-descent template parser."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def parse(self) -> list[Any]:
        """Parse the full token stream into an AST node list."""
        body = self._parse_body(stop_tags=frozenset())
        tok = self._peek()
        if tok.kind != "EOF":
            raise TemplateSyntaxError(
                f"unexpected tag '{tok.value}'", tok.line, tok.col
            )
        return body

    def _parse_body(self, stop_tags: frozenset[str]) -> list[Any]:
        """Parse nodes until a stop tag or EOF is encountered.

        The stop tag is *not* consumed.
        """
        nodes: list[Any] = []
        while True:
            tok = self._peek()
            if tok.kind == "EOF":
                break
            if tok.kind == "TEXT":
                self._consume()
                nodes.append(TextNode(tok.value, tok.line, tok.col))
            elif tok.kind == "INTERP_START":
                self._consume()
                node = _parse_interp_tag(tok.value, tok.line, tok.col)
                nodes.append(node)
            elif tok.kind == "BLOCK_START":
                tag_word = tok.value.split()[0] if tok.value.split() else ""
                if tag_word in stop_tags:
                    break
                nodes.append(self._parse_block(tok))
            else:
                break
        return nodes

    def _parse_block(self, tok: Token) -> Any:
        """Parse a block tag (if, for, include, or raise on unknown)."""
        content = tok.value
        words = content.split()
        if not words:
            raise TemplateSyntaxError("empty block tag", tok.line, tok.col)
        tag_name = words[0]

        if tag_name == "if":
            return self._parse_if(tok)
        if tag_name == "for":
            return self._parse_for(tok)
        if tag_name == "include":
            return self._parse_include(tok)
        if tag_name in ("endif", "endfor", "else", "elif"):
            raise TemplateSyntaxError(
                f"stray '{tag_name}' tag", tok.line, tok.col
            )
        raise TemplateSyntaxError(
            f"unknown tag '{tag_name}'", tok.line, tok.col
        )

    def _parse_if(self, opener: Token) -> IfNode:
        """Parse an if/elif/else/endif block."""
        self._consume()  # consume the 'if ...' token
        # Parse the condition expression (everything after 'if ')
        cond_text = opener.value[2:].strip()  # strip 'if'
        cond_expr = _parse_expr_from_text(cond_text, opener.line, opener.col)

        branches: list[tuple[Any, list[Any]]] = []
        else_body: list[Any] = []

        body = self._parse_body(stop_tags=frozenset({"elif", "else", "endif"}))
        branches.append((cond_expr, body))

        while True:
            tok = self._peek()
            if tok.kind == "EOF":
                raise TemplateSyntaxError(
                    "unclosed 'if' block", opener.line, opener.col
                )
            if tok.kind != "BLOCK_START":
                break
            words = tok.value.split()
            tag_name = words[0] if words else ""

            if tag_name == "elif":
                self._consume()
                elif_text = tok.value[4:].strip()  # strip 'elif'
                elif_expr = _parse_expr_from_text(elif_text, tok.line, tok.col)
                elif_body = self._parse_body(stop_tags=frozenset({"elif", "else", "endif"}))
                branches.append((elif_expr, elif_body))
            elif tag_name == "else":
                self._consume()
                else_body = self._parse_body(stop_tags=frozenset({"endif"}))
                # Now expect endif
                end_tok = self._peek()
                if end_tok.kind == "EOF":
                    raise TemplateSyntaxError(
                        "unclosed 'if' block", opener.line, opener.col
                    )
                end_words = end_tok.value.split()
                end_name = end_words[0] if end_words else ""
                if end_name != "endif":
                    raise TemplateSyntaxError(
                        f"expected 'endif', got '{end_name}'",
                        end_tok.line,
                        end_tok.col,
                    )
                self._consume()
                break
            elif tag_name == "endif":
                self._consume()
                break
            elif tag_name in ("endfor",):
                raise TemplateSyntaxError(
                    f"mismatched closer '{tag_name}' inside 'if' block",
                    tok.line,
                    tok.col,
                )
            else:
                break

        return IfNode(branches, else_body, opener.line, opener.col)

    def _parse_for(self, opener: Token) -> ForNode:
        """Parse a for/endfor block."""
        self._consume()  # consume the 'for ...' token
        # Content: "for VAR in EXPR"
        rest = opener.value[3:].strip()  # strip 'for'
        inner_tokens = _lex_inner(rest, opener.line, opener.col)

        # Expect: NAME 'in' expr
        if len(inner_tokens) < 3:
            raise TemplateSyntaxError(
                "malformed 'for' tag", opener.line, opener.col
            )
        if inner_tokens[0][0] != "NAME":
            raise TemplateSyntaxError(
                "expected variable name in 'for'", opener.line, opener.col
            )
        var = inner_tokens[0][1]
        if inner_tokens[1] != ("NAME", "in"):
            raise TemplateSyntaxError(
                "expected 'in' in 'for'", opener.line, opener.col
            )
        expr_tokens = inner_tokens[2:]
        if not expr_tokens:
            raise TemplateSyntaxError(
                "missing iterable expression in 'for'", opener.line, opener.col
            )
        ep = _ExprParser(expr_tokens, opener.line, opener.col)
        expr = ep.parse_expr()
        if ep.remaining() > 0:
            raise TemplateSyntaxError(
                f"unexpected token in for expression: {ep._tokens[ep._pos][1]!r}",
                opener.line,
                opener.col,
            )

        body = self._parse_body(stop_tags=frozenset({"endfor"}))

        end_tok = self._peek()
        if end_tok.kind == "EOF":
            raise TemplateSyntaxError(
                "unclosed 'for' block", opener.line, opener.col
            )
        end_words = end_tok.value.split()
        end_name = end_words[0] if end_words else ""
        if end_name == "endif":
            raise TemplateSyntaxError(
                f"mismatched closer '{end_name}' inside 'for' block",
                end_tok.line,
                end_tok.col,
            )
        if end_name != "endfor":
            raise TemplateSyntaxError(
                f"expected 'endfor', got '{end_name}'",
                end_tok.line,
                end_tok.col,
            )
        self._consume()

        return ForNode(var, expr, body, opener.line, opener.col)

    def _parse_include(self, tok: Token) -> IncludeNode:
        """Parse an include tag."""
        self._consume()
        # Content: "include 'name'" or 'include "name"'
        rest = tok.value[7:].strip()  # strip 'include'
        inner_tokens = _lex_inner(rest, tok.line, tok.col)
        if not inner_tokens or inner_tokens[0][0] != "STRING":
            raise TemplateSyntaxError(
                "expected string literal in 'include'", tok.line, tok.col
            )
        name = _unescape_string(inner_tokens[0][1])
        return IncludeNode(name, tok.line, tok.col)


def parse(source: str) -> list[Any]:
    """Tokenise and parse *source* into an AST node list.

    Args:
        source: The raw template source string.

    Returns:
        A list of AST nodes (the top-level template body).

    Raises:
        TemplateSyntaxError: For any syntax error in the source.
    """
    tokens = tokenize(source)
    parser = _Parser(tokens)
    return parser.parse()
