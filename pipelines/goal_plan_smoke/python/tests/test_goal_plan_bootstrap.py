from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "goal_plan_bootstrap.py"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_hash(value: Any) -> str:
    return digest(canonical(value))


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = load_module(BOOTSTRAP_PATH, "goal_plan_bootstrap_under_test")


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [shutil.which("git") or "git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr}"
        )
    return result


def write_canonical(path: Path, value: Any, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.chmod(0o600, follow_symlinks=False)
    path.write_bytes(canonical(value) + b"\n")
    path.chmod(mode)


def file_identity(path: Path) -> dict[str, Any]:
    canonical_path = path.resolve()
    metadata = canonical_path.stat()
    data = canonical_path.read_bytes()
    return {
        "path": str(canonical_path),
        "realpath": str(canonical_path),
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "length": len(data),
        "sha256": digest(data),
    }


def source_record(repo: Path, role: str, relative: str) -> dict[str, Any]:
    path = repo / relative
    blob_id = git(repo, "hash-object", str(path)).stdout.strip()
    data = path.read_bytes()
    return {
        "role": role,
        "path": relative,
        "blob_id": blob_id,
        "git_mode": "100644",
        "length": len(data),
        "sha256": digest(data),
    }


@dataclass
class Harness:
    root: Path
    repo: Path
    launch_control: Path
    descriptor_path: Path
    launcher: Path
    plan_path: Path
    state_root: Path
    worktree_root: Path
    source_sha: str
    product_base_sha: str
    anchor_sha: str
    descriptor: dict[str, Any]
    plan: dict[str, Any]
    closed_environment: dict[str, str]
    runtime_bundle_hash: str
    binding_path: Path
    runtime_bytes: bytes
    supervisor_bytes: bytes
    sentinel: Path

    def rewrite_descriptor(
        self,
        mutate: Callable[[dict[str, Any]], None],
        *,
        recompute_hash: bool = True,
    ) -> None:
        value = copy.deepcopy(self.descriptor)
        mutate(value)
        if recompute_hash:
            value["descriptor_sha256"] = object_hash(
                {key: item for key, item in value.items() if key != "descriptor_sha256"}
            )
        write_canonical(self.descriptor_path, value, 0o444)
        self.descriptor = value

    def run(
        self, *suffix: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(Path(sys.executable).resolve()), str(self.launcher), *suffix],
            check=False,
            capture_output=True,
            text=True,
            env=self.closed_environment if env is None else env,
        )

    def self_check(
        self, descriptor: Path | None = None, plan: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.run(
            "self-check",
            "--launch-descriptor",
            str(self.descriptor_path if descriptor is None else descriptor),
            "--plan",
            str(self.plan_path if plan is None else plan),
            "--evidence",
            str(self.launch_control / "evidence" / "self-check.json"),
        )

    def materialize(
        self, command: str = "materialize-runtime"
    ) -> subprocess.CompletedProcess[str]:
        return self.run(
            command,
            "--launch-descriptor",
            str(self.descriptor_path),
            "--plan",
            str(self.plan_path),
            "--target-repo",
            str(self.repo),
            "--execution-source-sha",
            self.source_sha,
            "--state-root",
            str(self.state_root),
            "--binding",
            str(self.binding_path),
        )

    def load_external(self, suffix: str) -> ModuleType:
        return load_module(self.launcher, f"external_bootstrap_{suffix}")

    def parent_argv(self) -> list[str]:
        binding = json.loads(self.binding_path.read_text())
        prefix = list(self.plan["attractor_runner_argv_prefix"])
        fixed = prefix + [
            "run",
            self.plan["parent_runner_invocation"]["dot_source"]["path"],
            "--provider",
            self.plan["provider"],
            "--cwd",
            ".",
            "--logs-root",
            str(self.state_root / "parent-attractor-run"),
            "--on-human-gate",
            "fail",
        ]
        values = {
            "target_repo": str(self.repo),
            "execution_source_sha": self.source_sha,
            "run_id": "test-run",
            "state_root": str(self.state_root),
            "launch_descriptor_path": str(self.descriptor_path),
            "launch_descriptor_sha256": self.descriptor["descriptor_sha256"],
            "trusted_launcher_argv_prefix_sha256": self.descriptor[
                "trusted_launcher_prefix_sha256"
            ],
            "trusted_launcher_binding_sha256": self.plan["trusted_launcher_binding"][
                "binding_sha256"
            ],
            "runtime_bundle_hash": self.runtime_bundle_hash,
            "trusted_runtime_binding_path": str(self.binding_path),
            "worktree_root": str(self.worktree_root),
            "approval_mode": "preapproved",
            "human_gate_transport": "none",
            "delivery_mode": "none",
            "delivery_branch": self.plan["delivery_branch"],
        }
        result = list(fixed)
        for name in self.plan["parent_runner_invocation"]["parameter_order"]:
            result.extend(["--param", f"{name}={values[name]}"])
        assert binding["runtime_bundle_hash"] == self.runtime_bundle_hash
        return result

    def write_parent_argv(self, argv: list[str]) -> Path:
        path = self.state_root / "prelaunch" / "parent-argv.json"
        write_canonical(path, argv, 0o444)
        return path


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    root = tmp_path.resolve()
    repo = root / "target-repo"
    launch_control = root / "launch-control"
    launcher_root = root / "trusted-launcher"
    state_root = root / "state"
    worktree_root = root / "worktrees"
    descriptor_path = launch_control / "launch_descriptor.json"
    launcher = launcher_root / "goal_plan_bootstrap.py"
    plan_path = repo / "pipelines/goal_plan_smoke/plan.json"
    sentinel = root / "TARGET_MODULE_WAS_IMPORTED"
    repo.mkdir()
    launch_control.mkdir(mode=0o700)
    launcher_root.mkdir(mode=0o700)
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Bootstrap Test")
    git(repo, "config", "user.email", "bootstrap@example.invalid")

    (repo / "README").write_text("product base\n")
    git(repo, "add", "README")
    git(repo, "commit", "-q", "-m", "product base")
    product_base_sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    anchor_relative = "pipelines/goal_plan_smoke/goal_plan_smoke.md"
    anchor_path = repo / anchor_relative
    anchor_path.parent.mkdir(parents=True)
    anchor_path.write_text("immutable history anchor\n")
    git(repo, "add", anchor_relative)
    git(repo, "commit", "-q", "-m", "history anchor")
    anchor_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    anchor_blob_sha256 = digest(anchor_path.read_bytes())

    python_dir = repo / "pipelines/goal_plan_smoke/python"
    python_dir.mkdir(parents=True)
    bootstrap_source = BOOTSTRAP_PATH.read_bytes()
    (python_dir / "goal_plan_bootstrap.py").write_bytes(bootstrap_source)
    runtime_bytes = b"#!/usr/bin/python3\nRUNTIME_MARKER = 'exact-runtime-blob'\n"
    supervisor_bytes = (
        b"#!/usr/bin/python3\nSUPERVISOR_MARKER = 'exact-supervisor-blob'\n"
    )
    (python_dir / "goal_plan_runtime.py").write_bytes(runtime_bytes)
    (python_dir / "goal_plan_supervisor.py").write_bytes(supervisor_bytes)
    dot_path = repo / "pipelines/goal_plan_smoke/goal_plan_smoke.dot"
    dot_path.write_text("digraph goal_plan_smoke { Start -> Done }\n")
    malicious_module = repo / "malicious_target_module.py"
    malicious_module.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('imported')\n"
    )

    launcher.write_bytes(bootstrap_source)
    launcher.chmod(0o444)
    interpreter_path = Path(sys.executable).resolve()
    git_path = Path(shutil.which("git") or "/usr/bin/git").resolve()
    closed_variables = {"LC_ALL": {"value": "C"}}
    closed_environment = {
        "schema_version": "goal-plan.closed-environment/v1",
        "variables": closed_variables,
        "environment_sha256": object_hash(closed_variables),
    }
    process_environment = {"LC_ALL": "C"}
    interpreter_identity = file_identity(interpreter_path)
    git_identity = file_identity(git_path)
    git_identity["closed_environment_sha256"] = closed_environment["environment_sha256"]
    launcher_prefix = [str(interpreter_path), str(launcher)]
    git_prefix = [str(git_path)]
    interpreter_prefix = [str(interpreter_path)]

    bootstrap_record = source_record(
        repo,
        "bootstrap",
        "pipelines/goal_plan_smoke/python/goal_plan_bootstrap.py",
    )
    runtime_record = source_record(
        repo,
        "runtime",
        "pipelines/goal_plan_smoke/python/goal_plan_runtime.py",
    )
    supervisor_record = source_record(
        repo,
        "supervisor",
        "pipelines/goal_plan_smoke/python/goal_plan_supervisor.py",
    )
    dot_record = source_record(
        repo,
        "parent-dot",
        "pipelines/goal_plan_smoke/goal_plan_smoke.dot",
    )

    launcher_binding: dict[str, Any] = {
        "schema_version": "goal-plan.trusted-launcher-binding/v2",
        "bootstrap_cli_schema_version": "goal-plan.bootstrap-cli/v1",
        "launch_descriptor_schema_version": "goal-plan.launch-descriptor/v1",
        "launch_descriptor_path_input": "launch_descriptor_path",
        "launch_descriptor_sha256_input": "launch_descriptor_sha256",
        "source": bootstrap_record,
        "external_path": str(launcher),
        "external_realpath": str(launcher),
        "external_mode": 0o444,
        "external_length": len(bootstrap_source),
        "external_sha256": digest(bootstrap_source),
        "trusted_launcher_argv_prefix_sha256": object_hash(launcher_prefix),
        "trusted_git_argv_prefix": git_prefix,
        "trusted_git_prefix_sha256": object_hash(git_prefix),
        "trusted_git_identity": git_identity,
        "trusted_interpreter_or_executable_argv_prefix": interpreter_prefix,
        "trusted_interpreter_or_executable_prefix_sha256": object_hash(
            interpreter_prefix
        ),
        "trusted_interpreter_or_executable_identity": interpreter_identity,
        "closed_environment_sha256": closed_environment["environment_sha256"],
        "supported_subcommands": [
            "self-check",
            "materialize-runtime",
            "rehydrate-runtime",
            "launch-parent",
        ],
        "subcommand_suffixes": {
            "self-check": ["--launch-descriptor", "--plan", "--evidence"],
            "materialize-runtime": [
                "--launch-descriptor",
                "--plan",
                "--target-repo",
                "--execution-source-sha",
                "--state-root",
                "--binding",
            ],
            "rehydrate-runtime": [
                "--launch-descriptor",
                "--plan",
                "--target-repo",
                "--execution-source-sha",
                "--state-root",
                "--binding",
            ],
            "launch-parent": [
                "--launch-descriptor",
                "--binding",
                "--target-repo",
                "--parent-argv-json",
            ],
        },
        "system_call_allowlist": [
            "open",
            "lstat",
            "realpath",
            "fsync",
            "chmod",
            "renameat2-noreplace",
            "chdir",
            "execve",
        ],
        "installation_evidence_schema": ("goal-plan.trusted-launcher-installation/v2"),
        "self_check_evidence_schema": ("goal-plan.trusted-launcher-self-check/v2"),
        "per_invocation_validation": "complete",
    }
    launcher_binding["binding_sha256"] = object_hash(launcher_binding)

    runtime_definition: dict[str, Any] = {
        "schema_version": "goal-plan.trusted-runtime-definition/v3",
        "runtime_source": runtime_record,
        "supervisor_source": supervisor_record,
        "runtime_bundle_hash_policy": ("canonical-v1-exact-git-blobs-and-identities"),
        "runtime_suffix_schema_sha256": digest(b"runtime-suffix-schema-v1"),
        "supervisor_suffix_schema_sha256": digest(b"supervisor-suffix-schema-v1"),
    }
    runtime_definition["definition_sha256"] = object_hash(runtime_definition)
    parameter_order = [
        "target_repo",
        "execution_source_sha",
        "run_id",
        "state_root",
        "launch_descriptor_path",
        "launch_descriptor_sha256",
        "trusted_launcher_argv_prefix_sha256",
        "trusted_launcher_binding_sha256",
        "runtime_bundle_hash",
        "trusted_runtime_binding_path",
        "worktree_root",
        "approval_mode",
        "human_gate_transport",
        "delivery_mode",
        "delivery_branch",
    ]
    parent_invocation: dict[str, Any] = {
        "schema_version": "goal-plan.parent-runner-invocation-definition/v4",
        "dot_source": dot_record,
        "runner_cwd_arg": ".",
        "logs_root_policy": "state_root/parent-attractor-run",
        "parameter_order": parameter_order,
    }
    parent_invocation["definition_sha256"] = object_hash(parent_invocation)
    repository_identity = {
        "vcs": "git",
        "identity_mode": "history_anchor",
        "plan_commit_sha": anchor_sha,
        "plan_path": anchor_relative,
        "plan_blob_sha256": anchor_blob_sha256,
        "product_base_sha": product_base_sha,
    }
    plan: dict[str, Any] = {
        "schema_version": "goal-plan.plan/v5",
        "plan_id": "goal_plan_smoke",
        "target_repo": repository_identity,
        "product_base_sha": product_base_sha,
        "execution_source": {
            "mode": "containing_commit",
            "sha_input": "execution_source_sha",
        },
        "trusted_launcher_argv_prefix": launcher_prefix,
        "trusted_launcher_binding": launcher_binding,
        "trusted_runtime_definition": runtime_definition,
        "trusted_runtime_binding_policy": {
            "schema_version": "goal-plan.trusted-runtime-binding/v3",
            "path_policy": (
                "state_root/trusted-runtime/<runtime-bundle-hash>/"
                "trusted-runtime-binding.json"
            ),
            "no_replacement": True,
            "rehydrate_absent_only": True,
        },
        "provider": "test-provider",
        "attractor_runner_argv_prefix": ["/opt/goal-plan-test-attractor"],
        "attractor_runner_identity": {
            "schema_version": "goal-plan.attractor-runner-identity/v1",
            "argv_prefix_sha256": digest(canonical(["/opt/goal-plan-test-attractor"])),
            "module_name": None,
            "expected_doctor_contract": "amplifier_module_pipeline_runner.doctor/v1",
            "required_run_flags": ["--provider"],
        },
        "parent_runner_invocation": parent_invocation,
        "approval_mode": "preapproved",
        "delivery_mode": "none",
        "delivery_branch": "goal-plan/test-delivery",
        "untrusted_target_module": "malicious_target_module",
    }
    write_canonical(plan_path, plan)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "compiled goal plan")
    source_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    plan_blob_id = git(
        repo, "rev-parse", f"{source_sha}:pipelines/goal_plan_smoke/plan.json"
    ).stdout.strip()
    plan_bytes = plan_path.read_bytes()
    common_output = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    common = (repo / common_output).resolve()

    descriptor: dict[str, Any] = {
        "schema_version": "goal-plan.launch-descriptor/v1",
        "descriptor_version": 1,
        "execution_source_sha": source_sha,
        "repository_identity": repository_identity,
        "target_repo": {
            "path": str(repo),
            "realpath": str(repo),
            "git_common_dir": str(common),
            "git_common_dir_realpath": str(common),
        },
        "plan_path": "pipelines/goal_plan_smoke/plan.json",
        "plan_blob_id": plan_blob_id,
        "plan_blob_sha256": digest(plan_bytes),
        "plan_blob_length": len(plan_bytes),
        "trusted_launcher_argv_prefix": launcher_prefix,
        "trusted_launcher_prefix_sha256": object_hash(launcher_prefix),
        "trusted_launcher_identity": {
            "kind": "python-script",
            "interpreter": interpreter_identity,
            "script": file_identity(launcher),
        },
        "trusted_git_argv_prefix": git_prefix,
        "trusted_git_prefix_sha256": object_hash(git_prefix),
        "trusted_git_identity": git_identity,
        "trusted_interpreter_or_executable_argv_prefix": interpreter_prefix,
        "trusted_interpreter_or_executable_prefix_sha256": object_hash(
            interpreter_prefix
        ),
        "trusted_interpreter_or_executable_identity": interpreter_identity,
        "provider": "test-provider",
        "closed_environment": closed_environment,
        "created_from": {
            "compile_output_sha256": digest(b"compile output"),
            "commit_output_sha256": digest(b"commit output"),
            "harness_configuration_sha256": digest(b"harness configuration"),
            "descriptor_creation_request_sha256": digest(b"creation request"),
        },
    }
    descriptor["descriptor_sha256"] = object_hash(descriptor)
    write_canonical(descriptor_path, descriptor, 0o444)

    plan_blob_identity = {
        "path": "pipelines/goal_plan_smoke/plan.json",
        "blob_id": plan_blob_id,
        "length": len(plan_bytes),
        "sha256": digest(plan_bytes),
    }
    bundle_material = {
        "runtime_definition_schema": runtime_definition["schema_version"],
        "execution_source_sha": source_sha,
        "source_blobs": [runtime_record, supervisor_record],
        "trusted_interpreter_identity": interpreter_identity,
        "launch_descriptor_sha256": descriptor["descriptor_sha256"],
        "plan_blob_identity": plan_blob_identity,
        "trusted_launcher_binding_sha256": launcher_binding["binding_sha256"],
        "runtime_suffix_schema_sha256": runtime_definition[
            "runtime_suffix_schema_sha256"
        ],
        "supervisor_suffix_schema_sha256": runtime_definition[
            "supervisor_suffix_schema_sha256"
        ],
    }
    runtime_bundle_hash = object_hash(bundle_material)
    binding_path = (
        state_root
        / "trusted-runtime"
        / runtime_bundle_hash
        / "trusted-runtime-binding.json"
    )
    return Harness(
        root=root,
        repo=repo,
        launch_control=launch_control,
        descriptor_path=descriptor_path,
        launcher=launcher,
        plan_path=plan_path,
        state_root=state_root,
        worktree_root=worktree_root,
        source_sha=source_sha,
        product_base_sha=product_base_sha,
        anchor_sha=anchor_sha,
        descriptor=descriptor,
        plan=plan,
        closed_environment=process_environment,
        runtime_bundle_hash=runtime_bundle_hash,
        binding_path=binding_path,
        runtime_bytes=runtime_bytes,
        supervisor_bytes=supervisor_bytes,
        sentinel=sentinel,
    )


