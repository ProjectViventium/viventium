#!/usr/bin/env python3
"""Safe, predecessor-aware Telegram poller handoff.

The BotFather token is accepted only through ``BOT_TOKEN`` and is never written
to a receipt, transaction, command line, or log.  A process is signalable only
when its durable receipt and current PID/start/cwd/command identity all agree.
"""

from __future__ import annotations

import argparse
import ctypes
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, NamedTuple


OWNER_KIND = "viventium-telegram-poller-owner"
TRANSACTION_KIND = "viventium-telegram-poller-handoff"
SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = frozenset({1, SCHEMA_VERSION})
HANDOFF_READY_PROOFS = frozenset({"polling_started", "webhook_started"})
HEALTH_READY_PROOFS = HANDOFF_READY_PROOFS | frozenset(
    {"legacy_process_grace", "legacy_process_identity"}
)


class HandoffError(RuntimeError):
    pass


class ProcessIdentity(NamedTuple):
    pid: int
    uid: int
    start_id: str
    command: str
    cwd: str


def token_sha256(token: str) -> str:
    normalized = (token or "").strip()
    if not normalized:
        raise HandoffError("BOT_TOKEN is required")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _payload_execution_root(payload: Mapping[str, Any]) -> Path:
    """Return execution identity, falling back only for schema-v1 receipts."""
    execution_root = str(payload.get("execution_root") or "").strip()
    if execution_root:
        return Path(execution_root).resolve(strict=False)
    try:
        schema_version = int(payload.get("schema_version"))
    except (TypeError, ValueError) as error:
        raise HandoffError("Telegram owner state has no valid schema version") from error
    repo_root = str(payload.get("repo_root") or "").strip()
    if schema_version == 1 and repo_root:
        return Path(repo_root).resolve(strict=False)
    raise HandoffError(
        "Telegram schema-v2 owner state requires an explicit execution_root"
    )


