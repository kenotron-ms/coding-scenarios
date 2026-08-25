"""Acceptance tier (HELD OUT). Denominator declared in rubric.yaml. Defines "working".

Each test function is one registered check (id in the comment). Behavior is
verified end-to-end through the public API only (REQUIREMENTS Sec.6.3): the suite
imports nothing but ``Template``/``Environment`` and the exception taxonomy.
"""

import ast
import inspect
import time
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import template_engine
from template_engine import (
    Environment,
    Template,
    TemplateError,
    TemplateRuntimeError,
    TemplateSyntaxError,
)

# ---- G1 Interpolation & lookup -------------------------------------------


def test_interpolation_simple():  # L4-AC01
    assert Template("Hello {{ name }}!").render({"name": "World"}) == "Hello World!"
    assert Template("{{ a }}{{ b }}").render({"a": "x", "b": "y"}) == "xy"


def test_interpolation_dotted():  # L4-AC02
    ctx = {"user": {"address": {"city": "Paris"}}}
    assert Template("{{ user.address.city }}").render(ctx) == "Paris"


def test_interpolation_index_access():  # L4-AC03
    ctx = {"items": ["a", "b", "c"], "m": {"k": "v"}}
    assert Template("{{ items[0] }}-{{ items[2] }}-{{ m['k'] }}").render(ctx) == "a-c-v"


def test_interpolation_deep_chain():  # L4-AC04
    ctx = {"a": {"b": [0, {"c": "Z"}]}}
    assert Template("{{ a.b[1].c }}").render(ctx) == "Z"


def test_mapping_before_attribute():  # L4-AC05
    # A dict has a `get` attribute (bound method); the mapping key must win.
    assert Template("{{ d.get }}").render({"d": {"get": "KEY"}}) == "KEY"


def test_non_string_values_stringified():  # L4-AC06
    assert Template("{{ n }}/{{ b }}/{{ f }}").render(
        {"n": 42, "b": True, "f": 1.5}
    ) == "42/True/1.5"


def test_text_only_and_empty_template():  # L4-AC07
    assert Template("just literal text").render({}) == "just literal text"
    assert Template("").render({}) == ""
    assert Template("no tags here 12345").render(None) == "no tags here 12345"


# ---- G2 Conditionals ------------------------------------------------------


def test_if_comparison_operators():  # L4-AC08
    for op, ctx, expected in [
        ("==", {"n": 2}, "Y"),
        ("!=", {"n": 3}, "Y"),
        ("<", {"n": 1}, "Y"),
        ("<=", {"n": 2}, "Y"),
        (">", {"n": 5}, "Y"),
        (">=", {"n": 2}, "Y"),
    ]:
        src = "{% if n " + op + " 2 %}Y{% else %}N{% endif %}"
        assert Template(src).render(ctx) == "Y", op


def test_if_boolean_ops_and_precedence():  # L4-AC09
    src = "{% if a and not b %}Y{% else %}N{% endif %}"
    assert Template(src).render({"a": True, "b": False}) == "Y"
    assert Template(src).render({"a": True, "b": True}) == "N"
    # `not` binds tighter than `and`, `and` tighter than `or`.
    src2 = "{% if a or b and c %}Y{% else %}N{% endif %}"
    assert Template(src2).render({"a": True, "b": False, "c": False}) == "Y"
    assert Template(src2).render({"a": False, "b": True, "c": False}) == "N"


def test_if_elif_else_chain():  # L4-AC10
    src = "{% if n > 2 %}big{% elif n == 2 %}two{% elif n == 1 %}one{% else %}small{% endif %}"
    assert Template(src).render({"n": 5}) == "big"
    assert Template(src).render({"n": 2}) == "two"
    assert Template(src).render({"n": 1}) == "one"
    assert Template(src).render({"n": 0}) == "small"


def test_if_nested():  # L4-AC11
    src = "{% if a %}[{% if b %}AB{% else %}A{% endif %}]{% endif %}"
    assert Template(src).render({"a": 1, "b": 1}) == "[AB]"
    assert Template(src).render({"a": 1, "b": 0}) == "[A]"
    assert Template(src).render({"a": 0, "b": 1}) == ""


