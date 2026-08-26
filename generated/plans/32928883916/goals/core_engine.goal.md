# Lane core_engine

## Outcome

Implement the L4 template-engine library under `scenarios/L4-template-engine/solution/template_engine/` so that:

1. All 7 smoke tests pass (`pytest tests/smoke -q`).
2. At least 95% of the acceptance suite passes (`pytest tests/acceptance -q`).
3. The required design documents exist under `scenarios/L4-template-engine/solution/design/`.

The package must be importable as `template_engine` when `SOLUTION_DIR` is set to `scenarios/L4-template-engine/solution`.

## Steps

### 1. Read the authoritative requirements

Read (in order):
- `scenarios/L4-template-engine/REQUIREMENTS.md` — full spec
- `scenarios/L4-template-engine/SPEC.md` — condensed prompt
- `scenarios/L4-template-engine/manifest.yaml` — entrypoint and verify commands
- `scenarios/L4-template-engine/tests/smoke/test_smoke.py` — the 7 visible smoke cases

### 2. Create the module skeleton under `scenarios/L4-template-engine/solution/template_engine/`

Minimum files (names may vary slightly but the decomposition must match §2.2):

```
solution/
  template_engine/
    __init__.py       # public surface: re-exports Template, Environment, TemplateError, TemplateSyntaxError, TemplateRuntimeError
    errors.py         # TemplateError, TemplateSyntaxError(msg,line,col), TemplateRuntimeError
    nodes.py          # AST node dataclasses: TextNode, OutputNode, IfNode, ForNode, IncludeNode
    lexer.py          # source -> List[Token(kind,value,line,col)]
    parser.py         # tokens -> AST  (imports lexer, nodes, errors)
    renderer.py       # AST + context + env -> str  (imports nodes, errors only)
    filters.py        # built-in filter registry: upper, lower, length, default
    environment.py    # Environment class (loader, filter registry, template cache)
  design/
    PRD.md
    USER_STORIES.md
    API_REFERENCE.md  # must include the three §1.6 ambiguity resolutions
    GRAMMAR.md
    EXAMPLES.md
```

Dependency order (strictly one-way, no cycles):
```
__init__ -> environment -> {parser, renderer, filters} -> {lexer, nodes, errors}
```

### 3. Implement `errors.py`

```python
class TemplateError(Exception): ...
class TemplateSyntaxError(TemplateError):
    def __init__(self, msg: str, line: int, col: int) -> None: ...
    msg: str; line: int; col: int
class TemplateRuntimeError(TemplateError): ...
```

### 4. Implement `nodes.py`

Dataclasses only — no rendering logic:
- `TextNode(text, line, col)`
- `OutputNode(expr, filters, line, col)` — expr is a parsed expression tree; filters is a list of `(name, args)` tuples
- `IfNode(branches: list[tuple[expr, body]], else_body, line, col)` — branches is list of `(condition_expr, body_nodes)` tuples
- `ForNode(var: str, expr, body, line, col)`
- `IncludeNode(name: str, line, col)`

Also define expression node types (e.g. `PathExpr`, `LiteralExpr`, `BinaryExpr`, `NotExpr`) — all data-only dataclasses.

### 5. Implement `lexer.py`

Tokenize the source into a flat list of `Token(kind, value, line, col)` objects.

Token kinds: `TEXT`, `INTERPOLATION_START`/`INTERPOLATION_END`, `BLOCK_START`/`BLOCK_END`, `EOF` (or a finer-grained set).

Key rules:
- `line` and `col` are 1-based.
- `col` counts characters; a tab is one column.
- `\r\n` counts as one newline; `\r` is not counted in the column.
- The position of a `{{` or `{%` token is the position of the `{`.
- Raise `TemplateSyntaxError` for unterminated `{{` or `{%`.

### 6. Implement `parser.py`

Consume the token list and produce an AST (list of nodes from `nodes.py`).

Grammar to implement (from §2.1):
```
template      := (TEXT | interpolation | block)*
interpolation := '{{' expr ('|' filter)* '}}'
block         := if_block | for_block | include
if_block      := '{% if' expr '%}' template ('{% elif' expr '%}' template)* ('{% else %}' template)? '{% endif %}'
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
```

Position metadata: carry `line`/`col` from tokens onto AST nodes. Do NOT re-scan source.

Error taxonomy (raise `TemplateSyntaxError` with accurate position):
- Unterminated `{{` or `{%`
- Empty or malformed expression
- Unknown tag name
- Unclosed block at EOF (position = opening tag)
- Mismatched closer (position = closing tag)
- Stray closer (position = closing tag)
- `elif`/`else` outside `if`

### 7. Implement `filters.py`

