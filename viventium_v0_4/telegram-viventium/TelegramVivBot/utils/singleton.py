# === VIVENTIUM START ===
# Feature: Telegram BotFather-token singleton lock.
# Purpose: Prevent two local Telegram pollers for the same bot token from
# competing for getUpdates and delaying or splitting voice replies.
# === VIVENTIUM END ===

from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import sys
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
    return lock_file