@pytest.fixture
def unused_closed_environment_fixture() -> None:
    """Keep pytest from treating the exact process environment as test setup."""


@contextmanager
def exact_environment(values: dict[str, str]) -> Iterator[None]:
    original = dict(os.environ)
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def assert_blocked(
    result: subprocess.CompletedProcess[str], token: str = "PRELAUNCH"
) -> None:
    assert result.returncode == 78
    assert result.stdout == ""
    assert result.stderr.startswith(f"{token}_INFRASTRUCTURE_BLOCKED:")


def test_self_check_authenticates_descriptor_and_writes_sealed_evidence(
    harness: Harness,
) -> None:
    result = harness.self_check()
    assert result.returncode == 0, result.stderr
    assert result.stdout == "TRUSTED_LAUNCHER_SELF_CHECK:PASS\n"
    evidence_path = harness.launch_control / "evidence" / "self-check.json"
    evidence = json.loads(evidence_path.read_text())
    assert evidence["status"] == "PASS"
    assert (
        evidence["launch_descriptor_sha256"] == harness.descriptor["descriptor_sha256"]
    )
    assert stat.S_IMODE(evidence_path.stat().st_mode) == 0o444
    assert not harness.sentinel.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.__setitem__("schema_version", "wrong-schema"),
        lambda value: value.__setitem__("descriptor_sha256", "0" * 64),
        lambda value: value.__setitem__("unknown_field", "forbidden"),
    ],
    ids=["schema", "hash", "unknown-field"],
)
def test_rejects_wrong_descriptor_schema_hash_and_unknown_field(
    harness: Harness,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    value = copy.deepcopy(harness.descriptor)
    mutation(value)
    if value.get("descriptor_sha256") != "0" * 64:
        value["descriptor_sha256"] = object_hash(
            {key: item for key, item in value.items() if key != "descriptor_sha256"}
        )
    write_canonical(harness.descriptor_path, value, 0o444)
    assert_blocked(harness.self_check())


def test_rejects_descriptor_wrong_path_mode_and_symlink(harness: Harness) -> None:
    wrong_name = harness.launch_control / "descriptor-copy.json"
    shutil.copyfile(harness.descriptor_path, wrong_name)
    wrong_name.chmod(0o444)
    assert_blocked(harness.self_check(descriptor=wrong_name))

    harness.descriptor_path.chmod(0o644)
    assert_blocked(harness.self_check())
    harness.descriptor_path.chmod(0o444)

    alias_root = harness.root / "descriptor-alias"
    alias_root.mkdir()
    alias = alias_root / "launch_descriptor.json"
    alias.symlink_to(harness.descriptor_path)
    assert_blocked(harness.self_check(descriptor=alias))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan_blob_id", "0" * 40),
        ("plan_blob_length", 1),
        ("plan_blob_sha256", "0" * 64),
    ],
)
def test_rejects_wrong_plan_blob_identity(
    harness: Harness, field: str, value: Any
) -> None:
    harness.rewrite_descriptor(lambda descriptor: descriptor.__setitem__(field, value))
    assert_blocked(harness.self_check())