def _transaction_payload_schema(
    transaction: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Inherit schema 1 only for nested payloads written by legacy transactions."""
    if payload.get("schema_version") in SUPPORTED_SCHEMA_VERSIONS:
        return payload
    if transaction.get("schema_version") == 1:
        normalized = dict(payload)
        normalized["schema_version"] = 1
        return normalized
    return payload


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise HandoffError(f"Unsafe state directory: {path}")
    if path.stat().st_uid != os.getuid():
        raise HandoffError(f"State directory is not owned by the current user: {path}")
    path.chmod(0o700)


@contextmanager
def _exclusive_state_lock(state_dir: Path):
    _ensure_private_dir(state_dir)
    lock_path = state_dir / "handoff.lock"
    if lock_path.is_symlink():
        raise HandoffError("Telegram handoff lock is a symlink")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise HandoffError("Telegram handoff lock is not owner-only")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _ensure_private_dir(path.parent)
    if path.is_symlink():
        raise HandoffError(f"Refusing symlink receipt: {path}")
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _load_secure_json(path: Path, *, expected_kind: str) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise HandoffError(f"Missing receipt: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise HandoffError(f"Receipt is not a regular file: {path}")
    if metadata.st_uid != os.getuid():
        raise HandoffError(f"Receipt is not owned by the current user: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise HandoffError(f"Receipt permissions are not owner-only: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HandoffError(f"Receipt is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise HandoffError(f"Receipt payload is not an object: {path}")
    if (
        payload.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS
        or payload.get("kind") != expected_kind
    ):
        raise HandoffError(f"Receipt schema/kind mismatch: {path}")
    return payload


def _linux_process_identity(pid: int) -> ProcessIdentity | None:
    proc = Path("/proc") / str(pid)
    try:
        proc_stat = (proc / "stat").read_text(encoding="utf-8")
        end_comm = proc_stat.rfind(")")
        fields = proc_stat[end_comm + 2 :].split()
        # Field 22 (starttime); fields begins at field 3 after the command.
        start_ticks = fields[19]
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            boot_id = "unknown-boot"
        command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace"
        ).strip()
        cwd = os.readlink(proc / "cwd")
        uid = proc.stat().st_uid
    except (OSError, IndexError, ValueError):
        return None
    return ProcessIdentity(pid, uid, f"{boot_id}:{start_ticks}", command, cwd)


def _command_output(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _darwin_process_identity(pid: int) -> ProcessIdentity | None:
    class ProcBSDInfo(ctypes.Structure):
        _fields_ = [
            ("flags", ctypes.c_uint32),
            ("status", ctypes.c_uint32),
            ("xstatus", ctypes.c_uint32),
            ("pid", ctypes.c_uint32),
            ("ppid", ctypes.c_uint32),
            ("uid", ctypes.c_uint32),
            ("gid", ctypes.c_uint32),
            ("ruid", ctypes.c_uint32),
            ("rgid", ctypes.c_uint32),
            ("svuid", ctypes.c_uint32),
            ("svgid", ctypes.c_uint32),
            ("rfu", ctypes.c_uint32),
            ("comm", ctypes.c_char * 16),
            ("name", ctypes.c_char * 32),
            ("nfiles", ctypes.c_uint32),
            ("pgid", ctypes.c_uint32),
            ("pjobc", ctypes.c_uint32),
            ("tdev", ctypes.c_uint32),
            ("tpgid", ctypes.c_uint32),
            ("nice", ctypes.c_int32),
            ("start_sec", ctypes.c_uint64),
            ("start_usec", ctypes.c_uint64),
        ]

    start_id = ""
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
        libproc.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        libproc.proc_pidinfo.restype = ctypes.c_int
        info = ProcBSDInfo()
        copied = libproc.proc_pidinfo(
            pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)
        )
        if copied == ctypes.sizeof(info) and info.pid == pid:
            start_id = f"darwin:{info.start_sec}:{info.start_usec}"
    except (OSError, AttributeError):
        pass
    if not start_id:
        # Compatibility fallback for restricted environments. Receipt matching
        # still also requires uid, exact cwd, and recognized command.
        start_id = _command_output(
            ["/bin/ps", "-p", str(pid), "-o", "lstart="]
        )
    command = _command_output(["/bin/ps", "-p", str(pid), "-o", "command="])
    uid_text = _command_output(["/bin/ps", "-p", str(pid), "-o", "uid="])
    lsof = _command_output(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"]
    )
    cwd = ""
    for line in lsof.splitlines():
        if line.startswith("n"):
            cwd = line[1:].strip()
            break
    if not start_id or not command or not cwd or not uid_text.isdigit():
        return None
    return ProcessIdentity(pid, int(uid_text), start_id, command, cwd)


class SystemProcessInspector:
    def inspect(self, pid: int) -> ProcessIdentity | None:
        if int(pid) <= 1:
            return None
        if sys.platform.startswith("linux"):
            return _linux_process_identity(int(pid))
        return _darwin_process_identity(int(pid))


def _looks_like_telegram_poller(process: ProcessIdentity) -> bool:
    command_parts = process.command.replace("\\", "/").split()
    has_bot_entrypoint = any(
        part == "bot.py" or part.endswith("/TelegramVivBot/bot.py")
        for part in command_parts
    )
    cwd = Path(process.cwd)
    return (
        process.uid == os.getuid()
        and has_bot_entrypoint
        and cwd.name == "TelegramVivBot"
        and cwd.parent.name == "telegram-viventium"
    )


def _process_matches_payload(
    process: ProcessIdentity, payload: Mapping[str, Any]
) -> bool:
    try:
        pid = int(payload.get("pid"))
    except (TypeError, ValueError):
        return False
    expected_cwd = str(payload.get("working_directory") or "")
    expected_repo_text = str(payload.get("repo_root") or "").strip()
    if not expected_repo_text:
        return False
    try:
        expected_execution_root = _payload_execution_root(payload)
    except HandoffError:
        return False
    if (
        pid != process.pid
        or str(payload.get("process_start_id") or "") != process.start_id
        or not expected_cwd
        or Path(process.cwd).resolve(strict=False)
        != Path(expected_cwd).resolve(strict=False)
        or not _looks_like_telegram_poller(process)
    ):
        return False
    return _path_within(Path(process.cwd), expected_execution_root)


def write_owner_receipt(
    path: Path,
    *,
    token: str,
    process: ProcessIdentity,
    repo_root: Path,
    execution_root: Path | None = None,
    launch_script: Path,
    ready: bool,
    readiness_proof: str = "initializing",
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": OWNER_KIND,
        "token_sha256": token_sha256(token),
        "pid": process.pid,
        "process_start_id": process.start_id,
        "repo_root": str(repo_root.resolve(strict=False)),
        "execution_root": str(
            (execution_root or repo_root).resolve(strict=False)
        ),
        "working_directory": str(Path(process.cwd).resolve(strict=False)),
        "launch_script": str(launch_script.resolve(strict=False)),
        "ready": bool(ready),
        "readiness_proof": readiness_proof,
        "updated_at_unix": int(time.time()),
    }
    _atomic_write_json(path, payload)


def _owner_has_handoff_readiness(owner: Mapping[str, Any] | None) -> bool:
    return bool(
        owner
        and owner.get("ready") is True
        and owner.get("readiness_proof") in HANDOFF_READY_PROOFS
    )


def _owner_has_health_readiness(owner: Mapping[str, Any] | None) -> bool:
    return bool(
        owner
        and owner.get("ready") is True
        and owner.get("readiness_proof") in HEALTH_READY_PROOFS
    )


def load_recognized_owner(
    receipt_path: Path,
    *,
    token_hash: str,
    inspector: Any | None = None,
) -> dict[str, Any] | None:
    try:
        payload = _load_secure_json(receipt_path, expected_kind=OWNER_KIND)
    except HandoffError:
        return None
    if payload.get("token_sha256") != token_hash:
        return None
    process_inspector = inspector or SystemProcessInspector()
    try:
        process = process_inspector.inspect(int(payload.get("pid")))
    except (TypeError, ValueError):
        return None
    if process is None or not _process_matches_payload(process, payload):
        return None
    return payload


def _load_transition_owner(
    receipt_path: Path, *, token_hash: str, inspector: Any
) -> dict[str, Any] | None:
    if not os.path.lexists(receipt_path):
        return None
    # Transition paths fail closed on an unsafe or wrong-token receipt. They
    # may not silently downgrade to legacy pid-file trust after tampering.
    payload = _load_secure_json(receipt_path, expected_kind=OWNER_KIND)
    if payload.get("token_sha256") != token_hash:
        raise HandoffError("Telegram owner receipt token hash mismatch")
    process = inspector.inspect(int(payload.get("pid") or 0))
    if process is None or not _process_matches_payload(process, payload):
        return None
    return payload


def terminate_recognized_owner(
    owner: Mapping[str, Any] | None,
    *,
    inspector: Any | None = None,
    signal_process: Callable[[int, int], None] = os.kill,
    wait_timeout: float = 12.0,
) -> bool:
    if not owner:
        return False
    process_inspector = inspector or SystemProcessInspector()
    try:
        pid = int(owner["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    # Reinspect immediately before signalling so a stale receipt cannot hit a
    # different process after PID reuse.
    current = process_inspector.inspect(pid)
    if current is None or not _process_matches_payload(current, owner):
        return False
    try:
        signal_process(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except (OSError, PermissionError):
        return False
    deadline = time.monotonic() + max(0.0, wait_timeout)
    while time.monotonic() < deadline:
        current = process_inspector.inspect(pid)
        if current is None or current.start_id != owner.get("process_start_id"):
            return True
        time.sleep(0.1)
    return False


def _trusted_launch_script(path_value: str, state_dir: Path) -> Path:
    path = Path(path_value)
    trusted_runtime_root = state_dir.resolve(strict=False).parent
    if not _path_within(path, trusted_runtime_root):
        raise HandoffError("Predecessor launch script is outside the trusted state directory")
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise HandoffError("Predecessor launch script is missing") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise HandoffError("Predecessor launch script is not a trusted owner file")
    return path


def _file_sha256(path: Path) -> str:
    """Hash an owner-only regular file without following symlinks."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise HandoffError("Predecessor launch script cannot be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise HandoffError("Predecessor launch script is not a trusted owner file")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _trusted_bound_launch_script(
    path_value: str,
    state_dir: Path,
    *,
    expected_sha256: str | None = None,
    package_sha256: Mapping[str, Any] | None = None,
) -> Path:
    path = _trusted_launch_script(path_value, state_dir)
    if expected_sha256 is not None:
        normalized = expected_sha256.strip().lower()
        if (
            len(normalized) != 64
            or any(character not in "0123456789abcdef" for character in normalized)
        ):
            raise HandoffError("Predecessor launch script content hash is invalid")
        if _file_sha256(path) != normalized:
            raise HandoffError("Predecessor launch script content hash mismatch")
    if package_sha256 is not None:
        expected_names = {
            "telegram_bot_launch.sh",
            "telegram_bot_runtime.env",
            "telegram_overlay.env",
        }
        if set(package_sha256) != expected_names:
            raise HandoffError("Predecessor launch package manifest is invalid")
        if path.name != "telegram_bot_launch.sh":
            raise HandoffError("Predecessor launch package entrypoint is invalid")
        for name in sorted(expected_names):
            artifact = _trusted_launch_script(str(path.parent / name), state_dir)
            expected = str(package_sha256[name]).strip().lower()
            if (
                len(expected) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in expected
                )
                or _file_sha256(artifact) != expected
            ):
                raise HandoffError(
                    f"Predecessor launch package content hash mismatch: {name}"
                )
    return path


