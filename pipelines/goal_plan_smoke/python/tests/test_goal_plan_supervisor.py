"""Fault-injection proof suite for goal_plan_supervisor.py.

Every test here launches the supervisor CLI as a real subprocess against a
real child process (no mocks): the reaper's job is to observe genuine OS
wait-status, procfs identity, and process-group state, so the proof has to
exercise the real kernel primitives it depends on.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

SUPERVISOR_PATH = Path(__file__).resolve().parents[1] / "goal_plan_supervisor.py"
SCHEMA_CONTRACT = "goal-plan.process-launch-contract/v1"
SCHEMA_INTENT = "goal-plan.launch-intent/v1"


def canonical(value: Any) -> bytes:
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


def sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> bytes:
    data = canonical(value)
    path.write_bytes(data)
    return data


class Paths:
    def __init__(self, base: Path, process_run_id: str) -> None:
        self.base = base
        self.process_run_id = process_run_id
        self.contract = base / "launch-contract.json"
        self.intent = base / "launch-intent.json"
        self.ledger = base / "process-ledger.json"
        self.ack = base / "launch-ack.json"
        self.result = base / "supervisor-result.json"
        self.stdout = base / "child.stdout"
        self.stderr = base / "child.stderr"


def make_contract(
    tmp_path: Path,
    process_run_id: str,
    child_argv: list[str],
    *,
    wall_timeout_seconds: float = 20.0,
    term_grace_seconds: float = 2.0,
    child_env: dict[str, str] | None = None,
) -> Paths:
    paths = Paths(tmp_path, process_run_id)
    contract = {
        "schema_version": SCHEMA_CONTRACT,
        "process_kind": "lane",
        "process_id": "lane_a",
        "process_run_id": process_run_id,
        "child_argv": child_argv,
        "child_cwd": str(tmp_path),
        "child_env": child_env or {},
        "wall_timeout_seconds": wall_timeout_seconds,
        "term_grace_seconds": term_grace_seconds,
        "stdout_path": str(paths.stdout),
        "stderr_path": str(paths.stderr),
    }
    contract_bytes = write_json(paths.contract, contract)
    intent = {
        "schema_version": SCHEMA_INTENT,
        "process_kind": "lane",
        "process_id": "lane_a",
        "process_launch": 1,
        "process_run_id": process_run_id,
        "contract_sha256": sha256(contract_bytes),
    }
    write_json(paths.intent, intent)
    return paths


def run_supervisor(
    command: str, paths: Paths, *extra: str, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(SUPERVISOR_PATH),
        command,
        "--contract",
        str(paths.contract),
        "--intent",
        str(paths.intent),
        "--ledger",
        str(paths.ledger),
        *extra,
    ]
    return subprocess.run(
        argv, check=False, capture_output=True, text=True, timeout=timeout
    )


def run_reaper_foreground(
    paths: Paths, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    return run_supervisor(
        "run",
        paths,
        "--ack",
        str(paths.ack),
        "--result",
        str(paths.result),
        timeout=timeout,
    )


def spawn_reaper_background(paths: Paths) -> subprocess.Popen[bytes]:
    argv = [
        sys.executable,
        str(SUPERVISOR_PATH),
        "run",
        "--contract",
        str(paths.contract),
        "--intent",
        str(paths.intent),
        "--ledger",
        str(paths.ledger),
        "--ack",
        str(paths.ack),
        "--result",
        str(paths.result),
    ]
    return subprocess.Popen(argv, start_new_session=True)


def wait_for(predicate, timeout: float = 15.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def assert_no_zombie(pid: int) -> None:
    """Assert the given pid is fully reaped: no /proc entry, no zombie state."""
    proc_path = Path(f"/proc/{pid}")
    if not proc_path.exists():
        return
    stat_text = (proc_path / "stat").read_text()
    state = stat_text.rsplit(")", 1)[1].split()[0]
    assert state != "Z", f"pid {pid} left as zombie"


# ---------------------------------------------------------------------------
# 1. Clean exit 0
# ---------------------------------------------------------------------------


def test_child_exit_zero_produces_exited_verdict(tmp_path: Path) -> None:
    paths = make_contract(
        tmp_path, "run-exit0", [sys.executable, "-c", "import sys; sys.exit(0)"]
    )
    proc = run_reaper_foreground(paths)
    assert proc.returncode == 0, proc.stderr

    result = read_json(paths.result)
    assert result["verdict"] == "EXITED"
    assert result["normalized_exit_code"] == 0
    assert result["terminating_signal"] is None
    assert result["timed_out"] is False
    assert result["cancellation_reason"] is None
    assert result["child_group_empty"] is True

    ledger = read_json(paths.ledger)
    assert ledger["state"] == "CHILD_STARTED"
    assert ledger["child_identity"]["pid"] == result["final_child_identity"]["pid"]
    assert_no_zombie(result["final_child_identity"]["pid"])


# ---------------------------------------------------------------------------
# 2. Nonzero exit remains non-pass, distinguishable from success
# ---------------------------------------------------------------------------


def test_child_nonzero_exit_is_not_pass(tmp_path: Path) -> None:
    paths = make_contract(
        tmp_path, "run-exit7", [sys.executable, "-c", "import sys; sys.exit(7)"]
    )
    proc = run_reaper_foreground(paths)
    assert proc.returncode == 0, proc.stderr

    result = read_json(paths.result)
    assert result["verdict"] == "EXITED"
    assert result["normalized_exit_code"] == 7
    assert result["verdict"] != "TIMED_OUT"
    assert result["verdict"] != "CANCELLED"


# ---------------------------------------------------------------------------
# 3. Signal termination
# ---------------------------------------------------------------------------


def test_child_self_signal_produces_signaled_verdict(tmp_path: Path) -> None:
    script = "import os, signal; os.kill(os.getpid(), signal.SIGABRT)"
    paths = make_contract(tmp_path, "run-signal", [sys.executable, "-c", script])
    proc = run_reaper_foreground(paths)
    assert proc.returncode == 0, proc.stderr

    result = read_json(paths.result)
    assert result["verdict"] == "SIGNALED"
    assert result["terminating_signal"] == signal.SIGABRT
    assert result["normalized_exit_code"] is None
    assert result["cancellation_reason"] is None
    assert result["timed_out"] is False


# ---------------------------------------------------------------------------
# 4. Wall timeout: reaper enforces TERM -> grace -> KILL and reports TIMED_OUT
# ---------------------------------------------------------------------------


def test_wall_timeout_is_enforced_and_reported(tmp_path: Path) -> None:
    script = "import time; time.sleep(120)"
    paths = make_contract(
        tmp_path,
        "run-timeout",
        [sys.executable, "-c", script],
        wall_timeout_seconds=1.0,
        term_grace_seconds=1.0,
    )
    started = time.monotonic()
    proc = run_reaper_foreground(paths, timeout=15.0)
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 10.0, (
        "timeout enforcement took far longer than the configured budget"
    )

    result = read_json(paths.result)
    assert result["verdict"] == "TIMED_OUT"
    assert result["timed_out"] is True
    assert result["child_group_empty"] is True
    assert_no_zombie(result["final_child_identity"]["pid"])


# ---------------------------------------------------------------------------
# 5. Cancellation via the `terminate` control client
# ---------------------------------------------------------------------------


def test_terminate_control_client_cancels_running_child(tmp_path: Path) -> None:
    script = "import time; time.sleep(120)"
    paths = make_contract(
        tmp_path,
        "run-cancel",
        [sys.executable, "-c", script],
        wall_timeout_seconds=60.0,
        term_grace_seconds=1.0,
    )
    reaper = spawn_reaper_background(paths)
    try:
        assert wait_for(lambda: paths.ack.exists(), timeout=15.0), (
            "reaper never wrote launch-ack"
        )

        term_proc = run_supervisor(
            "terminate",
            paths,
            "--result",
            str(paths.result),
            "--reason",
            "child_cancelled",
            "--output",
            str(tmp_path / "termination-result.json"),
        )
        assert term_proc.returncode == 0, term_proc.stderr
        termination = read_json(tmp_path / "termination-result.json")
        assert termination["verdict_token"] == "SUPERVISOR:TERMINATION_REQUESTED"

        assert wait_for(lambda: paths.result.exists(), timeout=15.0), (
            "reaper never wrote a result after terminate"
        )
        reaper.wait(timeout=15.0)
    finally:
        if reaper.poll() is None:
            reaper.kill()
            reaper.wait(timeout=5.0)

    result = read_json(paths.result)
    assert result["verdict"] == "CANCELLED"
    assert result["cancellation_reason"] == "child_cancelled"
    assert result["timed_out"] is False
    assert_no_zombie(result["final_child_identity"]["pid"])


# ---------------------------------------------------------------------------
# 6. Parent crash: the reaper is independent of the process that launched it
# ---------------------------------------------------------------------------


def test_reaper_survives_disappearance_of_its_launcher(tmp_path: Path) -> None:
    paths = make_contract(
        tmp_path, "run-parentcrash", [sys.executable, "-c", "import sys; sys.exit(0)"]
    )

    launcher_script = tmp_path / "spawn_and_vanish.py"
    launcher_script.write_text(
        "import subprocess, sys\n"
        f"argv = {[sys.executable, str(SUPERVISOR_PATH), 'run', '--contract', str(paths.contract), '--intent', str(paths.intent), '--ledger', str(paths.ledger), '--ack', str(paths.ack), '--result', str(paths.result)]!r}\n"
        "subprocess.Popen(argv, start_new_session=True)\n"
        "sys.exit(0)\n"
    )
    # The launcher process starts the reaper and exits immediately, exactly
    # like a crashed/vanished parent graph process would -- proving the
    # reaper's completion does not depend on that launcher staying alive.
    launcher = subprocess.run(
        [sys.executable, str(launcher_script)], check=False, timeout=15.0
    )
    assert launcher.returncode == 0

    assert wait_for(lambda: paths.result.exists(), timeout=15.0), (
        "orphaned reaper never completed"
    )
    result = read_json(paths.result)
    assert result["verdict"] == "EXITED"
    assert result["normalized_exit_code"] == 0


# ---------------------------------------------------------------------------
# 7. Supervisor crash: reconcile finds and terminates the orphaned child
# ---------------------------------------------------------------------------


def test_reconcile_terminates_orphan_after_supervisor_crash(tmp_path: Path) -> None:
    script = "import time; time.sleep(120)"
    paths = make_contract(
        tmp_path,
        "run-supcrash",
        [sys.executable, "-c", script],
        wall_timeout_seconds=60.0,
        term_grace_seconds=1.0,
    )
    reaper = spawn_reaper_background(paths)
    try:
        assert wait_for(lambda: paths.ack.exists(), timeout=15.0), (
            "reaper never wrote launch-ack"
        )
        ledger = read_json(paths.ledger)
        child_pid = ledger["child_identity"]["pid"]
        assert Path(f"/proc/{child_pid}").exists(), (
            "child should be alive before the crash"
        )

        # Simulate the supervisor crashing: SIGKILL it directly. The child is
        # in its own session/process group, so it survives as an orphan.
        os.kill(reaper.pid, signal.SIGKILL)
        reaper.wait(timeout=5.0)
        assert wait_for(lambda: Path(f"/proc/{child_pid}").exists(), timeout=2.0)
        assert not paths.result.exists(), (
            "no authoritative result should exist after a supervisor crash"
        )

        reconcile_proc = run_supervisor(
            "reconcile",
            paths,
            "--ack",
            str(paths.ack),
            "--result",
            str(paths.result),
            "--output",
            str(tmp_path / "reconciliation-result.json"),
            "--pre-ledger-timeout",
            "1",
        )
        assert reconcile_proc.returncode == 0, reconcile_proc.stderr
        reconciliation = read_json(tmp_path / "reconciliation-result.json")
        assert reconciliation["verdict_token"] == "SUPERVISOR:RECONCILE_INFRA"
        assert reconciliation["detail"]["terminated_orphan_child"] is True

        assert wait_for(
            lambda: not Path(f"/proc/{child_pid}").exists(), timeout=10.0
        ), "orphaned child should be terminated by reconcile"
        assert_no_zombie(child_pid)
    finally:
        if reaper.poll() is None:
            reaper.kill()
            reaper.wait(timeout=5.0)


# ---------------------------------------------------------------------------
# 8. Stale/forged PID identity is never trusted
# ---------------------------------------------------------------------------


def test_stale_forged_identity_is_never_trusted(tmp_path: Path) -> None:
    paths = make_contract(
        tmp_path, "run-stale-pid", [sys.executable, "-c", "import sys; sys.exit(0)"]
    )

    forged_ledger = {
        "schema_version": "goal-plan.process-ledger/v1",
        "process_run_id": paths.process_run_id,
        "intent_sha256": sha256(paths.intent.read_bytes()),
        "contract_sha256": sha256(paths.contract.read_bytes()),
        "identity_policy": "goal-plan.linux-procfs-identity/v1",
        "supervisor_identity": {
            "boot_id": "0" * 32,
            "pid": 999999,
            "starttime_ticks": 1,
            "cmdline_sha256": "0" * 64,
            "pgid": 999999,
            "exe_realpath": "/nonexistent/forged/path",
        },
        "child_identity": None,
        "state": "SUPERVISOR_STARTED",
    }
    write_json(paths.ledger, forged_ledger)

    poll_proc = run_supervisor(
        "poll",
        paths,
        "--ack",
        str(paths.ack),
        "--result",
        str(paths.result),
        "--wait-seconds",
        "1",
        "--output",
        str(tmp_path / "poll-result.json"),
    )
    assert poll_proc.returncode == 0, poll_proc.stderr
    poll_result = read_json(tmp_path / "poll-result.json")
    assert poll_result["verdict_token"] == "SUPERVISOR:POLL_SUPERVISOR_GONE"

    terminate_proc = run_supervisor(
        "terminate",
        paths,
        "--result",
        str(paths.result),
        "--reason",
        "recovery_cleanup",
        "--output",
        str(tmp_path / "termination-result.json"),
    )
    assert terminate_proc.returncode == 0, terminate_proc.stderr
    termination = read_json(tmp_path / "termination-result.json")
    assert termination["verdict_token"] == "SUPERVISOR:TERMINATE_INFRA"


# ---------------------------------------------------------------------------
# 9. Result is atomic: no torn/partial file ever observed, no stray temp files
# ---------------------------------------------------------------------------


def test_result_write_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    paths = make_contract(
        tmp_path, "run-atomic", [sys.executable, "-c", "import sys; sys.exit(0)"]
    )
    proc = run_reaper_foreground(paths)
    assert proc.returncode == 0, proc.stderr

    raw = paths.result.read_bytes()
    assert raw.endswith(b"\n")
    parsed = json.loads(raw.decode("utf-8"))
    assert parsed["schema_version"] == "goal-plan.supervisor-result/v1"
    assert canonical(parsed) == raw, (
        "stored bytes must be canonical JSON, never partially written"
    )

    leftovers = list(tmp_path.glob(".goal-plan-sup-*"))
    assert leftovers == [], f"temporary files were not cleaned up: {leftovers}"
    assert not paths.result.with_name(
        paths.result.name + ".terminate-request.json"
    ).exists()


# ---------------------------------------------------------------------------
# 10. No zombie/orphan left behind across the whole suite's own children
# ---------------------------------------------------------------------------


def test_interrupted_before_launch_reconciliation(tmp_path: Path) -> None:
    """`reconcile` with no ledger and no matching /proc entry is a clean no-op."""
    paths = make_contract(
        tmp_path, "run-never-started", [sys.executable, "-c", "import sys; sys.exit(0)"]
    )
    reconcile_proc = run_supervisor(
        "reconcile",
        paths,
        "--ack",
        str(paths.ack),
        "--result",
        str(paths.result),
        "--output",
        str(tmp_path / "reconciliation-result.json"),
        "--pre-ledger-timeout",
        "0.5",
        "--max-passes",
        "1",
        "--scan-interval",
        "0.1",
    )
    assert reconcile_proc.returncode == 0, reconcile_proc.stderr
    reconciliation = read_json(tmp_path / "reconciliation-result.json")
    assert (
        reconciliation["verdict_token"]
        == "SUPERVISOR:RECONCILED_INTERRUPTED_BEFORE_LAUNCH"
    )


def test_self_check_reports_identity_without_mutation(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SUPERVISOR_PATH), "self-check", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["schema_version"] == "goal-plan.supervisor-self-check/v1"
    assert payload["ok"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