def test_rejects_wrong_execution_source_and_checked_out_plan_tampering(
    harness: Harness,
) -> None:
    harness.rewrite_descriptor(
        lambda descriptor: descriptor.__setitem__(
            "execution_source_sha", harness.anchor_sha
        )
    )
    assert_blocked(harness.self_check())

    harness = _fresh_harness_for_second_assertion(harness)
    harness.plan_path.write_bytes(harness.plan_path.read_bytes() + b" ")
    assert_blocked(harness.self_check())


def _fresh_harness_for_second_assertion(harness: Harness) -> Harness:
    original = git(
        harness.repo,
        "show",
        f"{harness.source_sha}:pipelines/goal_plan_smoke/plan.json",
    ).stdout.encode()
    harness.plan_path.write_bytes(original)
    descriptor = copy.deepcopy(harness.descriptor)
    descriptor["execution_source_sha"] = harness.source_sha
    descriptor["descriptor_sha256"] = object_hash(
        {key: item for key, item in descriptor.items() if key != "descriptor_sha256"}
    )
    write_canonical(harness.descriptor_path, descriptor, 0o444)
    harness.descriptor = descriptor
    return harness


def test_rejects_checked_out_plan_symlink(harness: Harness) -> None:
    copy_path = harness.root / "plan-copy.json"
    copy_path.write_bytes(harness.plan_path.read_bytes())
    harness.plan_path.unlink()
    harness.plan_path.symlink_to(copy_path)
    assert_blocked(harness.self_check())


