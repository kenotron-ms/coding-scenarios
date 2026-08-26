#!/usr/bin/env python3
"""Descriptor-first bootstrap for the compiled goal-plan pipeline.

This module deliberately uses only the Python standard library.  It is intended
to be installed outside every target repository and run from that sealed copy.
No target-repository Python is imported or executed.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import errno
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

EXIT_CONFIGURATION = 78
DESCRIPTOR_SCHEMA = "goal-plan.launch-descriptor/v1"
BOOTSTRAP_CLI_SCHEMA = "goal-plan.bootstrap-cli/v1"
PLAN_SCHEMA = "goal-plan.plan/v5"
LAUNCHER_BINDING_SCHEMA = "goal-plan.trusted-launcher-binding/v2"
RUNTIME_DEFINITION_SCHEMA = "goal-plan.trusted-runtime-definition/v3"
RUNTIME_BINDING_SCHEMA = "goal-plan.trusted-runtime-binding/v3"
CLOSED_ENVIRONMENT_SCHEMA = "goal-plan.closed-environment/v1"
SELF_CHECK_SCHEMA = "goal-plan.trusted-launcher-self-check/v2"
PARENT_INVOCATION_SCHEMA = "goal-plan.parent-runner-invocation-definition/v4"
RUNNER_IDENTITY_SCHEMA = "goal-plan.attractor-runner-identity/v1"

MAX_DESCRIPTOR_BYTES = 1024 * 1024
MAX_PLAN_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_ORDERING_OBSERVER: Callable[[str], None] | None = None
_BUNDLE_VALIDATION_OBSERVER: Callable[[str], None] | None = None
_HANDOFF_OBSERVER: Callable[[str], None] | None = None

_PARENT_PARAMETER_ORDER = [
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
_DELIVERY_PARENT_PARAMETERS = ["delivery_state_root", "github_repo"]

_COMMAND_SCHEMAS: dict[str, tuple[str, ...]] = {
    "self-check": ("--launch-descriptor", "--plan", "--evidence"),
    "materialize-runtime": (
        "--launch-descriptor",
        "--plan",
        "--target-repo",
        "--execution-source-sha",
        "--state-root",
        "--binding",
    ),
    "rehydrate-runtime": (
        "--launch-descriptor",
        "--plan",
        "--target-repo",
        "--execution-source-sha",
        "--state-root",
        "--binding",
    ),
    "launch-parent": (
        "--launch-descriptor",
        "--binding",
        "--target-repo",
        "--parent-argv-json",
    ),
}

_SOURCE_KEYS = {
    "role",
    "path",
    "blob_id",
    "git_mode",
    "length",
    "sha256",
}
_FILE_IDENTITY_KEYS = {
    "path",
    "realpath",
    "mode",
    "uid",
    "gid",
    "length",
    "sha256",
}
_DESCRIPTOR_KEYS = {
    "schema_version",
    "descriptor_version",
    "execution_source_sha",
    "repository_identity",
    "target_repo",
    "plan_path",
    "plan_blob_id",
    "plan_blob_sha256",
    "plan_blob_length",
    "trusted_launcher_argv_prefix",
    "trusted_launcher_prefix_sha256",
    "trusted_launcher_identity",
    "trusted_git_argv_prefix",
    "trusted_git_prefix_sha256",
    "trusted_git_identity",
    "trusted_interpreter_or_executable_argv_prefix",
    "trusted_interpreter_or_executable_prefix_sha256",
    "trusted_interpreter_or_executable_identity",
    "provider",
    "closed_environment",
    "created_from",
    "descriptor_sha256",
}
_LAUNCHER_BINDING_KEYS = {
    "schema_version",
    "bootstrap_cli_schema_version",
    "launch_descriptor_schema_version",
    "launch_descriptor_path_input",
    "launch_descriptor_sha256_input",
    "source",
    "external_path",
    "external_realpath",
    "external_mode",
    "external_length",
    "external_sha256",
    "trusted_launcher_argv_prefix_sha256",
    "trusted_git_argv_prefix",
    "trusted_git_prefix_sha256",
    "trusted_git_identity",
    "trusted_interpreter_or_executable_argv_prefix",
    "trusted_interpreter_or_executable_prefix_sha256",
    "trusted_interpreter_or_executable_identity",
    "closed_environment_sha256",
    "supported_subcommands",
    "subcommand_suffixes",
    "system_call_allowlist",
    "installation_evidence_schema",
    "self_check_evidence_schema",
    "per_invocation_validation",
    "binding_sha256",
}
_RUNTIME_DEFINITION_KEYS = {
    "schema_version",
    "runtime_source",
    "supervisor_source",
    "runtime_bundle_hash_policy",
    "runtime_suffix_schema_sha256",
    "supervisor_suffix_schema_sha256",
    "definition_sha256",
}
_RUNTIME_BINDING_POLICY = {
    "schema_version": RUNTIME_BINDING_SCHEMA,
    "path_policy": (
        "state_root/trusted-runtime/<runtime-bundle-hash>/trusted-runtime-binding.json"
    ),
    "no_replacement": True,
    "rehydrate_absent_only": True,
}
_RUNTIME_BINDING_KEYS = {
    "schema_version",
    "created_at",
    "launch_descriptor_path",
    "launch_descriptor_sha256",
    "plan_blob_identity",
    "execution_source_sha",
    "runtime_bundle_hash",
    "trusted_runtime_definition_sha256",
    "trusted_launcher_argv_prefix",
    "trusted_launcher_argv_prefix_sha256",
    "trusted_launcher_binding_sha256",
    "source_blobs",
    "external_files",
    "trusted_git_argv_prefix",
    "trusted_git_prefix_sha256",
    "trusted_git_identity",
    "trusted_interpreter_argv_prefix",
    "trusted_interpreter_prefix_sha256",
    "trusted_interpreter_identity",
    "trusted_runtime_argv_prefix",
    "trusted_runtime_argv_prefix_sha256",
    "trusted_supervisor_argv_prefix",
    "trusted_supervisor_argv_prefix_sha256",
    "materialization_commands",
    "binding_sha256",
}


class BootstrapError(RuntimeError):
    """A deterministic fail-closed bootstrap error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    values: dict[str, str]


@dataclass
class Authenticated:
    descriptor_path: str
    descriptor_bytes: bytes
    descriptor: dict[str, Any]
    descriptor_sha256: str
    target_repo: str
    git_common_dir: str
    plan_path: str
    plan_bytes: bytes
    plan: dict[str, Any]
    plan_blob_identity: dict[str, Any]
    launcher_binding: dict[str, Any]
    runtime_definition: dict[str, Any]
    runtime_sources: list[dict[str, Any]]
    source_bytes: dict[str, bytes]


@dataclass(frozen=True)
class PinnedDirectory:
    path: str
    descriptor: int
    device: int
    inode: int


def _event(name: str) -> None:
    if _ORDERING_OBSERVER is not None:
        _ORDERING_OBSERVER(name)


def _fail(code: str, message: str) -> NoReturn:
    raise BootstrapError(code, message)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_object(value: Any) -> str:
    return _sha256(_canonical_json(value))


def _without_hash(value: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: item for name, item in value.items() if name != key}


