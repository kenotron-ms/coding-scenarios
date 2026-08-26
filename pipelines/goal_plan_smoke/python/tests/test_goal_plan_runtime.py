"""Real-subprocess, real-git tests for goal_plan_runtime.py (Wave 2).

No mocks: every test builds a real git repository under `tmp_path` and
drives the runtime module against real worktrees, real flock-protected
ledgers, and real subprocess verifiers. This mirrors the testing convention
already used by test_goal_plan_bootstrap.py and test_goal_plan_supervisor.py
(fixture-built real git repos, real subprocess execution, one-mutation/
one-assertion fault injection).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

RUNTIME_PATH = Path(__file__).resolve().parents[1] / "goal_plan_runtime.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gpr = load_module(RUNTIME_PATH, "goal_plan_runtime_under_test")

GIT: tuple[str, ...] = ("git",)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def init_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("hello\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "initial")
    return git(path, "rev-parse", "HEAD").stdout.strip()


@dataclasses.dataclass
class Env:
    tmp_path: Path
    repo: Path
    state_root: Path
    worktree_root: Path
    base_sha: str


def make_env(tmp_path: Path) -> Env:
    repo = tmp_path / "repo"
    base_sha = init_repo(repo)
    state_root = tmp_path / "state"
    worktree_root = tmp_path / "worktrees"
    state_root.mkdir()
    worktree_root.mkdir()
    return Env(
        tmp_path=tmp_path,
        repo=repo,
        state_root=state_root,
        worktree_root=worktree_root,
        base_sha=base_sha,
    )


def registry_for(env: Env) -> Any:
    return gpr.WorktreeRegistry(str(env.state_root / "run-owned-worktrees.json"))


def write_script(path: Path, body: str) -> list[str]:
    path.write_text(body)
    path.chmod(0o755)
    return [sys.executable, str(path)]


PASS_VERIFIER = "import sys\nsys.exit(0)\n"
FAIL_VERIFIER = "import sys\nsys.exit(1)\n"
MUTATE_VERIFIER = "open('mutated.txt', 'w').write('x')\nimport sys\nsys.exit(0)\n"


# ---------------------------------------------------------------------------
# Item 1: Admission and roots
# ---------------------------------------------------------------------------


def test_admit_run_accepts_valid_disjoint_roots(tmp_path):
    env = make_env(tmp_path)
    admitted = gpr.admit_run(
        target_repo=str(env.repo),
        state_root=str(env.state_root),
        worktree_root=str(env.worktree_root),
        compiled_source_paths={"runtime": str(RUNTIME_PATH)},
        parent_binding={"run_id": "r1"},
    )
    assert admitted.target_repo == os.path.normpath(str(env.repo))
    assert "runtime" in admitted.compiled_source_manifest
    assert len(admitted.binding_sha256) == 64


def test_admit_run_rejects_overlapping_roots(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(env.repo / "sub"),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:ROOT_OVERLAP"


def test_admit_run_rejects_relative_root(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root="relative/path",
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:BAD_ROOT"


def test_admit_run_rejects_symlink_root_component(tmp_path):
    env = make_env(tmp_path)
    real_dir = tmp_path / "real_state"
    real_dir.mkdir()
    link_dir = tmp_path / "linked"
    link_dir.symlink_to(real_dir)
    alias_state_root = link_dir / "state"
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(alias_state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:BAD_ROOT"


def test_admit_run_rejects_missing_compiled_source(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(env.state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(tmp_path / "missing.py")},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:COMPILED_SOURCE_MISSING"


def test_admit_run_rejects_compiled_source_hash_mismatch(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(env.state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            expected_compiled_source_sha256={"runtime": "0" * 64},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:COMPILED_SOURCE_MISMATCH"


def test_admit_run_rejects_missing_target_repo(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(tmp_path / "no-such-repo"),
            state_root=str(env.state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            parent_binding={"run_id": "r1"},
        )
    assert excinfo.value.code == "ADMISSION:TARGET_REPO_MISSING"


def test_admit_run_rejects_empty_parent_binding(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.admit_run(
            target_repo=str(env.repo),
            state_root=str(env.state_root),
            worktree_root=str(env.worktree_root),
            compiled_source_paths={"runtime": str(RUNTIME_PATH)},
            parent_binding={},
        )
    assert excinfo.value.code == "ADMISSION:BAD_PARENT_BINDING"


# ---------------------------------------------------------------------------
# Item 2: Worktree lifecycle
# ---------------------------------------------------------------------------


def test_create_and_remove_registered_worktree(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
        branch="lane-a",
    )
    assert os.path.isdir(path)
    entry = registry.get("lane-a")
    assert entry["state"] == "ACTIVE"
    assert entry["head_sha"] == env.base_sha

    gpr.remove_registered_worktree(registry, GIT, str(env.repo), "lane-a")
    assert not os.path.exists(path)
    assert registry.get("lane-a")["state"] == "REMOVED"


def test_create_registered_worktree_rejects_path_escaping_root(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.create_registered_worktree(
            registry,
            GIT,
            str(env.repo),
            str(env.worktree_root),
            "../escape",
            kind="lane",
            commit_sha=env.base_sha,
        )
    assert excinfo.value.code == "WORKTREE:ESCAPES_ROOT"


def test_double_registration_of_same_worktree_id_rejected(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        registry.register_creating(
            "lane-a", kind="lane", path="x", base_sha=env.base_sha, git_common_dir="y"
        )
    assert excinfo.value.code == "WORKTREE:ALREADY_REGISTERED"


def test_remove_requires_active_state(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    registry.register_creating(
        "lane-crash",
        kind="lane",
        path=str(env.worktree_root / "lane-crash"),
        base_sha=env.base_sha,
        git_common_dir=str(env.repo / ".git"),
    )
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.remove_registered_worktree(registry, GIT, str(env.repo), "lane-crash")
    assert excinfo.value.code == "WORKTREE:BAD_TRANSITION"


def test_reconcile_collapses_stale_creating_entry_never_materialized(tmp_path):
    """Phase-safe recovery boundary: a durable CREATING entry written right
    before a crash, with `git worktree add` never having run, collapses to
    REMOVED rather than being treated as ACTIVE or blocking the run."""
    env = make_env(tmp_path)
    registry = registry_for(env)
    registry.register_creating(
        "lane-crash",
        kind="lane",
        path=str(env.worktree_root / "lane-crash"),
        base_sha=env.base_sha,
        git_common_dir=str(env.repo / ".git"),
    )
    result = gpr.reconcile_registry(registry, GIT, str(env.repo))
    assert "lane-crash" in result["reconciled"]
    assert registry.get("lane-crash")["state"] == "REMOVED"
    assert result["unresolved"] == []


def test_reconcile_flags_active_but_externally_deleted_as_unresolved(tmp_path):
    """Phase-safe recovery boundary: an ACTIVE worktree deleted by something
    other than remove_registered_worktree is surfaced as unresolved evidence,
    never silently auto-repaired."""
    env = make_env(tmp_path)
    registry = registry_for(env)
    path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    shutil.rmtree(path)
    result = gpr.reconcile_registry(registry, GIT, str(env.repo))
    assert any(u["worktree_id"] == "lane-a" for u in result["unresolved"])
    assert registry.get("lane-a")["state"] == "ACTIVE"  # never auto-mutated


# ---------------------------------------------------------------------------
# Item 3: Budgets
# ---------------------------------------------------------------------------


def make_ledger(env: Env, **overrides) -> Any:
    defaults = {
        "max_total_attempts": 2,
        "max_process_launches": 5,
        "max_integration_corrections": 1,
        "max_pipeline_seconds": 3600.0,
    }
    defaults.update(overrides)
    limits = gpr.BudgetLimits(**defaults)
    return gpr.BudgetLedger(
        str(env.state_root / "budgets" / "run-wide.json"),
        str(env.state_root / "budgets" / "run-wide.lock"),
        limits,
        run_id="run1",
    )


def test_reserve_attempt_is_idempotent(tmp_path):
    env = make_env(tmp_path)
    ledger = make_ledger(env)
    first = ledger.reserve_attempt("attempt-1")
    again = ledger.reserve_attempt("attempt-1")
    assert first == again


def test_reserve_attempt_exhausts_at_limit(tmp_path):
    env = make_env(tmp_path)
    ledger = make_ledger(env)
    ledger.reserve_attempt("attempt-1")
    ledger.reserve_attempt("attempt-2")
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        ledger.reserve_attempt("attempt-3")
    assert excinfo.value.code == "BUDGET:ATTEMPTS_EXHAUSTED"


def test_reserve_process_launch_and_correction_independent_buckets(tmp_path):
    env = make_env(tmp_path)
    ledger = make_ledger(env, max_process_launches=1, max_integration_corrections=1)
    ledger.reserve_process_launch("proc-1")
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        ledger.reserve_process_launch("proc-2")
    assert excinfo.value.code == "BUDGET:PROCESS_LAUNCHES_EXHAUSTED"
    # corrections bucket is untouched by process-launch exhaustion
    ledger.reserve_correction("corr-1")


def test_budget_deadline_exceeded(tmp_path):
    env = make_env(tmp_path)
    ledger = make_ledger(env, max_pipeline_seconds=0.02)
    ledger.check_deadline()
    time.sleep(0.08)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        ledger.check_deadline()
    assert excinfo.value.code == "BUDGET:DEADLINE_EXCEEDED"


def test_budget_reservation_race_is_serialized_by_flock(tmp_path):
    """Fault proof: concurrent reservation attempts against the same
    flocked ledger never double-book past the limit and never hand out a
    duplicate index."""
    env = make_env(tmp_path)
    ledger = make_ledger(env, max_total_attempts=5)
    results: list[int] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            reservation = ledger.reserve_attempt(f"attempt-{i}")
            with lock:
                results.append(reservation["index"])
        except gpr.GoalPlanRuntimeError as exc:
            with lock:
                errors.append(exc.code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 5
    assert sorted(results) == [1, 2, 3, 4, 5]
    assert len(errors) == 15
    assert all(code == "BUDGET:ATTEMPTS_EXHAUSTED" for code in errors)


# ---------------------------------------------------------------------------
# Items 4/5: Verifier envelopes
# ---------------------------------------------------------------------------


def test_child_envelope_preserves_dirty_state_and_passes(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    (Path(lane_path) / "scratch.txt").write_text("legitimate dirty adaptive state\n")
    verifier = write_script(tmp_path / "pass_verifier.py", PASS_VERIFIER)

    result = gpr.run_child_attempt_verifier_envelope(
        git_argv_prefix=GIT,
        worktree_path=lane_path,
        verifier_argv=verifier,
        timeout_seconds=10,
        output_root=str(env.state_root / "verify-out-1"),
        evidence_path=str(env.state_root / "envelope-1.json"),
    )
    assert result.verdict == "PASS"
    assert (Path(lane_path) / "scratch.txt").exists()


def test_child_envelope_detects_verifier_mutation_as_infra(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-b",
        kind="lane",
        commit_sha=env.base_sha,
    )
    verifier = write_script(tmp_path / "mutate_verifier.py", MUTATE_VERIFIER)

    result = gpr.run_child_attempt_verifier_envelope(
        git_argv_prefix=GIT,
        worktree_path=lane_path,
        verifier_argv=verifier,
        timeout_seconds=10,
        output_root=str(env.state_root / "verify-out-2"),
        evidence_path=str(env.state_root / "envelope-2.json"),
    )
    assert result.verdict == "INFRA"


def test_child_envelope_normal_dirty_worktree_read_only_fail_is_fail_not_infra(
    tmp_path,
):
    """A normal dirty-worktree control: legitimate pre-existing dirty state
    plus a read-only verifier that legitimately fails must stay FAIL, never
    be conflated with a mutation-caused INFRA."""
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-c",
        kind="lane",
        commit_sha=env.base_sha,
    )
    (Path(lane_path) / "scratch.txt").write_text("legitimate dirty state\n")
    verifier = write_script(tmp_path / "fail_verifier.py", FAIL_VERIFIER)

    result = gpr.run_child_attempt_verifier_envelope(
        git_argv_prefix=GIT,
        worktree_path=lane_path,
        verifier_argv=verifier,
        timeout_seconds=10,
        output_root=str(env.state_root / "verify-out-3"),
        evidence_path=str(env.state_root / "envelope-3.json"),
    )
    assert result.verdict == "FAIL"
    assert (Path(lane_path) / "scratch.txt").exists()


def test_child_envelope_rejects_output_root_inside_worktree(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-d",
        kind="lane",
        commit_sha=env.base_sha,
    )
    verifier = write_script(tmp_path / "pass_verifier2.py", PASS_VERIFIER)

    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.run_child_attempt_verifier_envelope(
            git_argv_prefix=GIT,
            worktree_path=lane_path,
            verifier_argv=verifier,
            timeout_seconds=10,
            output_root=os.path.join(lane_path, "out"),
            evidence_path=str(env.state_root / "envelope-4.json"),
        )
    assert excinfo.value.code == "ENVELOPE:OUTPUT_ROOT_NOT_EXTERNAL"


def test_child_envelope_timeout_is_infra(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-e",
        kind="lane",
        commit_sha=env.base_sha,
    )
    verifier = write_script(
        tmp_path / "sleep_verifier.py", "import time\ntime.sleep(5)\n"
    )

    result = gpr.run_child_attempt_verifier_envelope(
        git_argv_prefix=GIT,
        worktree_path=lane_path,
        verifier_argv=verifier,
        timeout_seconds=0.2,
        output_root=str(env.state_root / "verify-out-5"),
        evidence_path=str(env.state_root / "envelope-5.json"),
    )
    assert result.verdict == "INFRA"
    assert result.timed_out is True


def test_parent_envelope_clean_candidate_passes_and_disposable_worktree_is_removed(
    tmp_path,
):
    env = make_env(tmp_path)
    registry = registry_for(env)
    verifier = write_script(tmp_path / "pass_verifier3.py", PASS_VERIFIER)

    result = gpr.run_parent_verifier_envelope(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        worktree_root=str(env.worktree_root),
        worktree_id="candidate-1",
        candidate_sha=env.base_sha,
        verifier_argv=verifier,
        timeout_seconds=10,
        output_root=str(env.state_root / "candidate-out-1"),
        evidence_path=str(env.state_root / "candidate-envelope-1.json"),
    )
    assert result.verdict == "PASS"
    assert registry.get("candidate-1")["state"] == "REMOVED"
    assert not os.path.exists(os.path.join(str(env.worktree_root), "candidate-1"))


def test_parent_envelope_mutation_is_infra_and_disposable_worktree_still_removed(
    tmp_path,
):
    env = make_env(tmp_path)
    registry = registry_for(env)
    verifier = write_script(tmp_path / "mutate_verifier2.py", MUTATE_VERIFIER)

    result = gpr.run_parent_verifier_envelope(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        worktree_root=str(env.worktree_root),
        worktree_id="candidate-2",
        candidate_sha=env.base_sha,
        verifier_argv=verifier,
        timeout_seconds=10,
        output_root=str(env.state_root / "candidate-out-2"),
        evidence_path=str(env.state_root / "candidate-envelope-2.json"),
    )
    assert result.verdict == "INFRA"
    assert registry.get("candidate-2")["state"] == "REMOVED"


# ---------------------------------------------------------------------------
# Item 6: Candidate and ownership
# ---------------------------------------------------------------------------


def test_check_owned_paths_ok_when_change_is_inside_owned_prefix(tmp_path):
    env = make_env(tmp_path)
    lane_path = env.repo  # operate directly on the main checkout for simplicity
    (lane_path / "owned").mkdir()
    (lane_path / "owned" / "file.py").write_text("x = 1\n")
    git(lane_path, "add", "-A")
    git(lane_path, "commit", "-q", "-m", "owned change")
    candidate_sha = git(lane_path, "rev-parse", "HEAD").stdout.strip()

    result = gpr.check_owned_paths(
        GIT, str(lane_path), env.base_sha, candidate_sha, ["owned/"]
    )
    assert result["ok"] is True
    assert result["violations"] == []
    assert result["changed"] == ["owned/file.py"]


def test_check_owned_paths_flags_violation_outside_owned_prefix(tmp_path):
    env = make_env(tmp_path)
    lane_path = env.repo
    (lane_path / "forbidden.py").write_text("x = 1\n")
    git(lane_path, "add", "-A")
    git(lane_path, "commit", "-q", "-m", "unowned change")
    candidate_sha = git(lane_path, "rev-parse", "HEAD").stdout.strip()

    result = gpr.check_owned_paths(
        GIT, str(lane_path), env.base_sha, candidate_sha, ["owned/"]
    )
    assert result["ok"] is False
    assert "forbidden.py" in result["violations"]


def test_record_candidate_evidence_is_self_hashed(tmp_path):
    env = make_env(tmp_path)
    evidence_path = str(env.state_root / "candidate-evidence.json")
    owned_check = {"changed": [], "violations": [], "ok": True}
    record = gpr.record_candidate_evidence(
        evidence_path,
        lane_id="lane-a",
        base_sha=env.base_sha,
        candidate_sha=env.base_sha,
        owned_check=owned_check,
        verifier_result=None,
    )
    assert os.path.exists(evidence_path)
    assert "record_sha256" in record
    assert len(record["record_sha256"]) == 64


# ---------------------------------------------------------------------------
# Item 7: Integration
# ---------------------------------------------------------------------------


def make_integration_worktree(env: Env, registry) -> str:
    return gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "integration",
        kind="integration",
        commit_sha=env.base_sha,
        branch="integration",
    )


def make_lane_candidate(env: Env, registry, lane_id: str, filename: str) -> str:
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        lane_id,
        kind="lane",
        commit_sha=env.base_sha,
        branch=lane_id,
    )
    (Path(lane_path) / filename).write_text("content\n")
    git(Path(lane_path), "add", "-A")
    git(Path(lane_path), "commit", "-q", "-m", f"lane {lane_id} change")
    return git(Path(lane_path), "rev-parse", "HEAD").stdout.strip()


def test_integrate_candidate_accepts_clean_merge_with_passing_aggregate(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    integration_path = make_integration_worktree(env, registry)
    candidate_sha = make_lane_candidate(env, registry, "lane-a", "lane_a.txt")
    verifier = write_script(tmp_path / "aggregate_pass.py", PASS_VERIFIER)
    journal = gpr.IntegrationJournal(str(env.state_root / "integration-journal.json"))

    entry = gpr.integrate_candidate(
        git_argv_prefix=GIT,
        integration_worktree=integration_path,
        journal=journal,
        lane_id="lane-a",
        candidate_sha=candidate_sha,
        aggregate_verifier_argv=verifier,
        aggregate_timeout_seconds=10,
        output_root=str(env.state_root / "aggregate-out-1"),
        evidence_path=str(env.state_root / "aggregate-envelope-1.json"),
    )
    assert entry["result"] == "ACCEPTED"
    assert entry["rolled_back"] is False
    assert (Path(integration_path) / "lane_a.txt").exists()
    assert journal.read_all() == [entry]


def test_integrate_candidate_rolls_back_on_aggregate_failure(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    integration_path = make_integration_worktree(env, registry)
    candidate_sha = make_lane_candidate(env, registry, "lane-b", "lane_b.txt")
    verifier = write_script(tmp_path / "aggregate_fail.py", FAIL_VERIFIER)
    journal = gpr.IntegrationJournal(str(env.state_root / "integration-journal-2.json"))
    pre_merge_head = gpr.git_head_sha(GIT, integration_path)

    entry = gpr.integrate_candidate(
        git_argv_prefix=GIT,
        integration_worktree=integration_path,
        journal=journal,
        lane_id="lane-b",
        candidate_sha=candidate_sha,
        aggregate_verifier_argv=verifier,
        aggregate_timeout_seconds=10,
        output_root=str(env.state_root / "aggregate-out-2"),
        evidence_path=str(env.state_root / "aggregate-envelope-2.json"),
    )
    assert entry["result"] == "AGGREGATE_FAIL"
    assert entry["rolled_back"] is True
    assert gpr.git_head_sha(GIT, integration_path) == pre_merge_head
    assert not (Path(integration_path) / "lane_b.txt").exists()
    assert gpr.git_is_clean(GIT, integration_path)


def test_integrate_candidate_conflict_is_rolled_back_without_touching_head(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    integration_path = make_integration_worktree(env, registry)

    # Create two lane candidates that both touch the same line to force a
    # real merge conflict against the integration branch.
    lane1_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-conflict-a",
        kind="lane",
        commit_sha=env.base_sha,
        branch="lane-conflict-a",
    )
    (Path(lane1_path) / "README.md").write_text("lane a version\n")
    git(Path(lane1_path), "add", "-A")
    git(Path(lane1_path), "commit", "-q", "-m", "lane a readme change")
    candidate_a = git(Path(lane1_path), "rev-parse", "HEAD").stdout.strip()

    (Path(integration_path) / "README.md").write_text("integration version\n")
    git(Path(integration_path), "add", "-A")
    git(Path(integration_path), "commit", "-q", "-m", "integration readme change")
    pre_merge_head = gpr.git_head_sha(GIT, integration_path)

    verifier = write_script(tmp_path / "aggregate_unused.py", PASS_VERIFIER)
    journal = gpr.IntegrationJournal(str(env.state_root / "integration-journal-3.json"))

    entry = gpr.integrate_candidate(
        git_argv_prefix=GIT,
        integration_worktree=integration_path,
        journal=journal,
        lane_id="lane-conflict-a",
        candidate_sha=candidate_a,
        aggregate_verifier_argv=verifier,
        aggregate_timeout_seconds=10,
        output_root=str(env.state_root / "aggregate-out-3"),
        evidence_path=str(env.state_root / "aggregate-envelope-3.json"),
    )
    assert entry["result"] == "MERGE_CONFLICT"
    assert gpr.git_head_sha(GIT, integration_path) == pre_merge_head
    assert gpr.git_is_clean(GIT, integration_path)


def test_integration_journal_is_sequential(tmp_path):
    env = make_env(tmp_path)
    journal = gpr.IntegrationJournal(str(env.state_root / "seq-journal.json"))
    first = journal.append_entry({"lane_id": "a"})
    second = journal.append_entry({"lane_id": "b"})
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert [e["lane_id"] for e in journal.read_all()] == ["a", "b"]


# ---------------------------------------------------------------------------
# Item 8: Terminal safety
# ---------------------------------------------------------------------------


def test_derive_cleanup_authority_truth_table():
    assert (
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="PASS", parent_binding_verdict="PASS"
        )
        == gpr.AUTHORITY_FULL
    )
    assert (
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="PASS", parent_binding_verdict="FAIL"
        )
        == gpr.AUTHORITY_EXTERNAL_ONLY
    )
    assert (
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="PASS", parent_binding_verdict="UNKNOWN"
        )
        == gpr.AUTHORITY_EXTERNAL_ONLY
    )
    assert (
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="FAIL", parent_binding_verdict="PASS"
        )
        == gpr.AUTHORITY_NONE
    )
    assert (
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="UNKNOWN", parent_binding_verdict="UNKNOWN"
        )
        == gpr.AUTHORITY_NONE
    )
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.derive_cleanup_authority(
            trusted_runtime_verdict="BOGUS", parent_binding_verdict="PASS"
        )
    assert excinfo.value.code == "CLEANUP:BAD_VERDICT_TOKEN"


def test_pre_terminal_cleanup_full_removes_active_worktrees(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    result = gpr.pre_terminal_cleanup(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        authority=gpr.AUTHORITY_FULL,
        result_path=str(env.state_root / "cleanup-1.json"),
    )
    assert result["removed"] == ["lane-a"]
    assert registry.get("lane-a")["state"] == "REMOVED"


def test_pre_terminal_cleanup_full_preserves_named_residual(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    result = gpr.pre_terminal_cleanup(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        authority=gpr.AUTHORITY_FULL,
        result_path=str(env.state_root / "cleanup-2.json"),
        preserve_ids=frozenset({"lane-a"}),
    )
    assert result["preserved_residual"] == ["lane-a"]
    assert registry.get("lane-a")["state"] == "PRESERVED_RESIDUAL"
    assert os.path.isdir(path)  # untouched


def test_pre_terminal_cleanup_external_only_mutates_nothing(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    result = gpr.pre_terminal_cleanup(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        authority=gpr.AUTHORITY_EXTERNAL_ONLY,
        result_path=str(env.state_root / "cleanup-3.json"),
    )
    assert result["removed"] == []
    assert result["skipped"] == ["lane-a"]
    assert registry.get("lane-a")["state"] == "ACTIVE"
    assert os.path.isdir(path)


def test_pre_terminal_cleanup_none_authority_mutates_nothing(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-a",
        kind="lane",
        commit_sha=env.base_sha,
    )
    result = gpr.pre_terminal_cleanup(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        authority=gpr.AUTHORITY_NONE,
        result_path=str(env.state_root / "cleanup-4.json"),
    )
    assert result["removed"] == []
    assert registry.get("lane-a")["state"] == "ACTIVE"


def test_pre_terminal_cleanup_is_exactly_once(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    result_path = str(env.state_root / "cleanup-5.json")
    gpr.pre_terminal_cleanup(
        registry=registry,
        git_argv_prefix=GIT,
        target_repo=str(env.repo),
        authority=gpr.AUTHORITY_NONE,
        result_path=result_path,
    )
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.pre_terminal_cleanup(
            registry=registry,
            git_argv_prefix=GIT,
            target_repo=str(env.repo),
            authority=gpr.AUTHORITY_NONE,
            result_path=result_path,
        )
    assert excinfo.value.code == "CLEANUP:ALREADY_RUN"


def test_pre_terminal_cleanup_rejects_unknown_authority(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    with pytest.raises(gpr.GoalPlanRuntimeError) as excinfo:
        gpr.pre_terminal_cleanup(
            registry=registry,
            git_argv_prefix=GIT,
            target_repo=str(env.repo),
            authority="BOGUS",
            result_path=str(env.state_root / "cleanup-6.json"),
        )
    assert excinfo.value.code == "CLEANUP:BAD_AUTHORITY"


# ---------------------------------------------------------------------------
# Item 9: Additional fault-proof coverage (cross-cutting, not owned by a
# single item above) -- stale/foreign state and recovery boundaries.
# ---------------------------------------------------------------------------


def test_snapshot_manifest_excludes_git_internals_but_sees_new_files(tmp_path):
    env = make_env(tmp_path)
    registry = registry_for(env)
    lane_path = gpr.create_registered_worktree(
        registry,
        GIT,
        str(env.repo),
        str(env.worktree_root),
        "lane-manifest",
        kind="lane",
        commit_sha=env.base_sha,
    )
    before = gpr.snapshot_worktree_manifest(lane_path)
    assert all(not key.startswith(".git") for key in before["entries"])
    (Path(lane_path) / "new_file.txt").write_text("new\n")
    after = gpr.snapshot_worktree_manifest(lane_path)
    assert before["manifest_sha256"] != after["manifest_sha256"]
    assert "new_file.txt" in after["entries"]


def test_worktree_registry_survives_concurrent_distinct_registrations(tmp_path):
    """Fault proof: concurrent registration of distinct worktree ids under
    the same flocked registry file never loses an entry (no lost update)."""
    env = make_env(tmp_path)
    registry = registry_for(env)
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            registry.register_creating(
                f"lane-{i}",
                kind="lane",
                path=str(env.worktree_root / f"lane-{i}"),
                base_sha=env.base_sha,
                git_common_dir=str(env.repo / ".git"),
            )
        except Exception as exc:  # noqa: BLE001 - collected for assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(registry.all_entries()) == 10
