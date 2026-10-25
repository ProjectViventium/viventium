#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CODEX_APP_CLI = Path("/Applications/Codex.app/Contents/Resources/codex")
GLASSHIVE_PROVIDER_MODEL_BY_WORKER_PROFILE = {
    "grok-build": "grok-build:grok-4.7",
    "codex-cli": "codex-cli:gpt-6.1-sol",
    "claude-code": "claude-code:claude-opus-5-5",
}
GLASSHIVE_WORKER_COMMAND_BY_PROFILE = {
    "grok-build": "grok",
    "codex-cli": "codex",
    "claude-code": "claude",
}
DEFAULT_GLASSHIVE_PROVIDER_MODEL = GLASSHIVE_PROVIDER_MODEL_BY_WORKER_PROFILE["codex-cli"]
GROK_AUTH_PROBE = (
    Path(__file__).resolve().parents[2]
    / "viventium_v0_4/xPerfect/runtime_phase1/src/workers_projects_runtime/grok_auth.py"
)


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


def codex_app_cli_candidates(*, legacy_cli: Path | None = None) -> list[Path]:
    legacy_cli = legacy_cli if legacy_cli is not None else CODEX_APP_CLI
    layouts = (
        Path("Codex.app/Contents/Resources/codex"),
        Path("ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"),
    )
    root_candidates = [root / layout for root in codex_app_search_roots() for layout in layouts]
    if os.environ.get("VIVENTIUM_CODEX_APP_DIRS", "").strip():
        candidates: list[Path] = [*root_candidates, legacy_cli]
    else:
        candidates = [legacy_cli, *root_candidates]
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
    if command == "grok":
        configured = os.environ.get("WPR_GROK_BIN", "").strip()
        if configured:
            if Path(configured).is_absolute():
                return configured if executable_path_exists(Path(configured)) else ""
            return shutil.which(configured) or ""
    if command == "codex":
        for candidate in codex_app_cli_candidates():
            if executable_path_exists(candidate):
                return str(candidate)
    if command == "grok":
        selected = os.environ.get("WPR_GROK_BIN", "").strip()
        if selected:
            candidate = Path(selected).expanduser()
            resolved = str(candidate) if candidate.is_absolute() else shutil.which(selected)
            return resolved if resolved and executable_path_exists(Path(resolved)) else ""
    discovered = shutil.which(command)
    if not discovered and command == "grok":
        vendor = Path.home() / ".grok/bin/grok"
        if executable_path_exists(vendor):
            return str(vendor)
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
    if command == "grok":
        if not GROK_AUTH_PROBE.is_file():
            return False
        try:
            completed = subprocess.run(
                [sys.executable, str(GROK_AUTH_PROBE), "--binary", executable],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                env={**os.environ, "GROK_DISABLE_AUTOUPDATER": "1"},
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
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


def glasshive_provider_model_for_worker_profile(profile: str) -> str:
    return GLASSHIVE_PROVIDER_MODEL_BY_WORKER_PROFILE.get(str(profile or "").strip(), "")


def glasshive_worker_command_for_provider_model(model: str) -> str:
    normalized_model = str(model or "").strip()
    for profile, provider_model in GLASSHIVE_PROVIDER_MODEL_BY_WORKER_PROFILE.items():
        if provider_model == normalized_model:
            return GLASSHIVE_WORKER_COMMAND_BY_PROFILE[profile]
    # Explicit alternatives use the compiler's declared harness metadata. Keep the default
    # lookup cheap and do not infer a command from an undeclared model's name or prefix.
    from config_compiler import GLASSHIVE_PROVIDER_MODELS

    for declared_model in GLASSHIVE_PROVIDER_MODELS:
        if declared_model["id"] == normalized_model:
            return GLASSHIVE_WORKER_COMMAND_BY_PROFILE.get(
                str(declared_model.get("harnessProfile") or ""), ""
            )
    return ""
