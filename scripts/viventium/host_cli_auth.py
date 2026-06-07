#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


CODEX_APP_CLI = Path("/Applications/Codex.app/Contents/Resources/codex")


def resolve_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def executable_path_exists(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def codex_app_search_roots() -> list[Path]:
    override = os.environ.get("VIVENTIUM_CODEX_APP_DIRS", "").strip()
    if override:
        return [Path(entry).expanduser() for entry in override.split(os.pathsep) if entry.strip()]
    return [Path("/Applications"), Path.home() / "Applications"]


def codex_app_cli_candidates() -> list[Path]:
    root_candidates = [root / "Codex.app" / "Contents" / "Resources" / "codex" for root in codex_app_search_roots()]
    if os.environ.get("VIVENTIUM_CODEX_APP_DIRS", "").strip():
        candidates: list[Path] = [*root_candidates, CODEX_APP_CLI]
    else:
        candidates = [CODEX_APP_CLI, *root_candidates]
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def host_cli_command(command: str) -> str:
    if command == "codex":
        for candidate in codex_app_cli_candidates():
            if executable_path_exists(candidate):
                return str(candidate)
    discovered = shutil.which(command)
    return discovered or ""


def host_cli_exists(command: str) -> bool:
    return bool(host_cli_command(command))


def run_status(args: list[str], *, timeout_seconds: float = 5.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args=args, returncode=124, stdout="", stderr=str(exc))


def host_cli_auth_ready(command: str) -> bool:
    executable = host_cli_command(command)
    if not executable:
        return False
    if command == "codex":
        return run_status([executable, "login", "status"]).returncode == 0
    if command == "claude":
        completed = run_status([executable, "auth", "status"])
        if completed.returncode != 0:
            return False
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return False
        return resolve_bool(payload.get("loggedIn"), False)
    return True


def detect_worker_profile() -> str:
    if host_cli_auth_ready("codex"):
        return "codex-cli"
    if host_cli_auth_ready("claude"):
        return "claude-code"
    return ""