@pytest.mark.parametrize("fault", ["bytes", "prefix"])
def test_rejects_wrong_launcher_bytes_and_prefix(harness: Harness, fault: str) -> None:
    def mutate(descriptor: dict[str, Any]) -> None:
        if fault == "bytes":
            descriptor["trusted_launcher_identity"]["script"]["sha256"] = "0" * 64
        else:
            wrong = [
                descriptor["trusted_launcher_argv_prefix"][0],
                str(harness.root / "wrong-launcher.py"),
            ]
            descriptor["trusted_launcher_argv_prefix"] = wrong
            descriptor["trusted_launcher_prefix_sha256"] = object_hash(wrong)

    harness.rewrite_descriptor(mutate)
    assert_blocked(harness.self_check())


@pytest.mark.parametrize("dependency", ["git", "interpreter"])
@pytest.mark.parametrize("fault", ["realpath", "hash", "prefix"])
def test_rejects_wrong_git_and_interpreter_identity(
    harness: Harness, dependency: str, fault: str
) -> None:
    def mutate(descriptor: dict[str, Any]) -> None:
        if dependency == "git":
            prefix_key = "trusted_git_argv_prefix"
            prefix_hash_key = "trusted_git_prefix_sha256"
            identity_key = "trusted_git_identity"
        else:
            prefix_key = "trusted_interpreter_or_executable_argv_prefix"
            prefix_hash_key = "trusted_interpreter_or_executable_prefix_sha256"
            identity_key = "trusted_interpreter_or_executable_identity"
        if fault == "realpath":
            descriptor[identity_key]["realpath"] = str(harness.root / "wrong")
        elif fault == "hash":
            descriptor[identity_key]["sha256"] = "0" * 64
        else:
            wrong = [str(harness.root / f"wrong-{dependency}")]
            descriptor[prefix_key] = wrong
            descriptor[prefix_hash_key] = object_hash(wrong)

    harness.rewrite_descriptor(mutate)
    assert_blocked(harness.self_check())


