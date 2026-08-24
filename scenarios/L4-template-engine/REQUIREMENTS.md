# L4 — Template Engine — REQUIREMENTS

> Follows `framework/REQUIREMENTS_TEMPLATE.md`; scored per
> `framework/RUBRIC_FRAMEWORK.md`; verified per `framework/VERIFICATION_CONTRACT.md`;
> artifact obligations per `framework/ARTIFACT_GRADIENT.md` row L4.

## 0. Scenario Summary
- **Level:** L4
- **Codename / dir:** `L4-template-engine`
- **One-liner:** Build a small text/HTML template engine library with variable
  interpolation, conditionals, loops, partial includes, and filters, exposing a
  clean public API with position-aware error messages.
- **New difficulty introduced:** First **multi-module library**. The rung is not
  "more code" — it is **component composition behind a stable public API**. The
  solution must decompose into a tokenizer → parser/AST → renderer → environment
  pipeline with one-way dependencies, and it must report **line/column-accurate
  errors**, which forces position metadata to be carried correctly across every
  component boundary. L0–L3 could each be held in one head as one artifact; L4
  cannot.
- **Estimated reference solution size:** 450–800 LoC across 7–9 files (orienting
  only; not a target).
- **Time budget:** 60 minutes wall-clock.
- **Iteration budget:** soft 14, hard 35 edit→verify cycles.
- **Intervention budget:** 0.

## 1. Product Requirements
- **1.1 Problem statement** — Applications routinely need to generate text and
  HTML (emails, reports, config files, static pages) from data. Pulling a large
  third-party engine into a small service is disproportionate, and hand-rolled
  string formatting collapses the moment conditionals or loops appear. This
  library provides a dependency-free, embeddable template engine that covers the
  90% case — interpolation, conditionals, loops, includes, filters — and, when a
  template is wrong, tells the template author **exactly where** in terms of line
  and column rather than emitting a Python traceback from deep inside the parser.
- **1.2 Target users / personas** — Personas are **N/A** at this rung
  (`ARTIFACT_GRADIENT.md` L4 marks personas `—`), but the library has two
  distinct *consumer roles* that the API must serve, and they are the audience
  for §5's product artifacts:
  | Role | Relationship to the library | What they need |
  |------|-----------------------------|----------------|
  | **Integrating developer** | Imports the package, wires an `Environment`, registers filters, calls `render` | A small, stable, typed, docstringed API; predictable exceptions; no surprise I/O |
  | **Template author** | Writes `.html`/`.txt` templates; may not read the engine's source | Familiar syntax; errors that name a line, a column, and the offending construct |
- **1.3 User stories**
  - **US-1** As an *integrating developer*, I want to compile a template once and
    render it many times with different contexts, so that per-request rendering
    is cheap and no state leaks between renders.
  - **US-2** As an *integrating developer*, I want to register my own filters and
    partials on an `Environment`, so that shared formatting and layout fragments
    live in one place instead of being duplicated per template.
  - **US-3** As an *integrating developer* rendering user-supplied data into HTML,
    I want autoescaping I can turn on, so that a value containing `<script>` is
    inert in the output.
  - **US-4** As an *integrating developer*, I want every failure to surface as one
    of the library's own exception types, so that my error handling is a single
    `except TemplateError` rather than a guessing game about `KeyError` vs
    `AttributeError` vs `RecursionError`.
  - **US-5** As a *template author*, I want a syntax error to tell me the line and
    column of the tag I broke, so that I can fix a 400-line template without
    bisecting it.
  - **US-6** As a *template author*, I want loops to expose position metadata
    (`loop.index`, `loop.first`, `loop.last`), so that I can build tables and
    comma-separated lists without arithmetic in the template.
  - **US-7** As an *integrating developer* in a strict environment, I want a
    missing variable to raise rather than silently render nothing, so that broken
    templates fail in CI rather than in production output.
