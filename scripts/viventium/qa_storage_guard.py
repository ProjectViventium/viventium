#!/usr/bin/env python3
"""Fail-closed storage guard for disposable Viventium release QA.

The guard never discovers and adopts resources, never runs a shell, and never performs
global cleanup.  It owns at most the one Tart VM named in its persistent receipt.  All
other Docker and Tart state is baseline-only and must still exist after a guarded command.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from typing import Any, NoReturn, Sequence
import uuid


RUN_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\Z")
GLOB_RE = re.compile(r"[*?\[\]]")
SHELLS = {"bash", "csh", "dash", "fish", "ksh", "sh", "tcsh", "zsh"}
DIRECT_DESTRUCTIVE_TOOLS = {"rm", "rmdir", "xargs"}
EXECUTION_WRAPPERS = {"command", "env", "nohup", "sudo"}
DOCKER_MUTATING_ACTIONS = {
    "attach",
    "build",
    "commit",
    "compose",
    "cp",
    "create",
    "down",
    "exec",
    "export",
    "import",
    "kill",
    "load",
    "pause",
    "pull",
    "push",
    "rename",
    "restart",
    "rm",
    "rmi",
    "run",
    "save",
    "start",
    "stop",
    "tag",
    "unpause",
    "up",
    "update",
}
MAX_JSON_BYTES = 1024 * 1024
PROCESS_GROUP_TERM_GRACE_SECONDS = 0.5
PROCESS_GROUP_KILL_WAIT_SECONDS = 5.0
PROCESS_GROUP_POLL_SECONDS = 0.02


class GuardError(RuntimeError):
    """A safety gate failed and no broader cleanup is permitted."""


class GuardInterrupted(RuntimeError):
    """The operator interrupted a guarded child process."""


def _fail(message: str) -> NoReturn:
    raise GuardError(message)


def _read_json(path: Path, *, require_owner_only: bool = False) -> dict[str, Any]:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise GuardError(f"required guard record is missing: {path.name}") from error
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or (require_owner_only and stat.S_IMODE(info.st_mode) & 0o077)
        or info.st_size > MAX_JSON_BYTES
    ):
        _fail(f"unsafe guard record: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GuardError(f"unreadable guard record: {path.name}") from error
    if not isinstance(payload, dict):
        _fail(f"invalid guard record: {path.name}")
    return payload


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _create_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise GuardError("CLEANUP_REQUIRED: an active QA storage lease already exists") from error
    try:
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _ensure_state_root(path: Path) -> Path:
    if path.is_symlink():
        _fail("state root must not be a symlink")
    existed = path.exists()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        if existed:
            _fail("state root must be an existing owner-only directory")
        _fail("state root must be an owner-controlled directory")
    runs = path / "runs"
    if runs.is_symlink():
        _fail("runs directory must not be a symlink")
    runs_existed = runs.exists()
    runs.mkdir(mode=0o700, exist_ok=True)
    runs_info = runs.lstat()
    if (
        not stat.S_ISDIR(runs_info.st_mode)
        or runs_info.st_uid != os.getuid()
        or stat.S_IMODE(runs_info.st_mode) & 0o077
    ):
        if runs_existed:
            _fail("runs directory must be an existing owner-only directory")
        _fail("runs directory must be an owner-controlled directory")
    return path


def _validate_executable(raw: str, label: str) -> Path:
    path = Path(raw).expanduser().resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
        _fail(f"{label} is not an executable regular file")
    return path


def _validate_policy(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "qa_vm_prefix",
        "max_active_qa_vms",
        "minimum_free_bytes_before_run",
        "abort_below_free_bytes",
        "max_host_physical_growth_bytes",
        "max_docker_physical_growth_during_run_bytes",
        "max_docker_physical_residual_bytes",
        "max_docker_logical_growth_from_clean_baseline_bytes",
        "sample_interval_seconds",
    }
    if set(payload) != expected:
        _fail("storage policy keys do not match schema version 1")
    if payload["schema_version"] != 1 or payload["max_active_qa_vms"] != 1:
        _fail("storage policy must enforce schema version 1 and one active QA VM")
    prefix = payload["qa_vm_prefix"]
    if not isinstance(prefix, str) or not RUN_ID_RE.fullmatch(prefix.rstrip("-")):
        _fail("storage policy has an unsafe QA VM prefix")
    integer_fields = expected - {"qa_vm_prefix", "sample_interval_seconds"}
    for key in integer_fields:
        if not isinstance(payload[key], int) or isinstance(payload[key], bool) or payload[key] < 0:
            _fail(f"storage policy field {key} must be a non-negative integer")
    interval = payload["sample_interval_seconds"]
    if not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval <= 0:
        _fail("sample_interval_seconds must be positive")
    return payload


def _load_policy(path: Path) -> dict[str, Any]:
    payload = _read_json(path.resolve(strict=True))
    return _validate_policy(payload)


def _run_read_only(argv: Sequence[str], *, timeout: float = 20) -> str:
    try:
        result = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GuardError(f"read-only inventory failed: {Path(argv[0]).name}") from error
    if result.returncode != 0:
        _fail(f"read-only inventory failed: {Path(argv[0]).name}")
    return result.stdout


def _tart_names(tart: str) -> list[str]:
    raw = _run_read_only([tart, "list", "--format", "json"])
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise GuardError("Tart inventory did not return valid JSON") from error
    if isinstance(payload, dict):
        payload = payload.get("VMs", payload.get("vms"))
    if not isinstance(payload, list):
        _fail("Tart inventory has an unsupported JSON shape")
    names: list[str] = []
    for item in payload:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("Name", item.get("name"))
        else:
            _fail("Tart inventory contains an invalid VM entry")
        if not isinstance(name, str) or not name:
            _fail("Tart inventory contains an invalid VM name")
        names.append(name)
    return sorted(set(names))


def _qa_vms(tart: str, prefix: str) -> list[str]:
    return [name for name in _tart_names(tart) if name.startswith(prefix)]


def _disk_metrics(path: Path) -> dict[str, int | bool]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"exists": False, "device": 0, "inode": 0, "logical_bytes": 0, "physical_bytes": 0}
    if not stat.S_ISREG(info.st_mode):
        _fail("Docker sparse-disk path must be a regular file")
    return {
        "exists": True,
        "device": info.st_dev,
        "inode": info.st_ino,
        "logical_bytes": info.st_size,
        "physical_bytes": info.st_blocks * 512,
    }


def _docker_baseline(docker: str, docker_disk: Path) -> dict[str, Any]:
    def lines(*args: str) -> list[str]:
        return sorted(set(line for line in _run_read_only([docker, *args]).splitlines() if line))

    context = _run_read_only([docker, "context", "show"]).strip()
    if not context:
        _fail("Docker context inventory returned an empty context")
    return {
        "context": context,
        "containers": lines("ps", "-aq", "--no-trunc"),
        "volumes": lines("volume", "ls", "--quiet"),
        "images": lines("image", "ls", "--no-trunc", "--quiet"),
        "disk": _disk_metrics(docker_disk),
    }


def _assert_docker_preserved(baseline: dict[str, Any], current: dict[str, Any]) -> None:
    if current["context"] != baseline["context"]:
        _fail("Docker context changed during guarded QA")
    for key, singular in (("containers", "container"), ("volumes", "volume"), ("images", "image")):
        missing = sorted(set(baseline[key]) - set(current[key]))
        if missing:
            _fail(f"pre-existing Docker {singular} disappeared during guarded QA")
    before_disk = baseline["disk"]
    after_disk = current["disk"]
    if before_disk["exists"] and (
        not after_disk["exists"]
        or before_disk["device"] != after_disk["device"]
        or before_disk["inode"] != after_disk["inode"]
    ):
        _fail("pre-existing Docker sparse disk was replaced during guarded QA")


def _assert_no_new_docker_resources(baseline: dict[str, Any], current: dict[str, Any]) -> None:
    for key, singular in (("containers", "container"), ("volumes", "volume"), ("images", "image")):
        extra = sorted(set(current[key]) - set(baseline[key]))
        if extra:
            _fail(f"post-baseline Docker {singular} remains after guarded QA")


def _growth(current: int, baseline: int) -> int:
    return max(0, current - baseline)


def _assert_clean_baseline(
    clean: dict[str, Any], current: dict[str, Any], policy: dict[str, Any]
) -> None:
    clean_disk = clean["docker_disk"]
    current_disk = current["disk"]
    if clean_disk["exists"] and (
        not current_disk["exists"]
        or clean_disk["device"] != current_disk["device"]
        or clean_disk["inode"] != current_disk["inode"]
    ):
        _fail("CLEANUP_REQUIRED: Docker sparse disk no longer matches the persistent clean baseline")
    if _growth(current_disk["physical_bytes"], clean_disk["physical_bytes"]) > policy[
        "max_docker_physical_residual_bytes"
    ]:
        _fail("CLEANUP_REQUIRED: Docker physical growth exceeds the persistent clean baseline")
    if _growth(current_disk["logical_bytes"], clean_disk["logical_bytes"]) > policy[
        "max_docker_logical_growth_from_clean_baseline_bytes"
    ]:
        _fail("CLEANUP_REQUIRED: Docker logical growth exceeds the persistent clean baseline")


def _receipt_path(state_root: Path, run_id: str) -> Path:
    return state_root / "runs" / f"{run_id}.json"


def _load_receipt(state_root: Path, run_id: str) -> dict[str, Any]:
    receipt = _read_json(_receipt_path(state_root, run_id), require_owner_only=True)
    if receipt.get("run_id") != run_id:
        _fail("receipt run ID does not match the requested run")
    lease = _read_json(state_root / "active-lease.json", require_owner_only=True)
    if lease.get("run_id") != run_id:
        _fail("active lease belongs to a different run; CLEANUP_REQUIRED")
    _validate_policy(receipt.get("policy") if isinstance(receipt.get("policy"), dict) else {})
    return receipt


def _save_receipt(state_root: Path, receipt: dict[str, Any], phase: str, detail: str = "") -> None:
    receipt["phase"] = phase
    receipt["updated_unix_seconds"] = time.time()
    if detail:
        receipt["detail"] = detail
    _write_json_atomic(_receipt_path(state_root, receipt["run_id"]), receipt)


def _sample(receipt: dict[str, Any]) -> tuple[dict[str, Any], int]:
    candidate = Path(receipt["candidate"])
    free = shutil.disk_usage(candidate).free
    docker = _docker_baseline(receipt["docker"], Path(receipt["docker_disk"]))
    _assert_docker_preserved(receipt["docker_baseline"], docker)
    return docker, free


def _safety_violation(receipt: dict[str, Any]) -> str | None:
    try:
        docker, free = _sample(receipt)
    except GuardError as error:
        return str(error)
    policy = receipt["policy"]
    if free < policy["abort_below_free_bytes"]:
        return "free-space floor reached during guarded QA"
    if receipt["host_free_bytes_at_prepare"] - free > policy["max_host_physical_growth_bytes"]:
        return "host physical growth exceeded the guarded QA budget"
    before = receipt["docker_baseline"]["disk"]
    after = docker["disk"]
    if _growth(after["physical_bytes"], before["physical_bytes"]) > policy[
        "max_docker_physical_growth_during_run_bytes"
    ]:
        return "Docker physical growth exceeded the guarded QA budget"
    if _growth(after["logical_bytes"], before["logical_bytes"]) > policy[
        "max_docker_logical_growth_from_clean_baseline_bytes"
    ]:
        return "Docker logical growth exceeded the guarded QA budget"
    return None


def _process_group_present(process_group_id: int) -> bool | None:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    return True


def _wait_for_group_exit(
    process: subprocess.Popen[Any], process_group_id: int, timeout: float
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        process.poll()
        present = _process_group_present(process_group_id)
        if present is False:
            return True
        if present is None:
            return False
        time.sleep(PROCESS_GROUP_POLL_SECONDS)
    process.poll()
    return _process_group_present(process_group_id) is False


def _terminate_group(process: subprocess.Popen[Any]) -> str | None:
    process_group_id = process.pid
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        process.poll()
        if _process_group_present(process_group_id) is False:
            return None
    except PermissionError:
        return "owned process group could not be signaled or proven empty"

    if _wait_for_group_exit(process, process_group_id, PROCESS_GROUP_TERM_GRACE_SECONDS):
        return None
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        process.poll()
    except PermissionError:
        return "owned process group could not be killed or proven empty"
    if _wait_for_group_exit(process, process_group_id, PROCESS_GROUP_KILL_WAIT_SECONDS):
        return None
    return "owned process group remains or could not be proven empty after SIGKILL"


def _run_monitored(
    receipt: dict[str, Any], argv: Sequence[str], *, env: dict[str, str] | None = None
) -> tuple[int, str | None]:
    try:
        process = subprocess.Popen(list(argv), env=env, start_new_session=True)
    except OSError as error:
        return 127, f"guarded executable could not start: {Path(argv[0]).name}"
    interval = float(receipt["policy"]["sample_interval_seconds"])
    violation: str | None = None
    handled_signals = (signal.SIGINT, signal.SIGTERM)
    previous_handlers = {signum: signal.getsignal(signum) for signum in handled_signals}

    def interrupt(_signum: int, _frame: Any) -> NoReturn:
        raise GuardInterrupted("guarded command interrupted; exact cleanup required")

    for signum in handled_signals:
        signal.signal(signum, interrupt)
    try:
        while process.poll() is None:
            violation = _safety_violation(receipt)
            if violation:
                break
            time.sleep(interval)
        if violation is None:
            violation = _safety_violation(receipt)
    except (GuardInterrupted, KeyboardInterrupt) as error:
        violation = str(error) or "guarded command interrupted; exact cleanup required"
    finally:
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)

    group_present = _process_group_present(process.pid)
    if group_present is not False:
        if violation is None:
            if process.poll() is None:
                violation = "guarded command did not leave an empty owned process group"
            else:
                violation = "guarded command left descendant processes in its owned process group"
        termination_error = _terminate_group(process)
        if termination_error:
            violation = f"{violation}; {termination_error}"
    if _process_group_present(process.pid) is not False:
        uncertainty = "owned process group could not be proven empty"
        violation = f"{violation}; {uncertainty}" if violation else uncertainty
    return process.returncode if process.returncode is not None else 1, violation


def _validate_argv(argv: Sequence[str]) -> list[str]:
    values = list(argv)
    if values and values[0] == "--":
        values = values[1:]
    if not values or any(not isinstance(value, str) or "\x00" in value for value in values):
        _fail("unsafe argv: a non-empty argument vector is required")
    executable = Path(values[0]).name.lower()
    if (
        executable in SHELLS
        or executable in DIRECT_DESTRUCTIVE_TOOLS
        or executable in EXECUTION_WRAPPERS
    ):
        _fail("unsafe argv: shells and direct destructive tools are not allowed")
    normalized_arguments = {value.lower().lstrip("-") for value in values[1:]}
    if executable.endswith("docker") and normalized_arguments & DOCKER_MUTATING_ACTIONS:
        _fail("unsafe argv: direct Docker mutation is not allowed")
    if executable.endswith("tart") and normalized_arguments & {"clone", "delete", "prune"}:
        _fail("unsafe argv: Tart lifecycle must use the receipt-owned guard commands")
    for value in values:
        if GLOB_RE.search(value) or "prune" in value.lower():
            _fail("unsafe argv: prune operations and wildcard arguments are not allowed")
    return values


def command_prepare(args: argparse.Namespace) -> None:
    if not RUN_ID_RE.fullmatch(args.run_id):
        _fail("run ID must use lowercase letters, digits, and single-purpose hyphens")
    policy = _load_policy(Path(args.policy))
    expected_name = f"{policy['qa_vm_prefix']}{args.run_id}"
    if args.vm_name != expected_name or not RUN_ID_RE.fullmatch(args.vm_name):
        _fail(f"VM name must be exactly {expected_name}")
    candidate_input = Path(args.candidate).expanduser()
    if candidate_input.is_symlink():
        _fail("candidate directory must not be a symlink")
    candidate = candidate_input.resolve(strict=True)
    if not candidate.is_dir():
        _fail("candidate must be an existing directory")
    tart = _validate_executable(args.tart, "Tart executable")
    docker = _validate_executable(args.docker, "Docker executable")
    docker_disk = Path(args.docker_disk).expanduser()
    if docker_disk.is_symlink():
        _fail("Docker sparse-disk path must not be a symlink")
    docker_disk = docker_disk.resolve(strict=False)

    existing = _qa_vms(str(tart), policy["qa_vm_prefix"])
    if existing:
        _fail(f"CLEANUP_REQUIRED: existing QA VM(s) block a new run: {', '.join(existing)}")
    free = shutil.disk_usage(candidate).free
    if free < policy["minimum_free_bytes_before_run"]:
        _fail("insufficient free space for guarded QA")
    docker_baseline = _docker_baseline(str(docker), docker_disk)

    state_root = _ensure_state_root(Path(args.state_root).expanduser())
    receipt_path = _receipt_path(state_root, args.run_id)
    if receipt_path.exists() or receipt_path.is_symlink():
        _fail("a unique run ID is required; prior receipts are immutable evidence")
    clean_path = state_root / "clean-baseline.json"
    if clean_path.exists():
        clean = _read_json(clean_path, require_owner_only=True)
        _assert_clean_baseline(clean, docker_baseline, policy)
    else:
        clean = {
            "schema_version": 1,
            "created_unix_seconds": time.time(),
            "docker_disk": docker_baseline["disk"],
        }
        _create_json_exclusive(clean_path, clean)

    receipt = {
        "schema_version": 1,
        "run_id": args.run_id,
        "vm_name": args.vm_name,
        "candidate": str(candidate),
        "state_root": str(state_root.resolve()),
        "tart": str(tart),
        "docker": str(docker),
        "docker_disk": str(docker_disk),
        "policy": policy,
        "host_free_bytes_at_prepare": free,
        "docker_baseline": docker_baseline,
        "owned_vm_intended": False,
        "owned_vm_created": False,
        "phase": "PREPARED",
        "created_unix_seconds": time.time(),
        "updated_unix_seconds": time.time(),
    }
    _create_json_exclusive(receipt_path, receipt)
    lease = {
        "schema_version": 1,
        "run_id": args.run_id,
        "vm_name": args.vm_name,
        "created_unix_seconds": time.time(),
    }
    try:
        _create_json_exclusive(state_root / "active-lease.json", lease)
    except GuardError:
        receipt_path.unlink()
        _fsync_directory(receipt_path.parent)
        raise
    print(f"PREPARED {args.run_id}")


def command_clone(args: argparse.Namespace) -> None:
    state_root = _ensure_state_root(Path(args.state_root).expanduser())
    receipt = _load_receipt(state_root, args.run_id)
    if receipt["phase"] != "PREPARED" or receipt["owned_vm_intended"]:
        _fail("clone is allowed exactly once from a prepared receipt")
    if not RUN_ID_RE.fullmatch(args.source_vm):
        _fail("source VM name is unsafe")
    existing = _qa_vms(receipt["tart"], receipt["policy"]["qa_vm_prefix"])
    if existing:
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "unowned QA VM appeared before clone")
        _fail(f"CLEANUP_REQUIRED: existing QA VM(s) block clone: {', '.join(existing)}")
    receipt["owned_vm_intended"] = True
    _save_receipt(state_root, receipt, "CLONE_RUNNING")
    env = os.environ.copy()
    env["TART_NO_AUTO_PRUNE"] = "1"
    argv = [receipt["tart"], "clone", args.source_vm, receipt["vm_name"]]
    status, violation = _run_monitored(receipt, argv, env=env)
    names = _qa_vms(receipt["tart"], receipt["policy"]["qa_vm_prefix"])
    if violation or status != 0 or names != [receipt["vm_name"]]:
        detail = violation or f"clone failed with exit status {status}"
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", detail)
        _fail(f"CLEANUP_REQUIRED: {detail}")
    receipt["owned_vm_created"] = True
    _save_receipt(state_root, receipt, "VM_READY")
    print(f"VM_READY {receipt['vm_name']}")


def command_run(args: argparse.Namespace) -> None:
    state_root = _ensure_state_root(Path(args.state_root).expanduser())
    receipt = _load_receipt(state_root, args.run_id)
    if receipt["phase"] not in {"PREPARED", "VM_READY", "RUN_COMPLETE"}:
        _fail("guarded commands require a prepared or ready receipt; CLEANUP_REQUIRED")
    argv = _validate_argv(args.argv)
    _save_receipt(state_root, receipt, "COMMAND_RUNNING")
    status, violation = _run_monitored(receipt, argv)
    if violation or status != 0:
        detail = violation or f"guarded command failed with exit status {status}"
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", detail)
        _fail(f"CLEANUP_REQUIRED: {detail}")
    _save_receipt(state_root, receipt, "RUN_COMPLETE")
    print(f"RUN_COMPLETE {args.run_id}")


def command_cleanup(args: argparse.Namespace) -> None:
    if args.confirm_run_id != args.run_id:
        _fail("cleanup confirmation must exactly match the receipt run ID")
    state_root = _ensure_state_root(Path(args.state_root).expanduser())
    receipt = _load_receipt(state_root, args.run_id)
    prefix = receipt["policy"]["qa_vm_prefix"]
    names = _qa_vms(receipt["tart"], prefix)
    foreign = [name for name in names if name != receipt["vm_name"]]
    if foreign:
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "unowned QA VM present")
        _fail(f"CLEANUP_REQUIRED: unowned QA VM(s) must be reviewed manually: {', '.join(foreign)}")
    if receipt["vm_name"] in names:
        if not receipt["owned_vm_created"]:
            _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "receipt does not own present VM")
            _fail("CLEANUP_REQUIRED: present QA VM is not owned by this receipt")
        _save_receipt(state_root, receipt, "CLEANUP_RUNNING")
        env = os.environ.copy()
        env["TART_NO_AUTO_PRUNE"] = "1"
        try:
            result = subprocess.run(
                [receipt["tart"], "delete", receipt["vm_name"]],
                env=env,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "exact VM delete did not finish")
            _fail("CLEANUP_REQUIRED: exact receipt-owned VM delete did not finish")
        if result.returncode != 0:
            _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "exact VM delete failed")
            _fail("CLEANUP_REQUIRED: exact receipt-owned VM delete failed")
    remaining = _qa_vms(receipt["tart"], prefix)
    if remaining:
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "QA VM remains after cleanup")
        _fail("CLEANUP_REQUIRED: a QA VM remains after exact cleanup")

    try:
        current_docker, free = _sample(receipt)
        _assert_no_new_docker_resources(receipt["docker_baseline"], current_docker)
        clean = _read_json(state_root / "clean-baseline.json", require_owner_only=True)
        _assert_clean_baseline(clean, current_docker, receipt["policy"])
    except GuardError as error:
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", str(error))
        raise
    host_residual = receipt["host_free_bytes_at_prepare"] - free
    if host_residual > receipt["policy"]["max_docker_physical_residual_bytes"]:
        _save_receipt(state_root, receipt, "CLEANUP_REQUIRED", "host residual exceeds cleanup budget")
        _fail("CLEANUP_REQUIRED: host residual growth exceeds the cleanup budget")

    _save_receipt(state_root, receipt, "COMPLETE")
    lease = _read_json(state_root / "active-lease.json", require_owner_only=True)
    if lease.get("run_id") != args.run_id:
        _fail("active lease changed before release")
    (state_root / "active-lease.json").unlink()
    _fsync_directory(state_root)
    print(f"COMPLETE {args.run_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="inventory state and acquire an exclusive lease")
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--vm-name", required=True)
    prepare.add_argument("--candidate", required=True)
    prepare.add_argument("--state-root", required=True)
    prepare.add_argument("--policy", required=True)
    prepare.add_argument("--tart", required=True)
    prepare.add_argument("--docker", required=True)
    prepare.add_argument("--docker-disk", required=True)
    prepare.set_defaults(handler=command_prepare)

    clone = subparsers.add_parser("clone", help="create the one receipt-owned disposable VM")
    clone.add_argument("--run-id", required=True)
    clone.add_argument("--state-root", required=True)
    clone.add_argument("--source-vm", required=True)
    clone.set_defaults(handler=command_clone)

    run = subparsers.add_parser("run", help="run one argv-only command under storage monitoring")
    run.add_argument("--run-id", required=True)
    run.add_argument("--state-root", required=True)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    run.set_defaults(handler=command_run)

    cleanup = subparsers.add_parser("cleanup", help="delete only the receipt-owned VM and release")
    cleanup.add_argument("--run-id", required=True)
    cleanup.add_argument("--confirm-run-id", required=True)
    cleanup.add_argument("--state-root", required=True)
    cleanup.set_defaults(handler=command_cleanup)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except GuardError as error:
        print(f"qa-storage-guard: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