def test_if_truthiness_and_no_else():  # L4-AC12
    src = "{% if xs %}has{% endif %}"
    assert Template(src).render({"xs": [1]}) == "has"
    assert Template(src).render({"xs": []}) == ""
    assert Template("{% if s %}Y{% endif %}").render({"s": ""}) == ""


# ---- G3 Loops -------------------------------------------------------------


def test_for_basic_and_all_loop_fields():  # L4-AC13
    src = (
        "{% for i in xs %}"
        "{{ loop.index }}/{{ loop.index0 }}/{{ loop.first }}/"
        "{{ loop.last }}/{{ loop.length }}:{{ i }};"
        "{% endfor %}"
    )
    out = Template(src).render({"xs": ["a", "b"]})
    assert out == "1/0/True/False/2:a;2/1/False/True/2:b;"


def test_for_nested_shadowing():  # L4-AC14
    src = "{% for x in outer %}{% for x in inner %}{{ x }}{% endfor %}-{{ x }};{% endfor %}"
    assert Template(src).render({"outer": [1, 2], "inner": ["a", "b"]}) == "ab-1;ab-2;"


def test_for_scope_restore():  # L4-AC15
    src = "{{ x }}[{% for x in xs %}{{ x }}{% endfor %}]{{ x }}"
    assert Template(src).render({"x": "OUT", "xs": ["a", "b"]}) == "OUT[ab]OUT"


def test_for_empty_iterable():  # L4-AC16
    assert Template("[{% for i in xs %}{{ i }}{% endfor %}]").render({"xs": []}) == "[]"


def test_for_over_dict_and_string():  # L4-AC17
    assert Template("{% for k in d %}{{ k }},{% endfor %}").render(
        {"d": {"a": 1, "b": 2}}
    ) == "a,b,"
    assert Template("{% for c in s %}{{ c }}.{% endfor %}").render({"s": "ab"}) == "a.b."


# ---- G4 Includes ----------------------------------------------------------


def test_include_mapping_loader():  # L4-AC18
    env = Environment(loader={"header": "H:{{ title }}", "main": '{% include "header" %}|B'})
    assert env.render("main", {"title": "T"}) == "H:T|B"


def test_include_callable_loader():  # L4-AC19
    partials = {"p": "P{{ x }}"}
    env = Environment(loader=lambda name: partials[name])
    assert env.from_string('{% include "p" %}').render({"x": 9}) == "P9"


def test_include_inside_loop_sees_loop_vars():  # L4-AC20
    env = Environment(loader={"row": "[{{ i }}:{{ loop.index }}]"})
    tmpl = env.from_string('{% for i in xs %}{% include "row" %}{% endfor %}')
    assert tmpl.render({"xs": ["a", "b"]}) == "[a:1][b:2]"


def test_include_missing_and_no_loader():  # L4-AC21
    with pytest.raises(TemplateRuntimeError):
        Environment(loader={}).from_string('{% include "x" %}').render({})
    with pytest.raises(TemplateRuntimeError):
        Template('{% include "x" %}').render({})


# ---- G5 Filters -----------------------------------------------------------


def test_builtin_filters():  # L4-AC22
    assert Template("{{ s | upper }}").render({"s": "hi"}) == "HI"
    assert Template("{{ s | lower }}").render({"s": "HI"}) == "hi"
    assert Template("{{ s | length }}").render({"s": "abcd"}) == "4"
    assert Template("{{ xs | length }}").render({"xs": [1, 2, 3]}) == "3"


def test_default_filter_semantics():  # L4-AC23
    assert Template('{{ missing | default("n/a") }}').render({}) == "n/a"
    assert Template('{{ v | default("n/a") }}').render({"v": None}) == "n/a"
    # defined-but-falsy values pass through unchanged
    assert Template('{{ z | default("n/a") }}').render({"z": 0}) == "0"
    assert Template('{{ e | default("n/a") }}').render({"e": ""}) == ""


def test_filter_chaining_and_literal_args():  # L4-AC24
    assert Template('{{ name | default("anon") | upper }}').render({}) == "ANON"
    assert Template('{{ name | default("anon") | upper }}').render(
        {"name": "bob"}
    ) == "BOB"


