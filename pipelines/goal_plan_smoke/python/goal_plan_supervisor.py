#!/usr/bin/env python3
"""Accountable per-child process supervisor for goal_plan lanes.

This module implements Wave 1 of the goal_plan_smoke pipeline family: one
long-lived "reaper" process per lane/correction/delivery child launch, plus
short-lived deterministic control clients (`poll`, `terminate`, `reconcile`)
that observe or signal it without ever trusting child self-reports as
completion evidence.

Design contract reference: docs/plans/2026-08-22-goal-plan-attractor-design.md,
section "Child launch and process-supervision contract". This file owns only
the supervisor; it does not implement the trusted bootstrap, parent runtime,
or budget ledger, which are separate lanes/waves.

Stdlib only. Linux only (schema version 1 explicitly scopes non-Linux out).
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

SCHEMA_CONTRACT = "goal-plan.process-launch-contract/v1"
SCHEMA_INTENT = "goal-plan.launch-intent/v1"
SCHEMA_LEDGER = "goal-plan.process-ledger/v1"
SCHEMA_ACK = "goal-plan.launch-ack/v1"
SCHEMA_RESULT = "goal-plan.supervisor-result/v1"
SCHEMA_POLL = "goal-plan.supervisor-poll/v1"
SCHEMA_TERMINATION = "goal-plan.supervisor-termination/v1"
SCHEMA_RECONCILIATION = "goal-plan.supervisor-reconciliation/v1"
SCHEMA_TERMINATE_REQUEST = "goal-plan.termination-request/v1"
SCHEMA_SELF_CHECK = "goal-plan.supervisor-self-check/v1"
IDENTITY_POLICY = "goal-plan.linux-procfs-identity/v1"

TERMINATION_REASONS = {
    "global_deadline",
    "child_wall_timeout",
    "child_cancelled",
    "parent_aborted",
    "recovery_cleanup",
}

ENV_PROCESS_RUN_ID = "GOAL_PLAN_PROCESS_RUN_ID"

_CONTRACT_KEYS = {
    "schema_version",
    "process_kind",
    "process_id",
    "process_run_id",
    "child_argv",
    "child_cwd",
    "child_env",
    "wall_timeout_seconds",
    "term_grace_seconds",
    "stdout_path",
    "stderr_path",
}


class SupervisorError(RuntimeError):
    """A deterministic, fail-closed supervisor error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Canonical JSON / atomic durable writes
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _read_json(path: str) -> tuple[dict[str, Any], bytes]:
    data = _read_bytes(path)
    return json.loads(data.decode("utf-8")), data


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_json(path: str, value: dict[str, Any]) -> bytes:
    """Write JSON atomically: temp file in same dir, fsync, rename, fsync dir."""
    data = _canonical_json(value)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".goal-plan-sup-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        _fsync_dir(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return data


def _terminate_request_path(result_path: str) -> str:
    return result_path + ".terminate-request.json"


# ---------------------------------------------------------------------------
# Canonical Linux process identity (boot_id:pid:starttime_ticks + verification)
# ---------------------------------------------------------------------------


def _boot_id() -> str:
    with open("/proc/sys/kernel/random/boot_id", "r", encoding="ascii") as fh:
        return fh.read().strip()


def _proc_stat_starttime(pid: int) -> int:
    with open(f"/proc/{pid}/stat", "rb") as fh:
        data = fh.read()
    # comm field is "(name)" and may itself contain spaces/parens; the last
    # ")" unambiguously ends it per the procfs format.
    idx = data.rfind(b")")
    if idx == -1:
        raise SupervisorError("IDENTITY", f"unparseable /proc/{pid}/stat")
    rest = data[idx + 2 :].split()
    # rest[0] is field 3 (state); field 22 (starttime) is offset 22-3=19.
    if len(rest) <= 19:
        raise SupervisorError("IDENTITY", f"/proc/{pid}/stat too short")
    return int(rest[19])


def _proc_cmdline_hash(pid: int) -> str:
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        return _sha256(fh.read())


def _proc_exe_realpath(pid: int) -> str:
    return os.path.realpath(f"/proc/{pid}/exe")


def _proc_pgid(pid: int) -> int:
    return os.getpgid(pid)


