# Grammar Reference — template_engine

## Template Grammar

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

## Operator Precedence (highest to lowest)

| Level | Operators | Associativity |
|-------|-----------|---------------|
| 1 (highest) | `not` (unary) | right |
| 2 | comparison: `==`, `!=`, `<`, `<=`, `>`, `>=` | non-associative |
| 3 | `and` | left |
| 4 (lowest) | `or` | left |

Parentheses are **not** supported in expressions (out of scope).

## Lexical Rules

- Whitespace inside tags is insignificant: `{%if x%}` parses identically to `{% if x %}`.
- String literals accept single or double quotes: `'hello'` and `"hello"` are equivalent.
- `line` and `col` are 1-based; a tab counts as one column; `\r\n` counts as one newline.
- The position of `{{` or `{%` is the position of the first `{`.

## Path Resolution

For `a.b`:
1. If `a` is a `dict`, look up key `b` first; if not found, fall back to attribute `b`.
2. Otherwise, try item access `a[b]`; if that fails, try attribute `getattr(a, b)`.

For `a[k]`:
- If `k` is an integer literal, use integer index access.
- If `k` is a string literal, use string key access.

Names beginning with `_` (including dunders) are **refused** with `TemplateRuntimeError`.

## Error Taxonomy

All compile-time errors raise `TemplateSyntaxError(msg, line, col)`.

| Error class | Example | Position reported | Example message |
|-------------|---------|-------------------|-----------------|
| Unterminated `{{` | `{{ oops` | Position of `{{` | `unterminated '{{'` |
| Unterminated `{%` | `{% if x` | Position of `{%` | `unterminated '{%'` |
| Empty expression | `{{ }}` | Position of `{{` | `empty expression` |
| Malformed expression | `{{ + }}` | Position of `{{` | `unexpected token '+'` |
| Unknown tag name | `{% forr x in y %}` | Position of `{%` | `unknown tag 'forr'` |
| Unclosed block at EOF | `{% for x in y %} body` | Position of **opening** `{%` | `unclosed 'for' block` |
| Mismatched closer | `{% if a %}x{% endfor %}` | Position of **closing** `{%` | `mismatched closer 'endfor' inside 'if' block` |
| Stray closer | `hello {% endif %}` | Position of **closing** `{%` | `stray 'endif' tag` |
| `elif`/`else` outside `if` | `{% else %}` with no opener | Position of `{%` | `stray 'else' tag` |
| Malformed `for` | `{% for in y %}` | Position of `{%` | `expected variable name in 'for'` |
| Malformed `include` | `{% include %}` | Position of `{%` | `expected string literal in 'include'` |

All render-time errors raise `TemplateRuntimeError`.

| Error class | Example | Example message |
|-------------|---------|-----------------|
| Unknown filter | `{{ x \| nosuchfilter }}` | `unknown filter 'nosuchfilter'` |
| Filter failure | filter raises internally | `filter 'boom' raised: division by zero` |
| Missing include | `{% include "missing" %}` | `template 'missing' not found` |
| Include cycle | A → B → A | `include cycle detected: A -> B -> A` |
| No loader | `{% include "x" %}` with no env | `no loader configured; cannot resolve include` |
| Strict undefined | `{{ missing }}` with `strict_undefined=True` | `undefined variable 'missing'` |
| Non-iterable loop | `{% for i in 5 %}` | `cannot iterate over 'int'` |
| Sandboxed access | `{{ x.__class__ }}` | `access to private attribute '__class__' is not allowed` |
