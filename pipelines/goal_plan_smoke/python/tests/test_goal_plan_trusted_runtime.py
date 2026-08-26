"""Trust-boundary tests for goal_plan_runtime.py (Wave 2).

Scope note: goal_plan_bootstrap.py (Wave 0) already has its own exhaustive
test suite proving the trusted-bootstrap materialization mechanics in
general (exact-blob sealing, atomic no-clobber installs, self-check,
rehydrate-absent-only, etc.) -- none of that is re-verified here, and this
file is not a fixed/owned path for this lane (only goal_plan_runtime.py and
its own tests are). This file instead covers the "trusted runtime" surface
that IS this lane's own code: the compiled-source manifest/gate and
parent/source binding primitives in `admit_run`, plus the stdlib-only /
schema-stability properties a trusted runtime bundle must have to be safely
sealed by bootstrap in the first place (per the coupling documented in
goal_plan_runtime.py's own module docstring and in
docs/plans/2026-08-22-goal-plan-attractor-design.md's
`trusted_runtime_definition` description).

No mocks: real files, real hashing, real subprocess for the stdlib-only
scan.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

RUNTIME_PATH = Path(__file__).resolve().parents[1] / "goal_plan_runtime.py"
SUPERVISOR_PATH = Path(__file__).resolve().parents[1] / "goal_plan_supervisor.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gpr = load_module(RUNTIME_PATH, "goal_plan_runtime_trust_under_test")
_test_runtime_module = load_module(
    Path(__file__).resolve().parent / "test_goal_plan_runtime.py",
    "goal_plan_runtime_fixtures_under_test",
)
make_env = _test_runtime_module.make_env


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Compiled-source manifest/gate (item 1 half owned by this lane's admission)
# ---------------------------------------------------------------------------


def test_admit_run_compiled_source_manifest_matches_real_file_hash(tmp_path):
    env = make_env(tmp_path)
    admitted = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={
            "runtime": str(RUNTIME_PATH),
            "supervisor": str(SUPERVISOR_PATH),
        },
        parent_binding={"run_id": "trust-1"},
    )
    assert admitted.compiled_source_manifest["runtime"] == sha256_of(RUNTIME_PATH)
    assert admitted.compiled_source_manifest["supervisor"] == sha256_of(SUPERVISOR_PATH)


def test_admit_run_compiled_source_gate_rejects_single_byte_tamper(tmp_path):
    """Fault proof: a trusted-runtime bundle whose sealed copy diverges from
    the expected hash by even one byte must be rejected before any other
    runtime state is created."""
    env = make_env(tmp_path)
    tampered = tmp_path / "goal_plan_runtime_tampered.py"
    original = RUNTIME_PATH.read_bytes()
    tampered.write_bytes(original + b"\n# tampered\n")
    expected = {"runtime": sha256_of(RUNTIME_PATH)}  # gate expects the *real* hash

    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(env.state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(tampered)},
            expected_compiled_source_sha256=expected,
            parent_binding={"run_id": "trust-2"},
        )
    assert excinfo.value.code == "ADMISSION:COMPILED_SOURCE_MISMATCH"


def test_admit_run_compiled_source_gate_accepts_matching_expected_hash(tmp_path):
    env = make_env(tmp_path)
    expected = {
        "runtime": sha256_of(RUNTIME_PATH),
        "supervisor": sha256_of(SUPERVISOR_PATH),
    }
    admitted = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={
            "runtime": str(RUNTIME_PATH),
            "supervisor": str(SUPERVISOR_PATH),
        },
        expected_compiled_source_sha256=expected,
        parent_binding={"run_id": "trust-3"},
    )
    assert admitted.compiled_source_manifest == expected


# ---------------------------------------------------------------------------
# Parent/source binding hash integrity
# ---------------------------------------------------------------------------


def test_admit_run_binding_hash_changes_when_binding_content_changes(tmp_path):
    env = make_env(tmp_path)
    admitted_a = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={"runtime": str(RUNTIME_PATH)},
        parent_binding={"run_id": "trust-4", "runtime_bundle_hash": "aaaa"},
    )
    admitted_b = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={"runtime": str(RUNTIME_PATH)},
        parent_binding={"run_id": "trust-4", "runtime_bundle_hash": "bbbb"},
    )
    assert admitted_a.binding_sha256 != admitted_b.binding_sha256


def test_admit_run_binding_hash_is_stable_for_identical_binding(tmp_path):
    env = make_env(tmp_path)
    binding = {"run_id": "trust-5", "runtime_bundle_hash": "cccc"}
    admitted_a = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={"runtime": str(RUNTIME_PATH)},
        parent_binding=dict(binding),
    )
    admitted_b = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={"runtime": str(RUNTIME_PATH)},
        parent_binding=dict(binding),
    )
    assert admitted_a.binding_sha256 == admitted_b.binding_sha256


# ---------------------------------------------------------------------------
# Trusted-bundle sealability properties: this file must be safely sealable
# by goal_plan_bootstrap.py's trusted-runtime materialization (stdlib only,
# no dynamic imports of anything outside the standard library).
# ---------------------------------------------------------------------------

_STDLIB_ALLOWED_TOP_LEVEL = {
    "__future__",
    "collections",
    "dataclasses",
    "fcntl",
    "hashlib",
    "json",
    "os",
    "stat",
    "subprocess",
    "time",
    "pathlib",
    "typing",
}


def test_runtime_module_imports_are_stdlib_only():
    """A trusted-runtime bundle sealed by bootstrap must not silently
    depend on a third-party package that isn't part of the sealed bundle
    (goal_plan_runtime.py + goal_plan_supervisor.py + the binding json)."""
    tree = ast.parse(RUNTIME_PATH.read_text(), filename=str(RUNTIME_PATH))
    found_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found_modules.add(node.module.split(".")[0])
    unexpected = found_modules - _STDLIB_ALLOWED_TOP_LEVEL
    assert unexpected == set(), f"non-stdlib/unexpected imports found: {unexpected}"


def test_runtime_module_has_no_dynamic_target_repo_imports():
    """Mirrors goal_plan_bootstrap.py's own sentinel-import test: the
    trusted runtime must never dynamically import target-repository code
    (importlib, __import__, exec, eval)."""
    source = RUNTIME_PATH.read_text()
    tree = ast.parse(source, filename=str(RUNTIME_PATH))
    banned_calls = {"exec", "eval", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in banned_calls, (
                f"banned dynamic call used: {node.func.id}"
            )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or (
                node.names[0].name
                if isinstance(node, ast.Import) and node.names
                else ""
            )
            assert module_name != "importlib", (
                "goal_plan_runtime.py must not import importlib itself"
            )


# ---------------------------------------------------------------------------
# Schema-string stability: these exact strings are the interop contract a
# compiled parent graph and the trusted-runtime binding rely on; an
# accidental rename silently breaks cross-wave compatibility.
# ---------------------------------------------------------------------------


def test_schema_version_strings_are_stable():
    assert gpr.SCHEMA_ADMISSION == "goal-plan.runtime-admission/v1"
    assert gpr.SCHEMA_RUN_OWNED_WORKTREES == "goal-plan.run-owned-worktrees/v1"
    assert gpr.SCHEMA_RUN_BUDGET == "goal-plan.run-budget/v4"
    assert gpr.SCHEMA_CHILD_ENVELOPE == "goal-plan.child-verifier-envelope/v1"
    assert gpr.SCHEMA_INTEGRATION_JOURNAL == "goal-plan.integration-journal/v1"
    assert gpr.SCHEMA_CANDIDATE_EVIDENCE == "goal-plan.candidate-evidence/v1"
    assert gpr.SCHEMA_CLEANUP == "goal-plan.pre-terminal-cleanup/v2"


def test_worktree_states_and_authority_tokens_are_stable():
    assert gpr.WORKTREE_STATES == {
        "CREATING",
        "ACTIVE",
        "REMOVING",
        "REMOVED",
        "PRESERVED_RESIDUAL",
    }
    assert gpr.AUTHORITY_FULL == "FULL"
    assert gpr.AUTHORITY_EXTERNAL_ONLY == "EXTERNAL_ONLY"
    assert gpr.AUTHORITY_NONE == "NONE"