def _snapshot_launch_script(
    source: Path,
    destination: Path,
    *,
    state_dir: Path,
    destination_mode: int = 0o700,
) -> str:
    source = _trusted_launch_script(str(source), state_dir)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    source_descriptor = os.open(source, flags)
    try:
        before = os.fstat(source_descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) & 0o022
        ):
            raise HandoffError("Predecessor launch script is not a trusted owner file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(source_descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 4 * 1024 * 1024:
                raise HandoffError("Predecessor launch script is unexpectedly large")
            chunks.append(chunk)
        after = os.fstat(source_descriptor)
        if (
            before.st_ino != after.st_ino
            or before.st_dev != after.st_dev
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise HandoffError("Predecessor launch script changed while being sealed")
    finally:
        os.close(source_descriptor)

    _ensure_private_dir(destination.parent)
    destination_descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        destination_mode,
    )
    try:
        for chunk in chunks:
            view = memoryview(chunk)
            while view:
                written = os.write(destination_descriptor, view)
                view = view[written:]
        os.fchmod(destination_descriptor, destination_mode)
        os.fsync(destination_descriptor)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        os.close(destination_descriptor)
    expected_sha256 = hashlib.sha256(b"".join(chunks)).hexdigest()
    _trusted_bound_launch_script(
        str(destination),
        state_dir,
        expected_sha256=expected_sha256,
    )
    return expected_sha256


def _snapshot_launch_package(
    source: Path,
    destination_dir: Path,
    *,
    state_dir: Path,
) -> tuple[Path, str, dict[str, str] | None]:
    destination = destination_dir / "telegram_bot_launch.sh"
    launcher_sha256 = _snapshot_launch_script(
        source,
        destination,
        state_dir=state_dir,
    )
    launcher_text = destination.read_text(encoding="utf-8")
    if "# viventium-launch-package-schema: 1" not in launcher_text:
        return destination, launcher_sha256, None
    package_sha256 = {"telegram_bot_launch.sh": launcher_sha256}
    for name in ("telegram_bot_runtime.env", "telegram_overlay.env"):
        package_sha256[name] = _snapshot_launch_script(
            source.parent / name,
            destination_dir / name,
            state_dir=state_dir,
            destination_mode=0o600,
        )
    _trusted_bound_launch_script(
        str(destination),
        state_dir,
        expected_sha256=launcher_sha256,
        package_sha256=package_sha256,
    )
    return destination, launcher_sha256, package_sha256


def _predecessor_allows_legacy_grace(
    predecessor: Mapping[str, Any],
) -> bool:
    proof = str(predecessor.get("readiness_proof") or "")
    return bool(
        proof == "legacy_process_identity"
        and predecessor.get("legacy_migrated") is True
    ) or bool(
        proof == "legacy_process_grace"
        and predecessor.get("restored_legacy_compatibility") is True
    )


def _cleanup_transaction_launcher(
    transaction: Mapping[str, Any],
    *,
    state_dir: Path,
) -> None:
    predecessor = transaction.get("predecessor")
    if not isinstance(predecessor, dict):
        return
    if predecessor.get("launch_script_is_transaction_snapshot") is not True:
        return
    path = Path(str(predecessor.get("launch_script") or ""))
    package_dir = path.parent
    if not _path_within(package_dir, state_dir / "transactions"):
        raise HandoffError("Transaction launcher snapshot escaped its state directory")
    package_sha256 = predecessor.get("launch_package_sha256")
    names = (
        set(package_sha256)
        if isinstance(package_sha256, dict)
        else {path.name}
    )
    for name in names:
        artifact = package_dir / str(name)
        try:
            metadata = artifact.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise HandoffError("Transaction launcher snapshot is not an owner file")
        artifact.unlink()
    try:
        package_dir.rmdir()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise HandoffError("Transaction launcher package is not empty") from exc


def _cleanup_generated_launch_package(
    path_value: str,
    *,
    state_dir: Path,
) -> None:
    path = Path(path_value)
    launch_root = state_dir / "launches"
    try:
        relative = path.resolve(strict=False).relative_to(
            launch_root.resolve(strict=False)
        )
    except ValueError:
        return
    if len(relative.parts) != 2 or relative.name != "telegram_bot_launch.sh":
        return
    package_dir = path.parent
    if package_dir.is_symlink() or not package_dir.is_dir():
        return
    metadata = package_dir.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        return
    names = {
        "telegram_bot_launch.sh",
        "telegram_bot_runtime.env",
        "telegram_overlay.env",
    }
    try:
        entries = {entry.name for entry in os.scandir(package_dir)}
    except OSError:
        return
    if entries != names:
        return
    launcher = package_dir / "telegram_bot_launch.sh"
    try:
        if "# viventium-launch-package-schema: 1" not in launcher.read_text(
            encoding="utf-8"
        ):
            return
    except (OSError, UnicodeError):
        return
    for name in names:
        artifact = package_dir / name
        try:
            artifact_metadata = artifact.lstat()
        except FileNotFoundError:
            return
        if (
            stat.S_ISLNK(artifact_metadata.st_mode)
            or not stat.S_ISREG(artifact_metadata.st_mode)
            or artifact_metadata.st_uid != os.getuid()
        ):
            return
    for name in names:
        (package_dir / name).unlink()
    package_dir.rmdir()


def _default_launch_predecessor(
    predecessor: Mapping[str, Any], *, state_dir: Path
) -> int:
    launch_script = _trusted_bound_launch_script(
        str(predecessor.get("launch_script") or ""),
        state_dir,
        expected_sha256=(
            str(predecessor["launch_script_sha256"])
            if predecessor.get("launch_script_sha256") is not None
            else None
        ),
        package_sha256=(
            predecessor.get("launch_package_sha256")
            if isinstance(predecessor.get("launch_package_sha256"), dict)
            else None
        ),
    )
    working_directory = Path(str(predecessor.get("working_directory") or ""))
    execution_root = _payload_execution_root(predecessor)
    if (
        not working_directory.is_dir()
        or not execution_root.is_dir()
        or not _path_within(working_directory, execution_root)
    ):
        raise HandoffError("Predecessor working directory is no longer recognized")
    log_path = state_dir.parent / "logs" / "telegram_bot.log"
    _ensure_private_dir(log_path.parent)
    log_handle = log_path.open("ab", buffering=0)
    try:
        child = subprocess.Popen(
            ["/bin/bash", str(launch_script)],
            cwd=working_directory,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_handle.close()
    return int(child.pid)


def _rollback_transaction_unlocked(
    transaction_path: Path,
    *,
    state_dir: Path,
    inspector: Any | None = None,
    launch_predecessor: Callable[[Mapping[str, Any]], int] | None = None,
    signal_process: Callable[[int, int], None] = os.kill,
) -> dict[str, Any]:
    payload = _load_secure_json(transaction_path, expected_kind=TRANSACTION_KIND)
    predecessor = payload.get("predecessor")
    if not isinstance(predecessor, dict):
        transaction_path.unlink(missing_ok=True)
        return {"restored": False, "reason": "no-predecessor"}

    # Validate the launch target before touching any candidate process.
    _trusted_bound_launch_script(
        str(predecessor.get("launch_script") or ""),
        state_dir,
        expected_sha256=(
            str(predecessor["launch_script_sha256"])
            if predecessor.get("launch_script_sha256") is not None
            else None
        ),
        package_sha256=(
            predecessor.get("launch_package_sha256")
            if isinstance(predecessor.get("launch_package_sha256"), dict)
            else None
        ),
    )

    candidate = payload.get("candidate")
    if isinstance(candidate, dict):
        candidate = _transaction_payload_schema(payload, candidate)
        candidate_receipt = Path(str(candidate.get("receipt_file") or ""))
        candidate_owner = load_recognized_owner(
            candidate_receipt,
            token_hash=str(payload.get("token_sha256") or ""),
            inspector=inspector,
        )
        if (
            candidate_owner
            and candidate_owner.get("repo_root") == candidate.get("repo_root")
            and _payload_execution_root(candidate_owner)
            == _payload_execution_root(candidate)
        ):
            terminate_recognized_owner(
                candidate_owner,
                inspector=inspector,
                signal_process=signal_process,
            )
        elif isinstance(candidate.get("process"), dict):
            candidate_process = _transaction_payload_schema(
                payload,
                candidate["process"],
            )
            terminate_recognized_owner(
                candidate_process,
                inspector=inspector,
                signal_process=signal_process,
            )

    launcher = launch_predecessor or (
        lambda predecessor_payload: _default_launch_predecessor(
            predecessor_payload, state_dir=state_dir
        )
    )
    restored_pid = int(launcher(predecessor))
    if launch_predecessor is None:
        process_inspector = inspector or SystemProcessInspector()
        deadline = time.monotonic() + 25.0
        restored_process: ProcessIdentity | None = None
        while time.monotonic() < deadline:
            current = process_inspector.inspect(restored_pid)
            predecessor_execution_root = _payload_execution_root(predecessor)
            if (
                current is not None
                and _looks_like_telegram_poller(current)
                and _path_within(Path(current.cwd), predecessor_execution_root)
            ):
                restored_process = current
                break
            time.sleep(0.1)
        if restored_process is None:
            raise HandoffError("Recognized predecessor did not restart")
        owner_path = _owner_receipt_path(
            state_dir, str(payload.get("token_sha256") or "")
        )
        native_ready_deadline = time.monotonic() + 8.0
        native_ready = False
        while time.monotonic() < native_ready_deadline:
            owner = load_recognized_owner(
                owner_path,
                token_hash=str(payload.get("token_sha256") or ""),
                inspector=process_inspector,
            )
            if _owner_has_handoff_readiness(owner):
                native_ready = True
                break
            time.sleep(0.1)
        if not native_ready:
            current = process_inspector.inspect(restored_pid)
            if current is None or current.start_id != restored_process.start_id:
                raise HandoffError("Legacy predecessor exited during readiness grace")
            if not _predecessor_allows_legacy_grace(predecessor):
                terminate_recognized_owner(
                    {
                        **dict(predecessor),
                        "pid": restored_process.pid,
                        "process_start_id": restored_process.start_id,
                        "working_directory": restored_process.cwd,
                    },
                    inspector=process_inspector,
                    signal_process=signal_process,
                )
                raise HandoffError(
                    "Restored native predecessor did not publish native readiness"
                )
            restored_owner = {
                "schema_version": SCHEMA_VERSION,
                "kind": OWNER_KIND,
                "token_sha256": str(payload.get("token_sha256") or ""),
                "pid": restored_process.pid,
                "process_start_id": restored_process.start_id,
                "repo_root": str(
                    Path(str(predecessor.get("repo_root") or "")).resolve(
                        strict=False
                    )
                ),
                "execution_root": str(
                    _payload_execution_root(predecessor)
                ),
                "working_directory": str(
                    Path(restored_process.cwd).resolve(strict=False)
                ),
                "launch_script": str(
                    Path(
                        str(
                            predecessor.get("original_launch_script")
                            or predecessor.get("launch_script")
                            or ""
                        )
                    ).resolve(
                        strict=False
                    )
                ),
                # Legacy launchers cannot publish post-init readiness. Surviving
                # a compatibility grace after recognized bot.py exec is their
                # strongest available rollback proof.
                "ready": True,
                "readiness_proof": "legacy_process_grace",
                "restored_legacy_compatibility": True,
                "updated_at_unix": int(time.time()),
            }
            _atomic_write_json(owner_path, restored_owner)
    candidate_payload = payload.get("candidate")
    if isinstance(candidate_payload, dict):
        _cleanup_generated_launch_package(
            str(candidate_payload.get("launch_script") or ""),
            state_dir=state_dir,
        )
    _cleanup_transaction_launcher(payload, state_dir=state_dir)
    transaction_path.unlink(missing_ok=True)
    return {"restored": True, "pid": restored_pid}


def rollback_transaction(
    transaction_path: Path,
    *,
    state_dir: Path,
    inspector: Any | None = None,
    launch_predecessor: Callable[[Mapping[str, Any]], int] | None = None,
    signal_process: Callable[[int, int], None] = os.kill,
) -> dict[str, Any]:
    with _exclusive_state_lock(state_dir):
        if not transaction_path.exists():
            return {"restored": False, "reason": "transaction-already-resolved"}
        return _rollback_transaction_unlocked(
            transaction_path,
            state_dir=state_dir,
            inspector=inspector,
            launch_predecessor=launch_predecessor,
            signal_process=signal_process,
        )


def _owner_receipt_path(state_dir: Path, token_hash: str) -> Path:
    return state_dir / f"owner-{token_hash[:24]}.json"


def _read_legacy_pid(pid_file: Path) -> int | None:
    try:
        metadata = pid_file.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            return None
        if metadata.st_uid != os.getuid():
            return None
        value = pid_file.read_text(encoding="utf-8").strip().splitlines()[0]
        pid = int(value)
    except (OSError, ValueError, IndexError):
        return None
    return pid if pid > 1 else None


def _legacy_owner(
    *,
    pid_file: Path,
    launch_script: Path,
    token_hash: str,
    inspector: Any,
) -> dict[str, Any] | None:
    pid = _read_legacy_pid(pid_file)
    if pid is None:
        return None
    process = inspector.inspect(pid)
    if process is None or not _looks_like_telegram_poller(process):
        return None
    cwd = Path(process.cwd).resolve(strict=False)
    try:
        repo_root = cwd.parents[2]
    except IndexError:
        return None
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": OWNER_KIND,
        "token_sha256": token_hash,
        "pid": process.pid,
        "process_start_id": process.start_id,
        "repo_root": str(repo_root),
        "execution_root": str(repo_root),
        "working_directory": str(cwd),
        "launch_script": str(launch_script.resolve(strict=False)),
        "ready": True,
        "readiness_proof": "legacy_process_identity",
        "legacy_migrated": True,
    }


def _status(
    *,
    state_dir: Path,
    token_hash: str,
    pid_file: Path,
    legacy_launch_script: Path,
    inspector: Any,
) -> dict[str, Any]:
    receipt = _owner_receipt_path(state_dir, token_hash)
    owner = _load_transition_owner(
        receipt, token_hash=token_hash, inspector=inspector
    )
    if owner is None:
        owner = _legacy_owner(
            pid_file=pid_file,
            launch_script=legacy_launch_script,
            token_hash=token_hash,
            inspector=inspector,
        )
    if owner is None:
        return {"running": False}
    return {
        "running": True,
        "pid": owner["pid"],
        "ready": _owner_has_health_readiness(owner),
        "repo_root": owner["repo_root"],
        "legacy": bool(owner.get("legacy_migrated")),
    }


def _prepare_unlocked(args: argparse.Namespace, token: str) -> dict[str, Any]:
    state_dir = Path(args.state_dir)
    _ensure_private_dir(state_dir)
    transaction_dir = state_dir / "transactions"
    if transaction_dir.exists():
        active_transactions = list(transaction_dir.glob("handoff-*.json"))
        if active_transactions:
            for active in active_transactions:
                _load_secure_json(active, expected_kind=TRANSACTION_KIND)
            raise HandoffError("A Telegram poller handoff is already in progress")
    token_hash = token_sha256(token)
    inspector = SystemProcessInspector()
    receipt_path = _owner_receipt_path(state_dir, token_hash)
    owner = _load_transition_owner(
        receipt_path, token_hash=token_hash, inspector=inspector
    )
    if owner is None:
        owner = _legacy_owner(
            pid_file=Path(args.pid_file),
            launch_script=Path(args.legacy_launch_script),
            token_hash=token_hash,
            inspector=inspector,
        )
    candidate_repo = str(Path(args.candidate_repo).resolve(strict=False))
    candidate_execution_root = Path(args.candidate_execution_root).resolve(
        strict=False
    )
    if not candidate_execution_root.is_dir() or candidate_execution_root.is_symlink():
        raise HandoffError("Candidate Telegram execution root is unavailable")
    if owner is None:
        return {
            "action": "start",
            "receipt_file": str(receipt_path),
            "transaction": "",
        }
    if not args.takeover:
        return {
            "action": "already-running",
            "pid": owner["pid"],
            "repo_root": owner["repo_root"],
            "receipt_file": str(receipt_path),
            "transaction": "",
        }

    # A handoff is allowed only when its rollback target is already proven
    # safe and executable. Never stop the predecessor first and discover later
    # that it cannot be restored.
    predecessor_launch_script = _trusted_launch_script(
        str(owner.get("launch_script") or ""), state_dir
    )
    _ensure_private_dir(transaction_dir)
    transaction_path = transaction_dir / (
        f"handoff-{token_hash[:12]}-{int(time.time())}-{secrets.token_hex(4)}.json"
    )
    launcher_snapshot_dir = transaction_path.with_suffix(".rollback-package")
    (
        launcher_snapshot,
        launcher_sha256,
        launch_package_sha256,
    ) = _snapshot_launch_package(
        predecessor_launch_script,
        launcher_snapshot_dir,
        state_dir=state_dir,
    )
    sealed_predecessor = dict(owner)
    sealed_predecessor.update(
        {
            "original_launch_script": str(predecessor_launch_script),
            "launch_script": str(launcher_snapshot),
            "launch_script_sha256": launcher_sha256,
            "launch_script_is_transaction_snapshot": True,
        }
    )
    if launch_package_sha256 is not None:
        sealed_predecessor["launch_package_sha256"] = launch_package_sha256
    transaction = {
        "schema_version": SCHEMA_VERSION,
        "kind": TRANSACTION_KIND,
        "token_sha256": token_hash,
        "candidate": {
            "repo_root": candidate_repo,
            "execution_root": str(candidate_execution_root),
            "receipt_file": str(receipt_path),
            "launch_script": str(Path(args.candidate_launch_script).resolve(strict=False)),
        },
        "predecessor": sealed_predecessor,
        "created_at_unix": int(time.time()),
    }
    try:
        _atomic_write_json(transaction_path, transaction)
    except BaseException:
        _cleanup_transaction_launcher(transaction, state_dir=state_dir)
        raise
    if not terminate_recognized_owner(owner, inspector=inspector):
        _cleanup_transaction_launcher(transaction, state_dir=state_dir)
        transaction_path.unlink(missing_ok=True)
        raise HandoffError("Recognized predecessor did not stop gracefully")

    guard = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "guard",
            "--state-dir",
            str(state_dir),
            "--transaction",
            str(transaction_path),
            "--timeout",
            str(args.guard_timeout),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    transaction["guard_pid"] = int(guard.pid)
    _atomic_write_json(transaction_path, transaction)
    return {
        "action": "start",
        "receipt_file": str(receipt_path),
        "transaction": str(transaction_path),
        "predecessor_pid": owner["pid"],
    }


def _prepare(args: argparse.Namespace, token: str) -> dict[str, Any]:
    state_dir = Path(args.state_dir)
    with _exclusive_state_lock(state_dir):
        return _prepare_unlocked(args, token)


def _attached_candidate_process(
    transaction: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    candidate = transaction.get("candidate")
    if not isinstance(candidate, dict):
        return None
    attached = candidate.get("process")
    if not isinstance(attached, dict):
        return None
    candidate = _transaction_payload_schema(transaction, candidate)
    attached = _transaction_payload_schema(transaction, attached)
    try:
        pid = int(attached.get("pid"))
    except (TypeError, ValueError):
        return None
    if (
        pid <= 1
        or not str(attached.get("process_start_id") or "")
        or not str(attached.get("repo_root") or "")
        or not str(
            attached.get("execution_root")
            or attached.get("repo_root")
            or ""
        )
        or not str(attached.get("working_directory") or "")
        or not str(candidate.get("repo_root") or "")
        or not str(
            candidate.get("execution_root")
            or candidate.get("repo_root")
            or ""
        )
        or not str(candidate.get("receipt_file") or "")
    ):
        return None
    return candidate, attached


def _owner_matches_attached_candidate(
    owner: Mapping[str, Any] | None,
    *,
    candidate: Mapping[str, Any],
    attached: Mapping[str, Any],
) -> bool:
    if not _owner_has_handoff_readiness(owner):
        return False
    assert owner is not None
    try:
        owner_pid = int(owner.get("pid"))
        attached_pid = int(attached.get("pid"))
    except (TypeError, ValueError):
        return False
    candidate_repo = Path(str(candidate.get("repo_root") or "")).resolve(
        strict=False
    )
    candidate_execution_root = _payload_execution_root(candidate)
    return bool(
        owner_pid == attached_pid
        and str(owner.get("process_start_id") or "")
        == str(attached.get("process_start_id") or "")
        and Path(str(owner.get("repo_root") or "")).resolve(strict=False)
        == candidate_repo
        and Path(str(attached.get("repo_root") or candidate_repo)).resolve(
            strict=False
        )
        == candidate_repo
        and _payload_execution_root(owner) == candidate_execution_root
        and _payload_execution_root(attached) == candidate_execution_root
        and Path(str(owner.get("working_directory") or "")).resolve(
            strict=False
        )
        == Path(str(attached.get("working_directory") or "")).resolve(
            strict=False
        )
    )


def _transaction_candidate_ready(
    transaction: Mapping[str, Any],
    *,
    inspector: Any,
) -> dict[str, Any] | None:
    attached_parts = _attached_candidate_process(transaction)
    if attached_parts is None:
        return None
    candidate, attached = attached_parts
    receipt = Path(str(candidate.get("receipt_file") or ""))
    owner = load_recognized_owner(
        receipt,
        token_hash=str(transaction.get("token_sha256") or ""),
        inspector=inspector,
    )
    if not _owner_matches_attached_candidate(
        owner,
        candidate=candidate,
        attached=attached,
    ):
        return None
    assert owner is not None
    current = inspector.inspect(int(attached["pid"]))
    if (
        current is None
        or current.start_id != str(attached.get("process_start_id") or "")
        or Path(current.cwd).resolve(strict=False)
        != Path(str(attached.get("working_directory") or "")).resolve(
            strict=False
        )
        or not _process_matches_payload(current, owner)
    ):
        return None
    return owner


def _wait_ready(
    *,
    state_dir: Path,
    token_hash: str,
    candidate_repo: Path,
    timeout: float,
    candidate_execution_root: Path | None = None,
    candidate_pid: int | None = None,
    transaction_path: Path | None = None,
) -> dict[str, Any]:
    receipt = _owner_receipt_path(state_dir, token_hash)
    inspector = SystemProcessInspector()
    deadline = time.monotonic() + max(0.1, timeout)
    candidate = str(candidate_repo.resolve(strict=False))
    execution_root = (candidate_execution_root or candidate_repo).resolve(
        strict=False
    )
    expected_process: dict[str, Any] | None = None
    if transaction_path is not None:
        with _exclusive_state_lock(state_dir):
            if transaction_path.exists():
                transaction = _load_secure_json(
                    transaction_path, expected_kind=TRANSACTION_KIND
                )
                attached_parts = _attached_candidate_process(transaction)
                if attached_parts is None:
                    raise HandoffError(
                        "Candidate Telegram poller was not attached before readiness"
                    )
                transaction_candidate, attached = attached_parts
                if (
                    Path(
                        str(transaction_candidate.get("repo_root") or "")
                    ).resolve(strict=False)
                    != candidate_repo.resolve(strict=False)
                    or _payload_execution_root(transaction_candidate)
                    != execution_root
                    or (
                        candidate_pid is not None
                        and int(attached.get("pid") or 0) != candidate_pid
                    )
                ):
                    raise HandoffError(
                        "Candidate Telegram poller attachment does not match readiness target"
                    )
                expected_process = dict(attached)
    if candidate_pid is not None:
        candidate_process = inspector.inspect(candidate_pid)
        if (
            candidate_process is None
            or not _looks_like_telegram_poller(candidate_process)
            or not _path_within(Path(candidate_process.cwd), execution_root)
            or (
                expected_process is not None
                and (
                    candidate_process.start_id
                    != str(expected_process.get("process_start_id") or "")
                    or Path(candidate_process.cwd).resolve(strict=False)
                    != Path(
                        str(expected_process.get("working_directory") or "")
                    ).resolve(strict=False)
                )
            )
        ):
            raise HandoffError(
                "Candidate Telegram poller identity is unavailable before readiness"
            )
        if expected_process is None:
            expected_process = {
                "pid": candidate_process.pid,
                "process_start_id": candidate_process.start_id,
                "repo_root": candidate,
                "execution_root": str(execution_root),
                "working_directory": candidate_process.cwd,
            }
    while time.monotonic() < deadline:
        owner = load_recognized_owner(
            receipt, token_hash=token_hash, inspector=inspector
        )
        if (
            expected_process is not None
            and _owner_matches_attached_candidate(
                owner,
                candidate={
                    "repo_root": candidate,
                    "execution_root": str(execution_root),
                },
                attached=expected_process,
            )
        ):
            assert owner is not None
            current = inspector.inspect(int(expected_process["pid"]))
            if current is None:
                raise HandoffError(
                    "Candidate Telegram poller exited before publishing readiness"
                )
            if (
                current.start_id
                != str(expected_process.get("process_start_id") or "")
                or Path(current.cwd).resolve(strict=False)
                != Path(
                    str(expected_process.get("working_directory") or "")
                ).resolve(strict=False)
                or not _process_matches_payload(current, owner)
            ):
                raise HandoffError(
                    "Candidate Telegram poller changed identity before publishing readiness"
                )
            return {"ready": True, "pid": int(owner["pid"])}
        if expected_process is not None:
            current = inspector.inspect(int(expected_process["pid"]))
            if current is None:
                raise HandoffError(
                    "Candidate Telegram poller exited before publishing readiness"
                )
            if (
                current.start_id
                != str(expected_process.get("process_start_id") or "")
                or Path(current.cwd).resolve(strict=False)
                != Path(
                    str(expected_process.get("working_directory") or "")
                ).resolve(strict=False)
            ):
                raise HandoffError(
                    "Candidate Telegram poller changed identity before publishing readiness"
                )
        time.sleep(0.1)
    raise HandoffError("Candidate Telegram poller did not publish readiness")


def _commit_unlocked(
    transaction_path: Path,
    *,
    inspector: Any | None = None,
) -> dict[str, Any]:
    if not transaction_path:
        return {"committed": True}
    if not transaction_path.exists():
        # The detached guard commits automatically once it observes candidate
        # readiness, covering interruption between readiness and this call.
        return {"committed": True, "guard_committed": True}
    transaction = _load_secure_json(
        transaction_path, expected_kind=TRANSACTION_KIND
    )
    process_inspector = inspector or SystemProcessInspector()
    if _transaction_candidate_ready(
        transaction,
        inspector=process_inspector,
    ) is None:
        raise HandoffError("Candidate Telegram poller is not ready at commit")
    predecessor = transaction.get("predecessor")
    if isinstance(predecessor, dict):
        _cleanup_generated_launch_package(
            str(
                predecessor.get("original_launch_script")
                or predecessor.get("launch_script")
                or ""
            ),
            state_dir=transaction_path.parent.parent,
        )
    _cleanup_transaction_launcher(
        transaction,
        state_dir=transaction_path.parent.parent,
    )
    transaction_path.unlink(missing_ok=True)
    return {"committed": True}


def _commit(transaction_path: Path) -> dict[str, Any]:
    state_dir = transaction_path.parent.parent
    with _exclusive_state_lock(state_dir):
        return _commit_unlocked(
            transaction_path,
            inspector=SystemProcessInspector(),
        )


def _attach_candidate_unlocked(
    transaction_path: Path, *, pid: int, timeout: float
) -> dict[str, Any]:
    inspector = SystemProcessInspector()
    deadline = time.monotonic() + max(0.1, timeout)
    process: ProcessIdentity | None = None
    transaction: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if not transaction_path.exists():
            return {"attached": True, "guard_committed": True}
        transaction = _load_secure_json(
            transaction_path, expected_kind=TRANSACTION_KIND
        )
        candidate = transaction.get("candidate")
        if not isinstance(candidate, dict):
            raise HandoffError("Handoff transaction has no candidate")
        candidate = _transaction_payload_schema(transaction, candidate)
        process = inspector.inspect(pid)
        candidate_execution_root = _payload_execution_root(candidate)
        if (
            process is not None
            and _looks_like_telegram_poller(process)
            and _path_within(Path(process.cwd), candidate_execution_root)
        ):
            break
        time.sleep(0.1)
    else:
        raise HandoffError("Candidate process identity could not be recognized")
    assert transaction is not None and process is not None
    transaction["candidate"]["process"] = {
        "pid": process.pid,
        "process_start_id": process.start_id,
        "repo_root": str(Path(transaction["candidate"]["repo_root"]).resolve(strict=False)),
        "execution_root": str(
            _payload_execution_root(
                _transaction_payload_schema(
                    transaction,
                    transaction["candidate"],
                )
            )
        ),
        "working_directory": str(Path(process.cwd).resolve(strict=False)),
    }
    _atomic_write_json(transaction_path, transaction)
    return {"attached": True, "pid": process.pid}


def _attach_candidate(
    transaction_path: Path, *, pid: int, timeout: float
) -> dict[str, Any]:
    state_dir = transaction_path.parent.parent
    with _exclusive_state_lock(state_dir):
        return _attach_candidate_unlocked(
            transaction_path, pid=pid, timeout=timeout
        )


def _guard(transaction_path: Path, state_dir: Path, timeout: float) -> None:
    deadline = time.monotonic() + max(1.0, timeout)
    inspector = SystemProcessInspector()
    while time.monotonic() < deadline:
        with _exclusive_state_lock(state_dir):
            if not transaction_path.exists():
                return
            try:
                transaction = _load_secure_json(
                    transaction_path, expected_kind=TRANSACTION_KIND
                )
            except HandoffError:
                return
            if _transaction_candidate_ready(
                transaction,
                inspector=inspector,
            ) is not None:
                _commit_unlocked(
                    transaction_path,
                    inspector=inspector,
                )
                return
        time.sleep(0.2)
    if transaction_path.exists():
        rollback_transaction(transaction_path, state_dir=state_dir)


def _stop_owned(state_dir: Path, pid_file: Path) -> dict[str, Any]:
    inspector = SystemProcessInspector()
    stopped: list[int] = []
    if state_dir.exists() and not state_dir.is_symlink():
        for receipt in state_dir.glob("owner-*.json"):
            try:
                payload = _load_secure_json(receipt, expected_kind=OWNER_KIND)
            except HandoffError:
                continue
            owner = load_recognized_owner(
                receipt,
                token_hash=str(payload.get("token_sha256") or ""),
                inspector=inspector,
            )
            if owner and terminate_recognized_owner(owner, inspector=inspector):
                stopped.append(int(owner["pid"]))
                receipt.unlink(missing_ok=True)
    legacy_pid = _read_legacy_pid(pid_file)
    if legacy_pid and legacy_pid not in stopped:
        process = inspector.inspect(legacy_pid)
        if process and _looks_like_telegram_poller(process):
            legacy_owner = {
                "pid": process.pid,
                "process_start_id": process.start_id,
                "repo_root": str(Path(process.cwd).resolve(strict=False).parents[2]),
                "execution_root": str(
                    Path(process.cwd).resolve(strict=False).parents[2]
                ),
                "working_directory": process.cwd,
            }
            if terminate_recognized_owner(legacy_owner, inspector=inspector):
                stopped.append(legacy_pid)
    pid_file.unlink(missing_ok=True)
    return {"stopped": stopped}


def _health(
    state_dir: Path,
    pid_file: Path,
    *,
    require_receipt: bool = False,
) -> dict[str, Any]:
    inspector = SystemProcessInspector()
    expected_pid = _read_legacy_pid(pid_file)
    if state_dir.exists() and not state_dir.is_symlink():
        for receipt in state_dir.glob("owner-*.json"):
            try:
                payload = _load_secure_json(receipt, expected_kind=OWNER_KIND)
            except HandoffError:
                continue
            owner = load_recognized_owner(
                receipt,
                token_hash=str(payload.get("token_sha256") or ""),
                inspector=inspector,
            )
            if (
                _owner_has_health_readiness(owner)
                and (expected_pid is None or int(owner["pid"]) == expected_pid)
            ):
                return {"running": True, "ready": True, "pid": int(owner["pid"])}
    if expected_pid and not require_receipt:
        process = inspector.inspect(expected_pid)
        if process and _looks_like_telegram_poller(process):
            return {
                "running": True,
                "ready": True,
                "pid": expected_pid,
                "legacy": True,
            }
    return {"running": False, "ready": False}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--state-dir", required=True)
    status_parser.add_argument("--pid-file", required=True)
    status_parser.add_argument("--legacy-launch-script", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--state-dir", required=True)
    prepare.add_argument("--pid-file", required=True)
    prepare.add_argument("--legacy-launch-script", required=True)
    prepare.add_argument("--candidate-repo", required=True)
    prepare.add_argument("--candidate-execution-root", required=True)
    prepare.add_argument("--candidate-launch-script", required=True)
    prepare.add_argument("--takeover", action="store_true")
    prepare.add_argument("--guard-timeout", type=float, default=30.0)

    wait_ready = subparsers.add_parser("wait-ready")
    wait_ready.add_argument("--state-dir", required=True)
    wait_ready.add_argument("--candidate-repo", required=True)
    wait_ready.add_argument("--candidate-execution-root", required=True)
    wait_ready.add_argument("--candidate-pid", type=int)
    wait_ready.add_argument("--transaction")
    wait_ready.add_argument("--timeout", type=float, default=20.0)

    commit = subparsers.add_parser("commit")
    commit.add_argument("--transaction", required=True)

    attach = subparsers.add_parser("attach-candidate")
    attach.add_argument("--transaction", required=True)
    attach.add_argument("--pid", required=True, type=int)
    attach.add_argument("--timeout", type=float, default=5.0)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--state-dir", required=True)
    rollback.add_argument("--transaction", required=True)

    guard = subparsers.add_parser("guard")
    guard.add_argument("--state-dir", required=True)
    guard.add_argument("--transaction", required=True)
    guard.add_argument("--timeout", type=float, default=30.0)

    stop = subparsers.add_parser("stop-owned")
    stop.add_argument("--state-dir", required=True)
    stop.add_argument("--pid-file", required=True)

    health = subparsers.add_parser("health")
    health.add_argument("--state-dir", required=True)
    health.add_argument("--pid-file", required=True)
    health.add_argument("--require-receipt", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in {"status", "prepare", "wait-ready"}:
            token = (os.environ.get("BOT_TOKEN") or "").strip()
            token_hash = token_sha256(token)
        if args.command == "status":
            result = _status(
                state_dir=Path(args.state_dir),
                token_hash=token_hash,
                pid_file=Path(args.pid_file),
                legacy_launch_script=Path(args.legacy_launch_script),
                inspector=SystemProcessInspector(),
            )
        elif args.command == "prepare":
            result = _prepare(args, token)
        elif args.command == "wait-ready":
            result = _wait_ready(
                state_dir=Path(args.state_dir),
                token_hash=token_hash,
                candidate_repo=Path(args.candidate_repo),
                candidate_execution_root=Path(args.candidate_execution_root),
                candidate_pid=args.candidate_pid,
                transaction_path=(
                    Path(args.transaction) if args.transaction else None
                ),
                timeout=args.timeout,
            )
        elif args.command == "commit":
            result = _commit(Path(args.transaction))
        elif args.command == "attach-candidate":
            result = _attach_candidate(
                Path(args.transaction), pid=args.pid, timeout=args.timeout
            )
        elif args.command == "rollback":
            result = rollback_transaction(
                Path(args.transaction), state_dir=Path(args.state_dir)
            )
        elif args.command == "guard":
            _guard(Path(args.transaction), Path(args.state_dir), args.timeout)
            result = {"guarded": True}
        elif args.command == "stop-owned":
            result = _stop_owned(Path(args.state_dir), Path(args.pid_file))
        elif args.command == "health":
            result = _health(
                Path(args.state_dir),
                Path(args.pid_file),
                require_receipt=bool(args.require_receipt),
            )
        else:
            raise HandoffError("Unsupported command")
    except HandoffError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