- **1.4 Functional requirements**
  - **FR-1 Interpolation and lookup.** `{{ expr }}` evaluates `expr` against the
    render context and writes `str(value)` into the output. Paths support dotted
    attribute access and bracket index/key access, chained arbitrarily deep:
    `{{ user.name }}`, `{{ items[0] }}`, `{{ a.b[1].c }}`. Resolution order for
    `a.b` is **mapping key first, then attribute**; `a[k]` is item access for
    mappings and sequences (integer literals index, string literals key).
    Literal text outside tags is emitted verbatim and byte-for-byte unchanged.
  - **FR-2 Conditionals.** `{% if expr %} … {% elif expr %} … {% else %} … {% endif %}`
    with zero-or-more `elif` arms and an optional `else`. Truthiness is Python
    truthiness. Supported condition grammar is bounded (§2.1): comparisons
    (`== != < <= > >=`), boolean `and`/`or`/`not`, literals, and paths. Blocks
    nest to arbitrary depth.
  - **FR-3 Loops.** `{% for x in expr %} … {% endfor %}` iterates any Python
    iterable, binding `x` in a child scope that is discarded at `endfor` (an
    outer `x` is restored, not clobbered). Inside the body, `loop` exposes
    metadata (§2.1 table). Loops nest, and a nested loop's `loop` shadows the
    outer one for the duration of the inner body. Iterating an empty iterable
    produces no body output and is not an error.
  - **FR-4 Partial includes.** `{% include "name" %}` resolves `name` through the
    `Environment` loader, compiles it (cached per environment), renders it with
    the **current** context including any active loop bindings, and splices the
    result in place. Includes nest. A template that is not reachable through the
    loader, or an include cycle (direct or indirect), raises
    `TemplateRuntimeError` — never `KeyError` and never `RecursionError`.
    A `Template` constructed without an environment that contains an `{% include %}`
    raises `TemplateRuntimeError` at render time with a message saying no loader
    is configured.
  - **FR-5 Filters.** `{{ value | upper }}` applies a named filter to a value.
    Filters chain left-to-right (`{{ v | default("n/a") | upper }}`) and accept
    literal arguments (`{{ v | default("n/a") }}`). The built-in set is
    `upper`, `lower`, `length`, `default` (§2.1 semantics table). Consumers
    register additional filters via `Environment(filters={...})` or
    `Environment.add_filter(name, fn)`; a user filter may shadow a built-in.
    An unknown filter name, or a filter that raises, produces
    `TemplateRuntimeError` naming the filter (the original exception attached as
    `__cause__`).
  - **FR-6 Autoescape.** When autoescape is enabled, every *interpolated* value —
    after all filters have run — is HTML-escaped (`&`, `<`, `>`, `"`, `'`) before
    being written. Literal template text is **never** escaped. When disabled,
    values are written unescaped. Autoescape is configurable per `Template` and
    per `Environment` (§2.1); an explicit setting always wins over an inherited
    default.
  - **FR-7 Undefined handling.** The engine supports a strict mode and a lenient
    mode for names that are absent from the context. **Strict:** resolving an
    undefined name raises `TemplateRuntimeError` naming the missing path.
    **Lenient:** rendering proceeds without raising, per the resolution the agent
    picks in §1.6/A-1. The `default` filter intercepts undefined values in
    lenient mode and supplies its argument. The mode is selectable on both
    `Template` and `Environment`.
  - **FR-8 Compile once, render many.** `Template(source)` performs tokenization
    and parsing **at construction**. `render()` walks the already-built AST and
    performs no re-tokenization or re-parsing. A `Template` is reusable: calling
    `render()` repeatedly with different contexts yields results that depend only
    on the context passed, with no leakage of bindings, loop state, or output
    buffers between calls. `Environment.get_template(name)` returns a cached
    compiled template for repeat calls with the same name.
  - **FR-9 Position-aware errors.** Any malformed template raises
    `TemplateSyntaxError` **at construction time** carrying `msg`, `line`, and
    `col` (both 1-based, §3 NFR-2 defines the pinning rules). Covered classes:
    unterminated `{{`/`{%`, empty or malformed expression, unknown tag name,
    unclosed block at EOF, mismatched closer (`{% if %}…{% endfor %}`), stray
    closer (`{% endif %}` with no opener), `elif`/`else` outside an `if`.
    Runtime failures raise `TemplateRuntimeError`. No other exception type may
    cross the public API boundary.
  - **FR-10 Environment.** `Environment` is the composition root: it owns the
    loader (partials), the filter registry (built-ins plus user filters), the
    autoescape and strictness defaults, and the compiled-template cache. It can
    compile from a string (`from_string`), fetch by name (`get_template`), and
    render by name in one call (`render`). Templates it produces inherit its
    filters, loader, and defaults.
- **1.5 Out of scope** — Template inheritance (`{% extends %}` / `{% block %}`);
  macros and `{% call %}`; assignment tags (`{% set %}`); comments (`{# … #}`);
  `{% for %}…{% else %}`; arbitrary Python expressions, arithmetic, slicing,
  function calls, or method calls inside templates; filter arguments that are
  themselves expressions (literals only); context-aware escaping (attribute vs.
  URL vs. JS contexts — text-level HTML escaping only); an escape hatch such as
  `| safe` (permitted as a documented extension, never tested); async or
  streaming rendering; loading templates from disk by the engine itself (the
  loader is supplied by the consumer); i18n; a CLI. Acceptance and adversarial
  suites never use out-of-scope syntax.