def test_rejects_closed_environment_mismatch(harness: Harness) -> None:
    result = harness.run(
        "self-check",
        "--launch-descriptor",
        str(harness.descriptor_path),
        "--plan",
        str(harness.plan_path),
        "--evidence",
        str(harness.launch_control / "evidence" / "self-check.json"),
        env={"LC_ALL": "C", "EXTRA": "not-closed"},
    )
    assert_blocked(result)


@pytest.mark.parametrize(
    "relative",
    [
        "pipelines/goal_plan_smoke/python/goal_plan_bootstrap.py",
        "pipelines/goal_plan_smoke/python/goal_plan_runtime.py",
        "pipelines/goal_plan_smoke/python/goal_plan_supervisor.py",
    ],
    ids=["bootstrap", "runtime", "supervisor"],
)
def test_rejects_target_working_copy_source_tampering(
    harness: Harness, relative: str
) -> None:
    path = harness.repo / relative
    path.write_bytes(path.read_bytes() + b"# target tamper\n")
    assert_blocked(harness.self_check())


def test_rejects_external_trusted_bootstrap_tampering(harness: Harness) -> None:
    harness.launcher.chmod(0o600)
    harness.launcher.write_bytes(harness.launcher.read_bytes() + b"# external tamper\n")
    harness.launcher.chmod(0o444)
    assert_blocked(harness.self_check())


