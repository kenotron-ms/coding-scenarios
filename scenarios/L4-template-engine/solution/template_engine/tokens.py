"""Token types and Token dataclass for the template engine lexer.

Position metadata (line, col) is 1-based and originates here; it is
carried through to AST nodes and ultimately surfaces in TemplateSyntaxError.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    TEXT = auto()          # literal text between tags
    VAR_START = auto()     # {{
    VAR_END = auto()       # }}
    BLOCK_START = auto()   # {%
    BLOCK_END = auto()     # %}
    NAME = auto()          # identifier
    STRING = auto()        # "..." or '...'
    INTEGER = auto()       # 12
    FLOAT = auto()         # 1.5
    BOOL = auto()          # true / false
    NONE = auto()          # none
    DOT = auto()           # .
    LBRACKET = auto()      # [
    RBRACKET = auto()      # ]
    PIPE = auto()          # |
    LPAREN = auto()        # (
    RPAREN = auto()        # )
    COMMA = auto()         # ,
    EQ = auto()            # ==
    NEQ = auto()           # !=
    LT = auto()            # <
    LTE = auto()           # <=
    GT = auto()            # >
    GTE = auto()           # >=
    AND = auto()           # and
    OR = auto()            # or
    NOT = auto()           # not
    IN = auto()            # in
    EOF = auto()


@dataclass(frozen=True)
class Token:
    """A single lexical token with position metadata."""
    kind: TokenKind
    value: str
    line: int   # 1-based
    col: int    # 1-based, tab = 1 column, \r not counted