def identity_for(pid: int, retries: int = 40, delay: float = 0.02) -> dict[str, Any]:
    """Read the canonical identity of a live pid, retrying briefly.

    A brief retry window absorbs the small race between `Popen` returning a
    pid and the child completing `execve`, without ever trusting a pid whose
    procfs entries cannot be read at all.
    """
    last_exc: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            return {
                "boot_id": _boot_id(),
                "pid": pid,
                "starttime_ticks": _proc_stat_starttime(pid),
                "cmdline_sha256": _proc_cmdline_hash(pid),
                "pgid": _proc_pgid(pid),
                "exe_realpath": _proc_exe_realpath(pid),
            }
        except (FileNotFoundError, ProcessLookupError, OSError) as exc:
            last_exc = exc
            time.sleep(delay)
    raise SupervisorError("IDENTITY", f"cannot read identity for pid {pid}: {last_exc}")


def identity_token(identity: dict[str, Any]) -> str:
    return (
        f"linux:{identity['boot_id']}:{identity['pid']}:{identity['starttime_ticks']}"
    )


def identity_alive_and_matches(identity: dict[str, Any]) -> bool:
    """Reread procfs for the recorded pid and require an exact identity match.

    This is the sole basis for treating a recorded pid as "the same process
    we recorded" rather than a reused, unrelated pid (stale-PID safety).
    """
    pid = identity.get("pid")
    if not isinstance(pid, int):
        return False
    try:
        current = {
            "boot_id": _boot_id(),
            "pid": pid,
            "starttime_ticks": _proc_stat_starttime(pid),
            "cmdline_sha256": _proc_cmdline_hash(pid),
            "pgid": _proc_pgid(pid),
            "exe_realpath": _proc_exe_realpath(pid),
        }
    except (FileNotFoundError, ProcessLookupError, OSError):
        return False
    return current == identity


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_group(pgid: int, grace_seconds: float) -> None:
    """TERM the whole process group, wait up to grace, then KILL it."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        if not _group_alive(pgid):
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    # bounded wait for the kernel to finish tearing down the group
    kill_deadline = time.monotonic() + 2.0
    while time.monotonic() < kill_deadline and _group_alive(pgid):
        time.sleep(0.05)


def _scan_proc_for_process_run_id(
    process_run_id: str, *, max_passes: int, interval: float, timeout: float
) -> int | None:
    """Bounded /proc scan for a live process carrying our process_run_id.

    Used only for pre-ledger recovery (intent existed, ledger never appeared)
    or to locate an orphaned child after its supervisor vanished mid-flight.
    """
    needle = f"{ENV_PROCESS_RUN_ID}={process_run_id}".encode()
    deadline = time.monotonic() + max(0.0, timeout)
    passes = 0
    while passes < max_passes:
        try:
            entries = os.listdir("/proc")
        except OSError:
            entries = []
        for entry in entries:
            if not entry.isdigit():
                continue
            pid = int(entry)
            try:
                with open(f"/proc/{pid}/environ", "rb") as fh:
                    environ = fh.read()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            if needle in environ.split(b"\x00"):
                return pid
        passes += 1
        if passes >= max_passes or time.monotonic() >= deadline:
            break
        time.sleep(max(0.0, interval))
    return None


# ---------------------------------------------------------------------------
# Contract / intent loading and validation
# ---------------------------------------------------------------------------


def _load_contract(path: str) -> tuple[dict[str, Any], bytes]:
    contract, raw = _read_json(path)
    if contract.get("schema_version") != SCHEMA_CONTRACT:
        raise SupervisorError("CONTRACT", "contract schema mismatch")
    if set(contract) != _CONTRACT_KEYS:
        missing = sorted(_CONTRACT_KEYS - set(contract))
        unknown = sorted(set(contract) - _CONTRACT_KEYS)
        raise SupervisorError(
            "CONTRACT", f"contract fields differ; missing={missing} unknown={unknown}"
        )
    if not isinstance(contract["child_argv"], list) or not contract["child_argv"]:
        raise SupervisorError("CONTRACT", "child_argv must be a non-empty list")
    return contract, raw


def _load_intent(path: str, contract_bytes: bytes) -> dict[str, Any]:
    intent, _raw = _read_json(path)
    if intent.get("schema_version") != SCHEMA_INTENT:
        raise SupervisorError("INTENT", "intent schema mismatch")
    if intent.get("contract_sha256") != _sha256(contract_bytes):
        raise SupervisorError("INTENT", "intent contract hash mismatch")
    return intent


def _load_common(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    contract, contract_bytes = _load_contract(args.contract)
    intent = _load_intent(args.intent, contract_bytes)
    if intent.get("process_run_id") != contract.get("process_run_id"):
        raise SupervisorError("INTENT", "intent/contract process_run_id mismatch")
    return contract, contract_bytes, intent


# ---------------------------------------------------------------------------
# `run`: the accountable long-lived reaper
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    contract, contract_bytes, _intent = _load_common(args)
    process_run_id = contract["process_run_id"]

    # A SIGTERM from `terminate` must not kill the reaper itself before it can
    # clean up its child and write the authoritative result; the actual
    # termination reason travels via the durable request file below.
    signal.signal(signal.SIGTERM, lambda *_a: None)

    supervisor_identity = identity_for(os.getpid())
    intent_bytes = _read_bytes(args.intent)
    ledger: dict[str, Any] = {
        "schema_version": SCHEMA_LEDGER,
        "process_run_id": process_run_id,
        "intent_sha256": _sha256(intent_bytes),
        "contract_sha256": _sha256(contract_bytes),
        "identity_policy": IDENTITY_POLICY,
        "supervisor_identity": supervisor_identity,
        "child_identity": None,
        "state": "SUPERVISOR_STARTED",
    }
    _atomic_write_json(args.ledger, ledger)

    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in contract["child_env"].items()})
    env[ENV_PROCESS_RUN_ID] = process_run_id

    stdout_path = contract["stdout_path"]
    stderr_path = contract["stderr_path"]
    os.makedirs(os.path.dirname(os.path.abspath(stdout_path)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(stderr_path)) or ".", exist_ok=True)

    with open(stdout_path, "wb") as stdout_f, open(stderr_path, "wb") as stderr_f:
        proc = subprocess.Popen(
            contract["child_argv"],
            cwd=contract["child_cwd"],
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            start_new_session=True,
        )
        child_pid = proc.pid

        try:
            child_identity = identity_for(child_pid)
        except SupervisorError:
            # Child ended (or never truly started) before we could observe
            # it; still reap it below so we never leave a zombie.
            child_identity = {
                "boot_id": supervisor_identity["boot_id"],
                "pid": child_pid,
                "starttime_ticks": -1,
                "cmdline_sha256": "",
                "pgid": child_pid,
                "exe_realpath": "",
            }

        ledger["child_identity"] = child_identity
        ledger["state"] = "CHILD_STARTED"
        ledger_bytes = _atomic_write_json(args.ledger, ledger)

        ack = {
            "schema_version": SCHEMA_ACK,
            "process_run_id": process_run_id,
            "ledger_sha256": _sha256(ledger_bytes),
            "supervisor_identity": supervisor_identity,
            "child_identity": child_identity,
        }
        _atomic_write_json(args.ack, ack)

        terminate_request_path = _terminate_request_path(args.result)
        wall_timeout = float(contract["wall_timeout_seconds"])
        grace = float(contract["term_grace_seconds"])
        start = time.monotonic()
        timed_out = False
        cancellation_reason: str | None = None
        termination_initiated = False
        raw_status: int | None = None

        while True:
            try:
                wpid, status = os.waitpid(child_pid, os.WNOHANG)
            except ChildProcessError:
                wpid, status = child_pid, 0
            if wpid == child_pid:
                raw_status = status
                break
            if not termination_initiated:
                if os.path.exists(terminate_request_path):
                    try:
                        request, _ = _read_json(terminate_request_path)
                        cancellation_reason = request.get("reason", "unknown")
                    except (OSError, ValueError):
                        cancellation_reason = "unknown"
                    termination_initiated = True
                    _terminate_group(child_pid, grace)
                elif time.monotonic() - start > wall_timeout:
                    timed_out = True
                    termination_initiated = True
                    _terminate_group(child_pid, grace)
            time.sleep(0.05)

        if raw_status is None:
            try:
                _, raw_status = os.waitpid(child_pid, 0)
            except ChildProcessError:
                raw_status = 0

    group_empty = not _group_alive(child_pid)
    if not group_empty:
        time.sleep(0.2)
        group_empty = not _group_alive(child_pid)

    if os.WIFEXITED(raw_status):
        normalized_exit_code: int | None = os.WEXITSTATUS(raw_status)
        terminating_signal: int | None = None
        core_dumped = False
        base_verdict = "EXITED"
    elif os.WIFSIGNALED(raw_status):
        normalized_exit_code = None
        terminating_signal = os.WTERMSIG(raw_status)
        core_dumped = (
            bool(os.WCOREDUMP(raw_status)) if hasattr(os, "WCOREDUMP") else False
        )
        base_verdict = "SIGNALED"
    else:
        normalized_exit_code = None
        terminating_signal = None
        core_dumped = False
        base_verdict = "INFRA"

    if cancellation_reason is not None:
        verdict = "CANCELLED"
    elif timed_out:
        verdict = "TIMED_OUT"
    else:
        verdict = base_verdict

    stdout_hash = _sha256(_read_bytes(stdout_path))
    stderr_hash = _sha256(_read_bytes(stderr_path))
    completed_at = (
        time.clock_gettime(time.CLOCK_BOOTTIME)
        if hasattr(time, "CLOCK_BOOTTIME")
        else time.time()
    )

    result = {
        "schema_version": SCHEMA_RESULT,
        "process_run_id": process_run_id,
        "intent_sha256": ledger["intent_sha256"],
        "contract_sha256": ledger["contract_sha256"],
        "ledger_sha256": _sha256(_canonical_json(ledger)),
        "supervisor_identity": supervisor_identity,
        "final_child_identity": ledger["child_identity"],
        "raw_wait_status": raw_status,
        "normalized_exit_code": normalized_exit_code,
        "terminating_signal": terminating_signal,
        "core_dumped": core_dumped,
        "timed_out": timed_out,
        "cancellation_reason": cancellation_reason,
        "child_group_empty": group_empty,
        "stdout_sha256": stdout_hash,
        "stderr_sha256": stderr_hash,
        "completed_at_boottime": completed_at,
        "verdict": verdict,
    }
    _atomic_write_json(args.result, result)
    if os.path.exists(terminate_request_path):
        try:
            os.unlink(terminate_request_path)
        except FileNotFoundError:
            pass
    return 0


# ---------------------------------------------------------------------------
# `poll`: short-lived observer, never a sleep node
# ---------------------------------------------------------------------------


def cmd_poll(args: argparse.Namespace) -> int:
    contract, _, _ = _load_common(args)
    deadline = time.monotonic() + max(0.0, args.wait_seconds)
    result_value: dict[str, Any] | None = None
    verdict_token = "SUPERVISOR:POLL_INFRA"

    while True:
        if os.path.exists(args.result):
            try:
                candidate, _ = _read_json(args.result)
            except (OSError, ValueError):
                candidate = None
            if (
                candidate is not None
                and candidate.get("schema_version") == SCHEMA_RESULT
            ):
                result_value = candidate
                verdict_token = "SUPERVISOR:POLL_TERMINAL"
                break
        if os.path.exists(args.ledger):
            try:
                ledger, _ = _read_json(args.ledger)
            except (OSError, ValueError):
                ledger = None
            sup_id = ledger.get("supervisor_identity") if ledger else None
            if sup_id is not None and not identity_alive_and_matches(sup_id):
                verdict_token = "SUPERVISOR:POLL_SUPERVISOR_GONE"
                break
        if time.monotonic() >= deadline:
            verdict_token = "SUPERVISOR:POLL_RUNNING"
            break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    output = {
        "schema_version": SCHEMA_POLL,
        "process_run_id": contract["process_run_id"],
        "verdict_token": verdict_token,
        "supervisor_result": result_value,
    }
    _atomic_write_json(args.output, output)
    print(verdict_token)
    return 0


# ---------------------------------------------------------------------------
# `terminate`: deterministic signalling client
# ---------------------------------------------------------------------------


def cmd_terminate(args: argparse.Namespace) -> int:
    contract, _, _ = _load_common(args)
    if args.reason not in TERMINATION_REASONS:
        raise SupervisorError("TERMINATE", f"unsupported reason: {args.reason}")

    if os.path.exists(args.result):
        token = "SUPERVISOR:ALREADY_TERMINAL"
    elif not os.path.exists(args.ledger):
        token = "SUPERVISOR:TERMINATE_INFRA"
    else:
        ledger, _ = _read_json(args.ledger)
        sup_id = ledger.get("supervisor_identity")
        if not sup_id or not identity_alive_and_matches(sup_id):
            token = "SUPERVISOR:TERMINATE_INFRA"
        else:
            request = {
                "schema_version": SCHEMA_TERMINATE_REQUEST,
                "process_run_id": contract["process_run_id"],
                "reason": args.reason,
            }
            _atomic_write_json(_terminate_request_path(args.result), request)
            try:
                os.kill(sup_id["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
            token = "SUPERVISOR:TERMINATION_REQUESTED"

    output = {
        "schema_version": SCHEMA_TERMINATION,
        "process_run_id": contract["process_run_id"],
        "reason": args.reason,
        "verdict_token": token,
    }
    _atomic_write_json(args.output, output)
    print(token)
    return 0


# ---------------------------------------------------------------------------
# `reconcile`: bounded recovery after parent/supervisor crash
# ---------------------------------------------------------------------------


def cmd_reconcile(args: argparse.Namespace) -> int:
    contract, _, _ = _load_common(args)
    process_run_id = contract["process_run_id"]
    detail: dict[str, Any] = {}

    if os.path.exists(args.result):
        token = "SUPERVISOR:RECONCILED_TERMINAL"
    elif os.path.exists(args.ledger):
        ledger, _ = _read_json(args.ledger)
        sup_id = ledger.get("supervisor_identity")
        if sup_id and identity_alive_and_matches(sup_id):
            token = "SUPERVISOR:RECONCILED_RUNNING"
        else:
            # Supervisor is gone with no authoritative result. Its child may
            # be a live orphan (reparented, still running) -- an unsupervised
            # child is never trusted as success, so terminate it if found.
            child_id = ledger.get("child_identity")
            terminated = False
            if child_id and identity_alive_and_matches(child_id):
                _terminate_group(child_id["pid"], float(contract["term_grace_seconds"]))
                terminated = True
            detail["terminated_orphan_child"] = terminated
            token = "SUPERVISOR:RECONCILE_INFRA"
    else:
        # Intent existed but no ledger ever appeared: bounded /proc scan for
        # a process carrying our process_run_id, in case a reaper or child
        # started but crashed before the first durable write.
        found_pid = _scan_proc_for_process_run_id(
            process_run_id,
            max_passes=args.max_passes,
            interval=args.scan_interval,
            timeout=args.pre_ledger_timeout,
        )
        if found_pid is None:
            token = "SUPERVISOR:RECONCILED_INTERRUPTED_BEFORE_LAUNCH"
        else:
            _terminate_group(found_pid, float(contract["term_grace_seconds"]))
            detail["terminated_orphan_child"] = True
            detail["found_pid"] = found_pid
            token = "SUPERVISOR:RECONCILE_INFRA"

    output = {
        "schema_version": SCHEMA_RECONCILIATION,
        "process_run_id": process_run_id,
        "verdict_token": token,
        "detail": detail,
    }
    _atomic_write_json(args.output, output)
    print(token)
    return 0


# ---------------------------------------------------------------------------
# `self-check`: non-mutating identity/version preflight
# ---------------------------------------------------------------------------


def cmd_self_check(args: argparse.Namespace) -> int:
    output = {
        "schema_version": SCHEMA_SELF_CHECK,
        "ok": True,
        "python_executable": os.path.realpath(sys.executable),
        "script_realpath": os.path.realpath(__file__),
        "platform": sys.platform,
        "identity_policy": IDENTITY_POLICY,
    }
    if args.format == "json":
        print(json.dumps(output, sort_keys=True))
    else:
        raise SupervisorError("SELF_CHECK", f"unsupported format: {args.format}")
    return 0


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goal_plan_supervisor.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--contract", required=True)
        p.add_argument("--intent", required=True)
        p.add_argument("--ledger", required=True)

    run_p = sub.add_parser("run")
    _common(run_p)
    run_p.add_argument("--ack", required=True)
    run_p.add_argument("--result", required=True)
    run_p.set_defaults(func=cmd_run)

    poll_p = sub.add_parser("poll")
    _common(poll_p)
    poll_p.add_argument("--ack", required=False, default=None)
    poll_p.add_argument("--result", required=True)
    poll_p.add_argument("--wait-seconds", required=True, type=float)
    poll_p.add_argument("--output", required=True)
    poll_p.set_defaults(func=cmd_poll)

    terminate_p = sub.add_parser("terminate")
    _common(terminate_p)
    terminate_p.add_argument("--result", required=True)
    terminate_p.add_argument("--reason", required=True)
    terminate_p.add_argument("--output", required=True)
    terminate_p.set_defaults(func=cmd_terminate)

    reconcile_p = sub.add_parser("reconcile")
    _common(reconcile_p)
    reconcile_p.add_argument("--ack", required=False, default=None)
    reconcile_p.add_argument("--result", required=True)
    reconcile_p.add_argument("--output", required=True)
    reconcile_p.add_argument(
        "--pre-ledger-timeout", dest="pre_ledger_timeout", type=float, default=3.0
    )
    reconcile_p.add_argument("--max-passes", dest="max_passes", type=int, default=3)
    reconcile_p.add_argument(
        "--scan-interval", dest="scan_interval", type=float, default=1.0
    )
    reconcile_p.set_defaults(func=cmd_reconcile)

    self_check_p = sub.add_parser("self-check")
    self_check_p.add_argument("--format", required=True)
    self_check_p.set_defaults(func=cmd_self_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SupervisorError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.EACCES, errno.ESRCH):
            print(f"OS_ERROR: {exc}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
