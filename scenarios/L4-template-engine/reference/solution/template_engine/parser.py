"""Tokens -> AST (imports lexer, nodes, errors, expressions).

The parser builds the template tree and delegates expression bodies to
:mod:`expressions`. All positions come from the lexer's tokens; the parser never
re-scans the source to recompute a ``line``/``col`` (REQUIREMENTS Sec.2.2). Error
positions follow NFR-2: opener-tag errors (unclosed block) point at the opener;
mismatched/stray closers point at the closer.
"""

from __future__ import annotations

import re

from .errors import TemplateSyntaxError
from .expressions import parse_expression, parse_output
from .lexer import Token, tokenize
from .nodes import ForNode, IfNode, IncludeNode, OutputNode, TextNode

_FOR_RE = re.compile(r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$", re.DOTALL)
_INCLUDE_RE = re.compile(
    r"""^include\s+("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*$""", re.DOTALL
)
_CLOSERS = {"endif", "elif", "else", "endfor"}


def _keyword(tok: Token) -> str:
    parts = tok.value.split()
    return parts[0] if parts else ""


def parse(source: str) -> list[object]:
    """Tokenize and parse ``source`` into a compiled template body."""
    return _Parser(tokenize(source)).parse_template()


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse_template(self) -> list[object]:
        body, _closer = self._parse_nodes(())
        return body

    def _parse_nodes(self, stop: tuple[str, ...]) -> tuple[list[object], Token | None]:
        """Parse nodes until a closer in ``stop`` or EOF.

        Returns the collected nodes and the closer token (left unconsumed) or
        ``None`` at EOF. A closer keyword that is not in ``stop`` is a stray or
        mismatched closer and raises immediately at its own position.
        """
        nodes: list[object] = []
        while True:
            tok = self._peek()
            if tok.kind == "eof":
                return nodes, None
            if tok.kind == "text":
                self._advance()
                nodes.append(TextNode(tok.value, tok.line, tok.col))
                continue
            if tok.kind == "var":
                self._advance()
                expr, filters = parse_output(tok.value, tok.line, tok.col)
                nodes.append(OutputNode(expr, filters, tok.line, tok.col))
                continue
            keyword = _keyword(tok)
            if keyword in stop:
                return nodes, tok
            if keyword == "if":
                nodes.append(self._parse_if())
                continue
            if keyword == "for":
                nodes.append(self._parse_for())
                continue
            if keyword == "include":
                nodes.append(self._parse_include())
                continue
            if keyword in _CLOSERS:
                raise TemplateSyntaxError(
                    f"unexpected '{{% {keyword} %}}' with no matching opener",
                    tok.line,
                    tok.col,
                )
            raise TemplateSyntaxError(f"unknown tag {keyword!r}", tok.line, tok.col)

    def _condition(self, tok: Token, keyword: str) -> object:
        rest = tok.value.strip()[len(keyword) :]
        return parse_expression(rest, tok.line, tok.col)

    def _parse_if(self) -> IfNode:
        open_tok = self._advance()
        line, col = open_tok.line, open_tok.col
        condition = self._condition(open_tok, "if")
        body, closer = self._parse_nodes(("elif", "else", "endif"))
        branches: list[tuple[object, list[object]]] = [(condition, body)]
        while closer is not None and _keyword(closer) == "elif":
            elif_tok = self._advance()
            econd = self._condition(elif_tok, "elif")
            ebody, closer = self._parse_nodes(("elif", "else", "endif"))
            branches.append((econd, ebody))
        else_body: list[object] | None = None
        if closer is not None and _keyword(closer) == "else":
            self._advance()
            else_body, closer = self._parse_nodes(("endif",))
        if closer is None:
            raise TemplateSyntaxError("unclosed 'if' block", line, col)
        keyword = _keyword(closer)
        if keyword != "endif":
            raise TemplateSyntaxError(
                f"expected '{{% endif %}}' but found '{{% {keyword} %}}'",
                closer.line,
                closer.col,
            )
        self._advance()
        return IfNode(branches, else_body, line, col)

    def _parse_for(self) -> ForNode:
        open_tok = self._advance()
        line, col = open_tok.line, open_tok.col
        match = _FOR_RE.match(open_tok.value.strip())
        if match is None:
            raise TemplateSyntaxError(
                "malformed 'for' tag; expected 'for NAME in EXPR'", line, col
            )
        var = match.group(1)
        expr = parse_expression(match.group(2), line, col)
        body, closer = self._parse_nodes(("endfor",))
        if closer is None:
            raise TemplateSyntaxError("unclosed 'for' block", line, col)
        keyword = _keyword(closer)
        if keyword != "endfor":
            raise TemplateSyntaxError(
                f"expected '{{% endfor %}}' but found '{{% {keyword} %}}'",
                closer.line,
                closer.col,
            )
        self._advance()
        return ForNode(var, expr, body, line, col)

    def _parse_include(self) -> IncludeNode:
        open_tok = self._advance()
        match = _INCLUDE_RE.match(open_tok.value.strip())
        if match is None:
            raise TemplateSyntaxError(
                "malformed 'include' tag; expected 'include \"name\"'",
                open_tok.line,
                open_tok.col,
            )
        name = match.group(1)[1:-1]
        return IncludeNode(name, open_tok.line, open_tok.col)
