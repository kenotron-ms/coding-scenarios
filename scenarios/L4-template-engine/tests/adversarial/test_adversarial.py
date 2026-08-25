"""Adversarial tier (HIDDEN, run once). Denominator declared in rubric.yaml.

Malformed and hostile inputs the strategy could not have coded to. Feeds COR/ROB;
never the gate. Every case must surface a typed ``TemplateError`` (syntax at
compile, runtime at render) -- never a bare Python traceback (NFR-2/NFR-3).
"""

import time

import pytest

from template_engine import (
    Environment,
    Template,
    TemplateError,
    TemplateRuntimeError,
    TemplateSyntaxError,
)


def _syntax(src: str) -> TemplateSyntaxError:
    try:
        Template(src)
    except TemplateSyntaxError as exc:
        return exc
    raise AssertionError("expected TemplateSyntaxError")


# ---- syntax errors (compile time) ----------------------------------------


def test_adv_unterminated_interpolation():
    assert _syntax("{{ unclosed").msg


def test_adv_if_without_condition():
    assert _syntax("{% if %}x{% endif %}").msg


def test_adv_stray_endfor():
    assert _syntax("{% endfor %}").msg


def test_adv_if_endfor_mismatch():
    exc = _syntax("{% if a %}x{% endfor %}")
    assert (exc.line, exc.col) == (1, 12)


def test_adv_unknown_tag():
    exc = _syntax("{% forr x in y %}")
    assert "forr" in exc.msg


def test_adv_else_outside_if():
    assert _syntax("hello {% else %} world").msg


def test_adv_empty_expression():
    assert _syntax("{{ }}").msg


def test_adv_leading_pipe():
    assert _syntax("{{ | upper }}").msg


def test_adv_trailing_pipe():
    assert _syntax("{{ x | }}").msg


def test_adv_unclosed_block_at_eof_points_opener():
    src = "l1\nl2\nl3\nl4\nl5\n{% if flag %}\nbody with no endif"
    exc = _syntax(src)
    assert exc.line == 6
    assert exc.col == 1
    assert "if" in exc.msg


def test_adv_crlf_positions_exact():
    exc = _syntax("row1\r\n{% if %}")
    assert (exc.line, exc.col) == (2, 1)


def test_adv_tab_indented_position():
    exc = _syntax("start\n\t\t{{ }}")
    assert exc.line == 2
    assert exc.col == 3  # two tabs = two columns, tag opens at column 3


# ---- runtime errors (render time) ----------------------------------------


def test_adv_unknown_filter():
    with pytest.raises(TemplateRuntimeError):
        Template("{{ x | nosuchfilter }}").render({"x": 1})


def test_adv_filter_that_raises():
    env = Environment(filters={"boom": lambda v: 1 / 0})
    with pytest.raises(TemplateRuntimeError):
        env.from_string("{{ x | boom }}").render({"x": 1})


def test_adv_default_missing_argument():
    with pytest.raises(TemplateRuntimeError):
        Template("{{ x | default }}").render({"x": 1})


def test_adv_length_on_non_sized():
    assert Template('{{ "" | length }}').render({}) == "0"
    with pytest.raises(TemplateRuntimeError):
        Template("{{ n | length }}").render({"n": 42})


def test_adv_for_non_iterable_target():
    with pytest.raises(TemplateRuntimeError):
        Template("{% for x in n %}{{ x }}{% endfor %}").render({"n": 5})


def test_adv_none_in_the_middle_of_chain():
    # a.b is None; a.b.c must not raise a bare AttributeError -- lenient renders "".
    assert Template("[{{ a.b.c }}]").render({"a": {"b": None}}) == "[]"
    with pytest.raises(TemplateRuntimeError):
        Template("{{ a.b.c }}", strict_undefined=True).render({"a": {"b": None}})


def test_adv_four_deep_nested_loops_with_shadowing():
    src = (
        "{% for x in a %}{% for x in b %}{% for x in c %}{% for x in d %}"
        "{{ x }}{% endfor %}{% endfor %}{% endfor %}{% endfor %}"
    )
    out = Template(src).render({"a": [0], "b": [0], "c": [0], "d": ["W", "X", "Y"]})
    assert out == "WXY"


def test_adv_include_missing_name():
    env = Environment(loader={"exists": "ok"})
    with pytest.raises(TemplateRuntimeError):
        env.from_string('{% include "nope" %}').render({})


def test_adv_self_include_cycle():
    env = Environment(loader={"a": 'A{% include "a" %}'})
    with pytest.raises(TemplateRuntimeError):
        env.render("a", {})


def test_adv_indirect_include_cycle():
    env = Environment(loader={"a": 'A{% include "b" %}', "b": 'B{% include "a" %}'})
    with pytest.raises(TemplateRuntimeError):
        env.render("a", {})


def test_adv_sandbox_dunder_probes():
    with pytest.raises(TemplateRuntimeError):
        Template("{{ user.__class__ }}").render({"user": object()})
    with pytest.raises(TemplateRuntimeError):
        Template("{{ user.__dict__ }}").render({"user": object()})
    # a literal cannot begin a path, so the classic escape chain never resolves
    with pytest.raises(TemplateError):
        Template("{{ ''.__class__.__mro__ }}").render({})


def test_adv_injection_autoescape_on_and_off():
    payload = "<script>alert(1)</script>"
    on = Template("{{ x }}", autoescape=True).render({"x": payload})
    assert "<script>" not in on
    assert "&lt;script&gt;" in on
    off = Template("{{ x }}").render({"x": payload})
    assert off == payload  # off does not escape (correct, but unsafe -- caller's choice)


def test_adv_undefined_in_both_modes():
    assert Template("[{{ ghost }}]").render({}) == "[]"
    with pytest.raises(TemplateRuntimeError):
        Template("{{ ghost }}", strict_undefined=True).render({})


def test_adv_large_nested_loop_is_linear():
    src = "{% for i in outer %}{% for j in inner %}.{% endfor %}{% endfor %}"
    tmpl = Template(src)
    ctx = {"outer": list(range(100)), "inner": list(range(100))}
    start = time.perf_counter()
    out = tmpl.render(ctx)
    elapsed = time.perf_counter() - start
    assert len(out) == 10000
    assert elapsed < 1.0