- **1.6 Ambiguities the agent must resolve** — Three behaviors are deliberately
  under-specified. Each must be **resolved, applied consistently, and documented**
  in `design/API_REFERENCE.md` and the relevant docstring. Acceptance pins only
  behaviors that are independent of the choice, **plus** the consistency of the
  choice.
  | # | Ambiguity | Acceptable resolutions | What acceptance pins regardless |
  |---|-----------|------------------------|---------------------------------|
  | **A-1** | What a missing name evaluates to in **lenient** mode | (a) empty string on interpolation, falsy in conditions, empty iteration in loops; (b) the interpolation emits nothing at all, with conditions/loops defined to match. Either is fine if uniform across interpolation, conditions, and loop iterables. | Lenient mode never raises for a missing name; the literal tag source (`{{ missing }}`) never appears in output; `default` supplies its fallback; strict mode raises `TemplateRuntimeError`; the same policy is observed in all three positions. |
  | **A-2** | **Whitespace control** around block tags | (a) strict literal preservation — all text emitted verbatim; (b) a block tag alone on a line consumes its own trailing newline (and optionally its leading indentation); (c) explicit `{%- … -%}` trim markers. | Templates with **no** block tags compare byte-exact. Templates **with** block tags compare after per-line whitespace normalization. The policy is identical for `if` bodies and `for` bodies, and identical across repeated renders of the same template. |
  | **A-3** | The **autoescape default** on `Environment` and how it propagates | (a) default `False`, matching `Template`'s pinned default; (b) default `True` ("HTML-safe by default"), which is defensible for an HTML-oriented engine. | An explicit `autoescape=True` escapes and `autoescape=False` does not, at both `Template` and `Environment` level; a template obtained from an environment inherits that environment's setting unless overridden; `Template(source)` with no argument does **not** escape (that default is pinned in §2.1, not ambiguous). |

## 2. Technical Requirements
- **2.1 Interface / API contract** — The public surface is the package root. Names
  below are exact; signatures are the contract the harness imports.
  ```python
  # solution/template_engine/__init__.py
  __all__ = [
      "Template", "Environment",
      "TemplateError", "TemplateSyntaxError", "TemplateRuntimeError",
  ]

  class TemplateError(Exception):
      """Base class for every exception this library raises."""

  class TemplateSyntaxError(TemplateError):
      def __init__(self, msg: str, line: int, col: int) -> None: ...
      msg: str    # human-readable, names the offending construct
      line: int   # 1-based line of the offending construct
      col: int    # 1-based column of the offending construct

  class TemplateRuntimeError(TemplateError):
      """Raised during render: unknown filter, filter failure, missing
      include, include cycle, strict-undefined, non-iterable loop target."""

  class Template:
      def __init__(
          self,
          source: str,
          *,
          autoescape: bool = False,          # PINNED default
          strict_undefined: bool = False,    # PINNED default
          environment: "Environment | None" = None,
      ) -> None: ...
      def render(self, context: Mapping[str, Any] | None = None) -> str: ...

  class Environment:
      def __init__(
          self,
          loader: Mapping[str, str] | Callable[[str], str] | None = None,
          filters: Mapping[str, Callable[..., Any]] | None = None,
          autoescape: bool = ...,            # AMBIGUOUS — see §1.6 A-3
          strict_undefined: bool = False,    # PINNED default
      ) -> None: ...
      def add_filter(self, name: str, fn: Callable[..., Any]) -> None: ...
      def from_string(self, source: str) -> Template: ...
      def get_template(self, name: str) -> Template: ...
      def render(self, name: str, context: Mapping[str, Any] | None = None) -> str: ...
  ```
  Both loader forms are required: a plain `Mapping[str, str]` of name → source,
  and a callable `(name) -> source`. `render(None)` is equivalent to `render({})`.
  Accepting `**kwargs` on `render` is a permitted extension; acceptance uses the
  mapping form only.

  **Template grammar** (this is the whole language — nothing outside it is
  evaluated, ever):
  ```
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
  ```
  Precedence: `not` > comparison > `and` > `or`. Whitespace inside tags is
  insignificant (`{%if x%}` parses identically to `{% if x %}`). String literals
  accept single or double quotes.

  **Loop metadata** — available as `loop.<field>` inside a `for` body:
  | Field | Type | Meaning |
  |-------|------|---------|
  | `loop.index` | int | 1-based position |
  | `loop.index0` | int | 0-based position |
  | `loop.first` | bool | True on the first iteration |
  | `loop.last` | bool | True on the final iteration |
  | `loop.length` | int | Total number of items |

  **Built-in filters** — semantics pinned (these are not §1.6 ambiguities):
  | Filter | Signature | Behavior |
  |--------|-----------|----------|
  | `upper` | `upper(v)` | `str(v).upper()` |
  | `lower` | `lower(v)` | `str(v).lower()` |
  | `length` | `length(v)` | `len(v)`; `TemplateRuntimeError` if `v` has no length |
  | `default` | `default(v, fallback)` | Returns `fallback` when `v` is undefined or `None`; **defined-but-falsy values (`0`, `""`, `[]`) pass through unchanged** |
- **2.2 Architecture constraints** — The composition is the point of this rung and
  is a graded requirement, not a suggestion. Minimum module decomposition, with a
  strictly **one-way** dependency graph (no module may import a module above it,
  no cycles):
  ```
  errors.py       leaf   TemplateError / TemplateSyntaxError / TemplateRuntimeError
  nodes.py        leaf   AST node types (data only, no rendering logic)
  lexer.py               source -> [Token(kind, value, line, col)]
  parser.py              tokens -> AST                  (imports lexer, nodes, errors)
  renderer.py            AST + context + env -> str     (imports nodes, errors)
  filters.py             built-in filter registry       (imports errors)
  environment.py         loader + filters + defaults + template cache
  __init__.py            public surface only: re-exports §2.1 names

  __init__ -> environment -> {parser, renderer, filters} -> {lexer, nodes, errors}
  ```
  Additional constraints:
  - The renderer consumes the AST only. It must not see raw source text and must
    not re-invoke the lexer or parser.
  - Position metadata (`line`, `col`) originates in the lexer and is carried on
    tokens **and** AST nodes; the parser must not recompute positions by
    re-scanning the source.
  - `eval`, `exec`, `compile`, `__import__`, and `getattr` on dunder/underscore
    names are **forbidden** anywhere in the solution.
  - Standard library only. No filesystem or network access at import or at render
    time (loaders are consumer-supplied; the engine performs no I/O of its own).
  - Importing the package must have no side effects beyond defining names.
