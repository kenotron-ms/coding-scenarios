"""Unit tests for the goal-plan compiler (D2, D3, D4).

Covers, per the lane goal:

* **D2** -- regenerating the known-good exemplar: feed the compiler a
  ``plan.json``-shaped spec equivalent to
  ``pipelines/goal_plan_smoke/plan.json`` and prove the *parsed graph
  structure* (node ids, shapes, edges, wave-gating topology, graph attrs) is
  equivalent to the hand-authored ``goal_plan_smoke.dot`` -- structural, not
  byte-for-byte.
* **D3** -- generated output validates against the engine's own
  ``parse_dot`` / ``validate`` with zero ERROR-severity diagnostics (for both
  the 3-lane/2-wave and 2-lane/1-wave plans).
* **D4** -- a 2-lane single-wave plan, the 3-lane/2-wave plan, and an invalid
  plan (missing a required field) producing a clear, named error.

Also covers the post-review-consensus hardening pass: injection/charset
validation (plan.py), the real (non-``SMOKE_MARKER_*``) marker-file
convention, ``terminals`` now being required, and depends_on enforcement.

Engine-dependent checks (D2, D3) locate the attractor engine via
``compiler.validate.load_engine`` and ``pytest.skip`` gracefully when it is not
present, so the pure-Python D4 tests still run in any environment. Set
``COMPILER_REQUIRE_ENGINE=1`` to turn that skip into a hard failure (for CI
environments that must not silently skip engine-dependent coverage).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

# Make the ``compiler`` package importable when this file is run directly or via
# a bare ``pytest`` from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from compiler import build_plan, compile_plan, load_plan
from compiler.plan import PlanValidationError
from compiler.validate import EngineUnavailable, load_engine

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PLAN_3LANE = FIXTURES / "plan_3lane_2wave.json"
PLAN_2LANE = FIXTURES / "plan_2lane_1wave.json"
PLAN_INVALID = FIXTURES / "plan_invalid_missing_wave.json"

EXEMPLAR_DOT = _REPO_ROOT / "pipelines" / "goal_plan_smoke" / "goal_plan_smoke.dot"


def _engine_or_skip():
    try:
        return load_engine()
    except EngineUnavailable as e:  # pragma: no cover - environment dependent
        if os.environ.get("COMPILER_REQUIRE_ENGINE") == "1":
            pytest.fail(
                f"attractor engine required (COMPILER_REQUIRE_ENGINE=1) but "
                f"unavailable: {e}"
            )
        pytest.skip(f"attractor engine unavailable: {e}")


def _minimal_spec(**overrides):
    """A minimal, well-formed 1-lane/1-wave spec with every optional field
    at its default. Used as a base for the injection-regression and
    minimal-spec tests below -- callers mutate a deep-enough copy.
    """
    spec = {
        "plan_id": "p",
        "lanes": {
            "a": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["/bin/sh", "-c", "true"],
                "marker_file": "m.txt",
                "marker_content": "ok",
            }
        },
        "waves": [{"wave": 1}],
        "integration_order": ["a"],
        "terminals": ["COMPLETE", "RESIDUALS_READY", "INFRA_FAILURE", "ABORTED"],
    }
    spec.update(overrides)
    return spec


def _structure(graph):
    """(nodes->shape dict, sorted edge tuples, graph_attrs, default_max_retry, name)."""
    nodes = {nid: n.shape for nid, n in graph.nodes.items()}
    edges = sorted((e.from_node, e.to_node, e.condition, e.weight) for e in graph.edges)
    return nodes, edges, dict(graph.graph_attrs), graph.default_max_retry, graph.name


# ----------------------------------------------------------------------------
# D4: build the two well-formed plans; reject the invalid one.
# ----------------------------------------------------------------------------


def test_d4_build_2lane_single_wave():
    dot = compile_plan(load_plan(PLAN_2LANE))
    assert dot.startswith("//")
    assert "digraph two_lane_single_wave {" in dot
    # Two lanes, one wave -> concurrent launch block, no sequential launch and
    # no second-wave nodes.
    assert "Wave1Launch" in dot
    assert "LaunchLaneA" in dot and "LaunchLaneB" in dot
    assert "Wave2" not in dot
    assert "LaunchLaneC" not in dot


def test_d4_build_3lane_two_wave():
    dot = compile_plan(load_plan(PLAN_3LANE))
    assert "digraph goal_plan_smoke {" in dot
    # Wave 2 lane_c is launched sequentially (just-in-time) as LaunchLaneC.
    assert "LaunchLaneC" in dot
    assert 'plan_waves="1,2"' in dot


def test_d4_invalid_plan_missing_field_named_error():
    with pytest.raises(PlanValidationError) as exc:
        load_plan(PLAN_INVALID)
    msg = str(exc.value)
    # The error must name the offending lane and field, not be a generic crash.
    assert "lane_b" in msg
    assert "wave" in msg


@pytest.mark.parametrize(
    "spec, needle",
    [
        ({"plan_id": "p"}, "lanes"),  # missing lanes
        (
            {
                "plan_id": "p",
                "lanes": {
                    "a": {
                        "wave": 1,
                        "depends_on": [],
                        "verifier_argv": ["x"],
                        "marker_file": "m",
                        "marker_content": "c",
                    }
                },
                "waves": [{"wave": 1, "lanes": ["a"]}],
            },
            "integration_order",
        ),  # missing integration_order
    ],
)
def test_d4_invalid_specs_are_named(spec, needle):
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert needle in str(exc.value)


def test_d4_integration_order_must_be_wave_monotonic():
    spec = {
        "plan_id": "p",
        "lanes": {
            "a": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "ma",
                "marker_content": "ca",
            },
            "b": {
                "wave": 2,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "mb",
                "marker_content": "cb",
            },
        },
        "waves": [{"wave": 1, "lanes": ["a"]}, {"wave": 2, "lanes": ["b"]}],
        "integration_order": ["b", "a"],  # wave 2 before wave 1 -- invalid
    }
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "non-decreasing" in str(exc.value)


# ----------------------------------------------------------------------------
# D2: structural equivalence to the hand-authored exemplar.
# ----------------------------------------------------------------------------


def test_d2_structural_equivalence_to_exemplar():
    parse_dot, _validate = _engine_or_skip()

    generated = compile_plan(load_plan(PLAN_3LANE))
    g_gen = parse_dot(generated)
    g_ref = parse_dot(EXEMPLAR_DOT.read_text(encoding="utf-8"))

    n_gen, e_gen, a_gen, dmr_gen, name_gen = _structure(g_gen)
    n_ref, e_ref, a_ref, dmr_ref, name_ref = _structure(g_ref)

    # Same node ids.
    assert set(n_gen) == set(n_ref), (
        f"node id mismatch; +{sorted(set(n_gen) - set(n_ref))} -{sorted(set(n_ref) - set(n_gen))}"
    )
    # Same shape for every node.
    shape_diffs = {
        nid: (n_gen[nid], n_ref[nid]) for nid in n_gen if n_gen[nid] != n_ref[nid]
    }
    assert not shape_diffs, f"shape diffs: {shape_diffs}"
    # Same edges (source, target, condition, weight) -- this is the wave-gating
    # topology.
    assert set(e_gen) == set(e_ref), (
        f"edge mismatch; +{sorted(set(e_gen) - set(e_ref))} -{sorted(set(e_ref) - set(e_gen))}"
    )
    # Same graph-level attributes and promoted fields.
    assert a_gen == a_ref
    assert dmr_gen == dmr_ref
    assert name_gen == name_ref


def test_d2_wave_gating_topology_reachability():
    """Wave 2's lane_c is reachable only via wave 1's ACCEPTED edges."""
    parse_dot, _validate = _engine_or_skip()
    g = parse_dot(compile_plan(load_plan(PLAN_3LANE)))

    incoming = {}
    for e in g.edges:
        incoming.setdefault(e.to_node, []).append(e)

    # LaunchLaneC (wave 2) has exactly one predecessor: IntegrateB's ACCEPTED edge.
    lc_in = incoming["LaunchLaneC"]
    assert len(lc_in) == 1
    assert lc_in[0].from_node == "IntegrateB"
    assert lc_in[0].condition == "context.tool.last_line=ACCEPTED"

    # IntegrateB's only non-failure successor is LaunchLaneC (ACCEPTED), and
    # IntegrateA's is ParentVerifyB (ACCEPTED) -- wave 2 sits structurally behind
    # both wave-1 ACCEPTED edges.
    accepted = {
        (e.from_node, e.to_node)
        for e in g.edges
        if e.condition == "context.tool.last_line=ACCEPTED"
    }
    assert ("IntegrateA", "ParentVerifyB") in accepted
    assert ("IntegrateB", "LaunchLaneC") in accepted
    assert ("IntegrateC", "PreCoherenceAggregate") in accepted


# ----------------------------------------------------------------------------
# D3: generated output validates (zero ERROR diagnostics).
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("plan_path", [PLAN_3LANE, PLAN_2LANE])
def test_d3_generated_output_validates(plan_path):
    parse_dot, validate = _engine_or_skip()
    graph = parse_dot(compile_plan(load_plan(plan_path)))
    diagnostics = validate(graph)
    errors = [d for d in diagnostics if getattr(d, "severity", "") == "ERROR"]
    assert not errors, "engine reported ERROR diagnostics: " + "; ".join(
        f"[{d.rule}] {d.message}" for d in errors
    )


# ----------------------------------------------------------------------------
# Bug fix: a single-lane wave 1 must not emit a single-outgoing-edge
# `component` fan-out node.
#
# Root cause: the attractor engine's Bug-G fix only reroutes `component`
# nodes with MORE THAN ONE outgoing edge to their fan-in. A component node
# with exactly one outgoing edge (a single-lane wave 1's old `Wave1Launch`)
# falls through to normal edge selection, so its lone successor executes
# TWICE -- once via the ParallelHandler fan-out, once via ordinary edge
# traversal -- and the second worktree creation crashes with
# WORKTREE:PATH_EXISTS. Because the wave-1 LaunchLane node had no failure
# edge, the pipeline then hard-aborted with "No matching edge from node
# 'LaunchLaneA'". The fix: skip the component wrapper entirely when wave 1
# has exactly one lane, route Admit straight to that lane's LaunchLane node,
# and give it a real failure edge to InfraCarrier.
# ----------------------------------------------------------------------------


def test_single_lane_wave1_emits_no_component_launch_node():
    """A single-lane, single-wave plan must NOT emit a `Wave1Launch`
    component-shaped fan-out node at all: Admit routes straight to the lone
    lane's LaunchLaneA (a parallelogram), never through a component node
    that would have exactly one outgoing edge."""
    spec = _minimal_spec()
    dot = compile_plan(build_plan(spec))

    assert "Wave1Launch" not in dot
    assert "shape=component" not in dot

    # Admit routes straight to LaunchLaneA (the same admitted/weight=2
    # condition previously used to reach the component node).
    assert (
        '  Admit -> LaunchLaneA [condition="context.tool.last_line=admitted", weight="2"];'
        in dot
    )

    # LaunchLaneA itself is a plain parallelogram launch node.
    laa_start = dot.index("LaunchLaneA [\n")
    laa_block = dot[laa_start : dot.index("];", laa_start)]
    assert "shape=parallelogram" in laa_block


def test_single_lane_wave1_launch_has_crash_edge_to_infracarrier():
    """The single wave-1 LaunchLaneA node has BOTH a success edge (to
    ClassifyWave1 -- NOT the `tripleoctagon` Wave1Collect fan-in, which has
    no parallel results to aggregate without a fan-out feeding it) and a
    failure edge (to InfraCarrier), using the EXACT two tokens
    _LAUNCH_WAVE1_BODY prints on normal completion -- 'launched' (the
    supervisor subprocess returned rc==0) and 'supervisor_infra_failure' (it
    did not) -- so a real launch failure is handled instead of dead-ending
    with 'No matching edge from node LaunchLaneA'."""
    spec = _minimal_spec()
    dot = compile_plan(build_plan(spec))

    assert (
        '  LaunchLaneA -> ClassifyWave1 [condition="context.tool.last_line=launched", weight="2"];'
        in dot
    )
    assert (
        '  LaunchLaneA -> InfraCarrier [condition="context.tool.last_line=supervisor_infra_failure"];'
        in dot
    )
    # Confirm this is what the launch body itself actually prints (not a
    # guessed token): _LAUNCH_WAVE1_BODY's own success/failure print line.
    from compiler.generator import _LAUNCH_WAVE1_BODY

    assert (
        'print("launched" if rc.returncode == 0 else "supervisor_infra_failure")'
        in _LAUNCH_WAVE1_BODY
    )


def test_single_lane_wave1_validates_with_zero_engine_errors():
    parse_dot, validate = _engine_or_skip()
    spec = _minimal_spec()
    graph = parse_dot(compile_plan(build_plan(spec)))
    diagnostics = validate(graph)
    errors = [d for d in diagnostics if getattr(d, "severity", "") == "ERROR"]
    assert not errors, "engine reported ERROR diagnostics: " + "; ".join(
        f"[{d.rule}] {d.message}" for d in errors
    )


def test_multilane_wave1_unaffected_by_single_lane_fix():
    """Guard: the multi-lane wave-1 fan-out path (>1 lane) is completely
    unchanged by the single-lane special case above -- still a `component`
    node with one outgoing edge per lane, still an unconditional edge from
    each LaunchLane to Wave1Collect (outcome classification happens later,
    in ClassifyWave1, from the actual per-lane result files)."""
    dot = compile_plan(load_plan(PLAN_2LANE))
    assert "Wave1Launch" in dot
    assert "shape=component" in dot
    assert "  Wave1Launch -> LaunchLaneA;" in dot
    assert "  Wave1Launch -> LaunchLaneB;" in dot
    assert "  LaunchLaneA -> Wave1Collect;" in dot
    assert "  LaunchLaneB -> Wave1Collect;" in dot
    assert (
        '  Admit -> Wave1Launch [condition="context.tool.last_line=admitted", weight="2"];'
        in dot
    )


# ----------------------------------------------------------------------------
# Follow-on defect: the single-lane fix above still routed success through
# `Wave1Collect`, a `tripleoctagon` PARALLEL fan-in node. That node only has
# results to aggregate when fed by a `component` fan-out's ParallelHandler
# run; with no fan-out in the single-lane branch, the engine dead-ended at
# runtime with "No parallel results to evaluate" / "No matching edge from
# node 'Wave1Collect'". Root-cause data-flow check: `ClassifyWave{fw}`'s
# `classify()` reads each lane's outcome from per-lane result FILES under
# $state_root (`$state_root/results/<lane>.json`,
# `$state_root/lane-results/<lane>.json`) -- never the engine's
# parallel-results context -- so it is safe to route straight to it for
# exactly one lane. The fix: skip `Wave{fw}Collect` entirely in the
# single-lane branch and route `LaunchLane{sfx} -> ClassifyWave{fw}` on
# 'launched' instead.
# ----------------------------------------------------------------------------


def test_single_lane_wave1_bypasses_parallel_fan_in_with_no_dead_ends():
    """For a single-lane, single-wave plan the generated DOT must: contain
    no `tripleoctagon`-shaped node and no `Wave1Collect` node at all; route
    the launch node's success outcome ('launched') to ClassifyWave1 (which
    still forwards to ParentVerifyA); keep the failure outcome
    ('supervisor_infra_failure') routed to InfraCarrier; and have every node
    reachable from Start with at least one outgoing edge (Exit excepted) --
    i.e. no dead-ends of the kind that produced the runtime
    'No matching edge from node Wave1Collect' failure."""
    spec = _minimal_spec()
    dot = compile_plan(build_plan(spec))

    assert "tripleoctagon" not in dot
    assert "Wave1Collect" not in dot
    assert (
        '  LaunchLaneA -> ClassifyWave1 [condition="context.tool.last_line=launched", weight="2"];'
        in dot
    )
    assert (
        '  LaunchLaneA -> InfraCarrier [condition="context.tool.last_line=supervisor_infra_failure"];'
        in dot
    )
    assert (
        "  ClassifyWave1 -> ParentVerifyA "
        "[condition=\"context.tool.last_line!=''\"];" in dot
    )

    # Plain-regex structural reachability / dead-end sweep -- deliberately
    # engine-independent so this part of the test always runs. Node blocks
    # are emitted either as multi-line "  Id [\n    attr,\n    ...\n  ];"
    # (_Emitter.node) or, for Start/Exit only, a one-line
    # "  Id [shape=..., label=...];" (_Emitter.line); both start with
    # "  <word> [" followed immediately by either end-of-line or "shape=".
    # "graph" itself renders identically (it is a graph-attributes block,
    # not a node) so it is explicitly excluded.
    node_ids = {
        n
        for n in re.findall(r"^  (\w+)\s*\[(?:shape=|$)", dot, re.MULTILINE)
        if n != "graph"
    }
    edges = re.findall(r"^  (\w+) -> (\w+)", dot, re.MULTILINE)
    assert node_ids and edges

    outgoing: dict[str, set[str]] = {}
    for src, dst in edges:
        outgoing.setdefault(src, set()).add(dst)

    reachable = {"Start"}
    frontier = ["Start"]
    while frontier:
        cur = frontier.pop()
        for nxt in outgoing.get(cur, ()):
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)
    assert reachable == node_ids, f"unreachable nodes: {node_ids - reachable}"

    # Every node has an outgoing edge except the terminal Exit sink.
    dead_ends = {n for n in node_ids if n != "Exit" and n not in outgoing}
    assert not dead_ends, f"dead-end nodes with no outgoing edge: {dead_ends}"


def test_single_lane_wave1_validates_with_zero_engine_errors_no_fan_in():
    """Engine-backed companion to the structural test above: parse + validate
    the single-lane DOT and require zero ERROR-severity diagnostics (skips
    gracefully if the attractor engine is unavailable)."""
    parse_dot, validate = _engine_or_skip()
    spec = _minimal_spec()
    graph = parse_dot(compile_plan(build_plan(spec)))
    diagnostics = validate(graph)
    errors = [d for d in diagnostics if getattr(d, "severity", "") == "ERROR"]
    assert not errors, "engine reported ERROR diagnostics: " + "; ".join(
        f"[{d.rule}] {d.message}" for d in errors
    )


# ----------------------------------------------------------------------------
# Escaping round-trip: an intended tool_command survives DOT emission and
# engine re-parse unchanged (the correctness guarantee behind D2/D3).
# ----------------------------------------------------------------------------


def test_toolcommand_roundtrips_through_parse_dot():
    parse_dot, _validate = _engine_or_skip()
    g = parse_dot(compile_plan(load_plan(PLAN_3LANE)))

    pv = g.nodes["ParentVerifyA"].attrs.get("tool_command")
    # Real newlines (not literal backslash-n) after DOT unescaping.
    assert pv.startswith("#!/bin/sh\nset -e\n")
    # The lane's verifier argv is embedded as a Python literal, with the shell
    # command-substitution left intact (not mangled by engine $-substitution or
    # our escaping).
    assert "'/bin/sh', '-c'" in pv
    assert '"$(cat SMOKE_MARKER_lane_a.txt)"' in pv

    # Per-lane data-driven fields.
    assert "seeded_failure=true" in g.nodes["LaunchLaneB"].attrs.get("tool_command")
    assert "seeded_failure=false" in g.nodes["LaunchLaneA"].attrs.get("tool_command")
    # Cumulative + full aggregate checks are data-driven from each lane's REAL
    # marker_file (not a synthesized SMOKE_MARKER_$f.txt template loop --
    # see BLOCKING 3 / test_real_marker_convention_used_in_aggregate_gate).
    integrate_b_cmd = g.nodes["IntegrateB"].attrs.get("tool_command")
    assert "test -f SMOKE_MARKER_lane_a.txt" in integrate_b_cmd
    assert "test -f SMOKE_MARKER_lane_b.txt" in integrate_b_cmd
    assert "for f in" not in integrate_b_cmd
    pre_coherence_cmd = g.nodes["PreCoherenceAggregate"].attrs.get("tool_command")
    assert "test -f SMOKE_MARKER_lane_a.txt" in pre_coherence_cmd
    assert "test -f SMOKE_MARKER_lane_b.txt" in pre_coherence_cmd
    assert "test -f SMOKE_MARKER_lane_c.txt" in pre_coherence_cmd
    assert "for f in" not in pre_coherence_cmd


def test_launch_forks_base_sha_in_wave1_and_head_in_later_wave():
    parse_dot, _validate = _engine_or_skip()
    g = parse_dot(compile_plan(load_plan(PLAN_3LANE)))
    # Wave-1 lane forks the immutable base SHA.
    assert 'commit_sha="$product_base_sha"' in g.nodes["LaunchLaneA"].attrs.get(
        "tool_command"
    )
    # Wave-2 lane forks the current integration HEAD (post wave-1 integration).
    lc = g.nodes["LaunchLaneC"].attrs.get("tool_command")
    assert "integration_head = subprocess.run" in lc
    assert "commit_sha=integration_head" in lc


def test_determinism_same_spec_same_output():
    spec = load_plan(PLAN_3LANE)
    assert compile_plan(spec) == compile_plan(spec)


# ----------------------------------------------------------------------------
# CRITICAL 1 -- injection/charset validation regression tests.
#
# Each hostile fragment below was (per the PoC that motivated this fix) either
# live-shell-injectable, heredoc-breaking, or DOT-header-breaking when
# interpolated raw. Every one of them must be rejected with a named
# PlanValidationError at plan.py's validation boundary -- never reach the
# generator.
# ----------------------------------------------------------------------------

HOSTILE_FRAGMENTS = [
    ";",
    "$",
    "`",
    '"',
    "'",
    "\\",
    "|",
    "&",
    "\n",
    "..",
    "PYEOF",
]


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_plan_id(fragment):
    spec = _minimal_spec(plan_id=f"p{fragment}x")
    with pytest.raises(PlanValidationError):
        build_plan(spec)


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_lane_id(fragment):
    lane_id = f"a{fragment}x"
    spec = _minimal_spec(
        lanes={
            lane_id: {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["/bin/sh", "-c", "true"],
                "marker_file": "m.txt",
                "marker_content": "ok",
            }
        },
        integration_order=[lane_id],
    )
    with pytest.raises(PlanValidationError):
        build_plan(spec)


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_marker_file(fragment):
    spec = _minimal_spec()
    spec["lanes"]["a"]["marker_file"] = f"m{fragment}x.txt"
    with pytest.raises(PlanValidationError):
        build_plan(spec)


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_marker_content(fragment):
    spec = _minimal_spec()
    spec["lanes"]["a"]["marker_content"] = f"c{fragment}x"
    with pytest.raises(PlanValidationError):
        build_plan(spec)


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_branch(fragment):
    spec = _minimal_spec()
    spec["lanes"]["a"]["branch"] = f"b{fragment}x"
    with pytest.raises(PlanValidationError):
        build_plan(spec)


def test_injection_rejected_in_correction_child_dot_git_ref_style():
    """Even correction.child_dot (which has no git-ref carve-out) must reject
    a value that looks like an attempted cross-repo/shell escape."""
    spec = _minimal_spec(correction={"child_dot": "subgraphs/x; touch /tmp/PWNED #"})
    with pytest.raises(PlanValidationError):
        build_plan(spec)


def test_delivery_child_dot_type_checked():
    """CRITICAL 1: delivery.child_dot and correction.child_dot previously had
    NO isinstance check at all."""
    spec = _minimal_spec(delivery={"child_dot": 12345})
    with pytest.raises(PlanValidationError):
        build_plan(spec)
    spec2 = _minimal_spec(correction={"child_dot": ["not", "a", "string"]})
    with pytest.raises(PlanValidationError):
        build_plan(spec2)


def test_delivery_child_dot_accepts_pinned_git_ref():
    """The one legitimate exception: delivery.child_dot may hold a SHA-pinned
    git+https cross-repo reference, and it is emitted verbatim (not truncated
    by _basename())."""
    git_ref = "git+https://github.com/org/repo.git@deadbeef#subdirectory=subgraphs/deliver_pr.dot"
    spec = _minimal_spec(delivery={"child_dot": git_ref})
    dot = compile_plan(build_plan(spec))
    assert git_ref in dot


def test_plan_id_with_hyphen_rejected_at_compile_time():
    """plan.py's charset for plan_id permits hyphens (it's also used in
    quoted contexts), but compile_plan() additionally requires plan_id to be
    a bare DOT identifier since it is used unquoted in 'digraph <id> {'."""
    spec = _minimal_spec(plan_id="goal-plan-smoke")
    plan = build_plan(spec)  # plan.py accepts it
    with pytest.raises(PlanValidationError):
        compile_plan(plan)  # generator.py rejects it


# ----------------------------------------------------------------------------
# BLOCKING 4 -- terminals is now required; a minimal spec must not KeyError.
# ----------------------------------------------------------------------------


def test_terminals_now_required():
    spec = _minimal_spec()
    del spec["terminals"]
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "terminals" in str(exc.value)


def test_minimal_spec_all_optional_fields_omitted_compiles_and_corresponds():
    """A minimal spec (every optional field omitted, only the now-required
    fields present) must compile, and the generated CheckPlanCorrespondence
    body's extraction logic (mirrored here) must not KeyError -- guards the
    class of bug where an optional field the generator reads unconditionally
    could compile fine and then blow up at pipeline run time."""
    spec = _minimal_spec()
    plan = build_plan(spec)
    dot_source = compile_plan(plan)

    # Mirror _CHECK_CORRESPONDENCE_BODY's extraction logic exactly, against
    # the same raw spec dict a real $plan_json_path would contain.
    import re as _re

    def attr(name):
        m = _re.search(name + r'="([^"]*)"', dot_source)
        return m.group(1) if m else None

    ok = True
    ok &= attr("plan_lanes") == ",".join(sorted(spec["lanes"].keys()))
    ok &= attr("plan_waves") == ",".join(str(w["wave"]) for w in spec["waves"])
    ok &= attr("plan_integration_order") == ",".join(spec["integration_order"])
    ok &= attr("plan_terminals") == ",".join(
        spec["terminals"]
    )  # would KeyError if omitted, pre-fix
    assert ok


# ----------------------------------------------------------------------------
# BLOCKING 3 -- aggregate/sweep gates are driven by each lane's REAL
# marker_file/marker_content, not a synthesized SMOKE_MARKER_<id>.txt template.
# ----------------------------------------------------------------------------


def test_real_marker_convention_used_in_aggregate_gate():
    spec = _minimal_spec(
        plan_id="real_plan",
        lanes={
            "auth": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["/bin/sh", "-c", "true"],
                "marker_file": "artifacts/auth.done",
                "marker_content": "auth-complete",
            }
        },
        integration_order=["auth"],
    )
    dot = compile_plan(build_plan(spec))
    assert "artifacts/auth.done" in dot
    assert "SMOKE_MARKER" not in dot
    assert "auth-complete" in dot


# ----------------------------------------------------------------------------
# Bug fix: FinalFreeze's final lane-sweep gated each lane's marker with EXACT
# STRING EQUALITY of the marker file's ENTIRE contents to marker_content
# (`[ "$(cat <file>)" = <content> ]`). That is correct only for the
# marker-FIXTURE brick (goal_lane.dot), whose lane writes a file whose entire
# contents equal marker_content (e.g. "lane_a:ok"). For a REAL-work lane
# (goal_lane_impl.dot), marker_file is real source (e.g.
# "solution/csvparse.py") that CONTAINS marker_content (e.g. "parse_csv")
# without being equal to it -- so the equality gate printed 'sweep_fail' and
# drove the whole pipeline to INFRA_FAILURE even after ParentVerify PASS and
# Integrate ACCEPTED. Fix: gate on CONTAINMENT (`grep -qF` fixed-string)
# instead of equality -- correct for both bricks.
# ----------------------------------------------------------------------------


def _real_work_marker_spec():
    return _minimal_spec(
        plan_id="real_work_plan",
        lanes={
            "a": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["/bin/sh", "-c", "true"],
                # A realistic real-work marker: marker_content is a SUBSTRING
                # of marker_file's contents (a real source file), never equal
                # to the file's entire contents -- unlike the fixture brick's
                # "whole file == marker_content" convention.
                "marker_file": "solution/csvparse.py",
                "marker_content": "parse_csv",
            }
        },
        integration_order=["a"],
    )


def test_final_freeze_sweep_uses_containment_not_equality():
    """The generated FinalFreeze sweep for a real-work lane (marker_content a
    substring of, not equal to, marker_file's contents) must use a
    fixed-string containment check (`grep -qF`) and must NOT contain the old
    exact-equality form (`$(cat ...)` command substitution compared with
    `=`)."""
    dot = compile_plan(build_plan(_real_work_marker_spec()))

    m = re.search(r"  FinalFreeze \[\n(.*?)\n  \];", dot, re.DOTALL)
    assert m, "FinalFreeze node block not found in generated DOT"
    final_freeze_block = m.group(1)

    # New containment form: existence guard + fixed-string grep, still
    # correctly quoted/escaped by the same shlex.quote path as before.
    assert "grep -qF -e parse_csv -- solution/csvparse.py" in final_freeze_block
    assert "test -f solution/csvparse.py &&" in final_freeze_block

    # Old exact-equality form must be entirely gone.
    assert "$(cat" not in final_freeze_block
    assert '" = ' not in final_freeze_block


def test_final_freeze_sweep_validates_with_zero_engine_errors_for_real_work_lane():
    """Engine-backed companion: the generated DOT for a real-work lane (whose
    marker_content is a substring, not the whole file) still validates with
    zero ERROR-severity diagnostics (skips gracefully if the attractor engine
    is unavailable)."""
    parse_dot, validate = _engine_or_skip()
    graph = parse_dot(compile_plan(build_plan(_real_work_marker_spec())))
    diagnostics = validate(graph)
    errors = [d for d in diagnostics if getattr(d, "severity", "") == "ERROR"]
    assert not errors, "engine reported ERROR diagnostics: " + "; ".join(
        f"[{d.rule}] {d.message}" for d in errors
    )


# ----------------------------------------------------------------------------
# IMPORTANT 6 -- depends_on is enforced (wave + integration_order), not just
# referentially validated.
# ----------------------------------------------------------------------------


def test_depends_on_later_wave_rejected():
    spec = {
        "plan_id": "p",
        "lanes": {
            "a": {
                "wave": 1,
                "depends_on": ["b"],  # a depends on b, which is in a LATER wave
                "verifier_argv": ["x"],
                "marker_file": "ma",
                "marker_content": "ca",
            },
            "b": {
                "wave": 2,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "mb",
                "marker_content": "cb",
            },
        },
        "waves": [{"wave": 1}, {"wave": 2}],
        "integration_order": ["a", "b"],
        "terminals": ["COMPLETE", "RESIDUALS_READY", "INFRA_FAILURE", "ABORTED"],
    }
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "later wave" in str(exc.value)


def test_depends_on_wrong_integration_order_rejected():
    spec = {
        "plan_id": "p",
        "lanes": {
            "a": {
                "wave": 1,
                "depends_on": ["b"],  # a depends on b but is integrated first
                "verifier_argv": ["x"],
                "marker_file": "ma",
                "marker_content": "ca",
            },
            "b": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "mb",
                "marker_content": "cb",
            },
        },
        "waves": [{"wave": 1}],
        "integration_order": ["a", "b"],
        "terminals": ["COMPLETE", "RESIDUALS_READY", "INFRA_FAILURE", "ABORTED"],
    }
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "does not precede" in str(exc.value)


# ----------------------------------------------------------------------------
# IMPORTANT 7 -- budgets.lane_wall_timeout_seconds / verifier_timeout_seconds
# and waves[].concurrency are read (not hardcoded / not ignored).
# ----------------------------------------------------------------------------


def test_custom_timeouts_flow_into_generated_output():
    spec = _minimal_spec(
        budgets={"lane_wall_timeout_seconds": 1200, "verifier_timeout_seconds": 45}
    )
    dot = compile_plan(build_plan(spec))
    # tool_command is emitted as a quoted DOT attribute value, so the
    # embedded Python dict literal's own double quotes are backslash-escaped.
    assert '\\"wall_timeout_seconds\\": 1200' in dot
    assert "timeout_seconds=45" in dot
    assert "aggregate_timeout_seconds=45" in dot


def test_wave_concurrency_cap_flows_into_max_parallel():
    spec = _minimal_spec(
        lanes={
            "a": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "ma",
                "marker_content": "ca",
            },
            "b": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "mb",
                "marker_content": "cb",
            },
        },
        waves=[{"wave": 1, "concurrency": 1}],
        integration_order=["a", "b"],
    )
    dot = compile_plan(build_plan(spec))
    assert "max_parallel=1" in dot


# ----------------------------------------------------------------------------
# IMPORTANT 8 -- a declared wave with no lanes is rejected.
# ----------------------------------------------------------------------------


def test_empty_wave_rejected():
    spec = _minimal_spec(waves=[{"wave": 1}, {"wave": 2}])  # wave 2 has no lanes
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "wave 2" in str(exc.value)


# ----------------------------------------------------------------------------
# goal_condition_file -- optional, additive, opaque per-lane child --param.
#
# Contract (see compiler/README.md and the lane goal):
#   * omitted/empty  => output byte-identical to the pre-field compile (strictly
#     additive; not one byte changes);
#   * present        => appended as the LAST `--param goal_condition_file=<value>`
#     of EACH of that lane's launches, in BOTH launch bodies (wave-1 concurrent
#     AND later-wave sequential);
#   * the value is a path, charset-validated in plan.py exactly like marker_file
#     (the compiler passes it through opaquely, never reading its contents).
# ----------------------------------------------------------------------------


def test_goal_condition_file_omitted_is_byte_identical_additive_noop():
    """(6a) Omitting the field adds zero bytes: the 3-lane exemplar plan (whose
    fixtures never set the field) compiles with no `goal_condition_file` param and
    no un-substituted template token, and an explicit empty value is byte-for-byte
    identical to omission -- so a field-omitting spec's `.dot` is exactly the
    pre-field output."""
    # The exemplar plan omits the field entirely.
    dot_exemplar = compile_plan(load_plan(PLAN_3LANE))
    assert "goal_condition_file" not in dot_exemplar
    # The generator token must be fully collapsed -- never leak into output.
    assert "@@GOAL_CONDITION_FILE_PARAM@@" not in dot_exemplar

    # Omitted vs explicit empty string are byte-identical (empty => no bytes added).
    dot_omitted = compile_plan(build_plan(_minimal_spec()))
    with_empty = _minimal_spec()
    with_empty["lanes"]["a"]["goal_condition_file"] = ""
    assert compile_plan(build_plan(with_empty)) == dot_omitted
    assert "goal_condition_file" not in dot_omitted


def test_goal_condition_file_threaded_as_last_param_in_both_launch_bodies():
    """(6b) A lane with goal_condition_file set emits exactly one trailing
    `--param goal_condition_file=<value>` in EACH of its launches -- proven for
    BOTH launch bodies at once: lane `a` (wave 1, concurrent launch body) and lane
    `b` (wave 2, sequential launch body). Distinct per-lane values make the
    per-launch count and ordering unambiguous."""
    spec = {
        "plan_id": "p",
        "lanes": {
            "a": {
                "wave": 1,
                "depends_on": [],
                "verifier_argv": ["x"],
                "marker_file": "ma",
                "marker_content": "ca",
                "goal_condition_file": "goals/a.md",
            },
            "b": {
                "wave": 2,
                "depends_on": ["a"],
                "verifier_argv": ["x"],
                "marker_file": "mb",
                "marker_content": "cb",
                "goal_condition_file": "goals/b.md",
            },
        },
        "waves": [{"wave": 1}, {"wave": 2}],
        "integration_order": ["a", "b"],
        "terminals": ["COMPLETE", "RESIDUALS_READY", "INFRA_FAILURE", "ABORTED"],
    }
    dot = compile_plan(build_plan(spec))

    # Exactly one occurrence per lane -> exactly one per launch (each lane launches
    # once: wave-1 lane a concurrently, wave-2 lane b sequentially).
    assert dot.count("goal_condition_file=goals/a.md") == 1
    assert dot.count("goal_condition_file=goals/b.md") == 1

    # ...and it is the LAST --param, appended immediately after max_attempts, in
    # each launch's child_argv (raw DOT escapes the embedded list literal's
    # quotes as \"). Asserting the whole trailing fragment proves BOTH position
    # (last, closing the argv list with `]`) and that it is a real --param.
    assert (
        'max_attempts=3\\", \\"--param\\", \\"goal_condition_file=goals/a.md\\"]' in dot
    )
    assert (
        'max_attempts=3\\", \\"--param\\", \\"goal_condition_file=goals/b.md\\"]' in dot
    )


@pytest.mark.parametrize("fragment", HOSTILE_FRAGMENTS)
def test_injection_rejected_in_goal_condition_file(fragment):
    """The field is interpolated into the generated launch argv, so it is
    charset-validated (path charset) exactly like marker_file: every hostile
    fragment must be rejected at plan.py's boundary, never reaching the
    generator."""
    spec = _minimal_spec()
    spec["lanes"]["a"]["goal_condition_file"] = f"goals/{fragment}x.md"
    with pytest.raises(PlanValidationError):
        build_plan(spec)


def test_goal_condition_file_non_string_rejected():
    """A non-string goal_condition_file (when provided) is a named validation
    error, not a silent default or a downstream crash."""
    spec = _minimal_spec()
    spec["lanes"]["a"]["goal_condition_file"] = 12345
    with pytest.raises(PlanValidationError) as exc:
        build_plan(spec)
    assert "goal_condition_file" in str(exc.value)
