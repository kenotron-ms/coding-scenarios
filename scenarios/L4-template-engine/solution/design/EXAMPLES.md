# Examples — template_engine

All examples are runnable with `python3` after installing the package.

## Example 1 — Basic Interpolation

```python
from template_engine import Template

tmpl = Template("Hello {{ name }}! You are {{ user.age }} years old.")
print(tmpl.render({"name": "Alice", "user": {"age": 30}}))
# Hello Alice! You are 30 years old.
```

## Example 2 — Conditionals

```python
from template_engine import Template

src = """
{% if score >= 90 %}Grade: A
{% elif score >= 80 %}Grade: B
{% elif score >= 70 %}Grade: C
{% else %}Grade: F
{% endif %}
""".strip()

tmpl = Template(src)
print(tmpl.render({"score": 95}))  # Grade: A
print(tmpl.render({"score": 82}))  # Grade: B
print(tmpl.render({"score": 65}))  # Grade: F
```

## Example 3 — Loops with Loop Metadata

```python
from template_engine import Template

src = (
    "{% for item in items %}"
    "{{ loop.index }}. {{ item }}"
    "{% if not loop.last %}, {% endif %}"
    "{% endfor %}"
)

tmpl = Template(src)
print(tmpl.render({"items": ["apple", "banana", "cherry"]}))
# 1. apple, 2. banana, 3. cherry
```

## Example 4 — Partial Includes via Environment

```python
from template_engine import Environment

partials = {
    "header": "<header>{{ title }}</header>",
    "footer": "<footer>© {{ year }}</footer>",
}

env = Environment(loader=partials)
tmpl = env.from_string(
    '{% include "header" %}<main>{{ body }}</main>{% include "footer" %}'
)
print(tmpl.render({"title": "Home", "body": "Welcome!", "year": 2024}))
# <header>Home</header><main>Welcome!</main><footer>© 2024</footer>
```

## Example 5 — Filters

```python
from template_engine import Template, Environment

# Built-in filters
tmpl = Template('{{ name | default("anonymous") | upper }}')
print(tmpl.render({}))               # ANONYMOUS
print(tmpl.render({"name": "bob"}))  # BOB

# length filter
tmpl2 = Template("{{ items | length }} items")
print(tmpl2.render({"items": [1, 2, 3]}))  # 3 items

# User-registered filter
env = Environment(filters={"exclaim": lambda v: str(v) + "!"})
print(env.from_string("{{ msg | exclaim }}").render({"msg": "Hello"}))  # Hello!
```

## Example 6 — Autoescape

```python
from template_engine import Template, Environment

# Without autoescape (default): values are written verbatim
tmpl = Template("{{ content }}")
print(tmpl.render({"content": "<b>bold</b>"}))  # <b>bold</b>

# With autoescape: HTML characters are escaped
safe_tmpl = Template("{{ content }}", autoescape=True)
print(safe_tmpl.render({"content": "<script>alert(1)</script>"}))
# &lt;script&gt;alert(1)&lt;/script&gt;

# Via Environment (A-3: default False, but can be set to True)
env = Environment(autoescape=True)
print(env.from_string("{{ x }}").render({"x": "<b>"}))  # &lt;b&gt;

# Literal template text is NEVER escaped
print(Template("<b>{{ x }}</b>", autoescape=True).render({"x": "&"}))
# <b>&amp;</b>
```

## Example 7 — Strict vs Lenient Undefined

```python
from template_engine import Template, TemplateRuntimeError

# Lenient mode (default, A-1): missing names → empty string / falsy / empty
tmpl = Template("[{{ missing }}]")
print(tmpl.render({}))  # []

# Strict mode: missing names raise
strict = Template("{{ missing }}", strict_undefined=True)
try:
    strict.render({})
except TemplateRuntimeError as exc:
    print(exc)  # undefined variable 'missing' (line 1, col 1)

# default filter intercepts undefined in lenient mode
tmpl2 = Template('{{ name | default("guest") }}')
print(tmpl2.render({}))              # guest
print(tmpl2.render({"name": ""}))   # "" (defined-but-falsy passes through)
```
