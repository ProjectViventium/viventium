# === VIVENTIUM START ===
# Feature: Telegram BotFather-token singleton lock.
# Purpose: Prevent two local Telegram pollers for the same bot token from
# competing for getUpdates and delaying or splitting voice replies.
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time
from typing import TextIO


class SingletonAlreadyRunning(RuntimeError):
    def __init__(self, *, lock_path: Path, owner_pid: str = "") -> None:
        self.lock_path = lock_path
        self.owner_pid = owner_pid
        detail = f"pid={owner_pid}" if owner_pid else "pid=unknown"
        super().__init__(f"Telegram bot singleton already held ({detail})")


def _token_lock_id(bot_token: str) -> str:
    digest = hashlib.sha256((bot_token or "").encode("utf-8")).hexdigest()
    return digest[:24]


def _token_hash(bot_token: str) -> str:
    return hashlib.sha256((bot_token or "").encode("utf-8")).hexdigest()


def default_lock_dir() -> Path:
    configured = (
        os.environ.get("VIVENTIUM_TELEGRAM_LOCK_DIR")
        or os.environ.get("VIVENTIUM_RUNTIME_LOCK_DIR")
        or ""
    ).strip()
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Viventium" / "runtime" / "locks"
    runtime_dir = (os.environ.get("XDG_RUNTIME_DIR") or "").strip()
    if runtime_dir:
        return Path(runtime_dir) / "viventium" / "locks"
    return Path.home() / ".cache" / "viventium" / "locks"


def telegram_singleton_lock_path(bot_token: str, *, lock_dir: Path | None = None) -> Path:
    root = lock_dir or default_lock_dir()
    return root / f"telegram-bot-{_token_lock_id(bot_token)}.lock"


def _process_start_identity(pid: int) -> str:
    if sys.platform.startswith("linux"):
        stat_path = Path("/proc") / str(pid) / "stat"
        stat_text = stat_path.read_text(encoding="utf-8")
        end_comm = stat_text.rfind(")")
        fields = stat_text[end_comm + 2 :].split()
        start_ticks = fields[19]
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            boot_id = "unknown-boot"
        return f"{boot_id}:{start_ticks}"
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
            return f"darwin:{info.start_sec}:{info.start_usec}"
    except (OSError, AttributeError):
        pass
    completed = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart="],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=2,
    )
    identity = completed.stdout.strip()
    if completed.returncode != 0 or not identity:
        raise RuntimeError("Unable to determine Telegram process start identity")
    return identity


def _owner_receipt_path() -> Path | None:
    configured = (os.environ.get("VIVENTIUM_TELEGRAM_OWNER_RECEIPT") or "").strip()
    return Path(configured).expanduser() if configured else None


def _write_owner_receipt(
    bot_token: str,
    *,
    ready: bool,
    readiness_proof: str,
) -> None:
    receipt_path = _owner_receipt_path()
    if receipt_path is None:
        return
    repo_root = (
        os.environ.get("VIVENTIUM_TELEGRAM_OWNER_REPO_ROOT") or ""
    ).strip()
    execution_root = (
        os.environ.get("VIVENTIUM_TELEGRAM_EXECUTION_ROOT") or ""
    ).strip()
    launch_script = (
        os.environ.get("VIVENTIUM_TELEGRAM_OWNER_LAUNCH_SCRIPT") or ""
    ).strip()
    user_configs_root = (os.environ.get("CONFIG_DIR") or "").strip()
    if (
        not repo_root
        or not execution_root
        or not launch_script
        or not user_configs_root
    ):
        raise RuntimeError("Telegram owner receipt metadata is incomplete")
    receipt_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if receipt_path.parent.is_symlink() or receipt_path.is_symlink():
        raise RuntimeError("Telegram owner receipt path is not safe")
    receipt_path.parent.chmod(0o700)
    if receipt_path.exists():
        metadata = receipt_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise RuntimeError("Telegram owner receipt is not an owner-only regular file")
    payload = {
        "schema_version": 2,
        "kind": "viventium-telegram-poller-owner",
        "token_sha256": _token_hash(bot_token),
        "pid": os.getpid(),
        "process_start_id": _process_start_identity(os.getpid()),
        "repo_root": str(Path(repo_root).resolve(strict=False)),
        "execution_root": str(Path(execution_root).resolve(strict=False)),
        "working_directory": str(Path.cwd().resolve(strict=False)),
        "launch_script": str(Path(launch_script).resolve(strict=False)),
        "user_configs_root": str(
            Path(user_configs_root).resolve(strict=False)
        ),
        "ready": bool(ready),
        "readiness_proof": readiness_proof,
        "updated_at_unix": int(time.time()),
    }
    temporary = receipt_path.parent / (
        f".{receipt_path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, receipt_path)
        receipt_path.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def schedule_telegram_singleton_readiness(
    application,
    bot_token: str,
    *,
    transport: str,
):
    """Publish readiness only after PTB's updater and application are running.

    PTB 22.5 orders lifecycle as post_init -> Updater.start_* -> Application.start.
    A watcher created by post_init therefore cannot publish until updater
    bootstrap has returned and the application update processor has started.
    """

    updater = getattr(application, "updater", None)
    if updater is None:
        raise RuntimeError("Telegram updater readiness watcher is unavailable")
    if transport == "polling":
        readiness_proof = "polling_started"
    elif transport == "webhook":
        readiness_proof = "webhook_started"
    else:
        raise RuntimeError("Telegram updater readiness watcher mode is unsupported")

    async def wait_for_receive_loop() -> None:
        while True:
            if (
                getattr(updater, "running", False) is True
                and getattr(application, "running", False) is True
            ):
                _write_owner_receipt(
                    bot_token,
                    ready=True,
                    readiness_proof=readiness_proof,
                )
                return
            await asyncio.sleep(0.025)

    return asyncio.create_task(
        wait_for_receive_loop(),
        name="viventium-telegram-readiness",
    )


async def cancel_telegram_singleton_readiness(task) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def clear_telegram_singleton_receipt() -> None:
    receipt_path = _owner_receipt_path()
    if receipt_path is None:
        return
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if (
        isinstance(payload, dict)
        and payload.get("kind") == "viventium-telegram-poller-owner"
        and payload.get("pid") == os.getpid()
        and payload.get("process_start_id") == _process_start_identity(os.getpid())
    ):
        receipt_path.unlink(missing_ok=True)


def acquire_telegram_singleton_lock(bot_token: str, *, lock_dir: Path | None = None) -> TextIO:
    token = (bot_token or "").strip()
    if not token:
        raise ValueError("BOT_TOKEN is required before acquiring the Telegram singleton lock")

    lock_path = telegram_singleton_lock_path(token, lock_dir=lock_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.seek(0)
        owner_pid = (lock_file.read().strip().splitlines() or [""])[0]
        lock_file.close()
        raise SingletonAlreadyRunning(lock_path=lock_path, owner_pid=owner_pid) from exc

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    os.fsync(lock_file.fileno())
    try:
        _write_owner_receipt(
            token,
            ready=False,
            readiness_proof="initializing",
        )
    except Exception:
        lock_file.close()
        raise
    return lock_file