- **2.3 Data model** — No persistence. The in-memory model is the token stream and
  the AST; both are part of the internal contract that makes §2.2 verifiable.
  | Structure | Fields | Notes |
  |-----------|--------|-------|
  | `Token` | `kind`, `value`, `line`, `col` | `kind` ∈ {text, interpolation, block, eof} (or finer); positions 1-based |
  | `TextNode` | `text`, `line`, `col` | Emitted verbatim |
  | `OutputNode` | `expr`, `filters`, `line`, `col` | Interpolation with its filter chain |
  | `IfNode` | `branches: [(expr, body)]`, `else_body`, `line`, `col` | `elif` arms are additional branches |
  | `ForNode` | `var`, `expr`, `body`, `line`, `col` | Body rendered in a child scope |
  | `IncludeNode` | `name`, `line`, `col` | Resolved via the environment loader |
  Node type *names* are not part of the public API and may differ; the required
  property is that an AST of typed nodes carrying positions exists between parser
  and renderer.
- **2.4 Technology constraints** — Python ≥ 3.11, standard library only. `html`
  (for `html.escape`), `dataclasses`, `enum`, `re`, and `typing` are permitted and
  expected. **Forbidden:** `jinja2`, `mako`, `chameleon`, Django templates, or any
  other third-party templating package; `string.Template` as the interpolation
  engine; any use of `eval`/`exec`/`compile` to evaluate template expressions.
  Type hints on all public signatures.
- **2.5 Entrypoint contract** — `kind: python-module`, `target:
  solution.template_engine`. The harness imports the §2.1 names from the package
  root and exercises them directly; that public API **is** the real path
  (`VERIFICATION_CONTRACT.md` §3). Mirrored in `manifest.yaml`:
  ```yaml
  entrypoint: {kind: python-module, target: solution.template_engine}
  budgets:   {wall_clock_s: 3600, iterations_soft: 14, iterations_hard: 35, interventions: 0}
  gate:      {acceptance_floor: 0.95}
  ```

## 3. Non-Functional Requirements
- **NFR-1 Performance** — Compile once, render many.
  - Parsing happens exactly once per `Template` construction; `render()` performs
    zero tokenization/parsing. Measured: for a ~200-node template, the mean cost
    of 1,000 `render()` calls on one instance must be **≤ 40%** of the mean cost
    of 1,000 construct-plus-render cycles.
  - `Environment.get_template(name)` compiles a given name at most once per
    environment.
  - Rendering is **linear** in (template nodes × iterations) + output length. No
    quadratic string building: a nested loop producing ≥ 100,000 characters of
    output completes in < 1 s on the reference runner.
  - Timing assertions are `flaky-guarded` (tolerances + repeated trials) per
    `VERIFICATION_CONTRACT.md` §4.
- **NFR-2 Reliability & error handling** — A malformed template must always
  produce a `TemplateSyntaxError` with an **accurate** position, never a bare
  Python traceback. Position pinning rules, so line/col are objectively testable:
  - `line` and `col` are **1-based**; `col` counts characters (a tab is one
    column); `\n` and `\r\n` both terminate a line and the `\r` is not counted.
  - The reported position is that of the **first character of the offending
    construct** — the `{` of `{{` or `{%` for tag-level errors.
  - For an **unclosed block at EOF**, the position reported is the **opening**
    tag, not EOF.
  - For a **mismatched or stray closer**, the position reported is the closing
    tag.
  - `msg` names the construct or token at fault (e.g. `unknown tag 'forr'`,
    `unclosed 'for' block`).
  - At render time, every internal failure is wrapped: `KeyError`,
    `AttributeError`, `IndexError`, `TypeError`, and `RecursionError` must not
    escape. Include cycles are detected explicitly and raised as
    `TemplateRuntimeError` naming the cycle — hitting Python's recursion limit is
    a failure of this NFR.
  - Rendering is side-effect-free with respect to the caller's context: `render()`
    must not mutate the mapping it is given.
- **NFR-3 Security** — The engine executes templates, so it is an injection
  surface twice over.
  - **Output injection:** with autoescape enabled, no interpolated value can
    introduce markup. `&`, `<`, `>`, `"`, `'` are escaped after the filter chain
    runs, so a filter cannot launder unsafe content into the output.
  - **No arbitrary code execution:** template expressions are evaluated by the
    engine's own bounded grammar (§2.1). No `eval`/`exec`/`compile` of template
    text, under any circumstance, including "just for the condition expression."
  - **Sandboxed attribute access:** path resolution must refuse names beginning
    with `_` (including all dunders), raising `TemplateRuntimeError`. `{{
    x.__class__ }}` and `{{ ''.__class__.__mro__ }}` must not resolve — the
    classic sandbox-escape chain is closed by construction.
  - The engine itself opens no files, sockets, or subprocesses.
