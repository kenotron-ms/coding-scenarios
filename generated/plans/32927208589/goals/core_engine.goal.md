# Lane core_engine

## Outcome

Implement the complete L4 Template Engine solution under `scenarios/L4-template-engine/solution/template_engine/` so that:

1. The smoke test suite (`tests/smoke/`) passes fully.
2. The acceptance test suite (`tests/acceptance/`) passes at >= 95% of assertions.
3. All required design artifacts exist under `scenarios/L4-template-engine/solution/design/`.

The package must be importable as `template_engine` when `PYTHONPATH` includes `scenarios/L4-template-engine/solution/`.

## Steps

### 1. Create the package skeleton

Create the directory `scenarios/L4-template-engine/solution/template_engine/` with the following module files (strictly one-way dependency graph — no cycles):

- `errors.py` — leaf: define `TemplateError(Exception)`, `TemplateSyntaxError(TemplateError)` with `msg`, `line`, `col` attributes, `TemplateRuntimeError(TemplateError)`.
- `nodes.py` — leaf: define AST node dataclasses: `TextNode(text, line, col)`, `OutputNode(expr, filters, line, col)`, `IfNode(branches, else_body, line, col)`, `ForNode(var, expr, body, line, col)`, `IncludeNode(name, line, col)`. These carry position metadata from the lexer.
- `lexer.py` — imports `errors` only: tokenize source into `Token(kind, value, line, col)` objects. Track line/col as characters are consumed. Token kinds: `TEXT`, `INTERPOLATION_START`/`END`, `BLOCK_START`/`END`, `EOF` (or similar fine-grained kinds). Position of `{{` and `{%` tags is the `{` character (1-based line and col).
- `parser.py` — imports `lexer`, `nodes`, `errors`: consume token stream and produce AST. Implement the full grammar from REQUIREMENTS §2.1:
  - `template := (TEXT | interpolation | block)*`
  - `interpolation := '{{' expr ('|' filter)* '}}'`
  - `block := if_block | for_block | include`
  - `if_block := '{% if' expr '%}' template ('{% elif' expr '%}' template)* ('{% else %}' template)? '{% endif %}'`
  - `for_block := '{% for' NAME 'in' expr '%}' template '{% endfor %}'`
  - `include := '{% include' STRING '%}'`
  - `expr := or_expr`, `or_expr := and_expr ('or' and_expr)*`, `and_expr := not_expr ('and' not_expr)*`, `not_expr := 'not' not_expr | comparison`, `comparison := operand (('=='|'!='|'<'|'<='|'>'|'>=') operand)?`, `operand := literal | path`, `path := NAME ('.' NAME | '[' (INT | STRING) ']')*`, `literal := STRING | INT | FLOAT | 'true' | 'false' | 'none'`
  - Raise `TemplateSyntaxError` with accurate `line`/`col` for: unterminated `{{`/`{%`, empty/malformed expression, unknown tag name, unclosed block at EOF (pointing at opening tag), mismatched closer, stray closer, `elif`/`else` outside `if`.
- `filters.py` — imports `errors` only: built-in filter registry with `upper(v)=str(v).upper()`, `lower(v)=str(v).lower()`, `length(v)=len(v)` (raises `TemplateRuntimeError` if no `len`), `default(v, fallback)` returns `fallback` when `v` is undefined-sentinel or `None`; defined-but-falsy values pass through unchanged.
- `renderer.py` — imports `nodes`, `errors` only (NOT `lexer` or `parser`): walk the AST and produce a string. Implement:
  - Context lookup with dotted/bracket paths. Resolution order for `a.b`: mapping key first, then `getattr`. Refuse `_`-prefixed names (raise `TemplateRuntimeError`). Handle strict vs lenient undefined.
  - Loop iteration: bind loop variable + `loop` metadata object with `index`, `index0`, `first`, `last`, `length`. Use child scope (outer bindings restored after loop).
  - Include: delegate to environment (passed at render time), detect cycles via a render stack, raise `TemplateRuntimeError` for missing names and cycles.
  - Autoescape: after all filters run on an interpolated value, HTML-escape (`&`, `<`, `>`, `"`, `'`) if autoescape is enabled. Never escape literal text.
  - Wrap all internal exceptions (`KeyError`, `AttributeError`, `IndexError`, `TypeError`, `RecursionError`) as `TemplateRuntimeError`.
  - Do NOT call `eval`, `exec`, `compile`, or `__import__` anywhere.