Built-in filter registry as a dict `{name: callable}`:
- `upper(v)` → `str(v).upper()`
- `lower(v)` → `str(v).lower()`
- `length(v)` → `len(v)`; raise `TemplateRuntimeError` if no length
- `default(v, fallback)` → `fallback` when `v` is undefined/None; pass through defined-but-falsy values (`0`, `""`, `[]`)

### 8. Implement `renderer.py`

Walk the AST and produce a string. Import only `nodes` and `errors` (never `lexer` or `parser`).

Key behaviors:
- **Interpolation:** evaluate expr, apply filters left-to-right, HTML-escape if autoescape enabled, write `str(result)`.
- **Conditionals:** evaluate each branch condition using Python truthiness; render the first true branch body.
- **Loops:** iterate the expression result; bind the loop variable and a `loop` object with `index`, `index0`, `first`, `last`, `length` in a child scope; restore outer bindings at `endfor`.
- **Includes:** resolve name through the environment loader (raise `TemplateRuntimeError` if no loader or name not found); detect cycles by tracking a render stack; render with current context.
- **Undefined handling:** in strict mode raise `TemplateRuntimeError` naming the missing path; in lenient mode resolve to empty string (choice A-1a: empty string on interpolation, falsy in conditions, empty iteration in loops).
- **Security:** refuse `_`-prefixed attribute/key names with `TemplateRuntimeError`; never call `eval`/`exec`/`compile`/`__import__`.
- **Wrap all exceptions:** `KeyError`, `AttributeError`, `IndexError`, `TypeError`, `RecursionError` must not escape; wrap in `TemplateRuntimeError`.
- **Autoescape:** escape `&`, `<`, `>`, `"`, `'` using `html.escape` after filters run; never escape literal text.
- **Context immutability:** do not mutate the caller's context dict.

Whitespace choice (A-2a): strict verbatim preservation — emit all text exactly as written.

### 9. Implement `environment.py`

```python
class Environment:
    def __init__(self, loader=None, filters=None, autoescape: bool = False, strict_undefined: bool = False): ...
    def add_filter(self, name: str, fn) -> None: ...
    def from_string(self, source: str) -> Template: ...
    def get_template(self, name: str) -> Template: ...   # cached per name
    def render(self, name: str, context=None) -> str: ...
```

- `loader` accepts a `Mapping[str, str]` or a `Callable[[str], str]`.
- `autoescape` default: `False` (choice A-3a, matching `Template`'s pinned default).
- Templates produced by `from_string`/`get_template` inherit the environment's `autoescape`, `strict_undefined`, filter registry, and loader reference.
- `get_template` compiles each name exactly once per environment instance (cache).

### 10. Implement `__init__.py`

```python
__all__ = ["Template", "Environment", "TemplateError", "TemplateSyntaxError", "TemplateRuntimeError"]
from .errors import TemplateError, TemplateSyntaxError, TemplateRuntimeError
from .environment import Environment
# Template is defined in environment or a separate template.py
```

`Template.__init__` must tokenize+parse at construction time. `render()` only walks the AST.

### 11. Write the design documents under `scenarios/L4-template-engine/solution/design/`

- `PRD.md` — problem, consumers, scope, non-goals, success metrics
- `USER_STORIES.md` — US-1 through US-7 with acceptance criteria traced to FR-n
- `API_REFERENCE.md` — every public name with signature, parameters, returns, raises, example; **explicitly document the three §1.6 resolutions**: A-1 (lenient = empty string), A-2 (strict verbatim whitespace), A-3 (Environment autoescape default = False)
- `GRAMMAR.md` — the template grammar, operator precedence, error taxonomy with example messages and positions
- `EXAMPLES.md` — ≥ 5 runnable examples covering interpolation, conditionals, loops, includes, filters, autoescape

### 12. Run the smoke suite to verify

```bash
cd scenarios/L4-template-engine
SOLUTION_DIR=$(pwd)/solution pytest tests/smoke -q
```

Fix any failures before proceeding.

### 13. Run the acceptance suite

```bash
cd scenarios/L4-template-engine
SOLUTION_DIR=$(pwd)/solution pytest tests/acceptance -q
```

Target: ≥ 95% pass rate. Iterate on failures until the gate is met.

## Done when

The following command exits 0 AND the acceptance pass rate is ≥ 95%:

```bash
cd scenarios/L4-template-engine && SOLUTION_DIR=$(pwd)/solution pytest tests/smoke -q && SOLUTION_DIR=$(pwd)/solution pytest tests/acceptance -q --tb=no 2>&1 | tail -5
```

Specifically:
- All 7 smoke tests pass.
- The acceptance suite reports ≥ 95% passing assertions (hard gate: `acceptance_pass >= 0.95`).

## Final step (REQUIRED)

After the work is done and the check above passes, write the file `artifacts/core_engine.done` containing exactly `core_engine:ok` and nothing else.

This marker file is how the batch orchestrator confirms the lane finished. It must be the LAST action taken — write it only after the acceptance suite gate is confirmed passing.