- **3.4 Accessibility** — **N/A** — the library has no UI. The accessibility of
  markup produced by a consumer's templates is the consumer's content decision;
  the engine neither generates nor rewrites semantic structure.
- **NFR-4 Maintainability** — Module boundaries exactly as §2.2, with the
  dependency direction enforced (a static import-graph check must find no
  upward or cyclic edges). `ruff` and `pyright` clean. Every public class,
  method, and exception has a docstring stating its contract, its parameters, and
  what it raises; the three §1.6 resolutions are documented where a consumer will
  find them. Cyclomatic complexity ≤ 12 per function; no single module carries
  the whole engine (a >250-LoC module is a design smell and is flagged in review).
- **3.6 Observability** — **N/A** — an in-process library with no long-running
  process, no request lifecycle, and no operator. The observability surface a
  consumer actually needs is the exception contract (typed exceptions with
  `line`/`col`/`msg`), which is specified under NFR-2 rather than duplicated here.
  The library must not emit logging or print output of its own.
- **NFR-5 Portability / footprint** — Zero third-party dependencies. Importable
  and fully functional on any CPython ≥ 3.11 on Linux/macOS/Windows. No compiled
  extensions, no data files, no environment variables.

## 4. The Ask (Deliverables & Definition of Done)
- **4.1 Required artifacts**
  | Path | Contents |
  |------|----------|
  | `solution/template_engine/` | The package: `__init__.py`, `errors.py`, `nodes.py`, `lexer.py`, `parser.py`, `renderer.py`, `filters.py`, `environment.py` (names may vary; the §2.2 decomposition and dependency direction may not) |
  | `design/PRD.md` | Problem, target consumers, scope/non-goals, success metrics (§5.2) |
  | `design/USER_STORIES.md` | Consumer stories with acceptance criteria, traceable to `FR-n` (§5.2) |
  | `design/API_REFERENCE.md` | Every public name from §2.1: signature, parameters, returns, raises, example — **plus** the three §1.6 resolutions stated explicitly (§5.4) |
  | `design/GRAMMAR.md` | The supported template grammar, precedence, and the error taxonomy with example messages (§5.4) |
  | `design/EXAMPLES.md` | ≥ 5 runnable usage examples covering interpolation, conditionals, loops, includes via `Environment`, filters, and autoescape (§5.4) |
- **4.2 Definition of Done**
  - [ ] `smoke` tests pass.
  - [ ] `acceptance` suite passes at ≥ 95% (hard gate).
  - [ ] All six §4.1 artifacts exist and are internally consistent with the code.
  - [ ] `ruff` + `pyright` clean; public API fully docstringed.
  - [ ] Module decomposition matches §2.2; import-graph check finds no upward or
        cyclic edges.
  - [ ] Source scan finds no `eval`, `exec`, `compile`, or `__import__`.
  - [ ] All three §1.6 ambiguities resolved, applied consistently, and documented
        in `design/API_REFERENCE.md`.
  - [ ] No non-`TemplateError` exception escapes the public API for any input in
        the malformed-template corpus.
- **4.3 Acceptance criteria**
  - **AC-1** (FR-1) Interpolation renders dotted, indexed, and deeply chained
    paths; literal text is preserved byte-for-byte.
  - **AC-2** (FR-2) `if`/`elif`/`else`/`endif` select the correct arm across the
    full comparison and boolean grammar, including nested conditionals.
  - **AC-3** (FR-3) Loops iterate correctly, expose all five `loop` fields, nest
    with correct shadowing, restore outer bindings, and handle empty iterables.
  - **AC-4** (FR-4) Includes resolve through both loader forms, nest, see loop
    bindings, and raise `TemplateRuntimeError` for missing names and cycles.
  - **AC-5** (FR-5) Built-in filters behave per the §2.1 table; user filters
    register and chain; unknown/raising filters produce `TemplateRuntimeError`.
  - **AC-6** (FR-6, NFR-3) Autoescape on neutralizes injected markup; autoescape
    off does not escape; literal text is never escaped either way.
  - **AC-7** (FR-7) Strict mode raises on undefined; lenient mode does not; the
    chosen lenient policy is uniform; `default` intercepts.
  - **AC-8** (FR-8, NFR-1) One `Template` renders repeatedly with independent
    results; the render-many timing ratio holds; no parse on render.
  - **AC-9** (FR-9, NFR-2) Every malformed-template case raises
    `TemplateSyntaxError` with the exact expected `line` and `col`.
  - **AC-10** (FR-10) `Environment` composes loader + filters + defaults, caches
    compiled templates, and propagates settings to the templates it creates.
  - **AC-11** (NFR-3) No `eval`/`exec`/`compile` in source; `_`-prefixed and
    dunder attribute access is refused.
  - **AC-12** (NFR-4, §5) Static checks clean, docstrings present, §2.2 boundaries
    hold, and all §4.1 design artifacts are present and consistent.