def test_materializes_exact_blobs_seals_and_accepts_exact_bundle_idempotently(
    harness: Harness,
) -> None:
    first = harness.materialize()
    assert first.returncode == 0, first.stderr
    assert first.stdout == (
        f"TRUSTED_RUNTIME_MATERIALIZED:{harness.runtime_bundle_hash}\n"
    )
    bundle = harness.binding_path.parent
    runtime = bundle / "goal_plan_runtime.py"
    supervisor = bundle / "goal_plan_supervisor.py"
    assert runtime.read_bytes() == harness.runtime_bytes
    assert supervisor.read_bytes() == harness.supervisor_bytes
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o444
    assert stat.S_IMODE(supervisor.stat().st_mode) == 0o444
    assert stat.S_IMODE(harness.binding_path.stat().st_mode) == 0o444
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o555
    binding_before = harness.binding_path.read_bytes()
    inode_before = bundle.stat().st_ino

    second = harness.materialize()
    assert second.returncode == 0, second.stderr
    assert bundle.stat().st_ino == inode_before
    assert harness.binding_path.read_bytes() == binding_before
    assert not harness.sentinel.exists()


def test_materialization_performs_final_bundle_reread(
    harness: Harness,
) -> None:
    external = harness.load_external("final_reread")
    observed: list[str] = []
    external.__dict__["_BUNDLE_VALIDATION_OBSERVER"] = observed.append
    with exact_environment(harness.closed_environment):
        auth = external._authenticate(
            str(harness.descriptor_path),
            str(harness.plan_path),
            supplied_target_repo=str(harness.repo),
            supplied_source_sha=harness.source_sha,
        )
        result = external._materialize(
            auth, str(harness.state_root), str(harness.binding_path)
        )
    assert result == harness.runtime_bundle_hash
    assert observed == [str(harness.binding_path.parent)]