def test_user_filter_and_shadowing():  # L4-AC25
    env = Environment(filters={"exclaim": lambda v: str(v) + "!"})
    assert env.from_string("{{ w | exclaim }}").render({"w": "hi"}) == "hi!"
    env.add_filter("upper", lambda v: "SHADOWED")
    assert env.from_string("{{ w | upper }}").render({"w": "hi"}) == "SHADOWED"


def test_unknown_and_raising_filter():  # L4-AC26
    with pytest.raises(TemplateRuntimeError):
        Template("{{ x | nosuchfilter }}").render({"x": 1})
    env = Environment(filters={"boom": lambda v: 1 / 0})
    with pytest.raises(TemplateRuntimeError):
        env.from_string("{{ x | boom }}").render({"x": 1})


# ---- G6 Autoescape & injection -------------------------------------------


def test_autoescape_on_escapes_all_five():  # L4-AC27
    out = Template("{{ x }}", autoescape=True).render({"x": "<a>&\"'"})
    assert out == "&lt;a&gt;&amp;&quot;&#x27;"
    assert "<a>" not in out


def test_autoescape_off_and_literal_never_escaped():  # L4-AC28
    assert Template("{{ x }}").render({"x": "<b>"}) == "<b>"
    # literal template text is never escaped, even with autoescape on
    assert Template("<b>{{ x }}</b>", autoescape=True).render({"x": "&"}) == "<b>&amp;</b>"


def test_autoescape_precedence_and_env_inheritance():  # L4-AC29
    env = Environment(autoescape=True)
    assert env.from_string("{{ x }}").render({"x": "<i>"}) == "&lt;i&gt;"
    # an explicit Template default is not overridden by the environment default
    assert Template("{{ x }}", autoescape=False).render({"x": "<i>"}) == "<i>"


# ---- G7 Undefined strictness ---------------------------------------------


def test_strict_undefined_raises_named_path():  # L4-AC30
    with pytest.raises(TemplateRuntimeError) as info:
        Template("{{ missing }}", strict_undefined=True).render({})
    assert "missing" in str(info.value)
    env = Environment(strict_undefined=True)
    with pytest.raises(TemplateRuntimeError):
        env.from_string("{{ nope }}").render({})


def test_lenient_undefined_and_default_intercepts():  # L4-AC31
    assert Template("[{{ missing }}]").render({}) == "[]"
    assert Template('{{ missing | default("x") }}').render({}) == "x"


# ---- G8 Error positions ---------------------------------------------------


def _syntax(src: str) -> TemplateSyntaxError:
    try:
        Template(src)
    except TemplateSyntaxError as exc:
        return exc
    raise AssertionError("expected TemplateSyntaxError")


def test_position_unterminated_tag():  # L4-AC32
    exc = _syntax("Line1\n{{ oops")
    assert (exc.line, exc.col) == (2, 1)
    assert exc.msg


def test_position_unclosed_block_points_opener():  # L4-AC33
    exc = _syntax("a\n{% for x in y %}\nbody")
    assert (exc.line, exc.col) == (2, 1)
    assert "for" in exc.msg


def test_position_mismatched_and_stray_closer():  # L4-AC34
    mismatch = _syntax("{% if a %}x{% endfor %}")
    assert (mismatch.line, mismatch.col) == (1, 12)
    stray = _syntax("hello {% endif %}")
    assert (stray.line, stray.col) == (1, 7)


def test_position_multiline_and_tabs():  # L4-AC35
    exc = _syntax("ok\n\t{% if %}")
    assert exc.line == 2
    assert exc.col == 2  # a tab counts as one column


# ---- G9 API contract ------------------------------------------------------


def test_public_names_and_exception_hierarchy():  # L4-AC36
    assert set(template_engine.__all__) == {
        "Template",
        "Environment",
        "TemplateError",
        "TemplateSyntaxError",
        "TemplateRuntimeError",
    }
    assert issubclass(TemplateSyntaxError, TemplateError)
    assert issubclass(TemplateRuntimeError, TemplateError)
    exc = _syntax("{{ }}")
    assert isinstance(exc, TemplateError)
    assert isinstance(exc.line, int) and isinstance(exc.col, int) and exc.msg


