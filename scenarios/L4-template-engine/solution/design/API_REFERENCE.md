# API Reference — template_engine

## Section 1.6 Ambiguity Resolutions

Three behaviours were deliberately under-specified in the requirements.
This library resolves them as follows, applied consistently throughout the
codebase:

| # | Ambiguity | Resolution chosen | Effect |
|---|-----------|-------------------|--------|
| **A-1** | What a missing name evaluates to in **lenient** mode | **(a) empty string** on interpolation; **falsy** in conditions; **empty iteration** in loops | `{{ missing }}` → `""`, `{% if missing %}` → false branch, `{% for i in missing %}` → no iterations |
| **A-2** | **Whitespace control** around block tags | **(a) strict literal preservation** — all text emitted verbatim | Templates with no block tags compare byte-exact; templates with block tags compare after per-line whitespace normalisation |
| **A-3** | **Autoescape default** on `Environment` | **(a) default `False`**, matching `Template`'s pinned default | `Environment()` does not escape; `Environment(autoescape=True)` does |

---

## Exception Hierarchy

```
TemplateError (base)
├── TemplateSyntaxError   — raised at compile time
└── TemplateRuntimeError  — raised at render time
```

No other exception type crosses the public API boundary.

---

## `TemplateError`

```python
class TemplateError(Exception):
    """Base class for every exception raised by the template engine."""
```

**Hierarchy:** `Exception → TemplateError`

---

## `TemplateSyntaxError`

```python
class TemplateSyntaxError(TemplateError):
    def __init__(self, msg: str, line: int, col: int) -> None: ...
    msg: str   # human-readable, names the offending construct
    line: int  # 1-based line of the offending construct
    col: int   # 1-based column of the offending construct
```

**Raised:** At `Template(source)` construction time when the source is malformed.

**Attributes:**
- `msg` — Non-empty string naming the offending construct (e.g. `"unclosed 'for' block"`).
- `line` — 1-based line number.  A tab counts as one column; `\r\n` counts as one newline.
- `col` — 1-based column number.

**Position pinning rules:**
- Position is the first character of the offending construct (the `{` of `{{` or `{%`).
- For an unclosed block at EOF, the position is the **opening** tag.
- For a mismatched or stray closer, the position is the **closing** tag.

**Example:**
```python
from template_engine import Template, TemplateSyntaxError
try:
    Template("Line1\n{{ oops")
except TemplateSyntaxError as exc:
    print(exc.line, exc.col, exc.msg)  # 2 1 unterminated '{{'
```

---

## `TemplateRuntimeError`

```python
class TemplateRuntimeError(TemplateError):
    """Raised during rendering."""
```

**Raised for:** unknown filter, filter failure, missing include, include cycle,
strict-undefined access, non-iterable loop target, sandboxed `_`-prefixed
attribute access, and any other runtime failure.

---

## `Template`

```python
class Template:
    def __init__(
        self,
        source: str,
        *,
        autoescape: bool = False,          # PINNED default (A-3)
        strict_undefined: bool = False,    # PINNED default
        environment: "Environment | None" = None,
    ) -> None: ...
    def render(self, context: Mapping[str, Any] | None = None) -> str: ...
```

### `__init__`

Tokenises and parses *source* at construction time.  `render()` performs no
re-parsing.

**Parameters:**
- `source` — The raw template source string.
- `autoescape` — HTML-escape interpolated values when `True` (default: `False`, pinned — see A-3).
- `strict_undefined` — Raise `TemplateRuntimeError` on undefined names when `True` (default: `False`).
- `environment` — The owning `Environment`, or `None`.

**Raises:** `TemplateSyntaxError` if *source* contains a syntax error.

### `render`

Walk the compiled AST and produce a string.

**Parameters:**
- `context` — A `Mapping[str, Any]` of variable bindings.  `None` is equivalent to `{}`.

**Returns:** The rendered string.

**Raises:** `TemplateRuntimeError` on any runtime failure.

**Notes:**
- Does not mutate the caller's `context` mapping.
- Multiple calls are independent; no state leaks between renders.

**Example:**
```python
from template_engine import Template
tmpl = Template("Hello {{ name }}!")
print(tmpl.render({"name": "World"}))  # Hello World!
print(tmpl.render({"name": "Alice"}))  # Hello Alice!
```

---

## `Environment`

```python
class Environment:
    def __init__(
        self,
        loader: Mapping[str, str] | Callable[[str], str] | None = None,
        filters: Mapping[str, Callable[..., Any]] | None = None,
        autoescape: bool = False,          # A-3: default False
        strict_undefined: bool = False,
    ) -> None: ...
    def add_filter(self, name: str, fn: Callable[..., Any]) -> None: ...
    def from_string(self, source: str) -> Template: ...
    def get_template(self, name: str) -> Template: ...
    def render(self, name: str, context: Mapping[str, Any] | None = None) -> str: ...
```

### `__init__`

**Parameters:**
- `loader` — A `Mapping[str, str]` of name → source, or a callable `(name) -> source`.  `None` means no loader.
- `filters` — Additional filters to register on top of the built-ins.
- `autoescape` — Default `False` (choice A-3a).  Templates produced by this environment inherit this setting.
- `strict_undefined` — Default `False`.

### `add_filter`

Register a filter function under *name*.  A user filter may shadow a built-in.

**Parameters:**
- `name` — Filter name used in templates.
- `fn` — The callable to invoke.

### `from_string`

Compile *source* and return a `Template` bound to this environment.

**Returns:** A compiled `Template` inheriting this environment's `autoescape`, `strict_undefined`, filter registry, and loader.

**Raises:** `TemplateSyntaxError` on syntax error.

### `get_template`

Return a compiled `Template` for *name*, cached per environment instance.  Each name is compiled at most once.

**Raises:**
- `TemplateRuntimeError` if the loader is `None` or the name is not found.
- `TemplateSyntaxError` if the loaded source contains a syntax error.

### `render`

Compile (or retrieve from cache) and render the named template.

**Raises:** `TemplateRuntimeError` or `TemplateSyntaxError`.

**Example:**
```python
from template_engine import Environment
env = Environment(loader={"greet": "Hello {{ name }}!"})
print(env.render("greet", {"name": "World"}))  # Hello World!
```

---

## Built-in Filters

| Filter | Signature | Behaviour |
|--------|-----------|-----------|
| `upper` | `upper(v)` | `str(v).upper()` |
| `lower` | `lower(v)` | `str(v).lower()` |
| `length` | `length(v)` | `len(v)`; raises `TemplateRuntimeError` if `v` has no length |
| `default` | `default(v, fallback)` | Returns `fallback` when `v` is undefined or `None`; defined-but-falsy values (`0`, `""`, `[]`) pass through unchanged |

---

## Loop Metadata

Inside a `{% for %}` body, the `loop` variable exposes:

| Field | Type | Meaning |
|-------|------|---------|
| `loop.index` | int | 1-based position |
| `loop.index0` | int | 0-based position |
| `loop.first` | bool | `True` on the first iteration |
| `loop.last` | bool | `True` on the final iteration |
| `loop.length` | int | Total number of items |

Nested loops shadow the outer `loop` for the duration of the inner body.