## 5. Discovery & Design Activities
Consistent with `ARTIFACT_GRADIENT.md` row L4: a library has an API audience, so
product framing and API design become **required**; there are no human end-users,
so visual design and a11y remain **N/A**.
- **5.1 User research** — **Optional / Stretch.** A short JTBD sketch for the two
  §1.2 consumer roles ("when I need to emit HTML from request data, help me do it
  without a heavyweight dependency…") is welcome and feeds `FID` positively if
  present, but the conventions of template engines are well established and
  interviews here would be theater. Personas: **N/A** (no human end-user).
- **5.2 Product design** — **Required.**
  - `design/PRD.md`: problem statement, target consumers, in-scope/out-of-scope
    (must not silently contradict §1.5), and **success metrics** — e.g. "an
    integrating developer can render a template with a filter and a loop in ≤ 10
    lines of setup"; "every malformed-template error names a line and column";
    "zero third-party dependencies."
  - `design/USER_STORIES.md`: consumer stories in `As a / I want / so that` form
    with per-story acceptance criteria, each traced to one or more `FR-n`. §1.3
    is the floor, not the ceiling.
  - Prioritized backlog: **Optional** (matrix marks it `O` at L4) — useful if the
    strategy sequences its own work, not scored as a deliverable.
- **5.3 Interaction/visual design** — The **public API is the interaction
  surface**, and designing it is **Required**: signatures, exception taxonomy,
  configuration precedence (`Template` vs `Environment`), and worked call-site
  examples must be written down *before* implementation, not reverse-engineered
  from finished code. Wireframes, hi-fi mockups, design tokens, interaction/state
  specs, and WCAG annotations: **N/A** — no rendered interface. CLI UX design:
  **N/A** — no CLI at this rung.
- **5.4 Design artifacts to produce** — under `design/`:
  | File | Must contain | Scored under |
  |------|--------------|--------------|
  | `PRD.md` | Problem, consumers, scope, non-goals, success metrics | `FID` |
  | `USER_STORIES.md` | Stories + acceptance criteria traced to `FR-n` | `FID` |
  | `API_REFERENCE.md` | Full §2.1 surface documented; **the three §1.6 resolutions stated explicitly**; exception table | `FID`, `QUA` |
  | `GRAMMAR.md` | Supported grammar, operator precedence, error taxonomy with example messages and positions | `FID` |
  | `EXAMPLES.md` | ≥ 5 runnable examples spanning every FR | `FID` |
  Artifacts are checked for **existence, internal consistency, and agreement with
  the shipped code** (`ARTIFACT_GRADIENT.md` §3). An API reference that documents
  a signature the code does not have costs more `FID` than a missing file.

## 6. Verification Method
- **6.1 Test tiers**
  - **`smoke` (visible)** — 7 worked template/expected-output pairs, deliberately
    small and structurally simple:
    | # | Template | Expectation |
    |---|----------|-------------|
    | 1 | `Hello {{ name }}!` | `Hello World!` |
    | 2 | `{{ user.address.city }}` | nested dotted lookup |
    | 3 | `{% if n > 2 %}big{% elif n == 2 %}two{% else %}small{% endif %}` | correct arm |
    | 4 | `{% for i in items %}{{ loop.index }}:{{ i }};{% endfor %}` | `1:a;2:b;3:c;` |
    | 5 | `{% include "header" %}Body` via `Environment(loader={...})` | partial spliced in |
    | 6 | `{{ name \| default("anon") \| upper }}` | filter chain |
    | 7 | `Line1\n{{ oops` | `TemplateSyntaxError` with `line == 2`, `col == 6` |
  - **`acceptance` (held-out)** — a broad behavioral matrix (~170 assertions),
    grouped so regression can be attributed per feature:
    | Group | Coverage | ≈ Assertions |
    |-------|----------|--------------|
    | G1 Interpolation & lookup | dotted/index/mixed chains, mapping-before-attribute order, non-string values, empty template, text-only template, unicode | 25 |
    | G2 Conditionals | every comparison and boolean operator, precedence, truthiness table, `elif` chains, nesting, no-`else` fallthrough | 20 |
    | G3 Loops | all five `loop` fields, nesting + shadowing, scope restore, empty iterables, dicts/strings/generators, 10k items | 25 |
    | G4 Includes | both loader forms, nested includes, includes inside loops seeing loop vars, per-environment caching, missing name, no-loader case | 12 |
    | G5 Filters | four built-ins incl. `default`'s falsy-passthrough pin, chaining, literal args, user filters, shadowing a built-in, unknown filter, raising filter | 20 |
    | G6 Autoescape & injection | on/off at both levels, escaping of all five characters, filter output escaped, literal text never escaped, explicit-over-inherited precedence | 14 |
    | G7 Undefined strictness | strict raises with the missing path named; lenient does not raise; `default` intercepts; both modes at both levels | 12 |
    | G8 Error positions | the full FR-9 taxonomy × exact `line`/`col`, incl. multi-line sources, CRLF, tabs, unclosed-at-EOF pointing at the opener | 18 |
    | G9 API contract | exact names exported; signatures/keyword-only params; exception hierarchy (`TemplateSyntaxError` is a `TemplateError`); `msg`/`line`/`col` attributes present; `render(None)` == `render({})`; context not mutated | 10 |
    | G10 Compile-once & linearity | render-many timing ratio, environment cache, independence across renders, 100k-char output under budget | 6 |
    | G11 §1.6 consistency | A-1 uniform across interpolation/condition/loop; A-2 identical for `if` and `for` bodies and stable across repeats; A-3 explicit-setting behavior + inheritance | 8 |
  - **`adversarial` (hidden, run once)** — malformed and hostile inputs the agent
    could not have coded to: `{{ unclosed`, `{% if %}` with no condition, `{%
    endfor %}` with no opener, `{% if %}…{% endfor %}` mismatch, `{% forr x in y
    %}` unknown tag, `{% else %}` outside an `if`, `{{ }}` empty expression, `{{ |
    upper }}`, `{{ x | }}`, `{{ x | nosuchfilter }}`, a filter that raises, `{{ x
    | default }}` with a missing required argument, `{{ ""|length }}` and
    `{{ 42|length }}`, `{% for x in notiterable %}`, `{{ a.b.c }}` where `a.b` is
    `None`, four-deep nested loops with shadowed names, include of a missing name,
    self-include, an A→B→A cycle, `{{ user.__class__ }}` and
    `{{ ''.__class__.__mro__ }}` sandbox probes, `<script>alert(1)</script>` and
    `" onerror="alert(1)` injected with autoescape on **and** off, CRLF and
    tab-indented sources checked for exact `line`/`col`, a 300-line template whose
    only error is on line 287, undefined names in both strictness modes, and a
    10k-iteration loop nested two deep (quadratic-blowup detector).
- **6.2 "Working" definition** — **≥ 95% of `acceptance` assertions pass** (hard
  gate). Additionally, any escape of a non-`TemplateError` exception across the
  public API is counted as a failed assertion in its group — it is not a
  "different but acceptable" outcome.
- **6.3 Verification mechanics**
  - `pytest`, importing **only** the public names from `solution.template_engine`.
    The public API is the real path; acceptance never imports internal modules to
    reach behavior it could reach through `Template`/`Environment`.
  - **Integration-style rendering tests:** each case is a (source, context,
    options) triple rendered end-to-end and compared to an expected string —
    byte-exact where §1.6 A-2 permits, per-line whitespace-normalized where it
    does not.
  - **API contract tests:** `inspect.signature` checks for the §2.1 signatures and
    keyword-only parameters, `__all__` contents, and exception-hierarchy
    assertions.
  - **Error-position tests:** assert on `exc.line` and `exc.col` (and that `msg`
    is non-empty and mentions the offending construct), never on the message
    string verbatim.
  - **Security tests:** render a context containing `<script>alert(1)</script>`
    with autoescape enabled and assert the substring `<script>` is absent and the
    escaped form present; assert the sandbox refuses `_`-prefixed access; a static
    AST scan of the solution source asserts no `eval`/`exec`/`compile`/`__import__`
    call nodes exist.
  - **Architecture probe:** a static import-graph analysis of the package asserts
    the §2.2 layering (no upward edges, no cycles, renderer does not import lexer
    or parser). Reported into `QUA`/`FID`; **not** part of the gate, since it
    grades structure rather than behavior.
  - **Cumulative regression run:** per `VERIFICATION_CONTRACT.md` §5 step 6, the
    grouped acceptance matrix is re-run at the end and diffed against
    per-iteration group results to attribute `regressions_introduced` to a feature
    group.
- **6.4 Anti-gaming measures**
  - Acceptance templates are structurally unlike the smoke seven (multi-line,
    nested, mixed constructs), so a lookup table keyed on template text fails.
  - The `G11` consistency group means there is no single "expected string" to
    hardcode for the ambiguous behaviors — the suite checks *coherence across
    positions*, which only a real implementation can satisfy.
  - `G8`'s positions are computed from generated multi-line sources, so a
    hardcoded `line=1, col=1` or an off-by-one scheme fails broadly rather than
    narrowly.
  - `G10`'s timing ratio and the environment cache check defeat the "re-parse on
    every render" shortcut that would otherwise pass every behavioral test.
  - The static scan for `eval`/`exec` catches the tempting shortcut of handing
    condition expressions to Python; using it is both an NFR-3 failure and a
    `QUA` cap.
  - A large gap between `acceptance_pass` and `adversarial_pass` caps `ROB` per
    `CONVERGENCE_METRICS.md` §6 — the usual signature of an engine that handles
    the demoed shapes and nothing else.

## 7. Scoring Rubric
- **7.1 Weight profile** (sum 100): `COR 30 · ROB 15 · EFF 14 · AUT 12 · QUA 13 ·
  REG 8 · FID 8`. `REG` is live at L4 because the feature set is large enough that
  later features (includes, autoescape, filters) routinely break earlier ones
  (loops, positions); `FID` is live because §5 makes product and API design
  required deliverables.
- **7.2 Per-axis scoring guide**
  | Axis | 0 | 2 | 4 |
  |------|---|---|---|
  | COR | acceptance < 95% (gate fail) | ≥ 95% acceptance but a whole feature group is weak (e.g. includes or `loop` metadata partially wrong) and adversarial < 75% | 100% acceptance and ≥ 95% adversarial, including nesting, cycles, and position cases |
  | ROB | bare `KeyError`/`RecursionError`/traceback escapes the public API | most malformed inputs raise `TemplateSyntaxError` but positions drift or include cycles blow the stack | every malformed input raises the right typed error with an accurate position and a message naming the construct; cycles and filter failures wrapped cleanly |
  | EFF | > 35 iterations or > 60 min | passed near the hard cap, or many failed runs before pass | passed ≤ 14 iterations, under time/token budget, ≤ 1 failed run before pass |
  | AUT | any `rescue`, or a `hint` that supplied the tokenizer/parser structure | one `clarify` on a §1.6 ambiguity (which the spec deliberately leaves to the agent — asking is a small negative) | zero interventions, zero dead-ends; ambiguities resolved and documented unaided |
  | QUA | lint/type errors, or the whole engine in one module, or `eval` used | modules exist but boundaries leak (renderer re-parsing, cyclic imports, positions recomputed); sparse docstrings | clean §2.2 layering with a one-way import graph, fully docstringed public API, `ruff`+`pyright` clean, complexity in budget |
  | REG | a later feature broke an earlier group and shipped broken | 1–2 transient regressions, caught and fixed within the run | zero `regressions_introduced`, zero `oscillations`; earlier groups stay green as later features land |
  | FID | required `design/` artifacts missing | artifacts present but thin, or the API reference contradicts the shipped signatures / omits the §1.6 resolutions | all five artifacts present, consistent with the code, stories traced to `FR-n`, ambiguity resolutions documented where a consumer will find them |
- **7.3 Hard gate** — `acceptance_floor = 0.95`.
- **7.4 Pass threshold** — **70**. L4 is where composition discipline starts to
  separate strategies; a score below 70 with the gate cleared means the engine
  works but was assembled without structure, cheaply verified, or rescued.

## 8. Convergence Signals
- **8.1 Healthy convergence** — Design before code: the API surface and grammar
  are written down (§5.3/§5.4) before the first module lands. The pipeline is
  built bottom-up with the smoke loop as the ratchet — lexer + text/interpolation
  rendering green first, then conditionals, then loops, then filters, then
  includes, then autoescape and strictness — with earlier groups re-run each time.
  Positions are carried from the lexer from the very first commit rather than
  bolted on after the first `line`/`col` failure. Ambiguities are resolved
  deliberately and documented in the same change that implements them. Lands in
  ≤ 14 iterations, zero interventions.
- **8.2 Pathological patterns**
  | Pattern | How it surfaces |
  |---------|-----------------|
  | **Regex-only "engine"** — one module of substitutions, no AST | Passes smoke; collapses on nested `if` inside `for`; `G2`/`G3` nesting assertions fail; architecture probe finds no parser/renderer split → `QUA` ≤ 1 |
  | **Positions bolted on late** | An epidemic of off-by-one failures in `G8` after everything else is green; many iterations spent nudging `col` by ±1; often accompanied by re-scanning the source in the parser |
  | **Re-parse per render** | All behavioral groups green, `G10` fails; strategy often does not notice because smoke says nothing about it |
  | **`eval` for expressions** | Fast apparent progress through `G2`, then NFR-3 static scan fails; a `QUA` cap and an integrity signal, not just a lost assertion |
  | **Autoescape retrofit** | Discovered late, threaded through every node type at once, spiking `regressions_introduced` in `G1`/`G3`/`G5` → `REG` collapse |
  | **Include recursion** | `RecursionError` in `G4`/adversarial instead of `TemplateRuntimeError`; symptom of no cycle bookkeeping in the render stack |
  | **Whitespace oscillation** | Repeated flips of trailing-newline handling as the strategy chases expected outputs it cannot see — visible as `oscillations` > 0 with no net progress; the §1.6 A-2 latitude exists precisely so this thrash is unnecessary, so it indicates the agent did not read the ambiguity table |
  | **Docs-last** | `design/` written after the code as a transcription of it; detectable as artifacts landing in the final iteration and as API-reference/code mismatches → `FID` ≤ 2 |
- **8.3 Instrumentation notes** — Beyond the shared `CONVERGENCE_METRICS.md` set,
  capture for this rung:
  - **Per-group acceptance pass fractions across iterations** — the substrate for
    `REG` attribution (which feature broke which group, when).
  - **Module count and import-graph edge list** at declaration time — direct
    evidence of whether composition happened or was simulated.
  - **Parse-call count during the `G10` render-many test** — the unambiguous
    compile-once signal.
  - **Iteration index at which `design/` artifacts first appear** relative to the
    first solution edit — distinguishes design-led from docs-last, and feeds the
    `FID` justification note.
  - **Count of `G8` position failures per iteration** — the cleanest single
    indicator of whether position metadata is architectural or patched.
