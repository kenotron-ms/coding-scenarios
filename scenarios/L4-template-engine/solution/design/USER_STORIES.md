# User Stories — template_engine

## US-1 — Compile once, render many (FR-8)

**As an** integrating developer,  
**I want to** compile a template once and render it many times with different contexts,  
**so that** per-request rendering is cheap and no state leaks between renders.

**Acceptance criteria:**
- `Template(source)` performs tokenisation and parsing exactly once at construction.
- `render()` walks the already-built AST; no re-tokenisation occurs.
- Repeated `render()` calls with different contexts produce independent results.
- `Environment.get_template(name)` returns the same compiled object on every call for the same name.

**Traced to:** FR-8

---

## US-2 — Custom filters and partials via Environment (FR-5, FR-4, FR-10)

**As an** integrating developer,  
**I want to** register my own filters and partials on an `Environment`,  
**so that** shared formatting and layout fragments live in one place instead of being duplicated per template.

**Acceptance criteria:**
- `Environment(filters={...})` and `Environment.add_filter(name, fn)` register user filters.
- A user filter may shadow a built-in filter by name.
- `Environment(loader={...})` or `Environment(loader=callable)` supplies partials for `{% include %}`.
- Templates produced by `from_string` / `get_template` inherit the environment's filter registry and loader.

**Traced to:** FR-4, FR-5, FR-10

---

## US-3 — Autoescape for HTML safety (FR-6, NFR-3)

**As an** integrating developer rendering user-supplied data into HTML,  
**I want** autoescaping I can turn on,  
**so that** a value containing `<script>` is inert in the output.

**Acceptance criteria:**
- `Template(source, autoescape=True)` escapes `&`, `<`, `>`, `"`, `'` in interpolated values.
- `Environment(autoescape=True)` applies the same escaping to all templates it produces.
- Literal template text is **never** escaped.
- An explicit `autoescape` argument always wins over an inherited default.

**Traced to:** FR-6, NFR-3

---

## US-4 — Unified exception type (FR-9, NFR-2)

**As an** integrating developer,  
**I want** every failure to surface as one of the library's own exception types,  
**so that** my error handling is a single `except TemplateError` rather than a guessing game about `KeyError` vs `AttributeError` vs `RecursionError`.

**Acceptance criteria:**
- All compile-time errors raise `TemplateSyntaxError(msg, line, col)`.
- All render-time errors raise `TemplateRuntimeError`.
- `KeyError`, `AttributeError`, `IndexError`, `TypeError`, `RecursionError` never escape the public API.
- Include cycles are detected and raise `TemplateRuntimeError` (never `RecursionError`).

**Traced to:** FR-9, NFR-2

---

## US-5 — Position-accurate syntax errors (FR-9, NFR-2)

**As a** template author,  
**I want** a syntax error to tell me the line and column of the tag I broke,  
**so that** I can fix a 400-line template without bisecting it.

**Acceptance criteria:**
- `TemplateSyntaxError` carries `msg` (non-empty, names the offending construct), `line` (1-based), and `col` (1-based).
- The position is the first character of the offending construct (the `{` of `{{` or `{%`).
- For an unclosed block at EOF, the position is the opening tag, not EOF.
- For a mismatched or stray closer, the position is the closing tag.

**Traced to:** FR-9, NFR-2

---

## US-6 — Loop metadata (FR-3)

**As a** template author,  
**I want** loops to expose position metadata (`loop.index`, `loop.first`, `loop.last`),  
**so that** I can build tables and comma-separated lists without arithmetic in the template.

**Acceptance criteria:**
- Inside a `{% for %}` body, `loop.index` (1-based), `loop.index0` (0-based), `loop.first`, `loop.last`, and `loop.length` are available.
- Nested loops shadow the outer `loop` object for the duration of the inner body.
- The outer `loop` is restored at `{% endfor %}`.

**Traced to:** FR-3

---

## US-7 — Strict undefined mode (FR-7)

**As an** integrating developer in a strict environment,  
**I want** a missing variable to raise rather than silently render nothing,  
**so that** broken templates fail in CI rather than in production output.

**Acceptance criteria:**
- `Template(source, strict_undefined=True)` raises `TemplateRuntimeError` naming the missing path.
- `Environment(strict_undefined=True)` propagates the same behaviour to all templates it produces.
- In lenient mode (the default), a missing name evaluates to empty string on interpolation, falsy in conditions, and empty iteration in loops.
- The `default` filter intercepts undefined values in lenient mode.

**Traced to:** FR-7
