#!/usr/bin/env python3
"""Deterministic Wave-2 runtime substrate for goal_plan lanes.

This module implements Wave 2 of the goal_plan_smoke pipeline family: the
external-state runtime primitives a compiled parent graph uses to admit a
run, create/track/remove Git worktrees, reserve run-wide budgets, run
verifier envelopes that prove a verifier caused no unintended mutation,
resolve/check candidate ownership, integrate accepted candidates with
rollback, and perform authority-scoped terminal cleanup.

Design contract reference: docs/plans/2026-08-22-goal-plan-attractor-design.md.
This file owns none of the trusted bootstrap (Wave 0, goal_plan_bootstrap.py)
or the process supervisor (Wave 1, goal_plan_supervisor.py); both are fixed,
uneditable dependencies consumed here as external, already-authenticated
inputs (a parent-invocation binding, and a supervisor argv prefix a caller
may use to launch children -- this module does not itself launch or poll
supervised children; it owns only the deterministic runtime state machinery
listed above).

Scope note: this module does not implement, discover, or run any `.dot`
Attractor graph. It is a library of deterministic primitives a compiled
parent graph (or its harness) calls; there is no CLI entry point because no
live engine execution is in scope for this lane.

Stdlib only. Linux only (uses CLOCK_BOOTTIME and fcntl.flock).
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

SCHEMA_ADMISSION = "goal-plan.runtime-admission/v1"
SCHEMA_RUN_OWNED_WORKTREES = "goal-plan.run-owned-worktrees/v1"
SCHEMA_RUN_BUDGET = "goal-plan.run-budget/v4"
SCHEMA_CHILD_ENVELOPE = "goal-plan.child-verifier-envelope/v1"
SCHEMA_INTEGRATION_JOURNAL = "goal-plan.integration-journal/v1"
SCHEMA_CANDIDATE_EVIDENCE = "goal-plan.candidate-evidence/v1"
SCHEMA_CLEANUP = "goal-plan.pre-terminal-cleanup/v2"

WORKTREE_STATES = {"CREATING", "ACTIVE", "REMOVING", "REMOVED", "PRESERVED_RESIDUAL"}

AUTHORITY_FULL = "FULL"
AUTHORITY_EXTERNAL_ONLY = "EXTERNAL_ONLY"
AUTHORITY_NONE = "NONE"


class GoalPlanRuntimeError(RuntimeError):
    """Fail-closed error for the Wave-2 runtime. Carries a stable code."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Shared primitives: canonical hashing and atomic/exclusive writes
#
# Mirrors the pattern already used in goal_plan_bootstrap.py and
# goal_plan_supervisor.py (copied, not imported -- both fixed files are
# meant to be standalone, and this file must remain standalone too).
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_json(path: str, value: dict[str, Any]) -> bytes:
    data = _canonical_json(value)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.tmp-{os.getpid()}-{time.time_ns()}"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    _fsync_dir(directory)
    return data


