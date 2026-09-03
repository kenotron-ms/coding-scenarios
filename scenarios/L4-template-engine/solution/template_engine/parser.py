"""Parser for the template engine.

Consumes a list of Tokens and produces a TemplateNode AST.
Raises TemplateSyntaxError (via exceptions module) on malformed input.

One-way dependency: parser -> lexer (tokens), parser -> ast_nodes.
The renderer never calls back into the parser.
"""

from __future__ import annotations

from typing import Any

from .tokens import Token, TokenKind
from .ast_nodes import (
    BinOpNode, FilterNode, ForNode, IfNode, IncludeNode,
    InterpolationNode, LiteralNode, NameNode, PathNode, TemplateNode,
    TextNode, UnaryOpNode,
)


class ParseError(Exception):
    """Internal parse error — caller converts to TemplateSyntaxError."""
    def __init__(self, msg: str, line: int, col: int) -> None:
        super().__init__(msg)
        self.line = line
        self.col = col


class Parser:
    """Recursive-descent parser over a flat token list."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind != TokenKind.EOF:
            self._pos += 1
        return tok

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ParseError(
                f"Expected {kind.name}, got {tok.kind.name} ({tok.value!r})",
                tok.line, tok.col,
            )
        return self._advance()

    def _expect_name(self, name: str) -> Token:
        tok = self._peek()
        if tok.kind != TokenKind.NAME or tok.value != name:
            raise ParseError(
                f"Expected keyword {name!r}, got {tok.kind.name} ({tok.value!r})",
                tok.line, tok.col,
            )
        return self._advance()

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> TemplateNode:
        tok = self._peek()
        body = self._parse_body(stop_at=None)
        if self._peek().kind != TokenKind.EOF:
            t = self._peek()
            raise ParseError(f"Unexpected token {t.value!r}", t.line, t.col)
        return TemplateNode(line=tok.line, col=tok.col, body=body)

    def _parse_body(self, stop_at: set[str] | None) -> list[Any]:
        """Parse a sequence of nodes until EOF or a block keyword in stop_at."""
        nodes: list[Any] = []
        while True:
            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                break
            if tok.kind == TokenKind.TEXT:
                self._advance()
                nodes.append(TextNode(line=tok.line, col=tok.col, text=tok.value))
            elif tok.kind == TokenKind.VAR_START:
                nodes.append(self._parse_interpolation())
            elif tok.kind == TokenKind.BLOCK_START:
                # Peek at the keyword inside
                keyword = self._peek_block_keyword()
                if stop_at and keyword in stop_at:
                    break
                nodes.append(self._parse_block())
            else:
                raise ParseError(
                    f"Unexpected token {tok.kind.name}", tok.line, tok.col
                )
        return nodes

    def _peek_block_keyword(self) -> str:
        """Look ahead past BLOCK_START to find the keyword name."""
        # BLOCK_START is at pos; next token should be NAME
        if self._pos + 1 < len(self._tokens):
            t = self._tokens[self._pos + 1]
            if t.kind == TokenKind.NAME:
                return t.value
        return ""

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    def _parse_interpolation(self) -> InterpolationNode:
        start = self._expect(TokenKind.VAR_START)
        expr = self._parse_filter_chain()
        self._expect(TokenKind.VAR_END)
        return InterpolationNode(line=start.line, col=start.col, expr=expr)

    # ------------------------------------------------------------------
    # Block statements
    # ------------------------------------------------------------------

    def _parse_block(self) -> Any:
        # BLOCK_START is current; look at keyword
        bs = self._peek()
        keyword = self._peek_block_keyword()
        if keyword == "if":
            return self._parse_if()
        elif keyword == "for":
            return self._parse_for()
        elif keyword == "include":
            return self._parse_include()
        elif keyword in ("endif", "endfor", "else", "elif"):
            raise ParseError(
                f"Unexpected block tag {keyword!r}", bs.line, bs.col
            )
        else:
            raise ParseError(
                f"Unknown block tag {keyword!r}", bs.line, bs.col
            )

    def _parse_if(self) -> IfNode:
        start = self._expect(TokenKind.BLOCK_START)
        self._expect_name("if")
        condition = self._parse_expression()
        self._expect(TokenKind.BLOCK_END)

        body = self._parse_body(stop_at={"elif", "else", "endif"})

        elif_clauses: list[tuple[Any, list[Any]]] = []
        else_body: list[Any] = []

        while True:
            kw = self._peek_block_keyword()
            if kw == "elif":
                self._expect(TokenKind.BLOCK_START)
                self._expect_name("elif")
                elif_cond = self._parse_expression()
                self._expect(TokenKind.BLOCK_END)
                elif_body = self._parse_body(stop_at={"elif", "else", "endif"})
                elif_clauses.append((elif_cond, elif_body))
            elif kw == "else":
                self._expect(TokenKind.BLOCK_START)
                self._expect_name("else")
                self._expect(TokenKind.BLOCK_END)
                else_body = self._parse_body(stop_at={"endif"})
                break
            elif kw == "endif":
                break
            else:
                t = self._peek()
                raise ParseError(
                    f"Unclosed {{% if %}} block (got {kw!r})", start.line, start.col
                )

        if self._peek_block_keyword() != "endif":
            raise ParseError("Expected {%endif%}", start.line, start.col)
        self._expect(TokenKind.BLOCK_START)
        self._expect_name("endif")
        self._expect(TokenKind.BLOCK_END)

        return IfNode(
            line=start.line, col=start.col,
            condition=condition,
            body=body,
            elif_clauses=elif_clauses,
            else_body=else_body,
        )

    def _parse_for(self) -> ForNode:
        start = self._expect(TokenKind.BLOCK_START)
        self._expect_name("for")
        var_tok = self._expect(TokenKind.NAME)
        self._expect(TokenKind.IN)
        iterable = self._parse_primary()  # only paths/names make sense here
        self._expect(TokenKind.BLOCK_END)

        body = self._parse_body(stop_at={"endfor"})

        if self._peek_block_keyword() != "endfor":
            raise ParseError("Unclosed {%for%} block", start.line, start.col)
        self._expect(TokenKind.BLOCK_START)
        self._expect_name("endfor")
        self._expect(TokenKind.BLOCK_END)

        return ForNode(
            line=start.line, col=start.col,
            var=var_tok.value,
            iterable=iterable,
            body=body,
        )

    def _parse_include(self) -> IncludeNode:
        start = self._expect(TokenKind.BLOCK_START)
        self._expect_name("include")
        name_tok = self._expect(TokenKind.STRING)
        template_name = name_tok.value[1:-1]  # strip quotes
        self._expect(TokenKind.BLOCK_END)
        return IncludeNode(line=start.line, col=start.col, template_name=template_name)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _parse_filter_chain(self) -> Any:
        """Parse expr (| filter)*"""
        expr = self._parse_expression()
        while self._peek().kind == TokenKind.PIPE:
            pipe_tok = self._advance()
            name_tok = self._expect(TokenKind.NAME)
            args: list[Any] = []
            if self._peek().kind == TokenKind.LPAREN:
                self._advance()
                while self._peek().kind != TokenKind.RPAREN:
                    args.append(self._parse_literal())
                    if self._peek().kind == TokenKind.COMMA:
                        self._advance()
                self._expect(TokenKind.RPAREN)
            expr = FilterNode(
                line=pipe_tok.line, col=pipe_tok.col,
                expr=expr, name=name_tok.value, args=args,
            )
        return expr

    def _parse_expression(self) -> Any:
        """Parse boolean expression (or/and/not/comparisons)."""
        return self._parse_or()

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while self._peek().kind == TokenKind.OR:
            op_tok = self._advance()
            right = self._parse_and()
            left = BinOpNode(line=op_tok.line, col=op_tok.col,
                             op="or", left=left, right=right)
        return left

    def _parse_and(self) -> Any:
        left = self._parse_not()
        while self._peek().kind == TokenKind.AND:
            op_tok = self._advance()
            right = self._parse_not()
            left = BinOpNode(line=op_tok.line, col=op_tok.col,
                             op="and", left=left, right=right)
        return left

    def _parse_not(self) -> Any:
        if self._peek().kind == TokenKind.NOT:
            op_tok = self._advance()
            operand = self._parse_not()
            return UnaryOpNode(line=op_tok.line, col=op_tok.col,
                               op="not", operand=operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        left = self._parse_primary()
        _CMP_OPS = {
            TokenKind.EQ: "==",
            TokenKind.NEQ: "!=",
            TokenKind.LT: "<",
            TokenKind.LTE: "<=",
            TokenKind.GT: ">",
            TokenKind.GTE: ">=",
        }
        tok = self._peek()
        if tok.kind in _CMP_OPS:
            op_tok = self._advance()
            right = self._parse_primary()
            return BinOpNode(
                line=op_tok.line, col=op_tok.col,
                op=_CMP_OPS[op_tok.kind],
                left=left, right=right,
            )
        return left

    def _parse_primary(self) -> Any:
        tok = self._peek()
        if tok.kind in (TokenKind.STRING, TokenKind.INTEGER,
                        TokenKind.FLOAT, TokenKind.BOOL, TokenKind.NONE):
            return self._parse_literal()
        if tok.kind == TokenKind.NAME:
            return self._parse_path()
        raise ParseError(
            f"Unexpected token {tok.kind.name} ({tok.value!r}) in expression",
            tok.line, tok.col,
        )

    def _parse_literal(self) -> LiteralNode:
        tok = self._advance()
        if tok.kind == TokenKind.STRING:
            value: Any = tok.value[1:-1]
        elif tok.kind == TokenKind.INTEGER:
            value = int(tok.value)
        elif tok.kind == TokenKind.FLOAT:
            value = float(tok.value)
        elif tok.kind == TokenKind.BOOL:
            value = tok.value == "true"
        elif tok.kind == TokenKind.NONE:
            value = None
        else:
            raise ParseError(
                f"Expected literal, got {tok.kind.name}", tok.line, tok.col
            )
        return LiteralNode(line=tok.line, col=tok.col, value=value)

    def _parse_path(self) -> Any:
        """Parse name (.attr | [expr])* — yields NameNode or PathNode."""
        name_tok = self._expect(TokenKind.NAME)
        root = NameNode(line=name_tok.line, col=name_tok.col, name=name_tok.value)
        steps: list[tuple[str, Any]] = []

        while True:
            tok = self._peek()
            if tok.kind == TokenKind.DOT:
                self._advance()
                attr_tok = self._expect(TokenKind.NAME)
                steps.append(("attr", attr_tok.value))
            elif tok.kind == TokenKind.LBRACKET:
                self._advance()
                idx_expr = self._parse_primary()
                self._expect(TokenKind.RBRACKET)
                steps.append(("index", idx_expr))
            else:
                break

        if not steps:
            return root
        return PathNode(line=name_tok.line, col=name_tok.col, root=root, steps=steps)