- `environment.py` — imports `parser`, `renderer`, `filters`, `errors`: implement `Environment` class with loader (dict or callable), filter registry (built-ins + user filters), autoescape/strict_undefined defaults, and compiled-template cache. Methods: `add_filter`, `from_string`, `get_template` (cached), `render`.
- `__init__.py` — re-exports only: `Template`, `Environment`, `TemplateError`, `TemplateSyntaxError`, `TemplateRuntimeError`. Set `__all__`.

### 2. Implement `Template` class

`Template(source, *, autoescape=False, strict_undefined=False, environment=None)`:
- At `__init__` time: tokenize and parse `source` into an AST. Store the AST. Do NOT store the source for re-parsing.
- `render(context=None) -> str`: walk the stored AST with the given context (default `{}`). Do not mutate the caller's mapping. Return the rendered string. No re-tokenization or re-parsing.

### 3. Resolve the three ambiguities (document in design/API_REFERENCE.md)

- **A-1 (lenient undefined):** Choose option (a): undefined name yields empty string on interpolation, is falsy in conditions, and yields an empty iterable in loops. Apply uniformly.
- **A-2 (whitespace control):** Choose option (a): strict verbatim preservation — all text emitted byte-for-byte. No special handling of block-tag lines.
- **A-3 (Environment autoescape default):** Choose option (a): `Environment` defaults `autoescape=False`, matching `Template`'s pinned default.

### 4. Create design artifacts

Under `scenarios/L4-template-engine/solution/design/`:
- `PRD.md` — problem statement, target consumers (integrating developer, template author), in-scope/out-of-scope, success metrics.
- `USER_STORIES.md` — US-1 through US-7 with acceptance criteria traced to FR-n.
- `API_REFERENCE.md` — every public name with signature, parameters, returns, raises, example. **Explicitly state the three §1.6 resolutions (A-1, A-2, A-3).**
- `GRAMMAR.md` — full grammar, operator precedence, error taxonomy with example messages and positions.
- `EXAMPLES.md` — at least 5 runnable usage examples covering interpolation, conditionals, loops, includes via Environment, filters, and autoescape.

### 5. Verify

Run the smoke and acceptance suites from the scenario root:

```bash
cd scenarios/L4-template-engine
SOLUTION_DIR=$(pwd)/solution PYTHONPATH=$(pwd)/solution pytest tests/smoke tests/acceptance -q
```

Iterate until acceptance passes at >= 95%.

## Done when

The following command exits 0 and shows >= 95% of acceptance assertions passing:

```bash
cd scenarios/L4-template-engine && SOLUTION_DIR=$(pwd)/solution PYTHONPATH=$(pwd)/solution pytest tests/smoke tests/acceptance -q --tb=no 2>&1 | grep -E 'passed|failed|error' | tail -3 && cd scenarios/L4-template-engine && SOLUTION_DIR=$(pwd)/solution PYTHONPATH=$(pwd)/solution python -c "import sys; sys.path.insert(0,'solution'); from template_engine import Template, Environment, TemplateError, TemplateSyntaxError, TemplateRuntimeError; print('imports ok')"
```

Specifically: all 7 smoke tests pass, and the acceptance suite reports >= 95% pass rate (i.e., if ~170 assertions, at most ~8 may fail).

## Final step (REQUIRED)

After the work is done and the check passes, write the file `artifacts/core_engine.done` (relative to the repo root: `scenarios/L4-template-engine/artifacts/core_engine.done` does NOT apply — write it at the repo root as `artifacts/core_engine.done`) containing exactly `core_engine:ok` and nothing else.

This marker file (`artifacts/core_engine.done` with content `core_engine:ok`) is how the batch orchestrator confirms the lane finished. It must be the LAST action you take.
