"""Plan-spec loading and validation for the goal-plan compiler.

A ``plan.json``-shaped spec is the *input* the compiler reads to generate a
``goal_plan_smoke``-family parent ``.dot`` (see the design doc,
``docs/plans/2026-08-24-goal-plan-compiler-resolve-design.md``). This module
turns that raw dict into a validated, normalized in-memory model, and raises a
single, clearly-named error (:class:`PlanValidationError`) the moment a required
field is missing or the wave/integration structure is internally inconsistent --
never a malformed graph downstream.

Determinism is the whole point: this module contains no LLM call and no
randomness. Same spec in, same model out.

Security note -- every spec value that the generator later interpolates into
generated shell text, Python heredocs, or DOT syntax is charset-validated (or,
for free-text fields like ``marker_content``, denylist-validated) HERE, before
it is ever stored on a :class:`Lane`/:class:`Plan`. This is the single
choke-point: a hostile ``plan.json`` is rejected with a named
:class:`PlanValidationError` long before any string ever reaches
``compiler/generator.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Family defaults -- applied only when the spec omits an optional field, so the
# compiler stays faithful to the hand-authored ``goal_plan_smoke`` exemplar it
# generalizes while accepting minimal specs.
DEFAULT_CHILD_DOT = "subgraphs/goal_lane.dot"
DEFAULT_CORRECTION_CHILD_DOT = "subgraphs/integration_correction.dot"
DEFAULT_DELIVERY_CHILD_DOT = "subgraphs/deliver_pr.dot"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LANE_WALL_TIMEOUT_SECONDS = 600
DEFAULT_VERIFIER_TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Charset/injection validation.
#
# Every one of these patterns is an ALLOWLIST: only the listed characters are
# accepted. Shell metacharacters (``; $ ` " ' \ | &``), newlines, and the
# heredoc delimiter used throughout the generated tool_command bodies
# (``PYEOF``) are structurally impossible to smuggle through an allowlisted
# field -- there is no need to separately denylist them there. ``marker_content``
# is the one exception: it is free-text *content*, not an identifier, so it
# cannot be charset-allowlisted the same way and is denylist-validated instead.
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
# The one legitimate case where a child_dot field is NOT a repo-relative path:
# delivery.child_dot may hold a SHA-pinned cross-repo reference. Charset here
# is deliberately narrow (no shell metacharacters, no spaces, no quotes).
_GIT_CHILD_DOT_RE = re.compile(
    r"^git\+https://[A-Za-z0-9._/:@-]+#subdirectory=[A-Za-z0-9._/-]+$"
)

_UNSAFE_SUBSTRINGS = ("..", "PYEOF")
_MARKER_CONTENT_MAX_LEN = 4096
# Shell/Python string-literal metacharacters that would let marker_content
# break out of the double-quoted Python string literal it is interpolated
# into inside a `python3 - <<'PYEOF'` heredoc (see _render_launch).
_MARKER_CONTENT_DENY_CHARS = ";$`\"'\\|&"


class PlanValidationError(ValueError):
    """Raised when a plan spec is missing a required field or is structurally
    inconsistent. The message always names the offending field/lane so a caller
    (human or Wave-2 integrating skill) gets an actionable error, not a stack
    trace deep inside graph emission.
    """


@dataclass(frozen=True)
class Lane:
    """One validated lane, as the generator consumes it."""

    lane_id: str
    wave: int
    depends_on: tuple[str, ...]
    verifier_argv: tuple[str, ...]
    marker_file: str
    marker_content: str
    seeded_failure: bool = False
    child_dot: str = DEFAULT_CHILD_DOT
    branch: str = ""  # resolved by Plan.__post_init__ if left empty
    # Optional per-lane path passed opaquely to the child lane brick as the LAST
    # runtime --param (goal_condition_file=<value>). The compiler never reads its
    # contents; it only charset-validates the path and threads it through. Empty
    # (the default) => no param emitted => byte-identical output to pre-field.
    goal_condition_file: str = ""


@dataclass(frozen=True)
class Plan:
    """A validated, normalized plan spec.

    Construct via :func:`load_plan` (from a file) or :func:`build_plan` (from an
    already-parsed dict). Both run full validation before returning.
    """

    plan_id: str
    lanes: dict[str, Lane]
    waves: tuple[int, ...]
    integration_order: tuple[str, ...]
    terminals: tuple[str, ...]
    branch_namespace: str
    max_attempts: int
    correction_child_dot: str
    delivery_child_dot: str
    lane_wall_timeout_seconds: int
    verifier_timeout_seconds: int
    concurrency_by_wave: dict[int, int]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def lane_ids_sorted(self) -> list[str]:
        return sorted(self.lanes.keys())

    def first_wave(self) -> int:
        return self.waves[0]

    def wave_of(self, lane_id: str) -> int:
        return self.lanes[lane_id].wave

    def first_wave_lane_ids(self) -> list[str]:
        """Lanes in the first wave, in integration order."""
        fw = self.first_wave()
        return [lid for lid in self.integration_order if self.lanes[lid].wave == fw]


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise PlanValidationError(message)


def _default_branch_namespace(plan_id: str) -> str:
    # "goal_plan_smoke" -> "goal-plan-smoke" (matches the exemplar's lane branch
    # prefix), while remaining deterministic for any plan_id.
    return plan_id.replace("_", "-")


def _validate_no_unsafe_substrings(value: str, field_name: str) -> None:
    for bad in _UNSAFE_SUBSTRINGS:
        _require(
            bad not in value,
            f"{field_name} has invalid value {value!r}: must not contain the substring {bad!r}",
        )


def _validate_charset(value: Any, pattern: re.Pattern[str], field_name: str) -> None:
    """Allowlist-validate ``value`` against ``pattern`` (anchored, full-string
    match), then belt-and-suspenders reject the injection substrings even
    though the allowlisted charset should already exclude them.
    """
    _require(
        isinstance(value, str) and bool(pattern.match(value)),
        f"{field_name} has invalid value {value!r}: must match pattern {pattern.pattern!r}",
    )
    _validate_no_unsafe_substrings(value, field_name)


def _validate_path_field(value: Any, field_name: str) -> None:
    _validate_charset(value, _PATH_RE, field_name)


def _validate_child_dot_field(
    value: Any, field_name: str, *, allow_git_ref: bool = False
) -> None:
    _require(
        isinstance(value, str) and bool(value),
        f"{field_name} must be a non-empty string",
    )
    assert isinstance(value, str)  # for type-checkers
    if allow_git_ref and value.startswith("git+https://"):
        _require(
            bool(_GIT_CHILD_DOT_RE.match(value)),
            f"{field_name} has invalid value {value!r}: a git+https cross-repo "
            f"reference must match pattern {_GIT_CHILD_DOT_RE.pattern!r}",
        )
        _validate_no_unsafe_substrings(value, field_name)
        return
    _validate_path_field(value, field_name)


def _validate_marker_content(value: Any, field_name: str) -> None:
    _require(isinstance(value, str), f"{field_name} must be a string")
    assert isinstance(value, str)  # for type-checkers
    _require(
        "\n" not in value and "\r" not in value,
        f"{field_name} has invalid value {value!r}: must not contain newline or "
        "carriage-return characters",
    )
    _validate_no_unsafe_substrings(value, field_name)
    bad_chars = [c for c in _MARKER_CONTENT_DENY_CHARS if c in value]
    _require(
        not bad_chars,
        f"{field_name} has invalid value {value!r}: must not contain any of the "
        f"unsafe characters {_MARKER_CONTENT_DENY_CHARS!r} (found {bad_chars!r})",
    )
    _require(
        len(value) <= _MARKER_CONTENT_MAX_LEN,
        f"{field_name} has invalid value {value!r}: must be at most "
        f"{_MARKER_CONTENT_MAX_LEN} characters (got {len(value)})",
    )


def build_plan(spec: dict[str, Any]) -> Plan:
    """Validate and normalize a raw plan dict into a :class:`Plan`.

    Raises :class:`PlanValidationError` with a named field on the first problem.
    """

    _require(isinstance(spec, dict), "plan spec must be a JSON object")

    plan_id = spec.get("plan_id")
    _require(
        isinstance(plan_id, str) and bool(plan_id),
        "plan spec missing required field 'plan_id' (non-empty string)",
    )
    assert isinstance(plan_id, str)  # for type-checkers
    _validate_charset(plan_id, _ID_RE, "plan spec field 'plan_id'")

    raw_lanes = spec.get("lanes")
    _require(
        isinstance(raw_lanes, dict) and len(raw_lanes) > 0,
        "plan spec missing required field 'lanes' (non-empty object keyed by lane id)",
    )
    assert isinstance(raw_lanes, dict)

    lanes: dict[str, Lane] = {}
    for lane_id, raw in raw_lanes.items():
        _validate_charset(lane_id, _ID_RE, "lane id")
        lanes[lane_id] = _build_lane(lane_id, raw)

    # ---- waves ---------------------------------------------------------
    raw_waves = spec.get("waves")
    _require(
        isinstance(raw_waves, list) and len(raw_waves) > 0,
        "plan spec missing required field 'waves' (non-empty list)",
    )
    assert isinstance(raw_waves, list)
    waves: list[int] = []
    concurrency_raw: dict[int, int] = {}
    for idx, w in enumerate(raw_waves):
        _require(
            isinstance(w, dict) and "wave" in w,
            f"waves[{idx}] missing required field 'wave'",
        )
        wnum = w["wave"]
        _require(isinstance(wnum, int), f"waves[{idx}].wave must be an integer")
        waves.append(wnum)
        if "concurrency" in w:
            concurrency = w["concurrency"]
            _require(
                isinstance(concurrency, int) and concurrency >= 1,
                f"waves[{idx}].concurrency must be an integer >= 1 when provided",
            )
            concurrency_raw[wnum] = concurrency
    _require(
        waves == sorted(waves) and len(set(waves)) == len(waves),
        f"waves must be strictly increasing and unique, got {waves}",
    )

    declared_wave_numbers = set(waves)
    for lane_id, lane in lanes.items():
        _require(
            lane.wave in declared_wave_numbers,
            f"lane '{lane_id}' has wave {lane.wave} not declared in top-level 'waves' {waves}",
        )

    # A declared-but-empty wave produces a dead graph (a fan-out/launch node
    # with nothing behind it) -- reject it the same way an undeclared lane
    # wave is rejected above (lanes-subset-of-waves is already enforced;
    # this is the other direction, waves-subset-of-lanes).
    lane_count_by_wave: dict[int, int] = {}
    for lane in lanes.values():
        lane_count_by_wave[lane.wave] = lane_count_by_wave.get(lane.wave, 0) + 1
    for w in waves:
        _require(
            lane_count_by_wave.get(w, 0) >= 1,
            f"wave {w} is declared in top-level 'waves' but has no lanes assigned to it",
        )

    # ---- integration_order --------------------------------------------
    order = spec.get("integration_order")
    _require(
        isinstance(order, list) and len(order) > 0,
        "plan spec missing required field 'integration_order' (non-empty list)",
    )
    assert isinstance(order, list)
    _require(
        sorted(order) == sorted(lanes.keys()),
        "integration_order must be a permutation of the lane ids; "
        f"got {order}, lanes {sorted(lanes.keys())}",
    )
    # Wave-monotonic: the structural wave-gating pattern requires every lane of
    # an earlier wave to be integrated before any lane of a later wave.
    prev_wave = None
    for lane_id in order:
        w = lanes[lane_id].wave
        if prev_wave is not None:
            _require(
                w >= prev_wave,
                "integration_order must be non-decreasing by wave "
                f"(lane '{lane_id}' wave {w} follows wave {prev_wave})",
            )
        prev_wave = w

    # ---- depends_on references + enforcement ---------------------------
    # Referential integrity: every dependency must name a known lane.
    for lane_id, lane in lanes.items():
        for dep in lane.depends_on:
            _require(
                dep in lanes,
                f"lane '{lane_id}' depends_on unknown lane '{dep}'",
            )

    # Enforcement (not just referential integrity): depends_on must be
    # consistent with the structural gating the generator actually builds --
    # a dependency in a strictly later wave, or one that does not precede its
    # dependent in integration_order, can never be satisfied by construction
    # and would otherwise create a false sense of dependency safety.
    order_index = {lid: i for i, lid in enumerate(order)}
    for lane_id, lane in lanes.items():
        for dep in lane.depends_on:
            _require(
                lanes[dep].wave <= lane.wave,
                f"lane '{lane_id}' depends_on '{dep}' which is in a later wave "
                f"({lanes[dep].wave} > {lane.wave}); a dependency must be in an "
                "earlier-or-equal wave",
            )
            _require(
                order_index[dep] < order_index[lane_id],
                f"lane '{lane_id}' depends_on '{dep}' but '{dep}' does not precede "
                f"'{lane_id}' in 'integration_order'",
            )

    # ---- required / defaulted fields ------------------------------------
    _require(
        "terminals" in spec,
        "plan spec missing required field 'terminals' (non-empty list of strings)",
    )
    terminals = spec.get("terminals")
    _require(
        isinstance(terminals, list)
        and all(isinstance(t, str) for t in terminals)
        and len(terminals) > 0,
        "plan spec field 'terminals' must be a non-empty list of strings",
    )
    assert isinstance(terminals, list)
    for t in terminals:
        _validate_charset(t, _ID_RE, "plan spec field 'terminals[]'")

    branch_namespace = spec.get("branch_namespace") or _default_branch_namespace(
        plan_id
    )
    _validate_charset(
        branch_namespace, _BRANCH_RE, "plan spec field 'branch_namespace'"
    )

    budgets = spec.get("budgets") or {}
    _require(isinstance(budgets, dict), "'budgets' must be an object when provided")
    max_attempts = budgets.get("max_adaptive_attempts_per_lane", DEFAULT_MAX_ATTEMPTS)
    _require(
        isinstance(max_attempts, int) and max_attempts >= 1,
        "budgets.max_adaptive_attempts_per_lane must be an integer >= 1 when provided",
    )
    lane_wall_timeout_seconds = budgets.get(
        "lane_wall_timeout_seconds", DEFAULT_LANE_WALL_TIMEOUT_SECONDS
    )
    _require(
        isinstance(lane_wall_timeout_seconds, int) and lane_wall_timeout_seconds >= 1,
        "budgets.lane_wall_timeout_seconds must be an integer >= 1 when provided",
    )
    verifier_timeout_seconds = budgets.get(
        "verifier_timeout_seconds", DEFAULT_VERIFIER_TIMEOUT_SECONDS
    )
    _require(
        isinstance(verifier_timeout_seconds, int) and verifier_timeout_seconds >= 1,
        "budgets.verifier_timeout_seconds must be an integer >= 1 when provided",
    )

    correction = spec.get("correction") or {}
    _require(
        isinstance(correction, dict), "'correction' must be an object when provided"
    )
    correction_child_dot = correction.get("child_dot", DEFAULT_CORRECTION_CHILD_DOT)
    _validate_child_dot_field(
        correction_child_dot, "plan spec field 'correction.child_dot'"
    )

    delivery = spec.get("delivery") or {}
    _require(isinstance(delivery, dict), "'delivery' must be an object when provided")
    delivery_child_dot = delivery.get("child_dot", DEFAULT_DELIVERY_CHILD_DOT)
    _validate_child_dot_field(
        delivery_child_dot, "plan spec field 'delivery.child_dot'", allow_git_ref=True
    )

    # concurrency_by_wave: an explicit waves[].concurrency wins; otherwise the
    # cap defaults to the number of lanes actually in that wave (today's
    # behavior of "everything in the wave runs at once").
    concurrency_by_wave: dict[int, int] = {
        w: concurrency_raw.get(w, lane_count_by_wave[w]) for w in waves
    }

    # Resolve empty lane branches now that the namespace is known.
    resolved_lanes: dict[str, Lane] = {}
    for lane_id, lane in lanes.items():
        branch = lane.branch or f"{branch_namespace}/{lane_id}"
        resolved_lanes[lane_id] = Lane(
            lane_id=lane.lane_id,
            wave=lane.wave,
            depends_on=lane.depends_on,
            verifier_argv=lane.verifier_argv,
            marker_file=lane.marker_file,
            marker_content=lane.marker_content,
            seeded_failure=lane.seeded_failure,
            child_dot=lane.child_dot,
            branch=branch,
            goal_condition_file=lane.goal_condition_file,
        )

    return Plan(
        plan_id=plan_id,
        lanes=resolved_lanes,
        waves=tuple(waves),
        integration_order=tuple(order),
        terminals=tuple(terminals),
        branch_namespace=branch_namespace,
        max_attempts=max_attempts,
        correction_child_dot=correction_child_dot,
        delivery_child_dot=delivery_child_dot,
        lane_wall_timeout_seconds=lane_wall_timeout_seconds,
        verifier_timeout_seconds=verifier_timeout_seconds,
        concurrency_by_wave=concurrency_by_wave,
        raw=spec,
    )


def _build_lane(lane_id: str, raw: Any) -> Lane:
    _require(isinstance(raw, dict), f"lane '{lane_id}' must be an object")

    _require("wave" in raw, f"lane '{lane_id}' missing required field 'wave'")
    wave = raw["wave"]
    _require(
        isinstance(wave, int) and wave >= 1,
        f"lane '{lane_id}' field 'wave' must be an integer >= 1",
    )

    _require(
        "depends_on" in raw,
        f"lane '{lane_id}' missing required field 'depends_on' (list; may be empty)",
    )
    depends_on = raw["depends_on"]
    _require(
        isinstance(depends_on, list) and all(isinstance(d, str) for d in depends_on),
        f"lane '{lane_id}' field 'depends_on' must be a list of lane-id strings",
    )

    _require(
        "verifier_argv" in raw,
        f"lane '{lane_id}' missing required field 'verifier_argv'",
    )
    verifier_argv = raw["verifier_argv"]
    _require(
        isinstance(verifier_argv, list)
        and len(verifier_argv) > 0
        and all(isinstance(a, str) for a in verifier_argv),
        f"lane '{lane_id}' field 'verifier_argv' must be a non-empty list of strings",
    )

    _require(
        "marker_file" in raw, f"lane '{lane_id}' missing required field 'marker_file'"
    )
    marker_file = raw["marker_file"]
    _validate_path_field(marker_file, f"lane '{lane_id}' field 'marker_file'")

    _require(
        "marker_content" in raw,
        f"lane '{lane_id}' missing required field 'marker_content'",
    )
    marker_content = raw["marker_content"]
    _validate_marker_content(marker_content, f"lane '{lane_id}' field 'marker_content'")

    seeded_failure = raw.get("seeded_failure", False)
    _require(
        isinstance(seeded_failure, bool),
        f"lane '{lane_id}' field 'seeded_failure' must be a boolean",
    )

    child_dot = raw.get("child_dot", DEFAULT_CHILD_DOT)
    _validate_child_dot_field(child_dot, f"lane '{lane_id}' field 'child_dot'")

    branch = raw.get("branch", "")
    _require(
        isinstance(branch, str),
        f"lane '{lane_id}' field 'branch' must be a string when provided",
    )
    if branch:
        _validate_charset(branch, _BRANCH_RE, f"lane '{lane_id}' field 'branch'")

    # Optional path passed opaquely to the child lane brick. Absent/empty => no
    # runtime --param emitted (byte-identical output). When present it is a path,
    # so it is charset-validated with the same path validator marker_file uses --
    # the value is later interpolated into a generated shell/heredoc argv, so it
    # must be rejected here if it carries any shell/quote metacharacter.
    goal_condition_file = raw.get("goal_condition_file", "")
    _require(
        isinstance(goal_condition_file, str),
        f"lane '{lane_id}' field 'goal_condition_file' must be a string when provided",
    )
    if goal_condition_file:
        _validate_path_field(
            goal_condition_file, f"lane '{lane_id}' field 'goal_condition_file'"
        )

    return Lane(
        lane_id=lane_id,
        wave=wave,
        depends_on=tuple(depends_on),
        verifier_argv=tuple(verifier_argv),
        marker_file=marker_file,
        marker_content=marker_content,
        seeded_failure=seeded_failure,
        child_dot=child_dot,
        branch=branch,
        goal_condition_file=goal_condition_file,
    )


def load_plan(path: str | Path) -> Plan:
    """Load and validate a plan spec from a JSON file path."""

    p = Path(path)
    _require(p.is_file(), f"plan spec file not found: {p}")
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlanValidationError(f"plan spec {p} is not valid JSON: {e}") from e
    return build_plan(spec)