def _require_mapping(value: Any, code: str, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(code, f"{name} must be a JSON object with string keys")
    return value


def _require_exact_keys(
    value: dict[str, Any], expected: set[str], code: str, name: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        _fail(code, f"{name} fields differ; missing={missing}; unknown={unknown}")


def _require_string(value: Any, code: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(code, f"{name} must be a non-empty string")
    return value


def _require_int(value: Any, code: str, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code, f"{name} must be a non-negative integer")
    return value


def _require_sha256(value: Any, code: str, name: str) -> str:
    text = _require_string(value, code, name)
    if SHA256_RE.fullmatch(text) is None:
        _fail(code, f"{name} must be a lowercase SHA-256")
    return text


def _require_full_git_sha(value: Any, code: str, name: str) -> str:
    text = _require_string(value, code, name)
    if FULL_GIT_SHA_RE.fullmatch(text) is None:
        _fail(code, f"{name} must be a full lowercase Git commit ID")
    return text


def _require_git_object(value: Any, code: str, name: str) -> str:
    text = _require_string(value, code, name)
    if GIT_OBJECT_RE.fullmatch(text) is None:
        _fail(code, f"{name} must be a full lowercase Git object ID")
    return text


def _require_string_list(value: Any, code: str, name: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        _fail(code, f"{name} must be a non-empty list of non-empty strings")
    return list(value)


def _require_absolute_normal_path(value: Any, code: str, name: str) -> str:
    path = _require_string(value, code, name)
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        _fail(code, f"{name} must be an absolute normalized path")
    return path


def _require_repo_relative_path(value: Any, code: str, name: str) -> str:
    path = _require_string(value, code, name)
    if (
        os.path.isabs(path)
        or path.startswith(("./", "../"))
        or os.path.normpath(path) != path
        or path == "."
        or "/../" in f"/{path}/"
        or "\x00" in path
    ):
        _fail(code, f"{name} must be a normalized repository-relative path")
    return path


def _path_contains(parent: str, child: str) -> bool:
    try:
        return os.path.commonpath((parent, child)) == parent
    except ValueError:
        return False


def _require_disjoint(path_a: str, path_b: str, code: str, names: str) -> None:
    if _path_contains(path_a, path_b) or _path_contains(path_b, path_a):
        _fail(code, f"{names} must be disjoint")


def _open_directory(
    path_value: str, code: str, *, create: bool = False, mode: int = 0o700
) -> PinnedDirectory:
    path = _require_absolute_normal_path(path_value, code, "directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(os.path.sep, flags)
    current_path = os.path.sep
    try:
        for part in (item for item in path.split(os.path.sep) if item):
            try:
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode, dir_fd=descriptor)
                os.fsync(descriptor)
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            current_path = os.path.join(current_path, part)
        observed_path = os.path.realpath(f"/proc/self/fd/{descriptor}")
        if observed_path != path:
            _fail(code, f"opened directory differs from canonical path: {path}")
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(code, f"opened path is not a directory: {path}")
        return PinnedDirectory(path, descriptor, metadata.st_dev, metadata.st_ino)
    except BaseException:
        os.close(descriptor)
        raise


def _close_directory(directory: PinnedDirectory) -> None:
    os.close(directory.descriptor)


def _verify_pinned_directory(directory: PinnedDirectory, code: str) -> None:
    metadata = os.fstat(directory.descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != (directory.device, directory.inode)
        or os.path.realpath(f"/proc/self/fd/{directory.descriptor}") != directory.path
    ):
        _fail(code, f"pinned directory identity changed: {directory.path}")


def _assert_no_symlink_components(
    path: str, code: str, *, allow_missing: bool = False
) -> None:
    current = os.path.sep
    parts = [part for part in path.split(os.path.sep) if part]
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if allow_missing:
                return
            _fail(code, f"path component is missing: {current}")
        if stat.S_ISLNK(metadata.st_mode):
            _fail(code, f"symlink traversal is forbidden: {current}")
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            _fail(code, f"non-directory path component: {current}")


def _read_regular(
    path: str,
    code: str,
    *,
    max_bytes: int,
    require_nonwritable: bool = False,
    expected_mode: int | None = None,
) -> tuple[bytes, os.stat_result]:
    path = _require_absolute_normal_path(path, code, "path")
    parent = _open_directory(os.path.dirname(path), code)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(os.path.basename(path), flags, dir_fd=parent.descriptor)
    except OSError as exc:
        _close_directory(parent)
        _fail(code, f"cannot open regular file safely: {path}: {exc.errno}")
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            _fail(code, f"path is not a regular file: {path}")
        if os.path.realpath(f"/proc/self/fd/{descriptor}") != path:
            _fail(code, f"opened file differs from canonical path: {path}")
        mode = stat.S_IMODE(opened.st_mode)
        if require_nonwritable and mode & 0o222:
            _fail(code, f"file must have no write bits: {path}")
        if expected_mode is not None and mode != expected_mode:
            _fail(code, f"file mode mismatch for {path}: {mode:04o}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                _fail(code, f"file exceeds bounded read limit: {path}")
        after = os.fstat(descriptor)
        if (
            opened.st_size != after.st_size
            or opened.st_mtime_ns != after.st_mtime_ns
            or opened.st_ctime_ns != after.st_ctime_ns
        ):
            _fail(code, f"file changed while reading: {path}")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)
        _close_directory(parent)


def _identity(path: str, code: str) -> dict[str, Any]:
    data, metadata = _read_regular(path, code, max_bytes=MAX_SOURCE_BYTES)
    return {
        "path": path,
        "realpath": os.path.realpath(path),
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "length": len(data),
        "sha256": _sha256(data),
    }


def _validate_identity(
    expected: Any,
    code: str,
    name: str,
    *,
    require_executable: bool,
    require_nonwritable: bool,
) -> dict[str, Any]:
    identity = _require_mapping(expected, code, name)
    _require_exact_keys(identity, _FILE_IDENTITY_KEYS, code, name)
    path = _require_absolute_normal_path(identity["path"], code, f"{name}.path")
    if identity["realpath"] != path:
        _fail(code, f"{name}.realpath must equal its canonical path")
    observed = _identity(path, code)
    if observed != identity:
        _fail(code, f"{name} does not match the current file identity")
    mode = _require_int(identity["mode"], code, f"{name}.mode")
    if require_executable and mode & 0o111 == 0:
        _fail(code, f"{name} is not executable")
    if require_nonwritable and mode & 0o222:
        _fail(code, f"{name} must have no write bits")
    if mode & 0o022:
        _fail(code, f"{name} may not be group/other writable")
    return identity


def _parse_canonical_json(
    data: bytes, code: str, name: str, *, require_newline: bool = True
) -> Any:
    try:
        text = data.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(code, f"{name} is not valid UTF-8 canonical JSON: {exc}")
    expected = _canonical_json(value) + (b"\n" if require_newline else b"")
    if data != expected:
        _fail(code, f"{name} is not in canonical JSON encoding")
    return value


def _parse_cli(argv: Sequence[str]) -> ParsedCommand:
    if not argv:
        _fail("CLI_ARGUMENTS", "missing subcommand")
    command = argv[0]
    options = _COMMAND_SCHEMAS.get(command)
    if options is None:
        _fail("CLI_ARGUMENTS", f"unsupported subcommand: {command}")
    expected_length = 1 + 2 * len(options)
    if len(argv) != expected_length:
        _fail(
            "CLI_ARGUMENTS",
            f"{command} requires exactly {expected_length - 1} ordered argument tokens",
        )
    values: dict[str, str] = {}
    for index, option in enumerate(options):
        actual = argv[1 + 2 * index]
        value = argv[2 + 2 * index]
        if actual != option:
            _fail(
                "CLI_ARGUMENTS",
                f"{command} argument {index + 1} must be {option}, not {actual}",
            )
        if not value or value.startswith("--"):
            _fail("CLI_ARGUMENTS", f"{option} requires one non-option value")
        values[option] = value
    return ParsedCommand(command, values)


def _validate_closed_environment(value: Any) -> dict[str, Any]:
    code = "CLOSED_ENVIRONMENT"
    closed = _require_mapping(value, code, "closed_environment")
    _require_exact_keys(
        closed,
        {"schema_version", "variables", "environment_sha256"},
        code,
        "closed_environment",
    )
    if closed["schema_version"] != CLOSED_ENVIRONMENT_SCHEMA:
        _fail(code, "closed environment schema mismatch")
    variables = _require_mapping(
        closed["variables"], code, "closed_environment.variables"
    )
    for key, rule_value in variables.items():
        if not key or "=" in key or "\x00" in key:
            _fail(code, f"invalid environment key: {key!r}")
        rule = _require_mapping(rule_value, code, f"environment rule {key}")
        if set(rule) not in ({"value"}, {"sha256"}):
            _fail(code, f"environment rule {key} must contain value or sha256")
        if "value" in rule:
            _require_string(rule["value"], code, f"environment value {key}")
        else:
            _require_sha256(rule["sha256"], code, f"environment hash {key}")
    expected_hash = _require_sha256(
        closed["environment_sha256"], code, "closed environment hash"
    )
    if _hash_object(variables) != expected_hash:
        _fail(code, "closed environment representation hash mismatch")
    if set(os.environ) != set(variables):
        _fail(code, "current environment key set is not closed")
    for key, rule_value in variables.items():
        current = os.environ[key]
        if "value" in rule_value and current != rule_value["value"]:
            _fail(code, f"environment value mismatch: {key}")
        if "sha256" in rule_value and _sha256(current.encode()) != rule_value["sha256"]:
            _fail(code, f"environment hash mismatch: {key}")
    return closed


def _validate_descriptor_shape(
    path: str, data: bytes, value: Any
) -> tuple[dict[str, Any], str]:
    code = "DESCRIPTOR"
    descriptor = _require_mapping(value, code, "launch descriptor")
    _require_exact_keys(descriptor, _DESCRIPTOR_KEYS, code, "launch descriptor")
    if os.path.basename(path) != "launch_descriptor.json":
        _fail(code, "descriptor canonical basename must be launch_descriptor.json")
    if descriptor["schema_version"] != DESCRIPTOR_SCHEMA:
        _fail(code, "descriptor schema mismatch")
    if descriptor["descriptor_version"] != 1:
        _fail(code, "descriptor version mismatch")
    _require_full_git_sha(
        descriptor["execution_source_sha"], code, "execution_source_sha"
    )
    _require_repo_relative_path(descriptor["plan_path"], code, "plan_path")
    _require_git_object(descriptor["plan_blob_id"], code, "plan_blob_id")
    _require_sha256(descriptor["plan_blob_sha256"], code, "plan_blob_sha256")
    _require_int(descriptor["plan_blob_length"], code, "plan_blob_length")
    _require_string(descriptor["provider"], code, "provider")
    target = _require_mapping(descriptor["target_repo"], code, "target_repo")
    _require_exact_keys(
        target,
        {"path", "realpath", "git_common_dir", "git_common_dir_realpath"},
        code,
        "target_repo",
    )
    for field in ("path", "realpath", "git_common_dir", "git_common_dir_realpath"):
        _require_absolute_normal_path(target[field], code, f"target_repo.{field}")
    if target["path"] != target["realpath"]:
        _fail(code, "target repository path and realpath must be identical")
    if target["git_common_dir"] != target["git_common_dir_realpath"]:
        _fail(code, "Git common-directory path and realpath must be identical")
    _require_mapping(descriptor["repository_identity"], code, "repository_identity")
    for prefix_name, hash_name in (
        ("trusted_launcher_argv_prefix", "trusted_launcher_prefix_sha256"),
        ("trusted_git_argv_prefix", "trusted_git_prefix_sha256"),
        (
            "trusted_interpreter_or_executable_argv_prefix",
            "trusted_interpreter_or_executable_prefix_sha256",
        ),
    ):
        prefix = _require_string_list(descriptor[prefix_name], code, prefix_name)
        expected_hash = _require_sha256(descriptor[hash_name], code, hash_name)
        if _hash_object(prefix) != expected_hash:
            _fail(code, f"{prefix_name} hash mismatch")
    created = _require_mapping(descriptor["created_from"], code, "created_from")
    _require_exact_keys(
        created,
        {
            "compile_output_sha256",
            "commit_output_sha256",
            "harness_configuration_sha256",
            "descriptor_creation_request_sha256",
        },
        code,
        "created_from",
    )
    for key, item in created.items():
        _require_sha256(item, code, f"created_from.{key}")
    observed_hash = _sha256(
        _canonical_json(_without_hash(descriptor, "descriptor_sha256"))
    )
    expected_descriptor_hash = _require_sha256(
        descriptor["descriptor_sha256"], code, "descriptor_sha256"
    )
    if observed_hash != expected_descriptor_hash:
        _fail(code, "descriptor SHA-256 mismatch")
    if data != _canonical_json(descriptor) + b"\n":
        _fail(code, "descriptor bytes are not canonical")
    return descriptor, observed_hash


def _load_descriptor(path_value: str) -> tuple[str, bytes, dict[str, Any], str]:
    code = "DESCRIPTOR"
    path = _require_absolute_normal_path(path_value, code, "launch descriptor")
    data, _ = _read_regular(
        path,
        code,
        max_bytes=MAX_DESCRIPTOR_BYTES,
        require_nonwritable=True,
    )
    value = _parse_canonical_json(data, code, "launch descriptor")
    descriptor, descriptor_hash = _validate_descriptor_shape(path, data, value)
    _event("descriptor_authenticated")
    return path, data, descriptor, descriptor_hash


def _current_launcher_path() -> str:
    return os.path.realpath(__file__)


def _authenticate_launcher(descriptor: dict[str, Any]) -> None:
    code = "LAUNCHER_IDENTITY"
    prefix = _require_string_list(
        descriptor["trusted_launcher_argv_prefix"], code, "launcher prefix"
    )
    current_script = _current_launcher_path()
    current_interpreter = os.path.realpath(sys.executable)
    identity = _require_mapping(
        descriptor["trusted_launcher_identity"], code, "launcher identity"
    )
    if len(prefix) == 2:
        if prefix != [current_interpreter, current_script]:
            _fail(code, "current interpreter/script prefix differs from descriptor")
        _require_exact_keys(
            identity, {"kind", "interpreter", "script"}, code, "launcher identity"
        )
        if identity["kind"] != "python-script":
            _fail(code, "launcher identity kind mismatch")
        interpreter = _validate_identity(
            identity["interpreter"],
            code,
            "launcher interpreter",
            require_executable=True,
            require_nonwritable=False,
        )
        script = _validate_identity(
            identity["script"],
            code,
            "launcher script",
            require_executable=False,
            require_nonwritable=True,
        )
        if (
            interpreter["path"] != current_interpreter
            or script["path"] != current_script
        ):
            _fail(code, "launcher identity paths differ from current process")
    elif len(prefix) == 1:
        if (
            prefix != [current_script]
            or os.path.realpath(sys.argv[0]) != current_script
        ):
            _fail(code, "current executable launcher prefix differs from descriptor")
        _require_exact_keys(identity, {"kind", "executable"}, code, "launcher identity")
        if identity["kind"] != "executable":
            _fail(code, "launcher identity kind mismatch")
        executable = _validate_identity(
            identity["executable"],
            code,
            "launcher executable",
            require_executable=True,
            require_nonwritable=True,
        )
        if executable["path"] != current_script:
            _fail(code, "launcher executable path differs from current process")
    else:
        _fail(code, "launcher prefix must be executable or interpreter plus script")
    _event("launcher_authenticated")


def _authenticate_dependencies(descriptor: dict[str, Any]) -> None:
    code = "DEPENDENCY_IDENTITY"
    closed = _validate_closed_environment(descriptor["closed_environment"])
    environment_hash = closed["environment_sha256"]

    git_prefix = _require_string_list(
        descriptor["trusted_git_argv_prefix"], code, "Git prefix"
    )
    if len(git_prefix) != 1:
        _fail(code, "Git prefix must contain exactly one absolute executable")
    git_path = _require_absolute_normal_path(git_prefix[0], code, "Git executable")
    git_identity = _require_mapping(
        descriptor["trusted_git_identity"], code, "Git identity"
    )
    _require_exact_keys(
        git_identity,
        _FILE_IDENTITY_KEYS | {"closed_environment_sha256"},
        code,
        "Git identity",
    )
    if git_identity["closed_environment_sha256"] != environment_hash:
        _fail(code, "Git closed-environment hash mismatch")
    _validate_identity(
        {key: git_identity[key] for key in _FILE_IDENTITY_KEYS},
        code,
        "Git executable",
        require_executable=True,
        require_nonwritable=False,
    )
    if git_identity["path"] != git_path:
        _fail(code, "Git prefix and identity path differ")

    interpreter_prefix = _require_string_list(
        descriptor["trusted_interpreter_or_executable_argv_prefix"],
        code,
        "interpreter prefix",
    )
    if len(interpreter_prefix) != 1:
        _fail(code, "interpreter prefix must contain exactly one executable")
    interpreter_path = _require_absolute_normal_path(
        interpreter_prefix[0], code, "interpreter executable"
    )
    interpreter_identity = _validate_identity(
        descriptor["trusted_interpreter_or_executable_identity"],
        code,
        "interpreter identity",
        require_executable=True,
        require_nonwritable=False,
    )
    if interpreter_identity["path"] != interpreter_path:
        _fail(code, "interpreter prefix and identity path differ")
    if os.path.realpath(sys.executable) != interpreter_path:
        _fail(code, "current interpreter differs from descriptor")
    _event("dependencies_authenticated")


def _run_git(
    descriptor: dict[str, Any],
    suffix: Sequence[str],
    code: str,
    *,
    allow_exit: set[int] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    prefix = list(descriptor["trusted_git_argv_prefix"])
    argv = prefix + list(suffix)
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=dict(os.environ),
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _fail(code, f"trusted Git execution failed: {type(exc).__name__}")
    accepted = {0} if allow_exit is None else allow_exit
    if result.returncode not in accepted:
        stderr = result.stderr[:4096].decode("utf-8", "replace").strip()
        _fail(code, f"trusted Git exited {result.returncode}: {stderr}")
    if len(result.stdout) > MAX_SOURCE_BYTES or len(result.stderr) > MAX_SOURCE_BYTES:
        _fail(code, "trusted Git output exceeded the bounded capture limit")
    return result


def _validate_repo_from_descriptor(
    descriptor: dict[str, Any], descriptor_path: str
) -> tuple[str, str]:
    code = "TARGET_REPOSITORY"
    target = descriptor["target_repo"]
    repo = target["path"]
    common = target["git_common_dir"]
    _assert_no_symlink_components(repo, code)
    _assert_no_symlink_components(common, code)
    if os.path.realpath(repo) != repo or os.path.realpath(common) != common:
        _fail(code, "target repository paths must be canonical realpaths")
    top = _run_git(
        descriptor, ("-C", repo, "rev-parse", "--show-toplevel"), code
    ).stdout.rstrip(b"\n")
    try:
        observed_top = top.decode("utf-8")
    except UnicodeDecodeError:
        _fail(code, "Git top-level path is not UTF-8")
    if observed_top != repo:
        _fail(code, "Git top-level differs from descriptor target repository")
    common_output = _run_git(
        descriptor, ("-C", repo, "rev-parse", "--git-common-dir"), code
    ).stdout.rstrip(b"\n")
    try:
        common_text = common_output.decode("utf-8")
    except UnicodeDecodeError:
        _fail(code, "Git common-directory path is not UTF-8")
    if not os.path.isabs(common_text):
        common_text = os.path.join(repo, common_text)
    observed_common = os.path.realpath(common_text)
    if observed_common != common:
        _fail(code, "Git common directory differs from descriptor")
    for external, external_name in (
        (os.path.dirname(descriptor_path), "launch-control root"),
        (_current_launcher_path(), "trusted launcher"),
    ):
        for protected, protected_name in (
            (repo, "target repository"),
            (common, "Git common directory"),
        ):
            _require_disjoint(
                external,
                protected,
                code,
                f"{external_name} and {protected_name}",
            )
    return repo, common


def _git_blob_id(
    descriptor: dict[str, Any], common: str, commit: str, path: str, code: str
) -> str:
    result = _run_git(
        descriptor,
        ("--git-dir", common, "rev-parse", "--verify", f"{commit}:{path}"),
        code,
    )
    try:
        object_id = result.stdout.rstrip(b"\n").decode("ascii")
    except UnicodeDecodeError:
        _fail(code, "Git object ID is not ASCII")
    return _require_git_object(object_id, code, "observed Git blob ID")


def _git_blob(
    descriptor: dict[str, Any], common: str, object_id: str, code: str
) -> bytes:
    return _run_git(
        descriptor, ("--git-dir", common, "cat-file", "blob", object_id), code
    ).stdout


def _git_entry_mode_and_id(
    descriptor: dict[str, Any], common: str, commit: str, path: str, code: str
) -> tuple[str, str]:
    result = _run_git(
        descriptor,
        ("--git-dir", common, "ls-tree", "-z", commit, "--", path),
        code,
    )
    entry = result.stdout
    if not entry.endswith(b"\x00") or entry.count(b"\x00") != 1:
        _fail(code, f"Git tree has no unique regular entry for {path}")
    header, separator, entry_path = entry[:-1].partition(b"\t")
    fields = header.split(b" ")
    if separator != b"\t" or len(fields) != 3 or fields[1] != b"blob":
        _fail(code, f"Git tree entry is not a blob for {path}")
    try:
        mode = fields[0].decode("ascii")
        object_id = fields[2].decode("ascii")
        decoded_path = entry_path.decode("utf-8")
    except UnicodeDecodeError:
        _fail(code, "Git tree entry is not canonical text")
    if decoded_path != path:
        _fail(code, "Git tree path differs from requested source path")
    return mode, _require_git_object(object_id, code, "tree blob ID")


def _authenticate_plan_blob(
    descriptor: dict[str, Any],
    repo: str,
    common: str,
    supplied_plan_path: str,
) -> tuple[str, bytes, dict[str, Any]]:
    code = "COMMITTED_PLAN"
    commit = descriptor["execution_source_sha"]
    plan_rel = descriptor["plan_path"]
    expected_path = os.path.join(repo, plan_rel)
    supplied = _require_absolute_normal_path(
        supplied_plan_path, code, "supplied plan path"
    )
    if supplied != expected_path:
        _fail(code, "supplied plan path differs from descriptor-bound plan path")
    object_id = _git_blob_id(descriptor, common, commit, plan_rel, code)
    if object_id != descriptor["plan_blob_id"]:
        _fail(code, "resolved plan blob ID differs from descriptor")
    committed = _git_blob(descriptor, common, object_id, code)
    if len(committed) != descriptor["plan_blob_length"]:
        _fail(code, "committed plan blob length differs from descriptor")
    if _sha256(committed) != descriptor["plan_blob_sha256"]:
        _fail(code, "committed plan blob SHA-256 differs from descriptor")
    _event("committed_plan_authenticated")
    checked_out, _ = _read_regular(
        supplied, code, max_bytes=MAX_PLAN_BYTES, require_nonwritable=False
    )
    if checked_out != committed:
        _fail(code, "checked-out plan bytes differ from committed plan blob")
    _event("working_copy_plan_authenticated")
    identity = {
        "path": plan_rel,
        "blob_id": object_id,
        "length": len(committed),
        "sha256": _sha256(committed),
    }
    return supplied, committed, identity


def _validate_hash_field(
    value: dict[str, Any], field: str, code: str, name: str
) -> str:
    expected = _require_sha256(value[field], code, f"{name}.{field}")
    observed = _sha256(_canonical_json(_without_hash(value, field)))
    if observed != expected:
        _fail(code, f"{name} hash mismatch")
    return expected


def _validate_source_record(
    descriptor: dict[str, Any],
    repo: str,
    common: str,
    record_value: Any,
    expected_role: str,
    *,
    require_working_copy: bool = True,
) -> tuple[dict[str, Any], bytes]:
    code = "SOURCE_IDENTITY"
    record = _require_mapping(record_value, code, f"{expected_role} source")
    _require_exact_keys(record, _SOURCE_KEYS, code, f"{expected_role} source")
    if record["role"] != expected_role:
        _fail(code, f"{expected_role} source role mismatch")
    path = _require_repo_relative_path(record["path"], code, f"{expected_role}.path")
    object_id = _require_git_object(record["blob_id"], code, f"{expected_role}.blob_id")
    mode = _require_string(record["git_mode"], code, f"{expected_role}.git_mode")
    length = _require_int(record["length"], code, f"{expected_role}.length")
    digest = _require_sha256(record["sha256"], code, f"{expected_role}.sha256")
    observed_mode, observed_id = _git_entry_mode_and_id(
        descriptor, common, descriptor["execution_source_sha"], path, code
    )
    if (observed_mode, observed_id) != (mode, object_id):
        _fail(code, f"{expected_role} Git tree identity mismatch")
    resolved_id = _git_blob_id(
        descriptor, common, descriptor["execution_source_sha"], path, code
    )
    if resolved_id != object_id:
        _fail(code, f"{expected_role} resolved blob ID mismatch")
    blob = _git_blob(descriptor, common, object_id, code)
    if len(blob) != length or _sha256(blob) != digest:
        _fail(code, f"{expected_role} committed bytes mismatch")
    if require_working_copy:
        working_path = os.path.join(repo, path)
        working, _ = _read_regular(
            working_path, code, max_bytes=MAX_SOURCE_BYTES, require_nonwritable=False
        )
        if working != blob:
            _fail(code, f"{expected_role} checked-out bytes differ from Git blob")
    return record, blob


def _normalize_fetch_remote(value: str) -> str:
    code = "REPOSITORY_IDENTITY"
    remote = _require_string(value, code, "fetch remote URL")
    host: str
    port: int | None
    path: str
    if "://" in remote:
        scheme, _, rest = remote.partition("://")
        scheme = scheme.lower()
        if scheme not in {"https", "ssh"}:
            _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
        if "?" in rest or "#" in rest:
            _fail(code, "fetch remote may not contain query or fragment")
        if "/" in rest:
            authority, _, path_part = rest.partition("/")
            path = "/" + path_part
        else:
            authority, path = rest, ""
        if "@" in authority:
            _, _, authority = authority.rpartition("@")
        if not authority:
            _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
        if authority.startswith("["):
            end = authority.find("]")
            if end == -1:
                _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
            host = authority[1:end]
            remainder = authority[end + 1 :]
            if remainder.startswith(":"):
                port_text = remainder[1:]
            elif remainder == "":
                port_text = ""
            else:
                _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
        elif ":" in authority:
            host, _, port_text = authority.partition(":")
        else:
            host, port_text = authority, ""
        if not host:
            _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
        host = host.lower()
        if port_text:
            if not port_text.isdigit() or int(port_text) > 65535:
                _fail(code, "fetch remote port is invalid")
            port = int(port_text)
        else:
            port = None
        default_port = 443 if scheme == "https" else 22
        if port == default_port:
            port = None
    else:
        match = re.fullmatch(r"(?:[^/@:\s]+@)?([^/@:\s]+):(.+)", remote)
        if match is None:
            _fail(code, "fetch remote must use HTTPS, ssh://, or scp-like SSH")
        host = match.group(1).lower()
        port = None
        path = match.group(2)
    normalized_path = path.strip("/")
    normalized_path = normalized_path.removesuffix(".git")
    if not normalized_path or any(
        part in {"", ".", ".."} for part in normalized_path.split("/")
    ):
        _fail(code, "fetch remote repository path is not canonical")
    authority = host if port is None else f"{host}:{port}"
    return f"{authority}/{normalized_path}"


def _validate_remote_repository_identity(
    descriptor: dict[str, Any], repo: str, identity: dict[str, Any]
) -> None:
    code = "REPOSITORY_IDENTITY"
    expected = _require_string(
        identity["expected_fetch_remote"], code, "expected fetch remote"
    )
    if re.fullmatch(
        r"[a-z0-9.-]+(?::[1-9][0-9]{0,4})?/.+", expected
    ) is None or expected.endswith(".git"):
        _fail(code, "expected fetch remote is not canonical host[:port]/path")
    remote_name = identity["remote_name"]
    if remote_name is not None and (
        not isinstance(remote_name, str)
        or not remote_name
        or re.fullmatch(r"[A-Za-z0-9._-]+", remote_name) is None
    ):
        _fail(code, "remote_name must be a canonical string or null")
    if remote_name is None:
        output = _run_git(descriptor, ("-C", repo, "remote"), code).stdout
        try:
            names = [line for line in output.decode("utf-8").splitlines() if line]
        except UnicodeDecodeError:
            _fail(code, "configured Git remote names are not UTF-8")
    else:
        names = [remote_name]
    observed: list[str] = []
    for name in names:
        result = _run_git(
            descriptor,
            ("-C", repo, "remote", "get-url", "--all", name),
            code,
            allow_exit={0, 2},
        )
        if result.returncode != 0:
            continue
        try:
            urls = [line for line in result.stdout.decode("utf-8").splitlines() if line]
        except UnicodeDecodeError:
            _fail(code, "configured Git fetch URL is not UTF-8")
        observed.extend(_normalize_fetch_remote(url) for url in urls)
    if expected not in observed:
        _fail(code, f"no configured fetch URL matches expected remote: {expected}")


def _validate_repository_identity(
    descriptor: dict[str, Any],
    plan: dict[str, Any],
    common: str,
) -> None:
    code = "REPOSITORY_IDENTITY"
    identity = _require_mapping(plan.get("target_repo"), code, "plan.target_repo")
    if identity != descriptor["repository_identity"]:
        _fail(code, "plan and descriptor repository identities differ")
    mode = identity.get("identity_mode")
    if mode == "history_anchor":
        expected = {
            "vcs",
            "identity_mode",
            "plan_commit_sha",
            "plan_path",
            "plan_blob_sha256",
            "product_base_sha",
        }
        _require_exact_keys(identity, expected, code, "history-anchor identity")
        if identity["vcs"] != "git":
            _fail(code, "history-anchor VCS must be git")
        anchor = _require_full_git_sha(
            identity["plan_commit_sha"], code, "history anchor commit"
        )
        anchor_path = _require_repo_relative_path(
            identity["plan_path"], code, "history anchor path"
        )
        anchor_digest = _require_sha256(
            identity["plan_blob_sha256"], code, "history anchor blob SHA-256"
        )
        product_base = _require_full_git_sha(
            identity["product_base_sha"], code, "history anchor product base"
        )
        if plan.get("product_base_sha") != product_base:
            _fail(code, "history-anchor and top-level product base differ")
        anchor_id = _git_blob_id(descriptor, common, anchor, anchor_path, code)
        if _sha256(_git_blob(descriptor, common, anchor_id, code)) != anchor_digest:
            _fail(code, "history anchor bytes mismatch")
        source = descriptor["execution_source_sha"]
        for older, newer, label in (
            (product_base, anchor, "product base -> history anchor"),
            (anchor, source, "history anchor -> execution source"),
            (product_base, source, "product base -> execution source"),
        ):
            result = _run_git(
                descriptor,
                ("--git-dir", common, "merge-base", "--is-ancestor", older, newer),
                code,
                allow_exit={0, 1},
            )
            if result.returncode != 0:
                _fail(code, f"required ancestry is false: {label}")
    elif mode == "remote":
        _require_exact_keys(
            identity,
            {"vcs", "identity_mode", "expected_fetch_remote", "remote_name"},
            code,
            "remote repository identity",
        )
        if identity["vcs"] != "git":
            _fail(code, "remote repository VCS must be git")
        _validate_remote_repository_identity(
            descriptor, descriptor["target_repo"]["path"], identity
        )
    else:
        _fail(code, "unsupported repository identity mode")


def _validate_launcher_binding(
    descriptor: dict[str, Any],
    descriptor_path: str,
    descriptor_hash: str,
    repo: str,
    common: str,
    binding_value: Any,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    code = "LAUNCHER_BINDING"
    binding = _require_mapping(binding_value, code, "trusted launcher binding")
    _require_exact_keys(
        binding, _LAUNCHER_BINDING_KEYS, code, "trusted launcher binding"
    )
    if binding["schema_version"] != LAUNCHER_BINDING_SCHEMA:
        _fail(code, "trusted launcher binding schema mismatch")
    if binding["bootstrap_cli_schema_version"] != BOOTSTRAP_CLI_SCHEMA:
        _fail(code, "bootstrap CLI schema mismatch")
    if binding["launch_descriptor_schema_version"] != DESCRIPTOR_SCHEMA:
        _fail(code, "launch descriptor schema binding mismatch")
    if binding["launch_descriptor_path_input"] != "launch_descriptor_path":
        _fail(code, "launch descriptor path input name mismatch")
    if binding["launch_descriptor_sha256_input"] != "launch_descriptor_sha256":
        _fail(code, "launch descriptor hash input name mismatch")
    _validate_hash_field(binding, "binding_sha256", code, "launcher binding")
    source, source_bytes = _validate_source_record(
        descriptor, repo, common, binding["source"], "bootstrap"
    )
    launcher_path = _current_launcher_path()
    external_path = _require_absolute_normal_path(
        binding["external_path"], code, "external launcher path"
    )
    if external_path != launcher_path or binding["external_realpath"] != launcher_path:
        _fail(code, "external launcher path differs from current launcher")
    external_bytes, external_stat = _read_regular(
        launcher_path,
        code,
        max_bytes=MAX_SOURCE_BYTES,
        require_nonwritable=True,
    )
    if (
        binding["external_mode"] != stat.S_IMODE(external_stat.st_mode)
        or binding["external_length"] != len(external_bytes)
        or binding["external_sha256"] != _sha256(external_bytes)
        or external_bytes != source_bytes
    ):
        _fail(code, "external launcher bytes or permissions mismatch")
    equalities = (
        (
            binding["trusted_launcher_argv_prefix_sha256"],
            descriptor["trusted_launcher_prefix_sha256"],
            "launcher prefix",
        ),
        (
            binding["trusted_git_argv_prefix"],
            descriptor["trusted_git_argv_prefix"],
            "Git prefix",
        ),
        (
            binding["trusted_git_prefix_sha256"],
            descriptor["trusted_git_prefix_sha256"],
            "Git prefix hash",
        ),
        (
            binding["trusted_git_identity"],
            descriptor["trusted_git_identity"],
            "Git identity",
        ),
        (
            binding["trusted_interpreter_or_executable_argv_prefix"],
            descriptor["trusted_interpreter_or_executable_argv_prefix"],
            "interpreter prefix",
        ),
        (
            binding["trusted_interpreter_or_executable_prefix_sha256"],
            descriptor["trusted_interpreter_or_executable_prefix_sha256"],
            "interpreter prefix hash",
        ),
        (
            binding["trusted_interpreter_or_executable_identity"],
            descriptor["trusted_interpreter_or_executable_identity"],
            "interpreter identity",
        ),
        (
            binding["closed_environment_sha256"],
            descriptor["closed_environment"]["environment_sha256"],
            "closed environment",
        ),
    )
    for observed, expected, label in equalities:
        if observed != expected:
            _fail(code, f"plan/descriptor {label} mismatch")
    expected_commands = list(_COMMAND_SCHEMAS)
    if binding["supported_subcommands"] != expected_commands:
        _fail(code, "supported bootstrap subcommands mismatch")
    expected_suffixes = {
        name: list(options) for name, options in _COMMAND_SCHEMAS.items()
    }
    if binding["subcommand_suffixes"] != expected_suffixes:
        _fail(code, "bootstrap suffix schemas mismatch")
    if binding["system_call_allowlist"] != [
        "open",
        "lstat",
        "realpath",
        "fsync",
        "chmod",
        "renameat2-noreplace",
        "chdir",
        "execve",
    ]:
        _fail(code, "bootstrap system-call allowlist mismatch")
    if (
        binding["installation_evidence_schema"]
        != "goal-plan.trusted-launcher-installation/v2"
        or binding["self_check_evidence_schema"] != SELF_CHECK_SCHEMA
        or binding["per_invocation_validation"] != "complete"
    ):
        _fail(code, "trusted launcher evidence/validation contract mismatch")
    if descriptor_path != os.path.join(
        os.path.dirname(descriptor_path), "launch_descriptor.json"
    ):
        _fail(code, "descriptor canonical location changed")
    if descriptor_hash != descriptor["descriptor_sha256"]:
        _fail(code, "descriptor observed hash differs from embedded hash")
    return binding, source, source_bytes


def _validate_runtime_definition(
    descriptor: dict[str, Any],
    repo: str,
    common: str,
    value: Any,
    *,
    require_working_copy: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, bytes]]:
    code = "RUNTIME_DEFINITION"
    definition = _require_mapping(value, code, "trusted runtime definition")
    _require_exact_keys(
        definition, _RUNTIME_DEFINITION_KEYS, code, "trusted runtime definition"
    )
    if definition["schema_version"] != RUNTIME_DEFINITION_SCHEMA:
        _fail(code, "trusted runtime definition schema mismatch")
    if (
        definition["runtime_bundle_hash_policy"]
        != "canonical-v1-exact-git-blobs-and-identities"
    ):
        _fail(code, "runtime bundle hash policy mismatch")
    _require_sha256(
        definition["runtime_suffix_schema_sha256"],
        code,
        "runtime suffix schema hash",
    )
    _require_sha256(
        definition["supervisor_suffix_schema_sha256"],
        code,
        "supervisor suffix schema hash",
    )
    _validate_hash_field(definition, "definition_sha256", code, "runtime definition")
    runtime, runtime_bytes = _validate_source_record(
        descriptor,
        repo,
        common,
        definition["runtime_source"],
        "runtime",
        require_working_copy=require_working_copy,
    )
    supervisor, supervisor_bytes = _validate_source_record(
        descriptor,
        repo,
        common,
        definition["supervisor_source"],
        "supervisor",
        require_working_copy=require_working_copy,
    )
    if runtime["path"] == supervisor["path"]:
        _fail(code, "runtime and supervisor source paths must differ")
    return (
        definition,
        [runtime, supervisor],
        {"runtime": runtime_bytes, "supervisor": supervisor_bytes},
    )


def _validate_plan(
    descriptor: dict[str, Any],
    descriptor_path: str,
    descriptor_hash: str,
    repo: str,
    common: str,
    plan: dict[str, Any],
    supplied_source_sha: str | None,
    *,
    require_runtime_working_copy: bool,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, bytes],
]:
    code = "PLAN_BINDING"
    required = {
        "schema_version",
        "plan_id",
        "target_repo",
        "product_base_sha",
        "execution_source",
        "trusted_launcher_argv_prefix",
        "trusted_launcher_binding",
        "trusted_runtime_definition",
        "trusted_runtime_binding_policy",
        "provider",
        "attractor_runner_argv_prefix",
        "attractor_runner_identity",
        "parent_runner_invocation",
        "approval_mode",
        "delivery_mode",
        "delivery_branch",
    }
    missing = sorted(required - set(plan))
    if missing:
        _fail(code, f"authenticated plan is missing required fields: {missing}")
    if plan["schema_version"] != PLAN_SCHEMA:
        _fail(code, "plan schema mismatch")
    plan_id = _require_string(plan["plan_id"], code, "plan_id")
    if SLUG_RE.fullmatch(plan_id) is None:
        _fail(code, "plan_id is not a slug")
    if plan["provider"] != descriptor["provider"]:
        _fail(code, "plan provider differs from descriptor")
    if (
        plan["trusted_launcher_argv_prefix"]
        != descriptor["trusted_launcher_argv_prefix"]
    ):
        _fail(code, "plan launcher prefix differs from descriptor")
    execution_source = _require_mapping(
        plan["execution_source"], code, "execution_source"
    )
    if execution_source != {
        "mode": "containing_commit",
        "sha_input": "execution_source_sha",
    }:
        _fail(code, "execution-source symbolic binding mismatch")
    if supplied_source_sha is not None:
        supplied = _require_full_git_sha(
            supplied_source_sha, code, "supplied execution_source_sha"
        )
        if supplied != descriptor["execution_source_sha"]:
            _fail(code, "supplied execution source differs from descriptor")
    _require_full_git_sha(plan["product_base_sha"], code, "product_base_sha")
    _validate_repository_identity(descriptor, plan, common)
    launcher, _, launcher_bytes = _validate_launcher_binding(
        descriptor,
        descriptor_path,
        descriptor_hash,
        repo,
        common,
        plan["trusted_launcher_binding"],
    )
    definition, sources, source_bytes = _validate_runtime_definition(
        descriptor,
        repo,
        common,
        plan["trusted_runtime_definition"],
        require_working_copy=require_runtime_working_copy,
    )
    if plan["trusted_runtime_binding_policy"] != _RUNTIME_BINDING_POLICY:
        _fail(code, "trusted runtime binding policy mismatch")
    source_bytes["bootstrap"] = launcher_bytes
    return launcher, definition, sources, source_bytes


def _authenticate(
    descriptor_path_value: str,
    plan_path_value: str | None,
    *,
    supplied_target_repo: str | None = None,
    supplied_source_sha: str | None = None,
    require_runtime_working_copy: bool = True,
) -> Authenticated:
    descriptor_path, descriptor_bytes, descriptor, descriptor_hash = _load_descriptor(
        descriptor_path_value
    )
    _authenticate_launcher(descriptor)
    _authenticate_dependencies(descriptor)
    repo, common = _validate_repo_from_descriptor(descriptor, descriptor_path)
    if supplied_target_repo is not None:
        supplied_repo = _require_absolute_normal_path(
            supplied_target_repo, "TARGET_REPOSITORY", "supplied target repository"
        )
        if supplied_repo != repo:
            _fail(
                "TARGET_REPOSITORY",
                "supplied target repository differs from descriptor",
            )
    expected_plan_path = os.path.join(repo, descriptor["plan_path"])
    plan_path, plan_bytes, plan_blob_identity = _authenticate_plan_blob(
        descriptor,
        repo,
        common,
        expected_plan_path if plan_path_value is None else plan_path_value,
    )
    _event("plan_parsed")
    parsed = _parse_canonical_json(plan_bytes, "AUTHENTICATED_PLAN", "plan")
    plan = _require_mapping(parsed, "AUTHENTICATED_PLAN", "plan")
    _event("plan_trust_consulted")
    launcher, definition, sources, source_bytes = _validate_plan(
        descriptor,
        descriptor_path,
        descriptor_hash,
        repo,
        common,
        plan,
        supplied_source_sha,
        require_runtime_working_copy=require_runtime_working_copy,
    )
    return Authenticated(
        descriptor_path=descriptor_path,
        descriptor_bytes=descriptor_bytes,
        descriptor=descriptor,
        descriptor_sha256=descriptor_hash,
        target_repo=repo,
        git_common_dir=common,
        plan_path=plan_path,
        plan_bytes=plan_bytes,
        plan=plan,
        plan_blob_identity=plan_blob_identity,
        launcher_binding=launcher,
        runtime_definition=definition,
        runtime_sources=sources,
        source_bytes=source_bytes,
    )


def _mkdir_chain(path: str, code: str) -> None:
    path = _require_absolute_normal_path(path, code, "directory")
    current = os.path.sep
    for part in [item for item in path.split(os.path.sep) if item]:
        current = os.path.join(current, part)
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
            except FileExistsError:
                metadata = os.lstat(current)
            else:
                metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            _fail(code, f"unsafe directory component: {current}")


def _fsync_directory(path: str, code: str) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        _fail(code, f"cannot open directory for fsync: {path}: {exc.errno}")
    try:
        os.fsync(descriptor)
    except OSError as exc:
        _fail(code, f"cannot fsync directory: {path}: {exc.errno}")
    finally:
        os.close(descriptor)


def _fsync_regular(path: str, code: str) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        _fail(code, f"cannot open file for fsync: {path}: {exc.errno}")
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            _fail(code, f"fsync target is not a regular file: {path}")
        os.fsync(descriptor)
    except OSError as exc:
        _fail(code, f"cannot fsync file: {path}: {exc.errno}")
    finally:
        os.close(descriptor)


def _write_exclusive(path: str, data: bytes, mode: int, code: str) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as exc:
        _fail(code, f"exclusive file creation failed: {path}: {exc.errno}")
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                _fail(code, f"short write while creating: {path}")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: str, destination: str, code: str) -> bool:
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        _fail(code, "Linux renameat2 is unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result == 0:
        return True
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        return False
    _fail(code, f"renameat2(RENAME_NOREPLACE) failed: errno={error_number}")


def _remove_staging(path: str) -> None:
    try:
        os.chmod(path, 0o700)
    except FileNotFoundError:
        return
    for name in os.listdir(path):
        file_path = os.path.join(path, name)
        try:
            os.chmod(file_path, 0o600)
        except FileNotFoundError:
            continue
        os.unlink(file_path)
    os.rmdir(path)


def _atomic_write_no_replace(
    destination: str, data: bytes, *, file_mode: int, code: str
) -> None:
    parent = os.path.dirname(destination)
    _mkdir_chain(parent, code)
    descriptor, temporary = tempfile.mkstemp(prefix=".bootstrap-", dir=parent)
    os.close(descriptor)
    os.unlink(temporary)
    try:
        _write_exclusive(temporary, data, 0o600, code)
        os.chmod(temporary, file_mode)
        _fsync_regular(temporary, code)
        reread, _ = _read_regular(
            temporary,
            code,
            max_bytes=max(len(data), 1),
            expected_mode=file_mode,
        )
        if reread != data:
            _fail(code, "atomic output temporary reread mismatch")
        if not _rename_noreplace(temporary, destination, code):
            _fail(code, f"output already exists: {destination}")
        _fsync_directory(parent, code)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _runtime_bundle_hash(auth: Authenticated) -> str:
    definition = auth.runtime_definition
    material = {
        "runtime_definition_schema": definition["schema_version"],
        "execution_source_sha": auth.descriptor["execution_source_sha"],
        "source_blobs": auth.runtime_sources,
        "trusted_interpreter_identity": auth.descriptor[
            "trusted_interpreter_or_executable_identity"
        ],
        "launch_descriptor_sha256": auth.descriptor_sha256,
        "plan_blob_identity": auth.plan_blob_identity,
        "trusted_launcher_binding_sha256": auth.launcher_binding["binding_sha256"],
        "runtime_suffix_schema_sha256": definition["runtime_suffix_schema_sha256"],
        "supervisor_suffix_schema_sha256": definition[
            "supervisor_suffix_schema_sha256"
        ],
    }
    return _hash_object(material)


def _prepare_state_paths(
    auth: Authenticated, state_root_value: str, binding_value: str
) -> tuple[str, str, str, str]:
    code = "STATE_ROOT"
    state_root = _require_absolute_normal_path(state_root_value, code, "state root")
    binding = _require_absolute_normal_path(binding_value, code, "binding path")
    _assert_no_symlink_components(state_root, code, allow_missing=True)
    if os.path.exists(state_root) and os.path.realpath(state_root) != state_root:
        _fail(code, "state root is not canonical")
    launch_root = os.path.dirname(auth.descriptor_path)
    launcher = _current_launcher_path()
    for protected, label in (
        (auth.target_repo, "state root and target repository"),
        (auth.git_common_dir, "state root and Git common directory"),
        (launch_root, "state root and launch-control root"),
        (launcher, "state root and trusted launcher"),
    ):
        _require_disjoint(state_root, protected, code, label)
    bundle_hash = _runtime_bundle_hash(auth)
    trusted_root = os.path.join(state_root, "trusted-runtime")
    bundle = os.path.join(trusted_root, bundle_hash)
    expected_binding = os.path.join(bundle, "trusted-runtime-binding.json")
    if binding != expected_binding:
        _fail(code, "binding path differs from the derived bundle path")
    _assert_no_symlink_components(binding, code, allow_missing=True)
    return state_root, trusted_root, bundle, binding


def _external_file_record(
    role: str, path: str, source: dict[str, Any]
) -> dict[str, Any]:
    return {
        "role": role,
        "path": path,
        "realpath": path,
        "mode": 0o444,
        "uid": os.geteuid(),
        "gid": os.getegid(),
        "length": source["length"],
        "sha256": source["sha256"],
    }


def _build_runtime_binding(
    auth: Authenticated,
    bundle_hash: str,
    bundle: str,
    *,
    created_at: str,
) -> dict[str, Any]:
    runtime_path = os.path.join(bundle, "goal_plan_runtime.py")
    supervisor_path = os.path.join(bundle, "goal_plan_supervisor.py")
    interpreter = auth.descriptor["trusted_interpreter_or_executable_argv_prefix"][0]
    runtime_prefix = [interpreter, runtime_path]
    supervisor_prefix = [interpreter, supervisor_path]
    external_files = [
        _external_file_record("runtime", runtime_path, auth.runtime_sources[0]),
        _external_file_record("supervisor", supervisor_path, auth.runtime_sources[1]),
    ]
    commands = [
        {
            "operation": "git-cat-file-to-sealed-file",
            "role": source["role"],
            "blob_id": source["blob_id"],
            "destination": external["path"],
            "write_mode": "0600",
            "seal_mode": "0444",
            "expected_length": source["length"],
            "expected_sha256": source["sha256"],
            "final_reread_length": source["length"],
            "final_reread_sha256": source["sha256"],
        }
        for source, external in zip(auth.runtime_sources, external_files)
    ]
    commands.append(
        {
            "operation": "renameat2-noreplace-and-fsync",
            "destination": bundle,
            "bundle_mode": "0555",
        }
    )
    binding: dict[str, Any] = {
        "schema_version": RUNTIME_BINDING_SCHEMA,
        "created_at": created_at,
        "launch_descriptor_path": auth.descriptor_path,
        "launch_descriptor_sha256": auth.descriptor_sha256,
        "plan_blob_identity": auth.plan_blob_identity,
        "execution_source_sha": auth.descriptor["execution_source_sha"],
        "runtime_bundle_hash": bundle_hash,
        "trusted_runtime_definition_sha256": auth.runtime_definition[
            "definition_sha256"
        ],
        "trusted_launcher_argv_prefix": auth.descriptor["trusted_launcher_argv_prefix"],
        "trusted_launcher_argv_prefix_sha256": auth.descriptor[
            "trusted_launcher_prefix_sha256"
        ],
        "trusted_launcher_binding_sha256": auth.launcher_binding["binding_sha256"],
        "source_blobs": auth.runtime_sources,
        "external_files": external_files,
        "trusted_git_argv_prefix": auth.descriptor["trusted_git_argv_prefix"],
        "trusted_git_prefix_sha256": auth.descriptor["trusted_git_prefix_sha256"],
        "trusted_git_identity": auth.descriptor["trusted_git_identity"],
        "trusted_interpreter_argv_prefix": auth.descriptor[
            "trusted_interpreter_or_executable_argv_prefix"
        ],
        "trusted_interpreter_prefix_sha256": auth.descriptor[
            "trusted_interpreter_or_executable_prefix_sha256"
        ],
        "trusted_interpreter_identity": auth.descriptor[
            "trusted_interpreter_or_executable_identity"
        ],
        "trusted_runtime_argv_prefix": runtime_prefix,
        "trusted_runtime_argv_prefix_sha256": _hash_object(runtime_prefix),
        "trusted_supervisor_argv_prefix": supervisor_prefix,
        "trusted_supervisor_argv_prefix_sha256": _hash_object(supervisor_prefix),
        "materialization_commands": commands,
    }
    binding["binding_sha256"] = _hash_object(binding)
    return binding


def _validate_runtime_binding(
    auth: Authenticated, bundle: str, binding_path: str
) -> dict[str, Any]:
    code = "RUNTIME_BUNDLE"
    _assert_no_symlink_components(bundle, code)
    bundle_metadata = os.lstat(bundle)
    if not stat.S_ISDIR(bundle_metadata.st_mode):
        _fail(code, "runtime bundle path is not a directory")
    if stat.S_IMODE(bundle_metadata.st_mode) != 0o555:
        _fail(code, "runtime bundle directory mode mismatch")
    binding_bytes, _ = _read_regular(
        binding_path,
        code,
        max_bytes=MAX_PLAN_BYTES,
        require_nonwritable=True,
        expected_mode=0o444,
    )
    binding_value = _parse_canonical_json(
        binding_bytes, code, "trusted runtime binding"
    )
    binding = _require_mapping(binding_value, code, "trusted runtime binding")
    _require_exact_keys(binding, _RUNTIME_BINDING_KEYS, code, "trusted runtime binding")
    if binding["schema_version"] != RUNTIME_BINDING_SCHEMA:
        _fail(code, "runtime binding schema mismatch")
    _validate_hash_field(binding, "binding_sha256", code, "runtime binding")
    bundle_hash = _runtime_bundle_hash(auth)
    expected_static = {
        "launch_descriptor_path": auth.descriptor_path,
        "launch_descriptor_sha256": auth.descriptor_sha256,
        "plan_blob_identity": auth.plan_blob_identity,
        "execution_source_sha": auth.descriptor["execution_source_sha"],
        "runtime_bundle_hash": bundle_hash,
        "trusted_runtime_definition_sha256": auth.runtime_definition[
            "definition_sha256"
        ],
        "trusted_launcher_argv_prefix": auth.descriptor["trusted_launcher_argv_prefix"],
        "trusted_launcher_argv_prefix_sha256": auth.descriptor[
            "trusted_launcher_prefix_sha256"
        ],
        "trusted_launcher_binding_sha256": auth.launcher_binding["binding_sha256"],
        "source_blobs": auth.runtime_sources,
        "trusted_git_argv_prefix": auth.descriptor["trusted_git_argv_prefix"],
        "trusted_git_prefix_sha256": auth.descriptor["trusted_git_prefix_sha256"],
        "trusted_git_identity": auth.descriptor["trusted_git_identity"],
        "trusted_interpreter_argv_prefix": auth.descriptor[
            "trusted_interpreter_or_executable_argv_prefix"
        ],
        "trusted_interpreter_prefix_sha256": auth.descriptor[
            "trusted_interpreter_or_executable_prefix_sha256"
        ],
        "trusted_interpreter_identity": auth.descriptor[
            "trusted_interpreter_or_executable_identity"
        ],
    }
    for field, expected in expected_static.items():
        if binding[field] != expected:
            _fail(code, f"runtime binding field mismatch: {field}")
    try:
        dt.datetime.fromisoformat(binding["created_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        _fail(code, "runtime binding created_at is not RFC 3339")
    runtime_path = os.path.join(bundle, "goal_plan_runtime.py")
    supervisor_path = os.path.join(bundle, "goal_plan_supervisor.py")
    expected_names = {
        "goal_plan_runtime.py",
        "goal_plan_supervisor.py",
        "trusted-runtime-binding.json",
    }
    if set(os.listdir(bundle)) != expected_names:
        _fail(code, "runtime bundle file set mismatch")
    observed_external: list[dict[str, Any]] = []
    for role, path, source in (
        ("runtime", runtime_path, auth.runtime_sources[0]),
        ("supervisor", supervisor_path, auth.runtime_sources[1]),
    ):
        data, metadata = _read_regular(
            path,
            code,
            max_bytes=MAX_SOURCE_BYTES,
            require_nonwritable=True,
            expected_mode=0o444,
        )
        if (
            len(data) != source["length"]
            or _sha256(data) != source["sha256"]
            or data != auth.source_bytes[role]
        ):
            _fail(code, f"sealed {role} bytes differ from exact Git blob")
        observed_external.append(
            {
                "role": role,
                "path": path,
                "realpath": os.path.realpath(path),
                "mode": stat.S_IMODE(metadata.st_mode),
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
                "length": len(data),
                "sha256": _sha256(data),
            }
        )
    if binding["external_files"] != observed_external:
        _fail(code, "runtime binding external-file identities mismatch")
    interpreter = auth.descriptor["trusted_interpreter_or_executable_argv_prefix"][0]
    runtime_prefix = [interpreter, runtime_path]
    supervisor_prefix = [interpreter, supervisor_path]
    for field, expected in (
        ("trusted_runtime_argv_prefix", runtime_prefix),
        ("trusted_runtime_argv_prefix_sha256", _hash_object(runtime_prefix)),
        ("trusted_supervisor_argv_prefix", supervisor_prefix),
        ("trusted_supervisor_argv_prefix_sha256", _hash_object(supervisor_prefix)),
    ):
        if binding[field] != expected:
            _fail(code, f"runtime binding prefix mismatch: {field}")
    expected_commands = _build_runtime_binding(
        auth, bundle_hash, bundle, created_at=binding["created_at"]
    )["materialization_commands"]
    if binding["materialization_commands"] != expected_commands:
        _fail(code, "runtime binding materialization observations mismatch")
    if _BUNDLE_VALIDATION_OBSERVER is not None:
        _BUNDLE_VALIDATION_OBSERVER(bundle)
    return binding


def _materialize(auth: Authenticated, state_root: str, binding: str) -> str:
    code = "MATERIALIZATION"
    _, trusted_root, bundle, binding_path = _prepare_state_paths(
        auth, state_root, binding
    )
    if os.path.lexists(bundle):
        _validate_runtime_binding(auth, bundle, binding_path)
        return _runtime_bundle_hash(auth)
    _mkdir_chain(trusted_root, code)
    _fsync_directory(os.path.dirname(trusted_root), code)
    _fsync_directory(trusted_root, code)
    trusted_metadata = os.lstat(trusted_root)
    if stat.S_IMODE(trusted_metadata.st_mode) & 0o022:
        _fail(code, "trusted-runtime root is group/other writable")
    staging = tempfile.mkdtemp(prefix=".staging-", dir=trusted_root)
    os.chmod(staging, 0o700)
    try:
        runtime_stage = os.path.join(staging, "goal_plan_runtime.py")
        supervisor_stage = os.path.join(staging, "goal_plan_supervisor.py")
        binding_stage = os.path.join(staging, "trusted-runtime-binding.json")
        _write_exclusive(runtime_stage, auth.source_bytes["runtime"], 0o600, code)
        _write_exclusive(supervisor_stage, auth.source_bytes["supervisor"], 0o600, code)
        bundle_hash = _runtime_bundle_hash(auth)
        created_at = (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        binding_value = _build_runtime_binding(
            auth, bundle_hash, bundle, created_at=created_at
        )
        _write_exclusive(
            binding_stage, _canonical_json(binding_value) + b"\n", 0o600, code
        )
        for path in (runtime_stage, supervisor_stage, binding_stage):
            os.chmod(path, 0o444)
            _fsync_regular(path, code)
            data, _ = _read_regular(
                path,
                code,
                max_bytes=MAX_SOURCE_BYTES,
                require_nonwritable=True,
                expected_mode=0o444,
            )
            if path == runtime_stage and data != auth.source_bytes["runtime"]:
                _fail(code, "staged runtime final reread mismatch")
            if path == supervisor_stage and data != auth.source_bytes["supervisor"]:
                _fail(code, "staged supervisor final reread mismatch")
        _fsync_directory(staging, code)
        os.chmod(staging, 0o555)
        _fsync_directory(staging, code)
        installed = _rename_noreplace(staging, bundle, code)
        if not installed:
            _remove_staging(staging)
            _validate_runtime_binding(auth, bundle, binding_path)
            return bundle_hash
        _fsync_directory(trusted_root, code)
        _validate_runtime_binding(auth, bundle, binding_path)
        return bundle_hash
    finally:
        if os.path.exists(staging):
            _remove_staging(staging)


def _write_self_check(auth: Authenticated, evidence_value: str) -> None:
    code = "SELF_CHECK_EVIDENCE"
    evidence = _require_absolute_normal_path(
        evidence_value, code, "self-check evidence"
    )
    launch_root = os.path.dirname(auth.descriptor_path)
    evidence_root = os.path.join(launch_root, "evidence")
    if not _path_contains(evidence_root, evidence) or evidence == evidence_root:
        _fail(code, "self-check evidence must be below launch-control evidence/")
    _assert_no_symlink_components(evidence, code, allow_missing=True)
    record: dict[str, Any] = {
        "schema_version": SELF_CHECK_SCHEMA,
        "status": "PASS",
        "launch_descriptor_path": auth.descriptor_path,
        "launch_descriptor_sha256": auth.descriptor_sha256,
        "plan_blob_identity": auth.plan_blob_identity,
        "trusted_launcher_binding_sha256": auth.launcher_binding["binding_sha256"],
        "execution_source_sha": auth.descriptor["execution_source_sha"],
    }
    record["record_sha256"] = _hash_object(record)
    _atomic_write_no_replace(
        evidence,
        _canonical_json(record) + b"\n",
        file_mode=0o444,
        code=code,
    )


def _validate_parent_invocation_definition(
    auth: Authenticated,
) -> tuple[dict[str, Any], list[str]]:
    code = "PARENT_INVOCATION"
    value = _require_mapping(
        auth.plan["parent_runner_invocation"], code, "parent runner invocation"
    )
    expected_keys = {
        "schema_version",
        "dot_source",
        "runner_cwd_arg",
        "logs_root_policy",
        "parameter_order",
        "definition_sha256",
    }
    _require_exact_keys(value, expected_keys, code, "parent runner invocation")
    if value["schema_version"] != PARENT_INVOCATION_SCHEMA:
        _fail(code, "parent runner invocation schema mismatch")
    if value["runner_cwd_arg"] != ".":
        _fail(code, "parent runner --cwd token must be literal '.'")
    if value["logs_root_policy"] != "state_root/parent-attractor-run":
        _fail(code, "parent logs-root policy mismatch")
    _validate_hash_field(value, "definition_sha256", code, "parent invocation")
    _, _ = _validate_source_record(
        auth.descriptor,
        auth.target_repo,
        auth.git_common_dir,
        value["dot_source"],
        "parent-dot",
    )
    parameter_order = _require_string_list(
        value["parameter_order"], code, "parent parameter order"
    )
    return value, parameter_order


def _validate_runner_prefix(value: Any) -> list[str]:
    code = "PARENT_INVOCATION"
    prefix = _require_string_list(value, code, "Attractor runner prefix")
    if len(prefix) == 1:
        _require_absolute_normal_path(prefix[0], code, "runner executable")
    elif len(prefix) == 3:
        _require_absolute_normal_path(prefix[0], code, "runner interpreter")
        if prefix[1:] != ["-m", "amplifier_module_pipeline_runner.cli"]:
            _fail(code, "Python module runner prefix mismatch")
    else:
        _fail(code, "Attractor runner prefix has an unsupported form")
    return prefix


def _split_parent_params(
    argv: list[str], start: int
) -> tuple[list[str], dict[str, str]]:
    code = "PARENT_ARGV"
    tokens = argv[start:]
    if len(tokens) % 2:
        _fail(code, "parent parameter suffix has an odd token count")
    names: list[str] = []
    values: dict[str, str] = {}
    for index in range(0, len(tokens), 2):
        if tokens[index] != "--param":
            _fail(code, "every parent parameter must be preceded by --param")
        assignment = tokens[index + 1]
        if "=" not in assignment:
            _fail(code, "parent parameter must use name=value")
        name, item = assignment.split("=", 1)
        if not name or not item or name in values:
            _fail(code, "parent parameter names and values must be unique/non-empty")
        names.append(name)
        values[name] = item
    return names, values


def _validate_parent_argv(
    auth: Authenticated,
    runtime_binding: dict[str, Any],
    binding_path: str,
    parent_argv: list[str],
) -> None:
    code = "PARENT_ARGV"
    invocation, parameter_order = _validate_parent_invocation_definition(auth)
    runner_prefix = _validate_runner_prefix(auth.plan["attractor_runner_argv_prefix"])
    state_root = os.path.dirname(os.path.dirname(os.path.dirname(binding_path)))
    dot_path = invocation["dot_source"]["path"]
    approval_mode = auth.plan["approval_mode"]
    delivery_mode = auth.plan["delivery_mode"]
    if approval_mode == "preapproved":
        human_gate = "fail"
        human_transport = "none"
    elif approval_mode == "required":
        human_gate = "console"
        human_transport = "console"
    else:
        _fail(code, "unsupported approval mode")
    fixed = runner_prefix + [
        "run",
        dot_path,
        "--provider",
        auth.plan["provider"],
        "--cwd",
        ".",
        "--logs-root",
        os.path.join(state_root, "parent-attractor-run"),
        "--on-human-gate",
        human_gate,
    ]
    if parent_argv[: len(fixed)] != fixed:
        _fail(code, "parent fixed argv prefix differs from compiled contract")
    names, values = _split_parent_params(parent_argv, len(fixed))
    if names != parameter_order:
        _fail(code, "parent parameter names/order differ from compiled contract")
    exact_values = {
        "target_repo": auth.target_repo,
        "execution_source_sha": auth.descriptor["execution_source_sha"],
        "state_root": state_root,
        "launch_descriptor_path": auth.descriptor_path,
        "launch_descriptor_sha256": auth.descriptor_sha256,
        "trusted_launcher_argv_prefix_sha256": auth.descriptor[
            "trusted_launcher_prefix_sha256"
        ],
        "trusted_launcher_binding_sha256": auth.launcher_binding["binding_sha256"],
        "runtime_bundle_hash": runtime_binding["runtime_bundle_hash"],
        "trusted_runtime_binding_path": binding_path,
        "approval_mode": approval_mode,
        "human_gate_transport": human_transport,
        "delivery_mode": delivery_mode,
        "delivery_branch": auth.plan["delivery_branch"],
    }
    for name, expected in exact_values.items():
        if values.get(name) != expected:
            _fail(code, f"parent parameter mismatch: {name}")
    run_id = values.get("run_id", "")
    if SLUG_RE.fullmatch(run_id) is None:
        _fail(code, "parent run_id is not a slug")
    worktree_root = _require_absolute_normal_path(
        values.get("worktree_root"), code, "parent worktree_root"
    )
    _assert_no_symlink_components(worktree_root, code, allow_missing=True)
    for protected, label in (
        (auth.target_repo, "worktree root and target repository"),
        (auth.git_common_dir, "worktree root and Git common directory"),
        (state_root, "worktree root and state root"),
        (os.path.dirname(auth.descriptor_path), "worktree and launch-control roots"),
    ):
        _require_disjoint(worktree_root, protected, code, label)
    if delivery_mode == "none":
        if "delivery_state_root" in values or "github_repo" in values:
            _fail(code, "delivery-disabled parent argv contains delivery-only values")
    elif delivery_mode == "pr":
        delivery_root = _require_absolute_normal_path(
            values.get("delivery_state_root"), code, "delivery_state_root"
        )
        _assert_no_symlink_components(delivery_root, code, allow_missing=True)
        for protected, label in (
            (auth.target_repo, "delivery root and target repository"),
            (auth.git_common_dir, "delivery root and Git common directory"),
            (state_root, "delivery root and state root"),
            (worktree_root, "delivery root and worktree root"),
            (
                os.path.dirname(auth.descriptor_path),
                "delivery and launch-control roots",
            ),
        ):
            _require_disjoint(delivery_root, protected, code, label)
        github_repo = values.get("github_repo", "")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repo) is None:
            _fail(code, "github_repo is not owner/repository")
    else:
        _fail(code, "unsupported delivery mode")
    branch = _require_string(auth.plan["delivery_branch"], code, "delivery branch")
    result = _run_git(
        auth.descriptor,
        ("check-ref-format", "--branch", branch),
        code,
        allow_exit={0, 1},
    )
    if result.returncode != 0:
        _fail(code, "compiled delivery branch is invalid")


def _load_parent_argv(path_value: str, state_root: str) -> list[str]:
    code = "PARENT_ARGV"
    path = _require_absolute_normal_path(path_value, code, "parent argv JSON")
    expected_root = os.path.join(state_root, "prelaunch")
    if not _path_contains(expected_root, path) or path == expected_root:
        _fail(code, "parent argv JSON must be below state_root/prelaunch")
    data, _ = _read_regular(
        path,
        code,
        max_bytes=MAX_PLAN_BYTES,
        require_nonwritable=True,
    )
    value = _parse_canonical_json(data, code, "parent argv JSON")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        _fail(code, "parent argv JSON must be a non-empty string array")
    return list(value)


def _launch_parent(
    descriptor_path: str,
    binding_path_value: str,
    target_repo_value: str,
    parent_argv_path: str,
) -> NoReturn:
    auth = _authenticate(
        descriptor_path,
        None,
        supplied_target_repo=target_repo_value,
    )
    _, _, bundle, binding_path = _prepare_state_paths(
        auth,
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    _require_absolute_normal_path(
                        binding_path_value, "RUNTIME_BUNDLE", "binding"
                    )
                )
            )
        ),
        binding_path_value,
    )
    runtime_binding = _validate_runtime_binding(auth, bundle, binding_path)
    state_root = os.path.dirname(os.path.dirname(os.path.dirname(binding_path)))
    parent_argv = _load_parent_argv(parent_argv_path, state_root)
    _validate_parent_argv(auth, runtime_binding, binding_path, parent_argv)
    canonical_target = os.path.realpath(auth.target_repo)
    if canonical_target != auth.target_repo:
        _fail("PARENT_HANDOFF", "target repository realpath changed")
    os.chdir(canonical_target)
    try:
        proc_cwd = os.path.realpath("/proc/self/cwd")
    except OSError as exc:
        _fail("PARENT_HANDOFF", f"cannot observe /proc/self/cwd: {exc.errno}")
    if (
        proc_cwd != canonical_target
        or os.path.realpath(os.getcwd()) != canonical_target
    ):
        _fail("PARENT_HANDOFF", "OS CWD does not equal canonical target repository")
    os.execve(parent_argv[0], parent_argv, dict(os.environ))
    _fail("PARENT_HANDOFF", "os.execve returned unexpectedly")


def _plan_path_from_descriptor(descriptor_path: str) -> str:
    path = _require_absolute_normal_path(
        descriptor_path, "DESCRIPTOR", "launch descriptor"
    )
    data, _ = _read_regular(
        path,
        "DESCRIPTOR",
        max_bytes=MAX_DESCRIPTOR_BYTES,
        require_nonwritable=True,
    )
    value = _parse_canonical_json(data, "DESCRIPTOR", "launch descriptor")
    descriptor = _require_mapping(value, "DESCRIPTOR", "descriptor")
    return os.path.join(descriptor["target_repo"]["path"], descriptor["plan_path"])


def run(command: ParsedCommand) -> int:
    values = command.values
    if command.name == "self-check":
        auth = _authenticate(
            values["--launch-descriptor"],
            values["--plan"],
        )
        _write_self_check(auth, values["--evidence"])
        print("TRUSTED_LAUNCHER_SELF_CHECK:PASS")
        return 0
    if command.name in {"materialize-runtime", "rehydrate-runtime"}:
        auth = _authenticate(
            values["--launch-descriptor"],
            values["--plan"],
            supplied_target_repo=values["--target-repo"],
            supplied_source_sha=values["--execution-source-sha"],
            require_runtime_working_copy=command.name == "materialize-runtime",
        )
        bundle_hash = _materialize(auth, values["--state-root"], values["--binding"])
        if command.name == "materialize-runtime":
            print(f"TRUSTED_RUNTIME_MATERIALIZED:{bundle_hash}")
        else:
            print(f"TRUSTED_RUNTIME_REHYDRATED:{bundle_hash}")
        return 0
    if command.name == "launch-parent":
        _launch_parent(
            values["--launch-descriptor"],
            values["--binding"],
            values["--target-repo"],
            values["--parent-argv-json"],
        )
    _fail("CLI_ARGUMENTS", "unreachable subcommand")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    command_name = arguments[0] if arguments else ""
    try:
        command = _parse_cli(arguments)
        return run(command)
    except BootstrapError as exc:
        token = (
            "RECOVERY_INFRASTRUCTURE_BLOCKED"
            if command_name == "rehydrate-runtime"
            else "PRELAUNCH_INFRASTRUCTURE_BLOCKED"
        )
        print(f"{token}: {exc.code}: {exc.message}", file=sys.stderr)
        return EXIT_CONFIGURATION


if __name__ == "__main__":
    raise SystemExit(main())