def test_rehydrate_reconstructs_only_an_absent_bundle_from_git_blobs(
    harness: Harness,
) -> None:
    first = harness.materialize()
    assert first.returncode == 0, first.stderr
    bundle = harness.binding_path.parent
    bundle.chmod(0o700)
    for path in bundle.iterdir():
        path.chmod(0o600)
    shutil.rmtree(bundle)
    assert not bundle.exists()

    recovered = harness.materialize("rehydrate-runtime")
    assert recovered.returncode == 0, recovered.stderr
    assert recovered.stdout == (
        f"TRUSTED_RUNTIME_REHYDRATED:{harness.runtime_bundle_hash}\n"
    )
    assert (bundle / "goal_plan_runtime.py").read_bytes() == harness.runtime_bytes
    assert (bundle / "goal_plan_supervisor.py").read_bytes() == harness.supervisor_bytes


def test_rejects_and_does_not_repair_present_external_bundle_tampering(
    harness: Harness,
) -> None:
    assert harness.materialize().returncode == 0
    runtime = harness.binding_path.parent / "goal_plan_runtime.py"
    runtime.chmod(0o600)
    tampered = b"present bundle tamper\n"
    runtime.write_bytes(tampered)
    result = harness.materialize("rehydrate-runtime")
    assert_blocked(result, "RECOVERY")
    assert runtime.read_bytes() == tampered


def test_ordering_spy_proves_plan_trust_is_consulted_last(
    harness: Harness,
) -> None:
    external = harness.load_external("ordering")
    events: list[str] = []
    external.__dict__["_ORDERING_OBSERVER"] = events.append
    with exact_environment(harness.closed_environment):
        external._authenticate(str(harness.descriptor_path), str(harness.plan_path))
    assert events == [
        "descriptor_authenticated",
        "launcher_authenticated",
        "dependencies_authenticated",
        "committed_plan_authenticated",
        "working_copy_plan_authenticated",
        "plan_parsed",
        "plan_trust_consulted",
    ]
    assert events.index("plan_trust_consulted") > events.index(
        "working_copy_plan_authenticated"
    )


class ExecCaptured(Exception):
    pass


