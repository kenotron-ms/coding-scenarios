# Product Requirements Document — template_engine

## 1. Problem Statement

Applications routinely need to generate text and HTML (emails, reports,
configuration files, static pages) from structured data. Pulling a large
third-party templating engine into a small service is disproportionate, and
hand-rolled string formatting collapses the moment conditionals or loops appear.

This library provides a **dependency-free, embeddable template engine** that
covers the 90% case — interpolation, conditionals, loops, includes, filters —
and, when a template is wrong, tells the template author **exactly where** in
terms of line and column rather than emitting a raw Python traceback.

## 2. Target Consumers

The library has two distinct consumer roles:

| Role | Relationship to the library | What they need |
|------|-----------------------------|----------------|
| **Integrating developer** | Imports the package, wires an `Environment`, registers filters, calls `render` | A small, stable, typed, docstringed API; predictable exceptions; no surprise I/O |
| **Template author** | Writes `.html`/`.txt` templates; may not read the engine's source | Familiar syntax; errors that name a line, a column, and the offending construct |

## 3. Scope

### In scope
- Variable interpolation with dotted/indexed path access
- Conditionals: `{% if %} / {% elif %} / {% else %} / {% endif %}`
- Loops: `{% for x in expr %} / {% endfor %}` with `loop` metadata
- Partial includes: `{% include "name" %}` via a consumer-supplied loader
- Filters: built-in `upper`, `lower`, `length`, `default`; user-registered filters
- Autoescape: HTML-escape interpolated values when enabled
- Strict and lenient undefined-variable handling
- Position-accurate syntax errors (`line`, `col`)
- `Environment` as a composition root (loader, filter registry, template cache)

### Out of scope
- Template inheritance (`{% extends %}` / `{% block %}`)
- Macros, `{% call %}`, `{% set %}`
- Comments (`{# … #}`)
- `{% for %} … {% else %}`
- Arithmetic, slicing, function calls, method calls in expressions
- Filter arguments that are themselves expressions (literals only)
- Context-aware escaping (URL, JS contexts)
- Async or streaming rendering
- Loading templates from disk by the engine itself
- i18n, CLI

## 4. Non-Goals

- Replacing Jinja2 for complex use cases
- Supporting arbitrary Python expressions in templates
- Providing a command-line interface
- Managing template files on disk

## 5. Success Metrics

- An integrating developer can render a template with a filter and a loop in ≤ 10 lines of setup code.
- Every malformed-template error names a line and column.
- Zero third-party dependencies.
- `Template(source)` compiles once; `render()` performs no re-parsing.
- All 7 smoke tests and ≥ 95% of acceptance assertions pass.
- Static scan finds no `eval`, `exec`, `compile`, or `__import__` calls.