def _write_exclusive(path: str, data: bytes, mode: int = 0o644) -> None:
    """No-clobber write: raises if `path` already exists. Used for the
    single, immutable pre-terminal cleanup result."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(directory)


def _flock_mutate(lock_path: str, fn):
    """Open (creating if absent) `lock_path`, hold an exclusive flock for
    the duration of `fn`, then release. `fn` receives nothing and returns
    whatever the caller wants back."""
    directory = os.path.dirname(lock_path) or "."
    os.makedirs(directory, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fn()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _boottime() -> float:
    return time.clock_gettime(time.CLOCK_BOOTTIME)


# ---------------------------------------------------------------------------
# Git helpers (no worktree lifecycle logic lives in bootstrap/supervisor --
# both were surveyed and confirmed to have none; this module owns all of it)
# ---------------------------------------------------------------------------

DEFAULT_GIT_ARGV_PREFIX: tuple[str, ...] = ("git",)


def _run_git(
    git_argv_prefix: Sequence[str],
    repo: str,
    args: Sequence[str],
    *,
    check: bool = True,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess:
    cmd = [*git_argv_prefix, "-C", repo, *args]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=check
        )
    except subprocess.CalledProcessError as exc:
        raise GoalPlanRuntimeError(
            "GIT:COMMAND_FAILED", f"{' '.join(args)}: {exc.stderr}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GoalPlanRuntimeError("GIT:COMMAND_TIMEOUT", " ".join(args)) from exc


def git_head_sha(git_argv_prefix: Sequence[str], worktree_path: str) -> str:
    return _run_git(
        git_argv_prefix, worktree_path, ["rev-parse", "HEAD"]
    ).stdout.strip()


def git_is_clean(git_argv_prefix: Sequence[str], worktree_path: str) -> bool:
    result = _run_git(
        git_argv_prefix, worktree_path, ["status", "--porcelain=v2", "--ignored"]
    )
    return result.stdout.strip() == ""


def create_worktree(
    git_argv_prefix: Sequence[str],
    target_repo: str,
    worktree_path: str,
    *,
    commit_sha: str,
    branch: str | None = None,
    detach: bool = False,
) -> None:
    args = ["worktree", "add"]
    if branch:
        args += ["-b", branch]
    elif detach:
        args.append("--detach")
    args += [worktree_path, commit_sha]
    _run_git(git_argv_prefix, target_repo, args, timeout=120.0)


def remove_worktree(
    git_argv_prefix: Sequence[str],
    target_repo: str,
    worktree_path: str,
    *,
    force: bool = False,
) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(worktree_path)
    _run_git(git_argv_prefix, target_repo, args, timeout=60.0)


def prune_worktrees(git_argv_prefix: Sequence[str], target_repo: str) -> None:
    _run_git(git_argv_prefix, target_repo, ["worktree", "prune"], timeout=30.0)


def list_worktrees(
    git_argv_prefix: Sequence[str], target_repo: str
) -> list[dict[str, Any]]:
    result = _run_git(git_argv_prefix, target_repo, ["worktree", "list", "--porcelain"])
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    if current:
        entries.append(current)
    return entries


def _listed_realpaths(git_argv_prefix: Sequence[str], target_repo: str) -> set[str]:
    return {
        os.path.realpath(entry["worktree"])
        for entry in list_worktrees(git_argv_prefix, target_repo)
        if isinstance(entry.get("worktree"), str)
    }


# ---------------------------------------------------------------------------
# Item 4/5 shared primitive: complete filesystem manifest (excludes .git)
# ---------------------------------------------------------------------------

# Ephemeral tool caches a read-only verifier may legitimately create (pytest,
# hypothesis, bytecode, linters). These are NOT source mutations, so the purity
# check must ignore them -- otherwise a passing `pytest` verifier that writes
# __pycache__/.pytest_cache is misread as a tree-mutating verifier and its
# verdict is discarded as INFRA regardless of exit code. Excluding them keeps
# tamper detection intact for real (tracked-source) changes.
_EPHEMERAL_DIR_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".hypothesis", ".ruff_cache", ".mypy_cache"}
)
_EPHEMERAL_FILE_SUFFIXES = (".pyc", ".pyo")


def snapshot_worktree_manifest(worktree_path: str) -> dict[str, Any]:
    """Complete recursive lstat manifest of the worktree, tracked/untracked/
    ignored, excluding `.git` and ephemeral tool caches (`_EPHEMERAL_DIR_NAMES`
    / `_EPHEMERAL_FILE_SUFFIXES`). Returns entries plus a canonical hash."""
    root = os.path.realpath(worktree_path)
    entries: dict[str, dict[str, Any]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d != ".git" and d not in _EPHEMERAL_DIR_NAMES
        )
        rel_dir = os.path.relpath(dirpath, root)
        # In a linked worktree, `.git` is a plain file (a gitdir pointer), not
        # a directory, so it must also be excluded from filenames at the root.
        filenames = [f for f in filenames if not f.endswith(_EPHEMERAL_FILE_SUFFIXES)]
        names = sorted(filenames) + dirnames
        if rel_dir == ".":
            names = [n for n in names if n != ".git"]
        for name in names:
            full = os.path.join(dirpath, name)
            rel = (
                name
                if rel_dir == "."
                else os.path.normpath(os.path.join(rel_dir, name))
            )
            st = os.lstat(full)
            entry: dict[str, Any] = {
                "mode": stat.S_IMODE(st.st_mode),
                "is_dir": stat.S_ISDIR(st.st_mode),
                "is_symlink": stat.S_ISLNK(st.st_mode),
            }
            if stat.S_ISLNK(st.st_mode):
                entry["symlink_target"] = os.readlink(full)
            elif stat.S_ISREG(st.st_mode):
                entry["size"] = st.st_size
                entry["mtime_ns"] = st.st_mtime_ns
            entries[rel] = entry
    manifest_sha256 = _sha256(_canonical_json(entries))
    return {"entries": entries, "manifest_sha256": manifest_sha256}


# ---------------------------------------------------------------------------
# Item 1: Admission and roots
# ---------------------------------------------------------------------------


def _assert_absolute_no_symlink(path: str, code: str) -> None:
    if not os.path.isabs(path):
        raise GoalPlanRuntimeError(code, f"not absolute: {path}")
    current = os.path.sep
    for part in Path(path).parts[1:]:
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise GoalPlanRuntimeError(code, f"symlink component: {current}")


def _assert_disjoint(paths: dict[str, str]) -> None:
    resolved = {name: os.path.normpath(p) for name, p in paths.items() if p}
    items = list(resolved.items())
    for i, (name_a, path_a) in enumerate(items):
        for name_b, path_b in items[i + 1 :]:
            if (
                path_a == path_b
                or path_a.startswith(path_b + os.sep)
                or path_b.startswith(path_a + os.sep)
            ):
                raise GoalPlanRuntimeError(
                    "ADMISSION:ROOT_OVERLAP", f"{name_a}<->{name_b}"
                )


@dataclasses.dataclass(frozen=True)
class AdmittedRun:
    target_repo: str
    state_root: str
    worktree_root: str
    delivery_state_root: str | None
    compiled_source_manifest: dict[str, str]
    binding_sha256: str
    schema_version: str = SCHEMA_ADMISSION


def admit_run(
    *,
    target_repo: str,
    state_root: str,
    worktree_root: str,
    delivery_state_root: str | None = None,
    compiled_source_paths: dict[str, str],
    expected_compiled_source_sha256: dict[str, str] | None = None,
    parent_binding: dict[str, Any],
    git_argv_prefix: Sequence[str] = DEFAULT_GIT_ARGV_PREFIX,
) -> AdmittedRun:
    """Validate canonical identity, external non-overlapping roots, the
    compiled-source manifest/gate, and parent/source binding before any
    other runtime state is created. Raises GoalPlanRuntimeError on any
    violation (fail-closed, no partial admission)."""
    roots = {
        "target_repo": target_repo,
        "state_root": state_root,
        "worktree_root": worktree_root,
    }
    if delivery_state_root:
        roots["delivery_state_root"] = delivery_state_root
    for path in roots.values():
        _assert_absolute_no_symlink(path, "ADMISSION:BAD_ROOT")
    _assert_disjoint(roots)

    if not os.path.isdir(target_repo):
        raise GoalPlanRuntimeError("ADMISSION:TARGET_REPO_MISSING", target_repo)
    _run_git(git_argv_prefix, target_repo, ["rev-parse", "--git-dir"])

    os.makedirs(state_root, exist_ok=True)
    os.makedirs(worktree_root, exist_ok=True)
    if delivery_state_root:
        os.makedirs(delivery_state_root, exist_ok=True)

    manifest: dict[str, str] = {}
    for role, path in compiled_source_paths.items():
        if not os.path.isfile(path):
            raise GoalPlanRuntimeError(
                "ADMISSION:COMPILED_SOURCE_MISSING", f"{role}:{path}"
            )
        with open(path, "rb") as handle:
            manifest[role] = _sha256(handle.read())
    if expected_compiled_source_sha256:
        for role, expected in expected_compiled_source_sha256.items():
            if manifest.get(role) != expected:
                raise GoalPlanRuntimeError("ADMISSION:COMPILED_SOURCE_MISMATCH", role)

    if not isinstance(parent_binding, dict) or not parent_binding:
        raise GoalPlanRuntimeError(
            "ADMISSION:BAD_PARENT_BINDING", "empty or non-dict binding"
        )
    binding_sha256 = _sha256(_canonical_json(parent_binding))

    return AdmittedRun(
        target_repo=os.path.normpath(target_repo),
        state_root=os.path.normpath(state_root),
        worktree_root=os.path.normpath(worktree_root),
        delivery_state_root=os.path.normpath(delivery_state_root)
        if delivery_state_root
        else None,
        compiled_source_manifest=manifest,
        binding_sha256=binding_sha256,
    )


# ---------------------------------------------------------------------------
# Item 2: Worktree lifecycle
# ---------------------------------------------------------------------------


class WorktreeRegistry:
    """Exact run-owned registry (`run-owned-worktrees.json`) for lane,
    integration, candidate, and delivery worktrees. All read-modify-write
    is flock-protected and atomically written."""

    def __init__(self, registry_path: str, lock_path: str | None = None) -> None:
        self.registry_path = registry_path
        self.lock_path = lock_path or (registry_path + ".lock")

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.registry_path):
            return {"schema_version": SCHEMA_RUN_OWNED_WORKTREES, "worktrees": {}}
        with open(self.registry_path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))

    def _mutate(self, fn) -> Any:
        def locked():
            doc = self._load()
            result = fn(doc)
            _atomic_write_json(self.registry_path, doc)
            return result

        return _flock_mutate(self.lock_path, locked)

    def register_creating(
        self,
        worktree_id: str,
        *,
        kind: str,
        path: str,
        base_sha: str,
        git_common_dir: str,
    ) -> None:
        def fn(doc):
            if worktree_id in doc["worktrees"]:
                raise GoalPlanRuntimeError("WORKTREE:ALREADY_REGISTERED", worktree_id)
            doc["worktrees"][worktree_id] = {
                "kind": kind,
                "path": path,
                "base_sha": base_sha,
                "git_common_dir": git_common_dir,
                "state": "CREATING",
                "head_sha": None,
                "created_at_boottime": _boottime(),
            }

        self._mutate(fn)

    def mark_active(self, worktree_id: str, *, head_sha: str) -> None:
        def fn(doc):
            entry = doc["worktrees"].get(worktree_id)
            if entry is None or entry["state"] != "CREATING":
                raise GoalPlanRuntimeError(
                    "WORKTREE:BAD_TRANSITION", f"{worktree_id}:to ACTIVE"
                )
            entry["state"] = "ACTIVE"
            entry["head_sha"] = head_sha

        self._mutate(fn)

    def mark_removing(self, worktree_id: str) -> None:
        def fn(doc):
            entry = doc["worktrees"].get(worktree_id)
            if entry is None or entry["state"] != "ACTIVE":
                raise GoalPlanRuntimeError(
                    "WORKTREE:BAD_TRANSITION", f"{worktree_id}:to REMOVING"
                )
            entry["state"] = "REMOVING"

        self._mutate(fn)

    def mark_removed(self, worktree_id: str) -> None:
        def fn(doc):
            entry = doc["worktrees"].get(worktree_id)
            if entry is None or entry["state"] not in ("REMOVING", "CREATING"):
                raise GoalPlanRuntimeError(
                    "WORKTREE:BAD_TRANSITION", f"{worktree_id}:to REMOVED"
                )
            entry["state"] = "REMOVED"

        self._mutate(fn)

    def mark_preserved_residual(
        self, worktree_id: str, *, reason: str, recovery_command: str
    ) -> None:
        def fn(doc):
            entry = doc["worktrees"].get(worktree_id)
            if entry is None or entry["state"] not in ("ACTIVE", "REMOVING"):
                raise GoalPlanRuntimeError(
                    "WORKTREE:BAD_TRANSITION", f"{worktree_id}:to PRESERVED_RESIDUAL"
                )
            entry["state"] = "PRESERVED_RESIDUAL"
            entry["residual_reason"] = reason
            entry["recovery_command"] = recovery_command

        self._mutate(fn)

    def get(self, worktree_id: str) -> dict[str, Any] | None:
        return self._load()["worktrees"].get(worktree_id)

    def all_entries(self) -> dict[str, Any]:
        return self._load()["worktrees"]


def create_registered_worktree(
    registry: WorktreeRegistry,
    git_argv_prefix: Sequence[str],
    target_repo: str,
    worktree_root: str,
    worktree_id: str,
    *,
    kind: str,
    commit_sha: str,
    branch: str | None = None,
    detach: bool = False,
) -> str:
    """Register `CREATING`, create the Git worktree, prove HEAD/listing
    match, then register `ACTIVE`. Any failure after `CREATING` leaves an
    honest, recoverable registry entry rather than a silent success."""
    worktree_path = os.path.join(worktree_root, worktree_id)
    if not os.path.normpath(worktree_path).startswith(
        os.path.normpath(worktree_root) + os.sep
    ):
        raise GoalPlanRuntimeError("WORKTREE:ESCAPES_ROOT", worktree_path)
    if os.path.exists(worktree_path):
        raise GoalPlanRuntimeError("WORKTREE:PATH_EXISTS", worktree_path)
    git_common_dir = _run_git(
        git_argv_prefix, target_repo, ["rev-parse", "--git-common-dir"]
    ).stdout.strip()
    registry.register_creating(
        worktree_id,
        kind=kind,
        path=worktree_path,
        base_sha=commit_sha,
        git_common_dir=git_common_dir,
    )
    create_worktree(
        git_argv_prefix,
        target_repo,
        worktree_path,
        commit_sha=commit_sha,
        branch=branch,
        detach=detach,
    )
    head = git_head_sha(git_argv_prefix, worktree_path)
    if head != commit_sha:
        raise GoalPlanRuntimeError(
            "WORKTREE:HEAD_MISMATCH", f"{worktree_id}:{head}!={commit_sha}"
        )
    if os.path.realpath(worktree_path) not in _listed_realpaths(
        git_argv_prefix, target_repo
    ):
        raise GoalPlanRuntimeError("WORKTREE:NOT_LISTED", worktree_path)
    registry.mark_active(worktree_id, head_sha=head)
    return worktree_path


def remove_registered_worktree(
    registry: WorktreeRegistry,
    git_argv_prefix: Sequence[str],
    target_repo: str,
    worktree_id: str,
    *,
    force: bool = False,
) -> None:
    entry = registry.get(worktree_id)
    if entry is None or entry["state"] != "ACTIVE":
        raise GoalPlanRuntimeError(
            "WORKTREE:BAD_TRANSITION", f"{worktree_id}:remove requires ACTIVE"
        )
    registry.mark_removing(worktree_id)
    remove_worktree(git_argv_prefix, target_repo, entry["path"], force=force)
    prune_worktrees(git_argv_prefix, target_repo)
    if os.path.exists(entry["path"]) or os.path.realpath(
        entry["path"]
    ) in _listed_realpaths(git_argv_prefix, target_repo):
        raise GoalPlanRuntimeError("WORKTREE:REMOVE_INCOMPLETE", worktree_id)
    registry.mark_removed(worktree_id)


def reconcile_registry(
    registry: WorktreeRegistry, git_argv_prefix: Sequence[str], target_repo: str
) -> dict[str, list]:
    """Phase-safe recovery: collapse `CREATING`/`REMOVING` entries whose
    worktree never materialized or is already gone; never auto-mutates an
    `ACTIVE` entry whose real state doesn't match -- that is unresolved
    evidence for the caller, not something this function repairs."""
    listed = _listed_realpaths(git_argv_prefix, target_repo)
    reconciled: list[str] = []
    unresolved: list[dict[str, str]] = []
    for worktree_id, entry in registry.all_entries().items():
        state = entry["state"]
        path_exists = os.path.exists(entry["path"])
        in_list = os.path.realpath(entry["path"]) in listed
        if state == "CREATING":
            if not path_exists and not in_list:
                registry.mark_removed(worktree_id)
                reconciled.append(worktree_id)
            else:
                unresolved.append(
                    {"worktree_id": worktree_id, "reason": "CREATING_BUT_PRESENT"}
                )
        elif state == "ACTIVE":
            if not path_exists or not in_list:
                unresolved.append(
                    {"worktree_id": worktree_id, "reason": "ACTIVE_BUT_MISSING"}
                )
            else:
                reconciled.append(worktree_id)
        elif state == "REMOVING":
            if not path_exists and not in_list:
                registry.mark_removed(worktree_id)
                reconciled.append(worktree_id)
            else:
                unresolved.append(
                    {"worktree_id": worktree_id, "reason": "REMOVING_BUT_PRESENT"}
                )
        else:
            reconciled.append(worktree_id)
    return {"reconciled": reconciled, "unresolved": unresolved}


# ---------------------------------------------------------------------------
# Item 3: Budgets
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BudgetLimits:
    max_total_attempts: int
    max_process_launches: int
    max_integration_corrections: int
    max_pipeline_seconds: float


class BudgetLedger:
    """Flocked, atomic, idempotent attempt/process/correction/deadline
    reservation ledger at `state_root/budgets/run-wide.json`, protected by
    `state_root/budgets/run-wide.lock`. Exhaustion raises a closed
    `BUDGET:<KIND>_EXHAUSTED` token rather than silently degrading."""

    def __init__(
        self, ledger_path: str, lock_path: str, limits: BudgetLimits, *, run_id: str
    ) -> None:
        self.ledger_path = ledger_path
        self.lock_path = lock_path
        self.limits = limits
        self.run_id = run_id

    def _load_or_init(self) -> dict[str, Any]:
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "rb") as handle:
                return json.loads(handle.read().decode("utf-8"))
        return {
            "schema_version": SCHEMA_RUN_BUDGET,
            "run_id": self.run_id,
            "limits": dataclasses.asdict(self.limits),
            "started_at_boottime": _boottime(),
            "reservations": {"attempts": {}, "process_launches": {}, "corrections": {}},
            "invalidated_lanes": {},
        }

    def _mutate(self, fn):
        def locked():
            doc = self._load_or_init()
            result = fn(doc)
            _atomic_write_json(self.ledger_path, doc)
            return result

        return _flock_mutate(self.lock_path, locked)

    def _reserve(self, kind: str, limit: int, reservation_id: str) -> dict[str, Any]:
        def fn(doc):
            bucket = doc["reservations"][kind]
            if reservation_id in bucket:
                return bucket[reservation_id]
            if len(bucket) >= limit:
                raise GoalPlanRuntimeError(
                    f"BUDGET:{kind.upper()}_EXHAUSTED", reservation_id
                )
            entry = {"index": len(bucket) + 1, "reserved_at_boottime": _boottime()}
            bucket[reservation_id] = entry
            return entry

        return self._mutate(fn)

    def reserve_attempt(self, reservation_id: str) -> dict[str, Any]:
        return self._reserve("attempts", self.limits.max_total_attempts, reservation_id)

    def reserve_process_launch(self, reservation_id: str) -> dict[str, Any]:
        return self._reserve(
            "process_launches", self.limits.max_process_launches, reservation_id
        )

    def reserve_correction(self, reservation_id: str) -> dict[str, Any]:
        return self._reserve(
            "corrections", self.limits.max_integration_corrections, reservation_id
        )

    def check_deadline(self) -> float:
        def fn(doc):
            elapsed = _boottime() - doc["started_at_boottime"]
            if elapsed > self.limits.max_pipeline_seconds:
                raise GoalPlanRuntimeError(
                    "BUDGET:DEADLINE_EXCEEDED", f"{elapsed:.3f}s"
                )
            return elapsed

        return self._mutate(fn)

    def invalidate_lane_closure(self, lane_id: str, reason: str) -> None:
        def fn(doc):
            doc["invalidated_lanes"][lane_id] = {
                "reason": reason,
                "invalidated_at_boottime": _boottime(),
            }

        self._mutate(fn)

    def snapshot(self) -> dict[str, Any]:
        if not os.path.exists(self.ledger_path):
            return {}
        with open(self.ledger_path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Items 4/5: Verifier envelopes (child, dirty-tolerant; parent, clean-only)
# ---------------------------------------------------------------------------


def _output_root_is_external(output_root: str, worktree_path: str) -> bool:
    worktree_real = os.path.realpath(worktree_path)
    output_real = os.path.realpath(output_root)
    return output_real != worktree_real and not output_real.startswith(
        worktree_real + os.sep
    )


@dataclasses.dataclass
class VerifierEnvelopeResult:
    verdict: str  # PASS | FAIL | INFRA
    exit_code: int | None
    timed_out: bool
    pre_head: str
    post_head: str
    pre_manifest_sha256: str
    post_manifest_sha256: str
    stdout_path: str
    stderr_path: str
    evidence_path: str


def _run_verifier_subprocess(
    verifier_argv: Sequence[str],
    cwd: str,
    timeout_seconds: float,
    env: dict[str, str],
    stdout_path: str,
    stderr_path: str,
) -> tuple[int | None, bool]:
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        try:
            completed = subprocess.run(
                list(verifier_argv),
                cwd=cwd,
                env=env,
                stdout=out,
                stderr=err,
                timeout=timeout_seconds,
                check=False,
            )
            return completed.returncode, False
        except subprocess.TimeoutExpired:
            return None, True


def run_child_attempt_verifier_envelope(
    *,
    git_argv_prefix: Sequence[str],
    worktree_path: str,
    verifier_argv: Sequence[str],
    timeout_seconds: float,
    output_root: str,
    evidence_path: str,
    env: dict[str, str] | None = None,
    expected_post_head: str | None = None,
) -> VerifierEnvelopeResult:
    """Run a read-only verifier against a (possibly legitimately dirty)
    lane/correction worktree. Preserves legitimate dirty candidate state
    while proving the verifier caused no tracked, untracked, ignored,
    staged, HEAD, index, or filesystem mutation. Any mutation -- or a
    timeout -- discards the verdict as `INFRA` regardless of exit code."""
    if not _output_root_is_external(output_root, worktree_path):
        raise GoalPlanRuntimeError("ENVELOPE:OUTPUT_ROOT_NOT_EXTERNAL", output_root)
    os.makedirs(output_root, exist_ok=True)

    pre_head = git_head_sha(git_argv_prefix, worktree_path)
    pre_manifest = snapshot_worktree_manifest(worktree_path)

    stdout_path = os.path.join(output_root, "verifier.stdout")
    stderr_path = os.path.join(output_root, "verifier.stderr")
    run_env = dict(env if env is not None else os.environ)
    run_env["GOAL_PLAN_VERIFIER_OUTPUT_ROOT"] = output_root

    exit_code, timed_out = _run_verifier_subprocess(
        verifier_argv, worktree_path, timeout_seconds, run_env, stdout_path, stderr_path
    )

    post_head = git_head_sha(git_argv_prefix, worktree_path)
    post_manifest = snapshot_worktree_manifest(worktree_path)

    mutated = (
        pre_head != post_head
        or pre_manifest["manifest_sha256"] != post_manifest["manifest_sha256"]
    )
    head_diverged_from_expectation = (
        expected_post_head is not None and post_head != expected_post_head
    )

    if timed_out or mutated or head_diverged_from_expectation:
        verdict = "INFRA"
    elif exit_code == 0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    record = {
        "schema_version": SCHEMA_CHILD_ENVELOPE,
        "verdict": verdict,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "pre_head": pre_head,
        "post_head": post_head,
        "pre_manifest_sha256": pre_manifest["manifest_sha256"],
        "post_manifest_sha256": post_manifest["manifest_sha256"],
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }
    _atomic_write_json(evidence_path, record)

    return VerifierEnvelopeResult(
        verdict=verdict,
        exit_code=exit_code,
        timed_out=timed_out,
        pre_head=pre_head,
        post_head=post_head,
        pre_manifest_sha256=pre_manifest["manifest_sha256"],
        post_manifest_sha256=post_manifest["manifest_sha256"],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        evidence_path=evidence_path,
    )


def run_parent_verifier_envelope(
    *,
    registry: WorktreeRegistry,
    git_argv_prefix: Sequence[str],
    target_repo: str,
    worktree_root: str,
    worktree_id: str,
    candidate_sha: str,
    verifier_argv: Sequence[str],
    timeout_seconds: float,
    output_root: str,
    evidence_path: str,
    env: dict[str, str] | None = None,
) -> VerifierEnvelopeResult:
    """Clean exact-SHA detached verification: creates a disposable detached
    worktree at `candidate_sha` (external, run-owned, registered), requires
    it to be clean before running the verifier, proves immutable pre/post
    HEAD/filesystem/source, and always attempts teardown of the disposable
    worktree even when the envelope itself fails."""
    worktree_path = create_registered_worktree(
        registry,
        git_argv_prefix,
        target_repo,
        worktree_root,
        worktree_id,
        kind="candidate_verification",
        commit_sha=candidate_sha,
        detach=True,
    )
    try:
        if not git_is_clean(git_argv_prefix, worktree_path):
            raise GoalPlanRuntimeError(
                "ENVELOPE:DIRTY_CANDIDATE_WORKTREE", worktree_path
            )
        return run_child_attempt_verifier_envelope(
            git_argv_prefix=git_argv_prefix,
            worktree_path=worktree_path,
            verifier_argv=verifier_argv,
            timeout_seconds=timeout_seconds,
            output_root=output_root,
            evidence_path=evidence_path,
            env=env,
            expected_post_head=candidate_sha,
        )
    finally:
        # The candidate-verification worktree is always disposable regardless
        # of verdict -- unlike a lane worktree's legitimate dirty state, there
        # is nothing here worth preserving, so force removal even if the
        # verifier itself left it dirty (that dirt is exactly what produced
        # the INFRA verdict above).
        remove_registered_worktree(
            registry, git_argv_prefix, target_repo, worktree_id, force=True
        )


# ---------------------------------------------------------------------------
# Item 6: Candidate resolution and ownership
# ---------------------------------------------------------------------------


def resolve_candidate_sha(git_argv_prefix: Sequence[str], worktree_path: str) -> str:
    return git_head_sha(git_argv_prefix, worktree_path)


def check_owned_paths(
    git_argv_prefix: Sequence[str],
    worktree_path: str,
    base_sha: str,
    candidate_sha: str,
    owned_paths: Sequence[str],
) -> dict[str, Any]:
    """Resolve the candidate from Git and enforce that every changed path
    between `base_sha` and `candidate_sha` falls under an owned path."""
    result = _run_git(
        git_argv_prefix, worktree_path, ["diff", "--name-only", base_sha, candidate_sha]
    )
    changed = [line for line in result.stdout.splitlines() if line]
    owned = [o.rstrip("/") for o in owned_paths]

    def is_owned(changed_path: str) -> bool:
        return any(changed_path == o or changed_path.startswith(o + "/") for o in owned)

    violations = [p for p in changed if not is_owned(p)]
    return {"changed": changed, "violations": violations, "ok": not violations}


def record_candidate_evidence(
    evidence_path: str,
    *,
    lane_id: str,
    base_sha: str,
    candidate_sha: str,
    owned_check: dict[str, Any],
    verifier_result: VerifierEnvelopeResult | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_CANDIDATE_EVIDENCE,
        "lane_id": lane_id,
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "owned_check": owned_check,
        "verifier_verdict": verifier_result.verdict if verifier_result else None,
        "verifier_evidence_path": verifier_result.evidence_path
        if verifier_result
        else None,
    }
    record["record_sha256"] = _sha256(_canonical_json(record))
    _atomic_write_json(evidence_path, record)
    return record


# ---------------------------------------------------------------------------
# Item 7: Integration
# ---------------------------------------------------------------------------


class IntegrationJournal:
    """Stable, sequential, flock-protected integration journal recording
    every accepted-or-rejected merge attempt in order."""

    def __init__(self, journal_path: str, lock_path: str | None = None) -> None:
        self.journal_path = journal_path
        self.lock_path = lock_path or (journal_path + ".lock")

    def append_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        def locked():
            if os.path.exists(self.journal_path):
                with open(self.journal_path, "rb") as handle:
                    doc = json.loads(handle.read().decode("utf-8"))
            else:
                doc = {"schema_version": SCHEMA_INTEGRATION_JOURNAL, "entries": []}
            new_entry = dict(entry)
            new_entry["sequence"] = len(doc["entries"]) + 1
            doc["entries"].append(new_entry)
            _atomic_write_json(self.journal_path, doc)
            return new_entry

        return _flock_mutate(self.lock_path, locked)

    def read_all(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.journal_path):
            return []
        with open(self.journal_path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))["entries"]


def integrate_candidate(
    *,
    git_argv_prefix: Sequence[str],
    integration_worktree: str,
    journal: IntegrationJournal,
    lane_id: str,
    candidate_sha: str,
    aggregate_verifier_argv: Sequence[str],
    aggregate_timeout_seconds: float,
    output_root: str,
    evidence_path: str,
) -> dict[str, Any]:
    """Sequentially merge one accepted candidate into the integration
    worktree, run the aggregate verifier after merge, and roll back to the
    exact pre-merge HEAD on any conflict or aggregate failure. Every
    outcome is appended to the journal, never silently dropped."""
    pre_merge_head = git_head_sha(git_argv_prefix, integration_worktree)

    merge = subprocess.run(
        [
            *git_argv_prefix,
            "-C",
            integration_worktree,
            "merge",
            "--no-ff",
            "--no-edit",
            candidate_sha,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if merge.returncode != 0:
        subprocess.run(
            [*git_argv_prefix, "-C", integration_worktree, "merge", "--abort"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return journal.append_entry(
            {
                "lane_id": lane_id,
                "candidate_sha": candidate_sha,
                "pre_merge_head": pre_merge_head,
                "post_merge_head": pre_merge_head,
                "result": "MERGE_CONFLICT",
                "rolled_back": False,
            }
        )

    post_merge_head = git_head_sha(git_argv_prefix, integration_worktree)
    verifier_result = run_child_attempt_verifier_envelope(
        git_argv_prefix=git_argv_prefix,
        worktree_path=integration_worktree,
        verifier_argv=aggregate_verifier_argv,
        timeout_seconds=aggregate_timeout_seconds,
        output_root=output_root,
        evidence_path=evidence_path,
        expected_post_head=post_merge_head,
    )

    if verifier_result.verdict != "PASS":
        subprocess.run(
            [
                *git_argv_prefix,
                "-C",
                integration_worktree,
                "reset",
                "--hard",
                pre_merge_head,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        rolled_back = (
            git_head_sha(git_argv_prefix, integration_worktree) == pre_merge_head
        )
        return journal.append_entry(
            {
                "lane_id": lane_id,
                "candidate_sha": candidate_sha,
                "pre_merge_head": pre_merge_head,
                "post_merge_head": post_merge_head,
                "result": f"AGGREGATE_{verifier_result.verdict}",
                "rolled_back": rolled_back,
            }
        )

    return journal.append_entry(
        {
            "lane_id": lane_id,
            "candidate_sha": candidate_sha,
            "pre_merge_head": pre_merge_head,
            "post_merge_head": post_merge_head,
            "result": "ACCEPTED",
            "rolled_back": False,
        }
    )


# ---------------------------------------------------------------------------
# Item 8: Terminal safety
# ---------------------------------------------------------------------------


def derive_cleanup_authority(
    *, trusted_runtime_verdict: str, parent_binding_verdict: str
) -> str:
    """FULL only when both gates are green; a green trusted runtime plus a
    red/unknown parent/source binding restricts to EXTERNAL_ONLY; a
    red/unknown trusted runtime grants NONE."""
    valid = {"PASS", "FAIL", "UNKNOWN"}
    if trusted_runtime_verdict not in valid or parent_binding_verdict not in valid:
        raise GoalPlanRuntimeError(
            "CLEANUP:BAD_VERDICT_TOKEN",
            f"{trusted_runtime_verdict}/{parent_binding_verdict}",
        )
    if trusted_runtime_verdict != "PASS":
        return AUTHORITY_NONE
    if parent_binding_verdict == "PASS":
        return AUTHORITY_FULL
    return AUTHORITY_EXTERNAL_ONLY


def pre_terminal_cleanup(
    *,
    registry: WorktreeRegistry,
    git_argv_prefix: Sequence[str],
    target_repo: str,
    authority: str,
    result_path: str,
    preserve_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Authority-scoped, exactly-once (no-clobber result file) cleanup.
    Under FULL, removes every non-preserved run-owned worktree and marks
    explicitly named ones PRESERVED_RESIDUAL. Under EXTERNAL_ONLY/NONE,
    performs no Git/worktree mutation and names every unresolved
    resource instead of guessing."""
    if authority not in (AUTHORITY_FULL, AUTHORITY_EXTERNAL_ONLY, AUTHORITY_NONE):
        raise GoalPlanRuntimeError("CLEANUP:BAD_AUTHORITY", authority)
    if os.path.exists(result_path):
        raise GoalPlanRuntimeError("CLEANUP:ALREADY_RUN", result_path)

    removed: list[str] = []
    preserved: list[str] = []
    skipped: list[str] = []
    unresolved: list[dict[str, str]] = []
    entries = registry.all_entries()
    live_states = ("ACTIVE", "CREATING", "REMOVING")

    if authority == AUTHORITY_FULL:
        for worktree_id, entry in entries.items():
            if entry["state"] not in live_states:
                continue
            try:
                if worktree_id in preserve_ids:
                    registry.mark_preserved_residual(
                        worktree_id,
                        reason="operator_selected",
                        recovery_command=f"git -C {target_repo} worktree remove {entry['path']}",
                    )
                    preserved.append(worktree_id)
                    continue
                if entry["state"] == "CREATING" and not os.path.exists(entry["path"]):
                    registry.mark_removed(worktree_id)
                    removed.append(worktree_id)
                    continue
                if entry["state"] == "CREATING":
                    registry.mark_active(
                        worktree_id,
                        head_sha=git_head_sha(git_argv_prefix, entry["path"]),
                    )
                remove_registered_worktree(
                    registry, git_argv_prefix, target_repo, worktree_id
                )
                removed.append(worktree_id)
            except GoalPlanRuntimeError as exc:
                unresolved.append({"worktree_id": worktree_id, "reason": exc.code})
    else:
        for worktree_id, entry in entries.items():
            if entry["state"] in live_states:
                skipped.append(worktree_id)
                unresolved.append(
                    {"worktree_id": worktree_id, "reason": f"AUTHORITY_{authority}"}
                )

    record = {
        "schema_version": SCHEMA_CLEANUP,
        "mutation_authority": authority,
        "removed": removed,
        "preserved_residual": preserved,
        "skipped": skipped,
        "unresolved_resources": unresolved,
    }
    _write_exclusive(result_path, _canonical_json(record))
    return record