def test_launch_parent_chdirs_then_execves_exact_argv_and_closed_environment(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert harness.materialize().returncode == 0
    argv = harness.parent_argv()
    argv_path = harness.write_parent_argv(argv)
    external = harness.load_external("handoff")
    captured: dict[str, Any] = {}

    def fake_execve(
        path: str, actual_argv: list[str], environment: dict[str, str]
    ) -> None:
        captured["path"] = path
        captured["argv"] = list(actual_argv)
        captured["environment"] = dict(environment)
        captured["cwd"] = os.path.realpath("/proc/self/cwd")
        raise ExecCaptured

    monkeypatch.setattr(external.os, "execve", fake_execve)
    original_cwd = os.getcwd()
    try:
        with (
            exact_environment(harness.closed_environment),
            pytest.raises(ExecCaptured),
        ):
            external._launch_parent(
                str(harness.descriptor_path),
                str(harness.binding_path),
                str(harness.repo),
                str(argv_path),
            )
    finally:
        os.chdir(original_cwd)
    assert captured == {
        "path": argv[0],
        "argv": argv,
        "environment": harness.closed_environment,
        "cwd": str(harness.repo),
    }
    assert not harness.sentinel.exists()


def test_launch_parent_rejects_noncanonical_parent_argv(
    harness: Harness,
) -> None:
    assert harness.materialize().returncode == 0
    argv = harness.parent_argv()
    provider_index = argv.index("--provider") + 1
    argv[provider_index] = "wrong-provider"
    argv_path = harness.write_parent_argv(argv)
    external = harness.load_external("bad_parent_argv")
    with (
        exact_environment(harness.closed_environment),
        pytest.raises(external.BootstrapError),
    ):
        external._launch_parent(
            str(harness.descriptor_path),
            str(harness.binding_path),
            str(harness.repo),
            str(argv_path),
        )


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["self-check"],
        [
            "self-check",
            "--plan",
            "/plan",
            "--launch-descriptor",
            "/descriptor",
            "--evidence",
            "/evidence",
        ],
        [
            "self-check",
            "--launch-descriptor",
            "/descriptor",
            "--launch-descriptor",
            "/descriptor",
            "--evidence",
            "/evidence",
        ],
        [
            "self-check",
            "--launch-descriptor",
            "/descriptor",
            "--plan",
            "/plan",
            "--evidence",
            "/evidence",
            "--extra",
            "value",
        ],
        [
            "materialize-runtime",
            "--launch-descriptor",
            "/descriptor",
            "--plan",
            "/plan",
            "--target-repo",
            "/repo",
            "--execution-source-sha",
            "a" * 40,
            "--binding",
            "/binding",
            "--state-root",
            "/state",
        ],
    ],
    ids=[
        "missing-all",
        "omitted",
        "reordered",
        "duplicate",
        "extra",
        "materialize-reordered",
    ],
)
def test_closed_cli_rejects_omissions_reordering_duplicates_and_extras(
    argv: list[str],
) -> None:
    with pytest.raises(BOOTSTRAP.BootstrapError) as caught:
        BOOTSTRAP._parse_cli(argv)
    assert caught.value.code == "CLI_ARGUMENTS"


@pytest.mark.parametrize(
    ("command", "options"),
    [
        ("self-check", ["--launch-descriptor", "--plan", "--evidence"]),
        (
            "materialize-runtime",
            [
                "--launch-descriptor",
                "--plan",
                "--target-repo",
                "--execution-source-sha",
                "--state-root",
                "--binding",
            ],
        ),
        (
            "rehydrate-runtime",
            [
                "--launch-descriptor",
                "--plan",
                "--target-repo",
                "--execution-source-sha",
                "--state-root",
                "--binding",
            ],
        ),
        (
            "launch-parent",
            [
                "--launch-descriptor",
                "--binding",
                "--target-repo",
                "--parent-argv-json",
            ],
        ),
    ],
)
def test_every_subcommand_has_one_exact_closed_argument_schema(
    command: str, options: list[str]
) -> None:
    valid = [command]
    for index, option in enumerate(options):
        valid.extend([option, f"/value-{index}"])
    parsed = BOOTSTRAP._parse_cli(valid)
    assert parsed.name == command
    assert list(parsed.values) == options

    invalid_variants = [
        valid[:-2],
        [*valid, "--extra", "/extra"],
        [command, options[0], "/duplicate", *valid[1:]],
        [command, options[1], "/reordered", options[0], "/first", *valid[5:]],
    ]
    for invalid in invalid_variants:
        with pytest.raises(BOOTSTRAP.BootstrapError):
            BOOTSTRAP._parse_cli(invalid)


def test_cli_failures_are_deterministic_exit_78(harness: Harness) -> None:
    result = harness.run("self-check")
    assert_blocked(result)
    assert "CLI_ARGUMENTS" in result.stderr


def test_implementation_is_stdlib_only_and_has_no_dynamic_target_imports() -> None:
    tree = ast.parse(BOOTSTRAP_PATH.read_text())
    imported_roots: set[str] = set()
    dynamic_import_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                dynamic_import_calls.append(node)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            ):
                dynamic_import_calls.append(node)
    assert imported_roots <= {
        "__future__",
        "collections",
        "ctypes",
        "datetime",
        "errno",
        "hashlib",
        "json",
        "os",
        "re",
        "stat",
        "subprocess",
        "sys",
        "tempfile",
        "dataclasses",
        "typing",
    }
    assert dynamic_import_calls == []
