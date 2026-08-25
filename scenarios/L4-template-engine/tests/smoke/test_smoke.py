"""Smoke tier (VISIBLE to the strategy). Not weight-bearing; a fast self-check.

Seven small, structurally simple worked examples (SPEC / REQUIREMENTS Sec.6.1) that
demonstrate every construct without revealing the held-out acceptance answers.
"""

from template_engine import Environment, Template, TemplateSyntaxError


def test_smoke_interpolation():
    assert Template("Hello {{ name }}!").render({"name": "World"}) == "Hello World!"


def test_smoke_nested_lookup():
    ctx = {"user": {"address": {"city": "Paris"}}}
    assert Template("{{ user.address.city }}").render(ctx) == "Paris"


def test_smoke_conditional_arm():
    src = "{% if n > 2 %}big{% elif n == 2 %}two{% else %}small{% endif %}"
    assert Template(src).render({"n": 2}) == "two"
    assert Template(src).render({"n": 5}) == "big"
    assert Template(src).render({"n": 1}) == "small"


def test_smoke_loop_with_index():
    src = "{% for i in items %}{{ loop.index }}:{{ i }};{% endfor %}"
    assert Template(src).render({"items": ["a", "b", "c"]}) == "1:a;2:b;3:c;"


def test_smoke_include_partial():
    env = Environment(loader={"header": "H:{{ title }}"})
    tmpl = env.from_string('{% include "header" %}|Body')
    assert tmpl.render({"title": "T"}) == "H:T|Body"


def test_smoke_filter_chain():
    assert Template('{{ name | default("anon") | upper }}').render({}) == "ANON"


def test_smoke_syntax_error_position():
    try:
        Template("Line1\n{{ oops")
    except TemplateSyntaxError as exc:
        assert exc.line == 2
        assert exc.col == 1
    else:
        raise AssertionError("expected TemplateSyntaxError")