def test_signatures_keyword_only():  # L4-AC37
    params = inspect.signature(Template.__init__).parameters
    assert params["autoescape"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["strict_undefined"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["autoescape"].default is False
    assert params["strict_undefined"].default is False


def test_render_none_equiv_and_context_not_mutated():  # L4-AC38
    tmpl = Template("{% for i in xs %}{{ i }}{% endfor %}{{ a }}")
    assert tmpl.render(None) == tmpl.render({})
    ctx = {"xs": [1, 2], "a": "A"}
    snapshot = dict(ctx)
    assert tmpl.render(ctx) == "12A"
    assert ctx == snapshot  # render must not mutate the caller's mapping


# ---- G10 Compile-once & linearity ----------------------------------------


def test_render_independence_across_calls():  # L4-AC39
    tmpl = Template("{% for i in xs %}{{ i }}{% endfor %}")
    assert tmpl.render({"xs": [1, 2, 3]}) == "123"
    assert tmpl.render({"xs": [4, 5]}) == "45"
    assert tmpl.render({"xs": [1, 2, 3]}) == "123"  # no leakage from prior render


def test_environment_caches_compiled_template():  # L4-AC40
    calls: list[str] = []

    def loader(name: str) -> str:
        calls.append(name)
        return "Hi {{ x }}"

    env = Environment(loader=loader)
    first = env.get_template("a")
    second = env.get_template("a")
    assert first is second  # compiled once, cached
    assert calls.count("a") == 1


def test_linear_output_under_budget():  # L4-AC41
    src = "{% for i in outer %}{% for j in inner %}x{% endfor %}{% endfor %}"
    tmpl = Template(src)
    ctx = {"outer": list(range(400)), "inner": list(range(400))}
    start = time.perf_counter()
    out = tmpl.render(ctx)
    elapsed = time.perf_counter() - start
    assert len(out) == 160000
    assert elapsed < 2.0


# ---- G11 Sec.1.6 consistency ---------------------------------------------


def test_a1_lenient_uniform_across_positions():  # L4-AC42
    # interpolation emits empty, condition is falsy, loop iterates empty -- same policy
    assert Template("[{{ missing }}]").render({}) == "[]"
    assert Template("{% if missing %}Y{% else %}N{% endif %}").render({}) == "N"
    assert Template("[{% for i in missing %}{{ i }}{% endfor %}]").render({}) == "[]"


def test_a3_autoescape_explicit_and_inherited():  # L4-AC43
    env_on = Environment(autoescape=True)
    env_off = Environment(autoescape=False)
    assert env_on.from_string("{{ x }}").render({"x": "<b>"}) == "&lt;b&gt;"
    assert env_off.from_string("{{ x }}").render({"x": "<b>"}) == "<b>"
    assert Template("{{ x }}").render({"x": "<b>"}) == "<b>"  # pinned default off


# ---- Security / sandbox (NFR-3) ------------------------------------------


def test_no_eval_exec_in_source():  # L4-AC44
    pkg_dir = Path(template_engine.__file__).resolve().parent
    banned = {"eval", "exec", "compile", "__import__"}
    for path in pkg_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in banned, f"{node.func.id} in {path.name}"


def test_sandbox_refuses_underscore_access():  # L4-AC45
    with pytest.raises(TemplateRuntimeError):
        Template("{{ user.__class__ }}").render({"user": object()})
    with pytest.raises(TemplateRuntimeError):
        Template("{{ obj._secret }}").render({"obj": object()})


# ---- Property test (hypothesis) ------------------------------------------

_PLAINTEXT = st.text(
    alphabet=st.characters(codec="utf-8", exclude_characters="{}"),
    max_size=40,
)


@settings(max_examples=150, deadline=None)
@given(text=_PLAINTEXT)
def test_plaintext_roundtrips_unchanged(text):  # L4-AC46
    # A template with no tags renders byte-for-byte unchanged (Sec.1.6 A-2).
    assert Template(text).render({"anything": 1}) == text


def test_error_taxonomy_no_foreign_exception():  # L4-AC47
    # Runtime failures across the malformed corpus surface only as TemplateError.
    cases = [
        ('{{ user.__class__ }}', {"user": object()}),
        ('{{ x | nofilter }}', {"x": 1}),
        ('{% for i in n %}{{ i }}{% endfor %}', {"n": 5}),
        ('{% include "missing" %}', {}),
    ]
    for src, ctx in cases:
        with pytest.raises(TemplateError):
            Template(src, environment=Environment(loader={})).render(ctx)
