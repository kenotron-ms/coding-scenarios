# L4 — Template Engine — SPEC (prompt handed to the strategy under test)

Implement a small, dependency-free **text/HTML template engine library** in a
package `template_engine/` in your workspace. The harness imports these names
from the package root (see `manifest.yaml`, entrypoint `template_engine`):

```python
# template_engine/__init__.py — public surface
__all__ = [
    "Template", "Environment",
    "TemplateError", "TemplateSyntaxError", "TemplateRuntimeError",
]

class TemplateError(Exception): ...
class TemplateSyntaxError(TemplateError):
    def __init__(self, msg: str, line: int, col: int) -> None: ...
    msg: str; line: int; col: int          # 1-based line/col of the offending construct
class TemplateRuntimeError(TemplateError): ...

class Template:
    def __init__(self, source: str, *, autoescape: bool = False,
                 strict_undefined: bool = False,
                 environment: "Environment | None" = None) -> None: ...
    def render(self, context: dict | None = None) -> str: ...

class Environment:
    def __init__(self, loader=None, filters=None,
                 autoescape: bool = False, strict_undefined: bool = False) -> None: ...
    def add_filter(self, name: str, fn) -> None: ...
    def from_string(self, source: str) -> "Template": ...
    def get_template(self, name: str) -> "Template": ...
    def render(self, name: str, context: dict | None = None) -> str: ...
```

## The template language (this is the whole grammar — nothing outside it evaluates)

- **Interpolation** `{{ expr }}` writes `str(value)`. Paths support dotted
  attribute access and bracket index/key access, chained arbitrarily deep:
  `{{ user.name }}`, `{{ items[0] }}`, `{{ a.b[1].c }}`. For `a.b`, resolve a
  **mapping key first, then an attribute**.
- **Conditionals** `{% if expr %} … {% elif expr %} … {% else %} … {% endif %}`
  with zero-or-more `elif` and an optional `else`. Condition grammar: comparisons
  (`== != < <= > >=`), boolean `and`/`or`/`not` (precedence `not > and > or`),
  literals (`"s"`, `12`, `1.5`, `true`, `false`, `none`), and paths.
- **Loops** `{% for x in expr %} … {% endfor %}` over any iterable. Inside the
  body, `loop` exposes `index` (1-based), `index0`, `first`, `last`, `length`.
  Loops nest; an inner loop shadows the outer `loop`/var and the outer binding is
  restored at `endfor`. An empty iterable renders nothing.
- **Includes** `{% include "name" %}` resolves `name` through the `Environment`
  loader, renders it with the **current** context (including active loop
  bindings), and splices it in. Includes are cached per environment and may nest.
- **Filters** `{{ value | upper }}` apply left-to-right and take literal args:
  `{{ v | default("n/a") | upper }}`. Built-ins: `upper`, `lower`, `length`,
  `default` (returns its fallback when the value is undefined or `None`;
  defined-but-falsy `0`/`""`/`[]` pass through). Register more via
  `Environment(filters={...})` or `add_filter`; a user filter may shadow a
  built-in. An unknown or raising filter → `TemplateRuntimeError` naming it.
- **Autoescape** — when enabled, every interpolated value (after its filters) is
  HTML-escaped (`& < > " '`) before being written; literal template text is
  **never** escaped. A value containing `<script>` must be inert in the output.
- **Undefined handling** — a **strict** mode raises `TemplateRuntimeError` on a
  missing name; a **lenient** mode does not raise. Selectable on both `Template`
  and `Environment`.

## Contract

- **Compile once, render many.** `Template(source)` tokenizes and parses at
  construction; `render()` only walks the built AST — no re-parsing — and leaks
  no state between calls. `Environment.get_template(name)` compiles once per name.
- **Position-aware errors.** A malformed template raises `TemplateSyntaxError` at
  construction with an accurate 1-based `line`/`col` pointing at the **first
  character of the offending construct** (the `{` of `{{`/`{%`); an unclosed
  block points at its **opening** tag; a mismatched/stray closer points at the
  closer. `col` counts characters (a tab is one column); the `\r` of `\r\n` is
  not counted. Runtime failures raise `TemplateRuntimeError`; **no** other
  exception type may cross the public API (`KeyError`, `AttributeError`,
  `RecursionError` from include cycles, etc. are all wrapped).
- **Composition.** Decompose into a tokenizer → parser/AST → renderer →
  environment pipeline with **one-way** module dependencies (no cycles; the
  renderer consumes the AST only and never re-invokes the lexer/parser). Position
  metadata originates in the lexer and is carried on tokens and AST nodes.
- **Security & purity.** Standard library only, Python ≥ 3.11. `eval`, `exec`,
  `compile`, and `__import__` are **forbidden** anywhere — a static scan enforces
  it. Path resolution must **refuse `_`-prefixed / dunder access** (`{{
  x.__class__ }}` → `TemplateRuntimeError`). The engine performs no I/O of its own
  (loaders are consumer-supplied). `ruff` + `pyright` clean; type hints on all
  public signatures.

## Ambiguities you must resolve (pick one each, apply consistently, document it)

1. **Lenient-undefined value** — what a missing name yields in lenient mode:
   (a) empty string on interpolation, falsy in conditions, empty iteration in
   loops; or (b) emit nothing at all with conditions/loops defined to match.
   Either is fine if **uniform** across interpolation, conditions, and loops.
   `default` must still intercept it; strict mode must still raise.
2. **Whitespace control** around block tags — (a) strict verbatim preservation,
   (b) a lone block-tag line consumes its trailing newline, or (c) `{%- … -%}`
   trim markers. A template with **no** block tags must be byte-exact either way.
3. **Environment autoescape default** — (a) `False` (matching `Template`'s pinned
   default) or (b) `True`. An explicit setting always wins over an inherited one;
   `Template(source)` with no argument does **not** escape.

You are given `tests/smoke/` to check your work. Held-out `acceptance` and
`adversarial` suites grade you (see `EVALUATION.md`). **Entrypoint:** the harness
imports `template_engine` from your workspace.
