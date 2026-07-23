#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from installer_ui import InstallerUI  # noqa: E402
from brain_readiness import (  # noqa: E402
    ADVANCED_OFF_KEYS,
    FEATURE_BY_KEY,
    GUIDED_EXPRESS_KEYS,
    UNAVAILABLE_KEYS,
    feature_guidance,
    feature_label,
)
from retrieval_config import resolve_retrieval_embeddings_settings  # noqa: E402
from telegram_tokens import telegram_bot_token_looks_valid  # noqa: E402


DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES = 4 * 1024 * 1024 * 1024


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


def secret_node_configured(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    return bool(
        str(node.get("secret_ref") or "").strip() or str(node.get("secret_value") or "").strip()
    )


def strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return data


def load_runtime_env(runtime_dir: Path | None) -> dict[str, str]:
    if runtime_dir is None:
        return {}

    merged: dict[str, str] = {}
    for env_path in (runtime_dir / "runtime.env", runtime_dir / "runtime.local.env"):
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            merged[key.strip()] = strip_wrapping_quotes(value.strip())
    return merged


def foundation_api_key_present(config: dict[str, Any]) -> bool:
    llm = config.get("llm", {}) or {}
    primary = llm.get("primary", {}) or {}
    secondary = llm.get("secondary", {}) or {}
    extra_provider_keys = llm.get("extra_provider_keys", {}) or {}
    return any(
        provider in {"openai", "anthropic"} and auth_mode == "api_key" and secret_node_configured(node)
        for provider, auth_mode, node in (
            (
                str(primary.get("provider") or "").strip().lower(),
                str(primary.get("auth_mode") or "").strip().lower(),
                primary,
            ),
            (
                str(secondary.get("provider") or "").strip().lower(),
                str(secondary.get("auth_mode") or "").strip().lower(),
                secondary,
            ),
        )
    ) or any(
        provider_name in {"openai", "anthropic"} and secret_node_configured(node)
        for provider_name, node in extra_provider_keys.items()
    )


def configured_foundation_account_labels(config: dict[str, Any]) -> list[str]:
    llm = config.get("llm", {}) or {}
    primary = llm.get("primary", {}) or {}
    secondary = llm.get("secondary", {}) or {}
    labels: list[str] = []
    for node in (primary, secondary):
        provider = str(node.get("provider") or "").strip().lower()
        auth_mode = str(node.get("auth_mode") or "").strip().lower()
        if auth_mode not in {"connected_account", "user_provided"}:
            continue
        label = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
        }.get(provider)
        if label and label not in labels:
            labels.append(label)
    return labels


def foundation_connected_account_runtime_configured(
    config: dict[str, Any], runtime_env: dict[str, str], provider: str
) -> bool:
    provider = str(provider or "").strip().lower()
    if provider not in {"openai", "anthropic"}:
        return False
    llm = config.get("llm", {}) or {}
    configured = False
    for node in (llm.get("primary", {}) or {}, llm.get("secondary", {}) or {}):
        if str(node.get("provider") or "").strip().lower() != provider:
            continue
        if str(node.get("auth_mode") or "").strip().lower() == "connected_account":
            configured = True
            break
    if not configured:
        return False

    env_key = {
        "openai": "VIVENTIUM_OPENAI_AUTH_MODE",
        "anthropic": "VIVENTIUM_ANTHROPIC_AUTH_MODE",
    }[provider]
    return (
        resolve_bool(runtime_env.get("VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH"), False)
        and resolve_bool(
            runtime_env.get("VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH"), False
        )
        and str(runtime_env.get(env_key) or "").strip().lower() == "connected_account"
    )


def runtime_port(config: dict[str, Any], runtime_env: dict[str, str], env_key: str, key: str, default: int) -> int:
    raw_env = str(runtime_env.get(env_key, "") or "").strip()
    if raw_env.isdigit():
        return int(raw_env)
    runtime = config.get("runtime", {}) or {}
    ports = runtime.get("ports", {}) or {}
    raw = str(ports.get(key, default) or default).strip()
    return int(raw) if raw.isdigit() else default


def http_ok(url: str) -> bool:
    curl_cmd = shutil.which("curl")
    if curl_cmd:
        try:
            completed = subprocess.run(
                [curl_cmd, "-fsS", "-o", "/dev/null", "--max-time", "2", url],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:
            completed = None
        if completed is not None and completed.returncode == 0:
            return True

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= getattr(response, "status", 200) < 400
    except urllib.error.HTTPError as error:
        return 200 <= error.code < 400
    except Exception:
        return False


def http_json(url: str) -> dict[str, Any] | None:
    curl_cmd = shutil.which("curl")
    if curl_cmd:
        try:
            completed = subprocess.run(
                [curl_cmd, "-fsS", "--max-time", "2", url],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:
            completed = None
        if completed is not None and completed.returncode == 0:
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                return payload

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            if getattr(response, "status", 200) != 200:
                return None
            payload = json.load(response)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def any_http_ok(*urls: str) -> bool:
    return any(url and http_ok(url) for url in urls)


def http_json_status_up(url: str) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            if getattr(response, "status", 200) != 200:
                return False
            payload = json.load(response)
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("status") == "UP"


def url_with_path(url: str, path: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    normalized_path = "/" + path.lstrip("/")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, normalized_path, parsed.query, parsed.fragment)
    )


def http_status(url: str) -> int | None:
    curl_cmd = shutil.which("curl")
    if curl_cmd:
        try:
            completed = subprocess.run(
                [
                    curl_cmd,
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "2",
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:
            completed = None
        if completed is not None and completed.returncode == 0:
            raw_status = completed.stdout.strip()
            if raw_status.isdigit():
                status = int(raw_status)
                if status > 0:
                    return status

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return int(getattr(response, "status", 200))
    except urllib.error.HTTPError as error:
        return int(error.code)
    except Exception:
        return None


def http_endpoint_reachable(url: str) -> bool:
    status = http_status(url)
    return status is not None and 100 <= status < 500


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def process_running_by_name(name: str) -> bool:
    pgrep_cmd = shutil.which("pgrep")
    if pgrep_cmd:
        try:
            completed = subprocess.run(
                [pgrep_cmd, "-x", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
        except Exception:
            completed = None
        if completed is not None:
            return completed.returncode == 0 and bool(completed.stdout.strip())

    ps_cmd = shutil.which("ps")
    if ps_cmd:
        try:
            completed = subprocess.run(
                [ps_cmd, "-axo", "comm="],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
        except Exception:
            completed = None
        if completed is not None and completed.returncode == 0:
            return any(Path(line.strip()).name == name for line in completed.stdout.splitlines())

    return False


def docker_total_memory_bytes() -> int | None:
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        return None
    try:
        completed = subprocess.run(
            [docker_cmd, "info", "--format", "{{.MemTotal}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except Exception:
        return None
    raw = completed.stdout.strip()
    return int(raw) if completed.returncode == 0 and raw.isdigit() else None


def local_firecrawl_memory_warning(config: dict[str, Any]) -> str | None:
    web_search = ((config.get("integrations") or {}).get("web_search") or {})
    if not resolve_bool(web_search.get("enabled"), False):
        return None
    scraper_provider = str(web_search.get("scraper_provider") or "firecrawl").strip().lower()
    if scraper_provider not in {"local", "firecrawl"}:
        return None
    docker_memory = docker_total_memory_bytes()
    if docker_memory is None or docker_memory >= DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES:
        return None
    current_gib = docker_memory / float(1024 * 1024 * 1024)
    recommended_gib = DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES / float(1024 * 1024 * 1024)
    return (
        "Docker Desktop is currently limited to about "
        f"{current_gib:.1f} GB. Raise it to at least {recommended_gib:.0f} GB or switch "
        "to Firecrawl API if the local scraper keeps restarting."
    )


def runtime_profile_name(config: dict[str, Any], runtime_env: dict[str, str]) -> str:
    runtime = config.get("runtime", {}) or {}
    configured = str(runtime.get("profile") or "isolated").strip()
    resolved = str(runtime_env.get("VIVENTIUM_RUNTIME_PROFILE") or configured or "isolated").strip()
    return resolved or "isolated"


def append_unique_path(paths: list[Path], path: Path | None) -> None:
    if path is None:
        return
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        resolved = path.expanduser()
    if resolved not in paths:
        paths.append(resolved)


def normalize_remote_call_mode(config: dict[str, Any]) -> str:
    runtime = config.get("runtime", {}) or {}
    network = runtime.get("network", {}) or {}
    mode = str(network.get("remote_call_mode") or "disabled").strip().lower()
    if not mode or mode == "auto":
        return "disabled"
    if mode in {"custom_domain", "custom_domain_public_edge", "public_custom_domain"}:
        return "public_https_edge"
    return mode


def runtime_state_root(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> Path | None:
    explicit_state_root = str(runtime_env.get("VIVENTIUM_STATE_ROOT") or "").strip()
    if explicit_state_root:
        return Path(explicit_state_root).expanduser()
    if runtime_dir is None:
        return None
    return runtime_dir.parent / "state" / "runtime" / runtime_profile_name(config, runtime_env)


def runtime_state_root_candidates(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    repo_root: Path | None = None,
) -> list[Path]:
    roots: list[Path] = []
    append_unique_path(roots, runtime_state_root(config, runtime_env, runtime_dir))
    if runtime_dir is not None:
        append_unique_path(
            roots,
            runtime_dir.parent / "state" / "runtime" / runtime_profile_name(config, runtime_env),
        )
    if repo_root is not None:
        append_unique_path(
            roots,
            repo_root / ".viventium" / "runtime" / runtime_profile_name(config, runtime_env),
        )
    return roots


def stack_owner_state_file(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> Path | None:
    state_root = runtime_state_root(config, runtime_env, runtime_dir)
    if state_root is None:
        return None
    return state_root / "stack-owner.json"


def load_stack_owner_state(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> dict[str, Any]:
    owner_file = stack_owner_state_file(config, runtime_env, runtime_dir)
    if owner_file is None or not owner_file.is_file():
        return {}
    try:
        payload = json.loads(owner_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def display_path(path: Path) -> str:
    try:
        home = Path.home().resolve()
        resolved = path.expanduser().resolve()
        relative = resolved.relative_to(home)
        return f"~/{relative}"
    except Exception:
        return str(path)


def stack_owner_checkout_row(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    repo_root: Path | None,
) -> tuple[str, str, str] | None:
    if repo_root is None:
        return None
    owner_state = load_stack_owner_state(config, runtime_env, runtime_dir)
    owner_repo_raw = str(owner_state.get("repoRoot") or "").strip()
    if not owner_repo_raw:
        return None

    current_repo = repo_root.expanduser().resolve()
    owner_repo = Path(owner_repo_raw).expanduser().resolve()
    if owner_repo == current_repo:
        return None

    return (
        "Runtime Checkout",
        "Different Checkout",
        f"Live stack owner: {display_path(owner_repo)} | this command: {display_path(current_repo)}",
    )


def stack_owner_command(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> str:
    owner_state = load_stack_owner_state(config, runtime_env, runtime_dir)
    command = str(owner_state.get("command") or "").strip().lower()
    if command == "launch":
        return "bin/viventium launch"
    return "bin/viventium start"


def stack_expected_live(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> bool:
    owner_state = load_stack_owner_state(config, runtime_env, runtime_dir)
    command = str(owner_state.get("command") or "").strip().lower()
    return command in {"install", "start", "launch", "upgrade", "update"}


def load_public_network_state(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> dict[str, Any]:
    if normalize_remote_call_mode(config) == "disabled":
        return {}

    candidates: list[Path] = []
    env_path = str(runtime_env.get("VIVENTIUM_PUBLIC_NETWORK_STATE_FILE") or "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    state_root = runtime_state_root(config, runtime_env, runtime_dir)
    if state_root is not None:
        candidates.append(state_root / "public-network.json")

    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def resolve_runtime_auth(config: dict[str, Any], runtime_env: dict[str, str]) -> dict[str, bool]:
    runtime = config.get("runtime", {}) or {}
    auth = runtime.get("auth", {}) or {}
    return {
        "allow_registration": resolve_bool(
            runtime_env.get("ALLOW_REGISTRATION"),
            resolve_bool(auth.get("allow_registration"), True),
        ),
        "bootstrap_registration_once": resolve_bool(
            runtime_env.get("VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE"),
            resolve_bool(auth.get("bootstrap_registration_once"), False),
        ),
        "allow_password_reset": resolve_bool(
            runtime_env.get("ALLOW_PASSWORD_RESET"),
            resolve_bool(auth.get("allow_password_reset"), False),
        ),
    }


def remote_access_label(remote_call_mode: str) -> str:
    return {
        "disabled": "Local-only on this Mac",
        "tailscale_tailnet_https": "Private access from your own Tailscale devices",
        "netbird_selfhosted_mesh": "Private access from your NetBird mesh devices",
        "cloudflare_quick_tunnel": "Experimental voice-only tunnel",
        "public_https_edge": "Public browser access from anywhere",
    }.get(remote_call_mode, remote_call_mode or "Local-only on this Mac")


def remote_access_status_and_detail(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    *,
    probe_live: bool,
    stack_should_be_live: bool,
) -> tuple[str, str]:
    remote_call_mode = normalize_remote_call_mode(config)
    if remote_call_mode == "disabled":
        return "Disabled", "Local-only install"

    public_state = load_public_network_state(config, runtime_env, runtime_dir)
    last_error = str(public_state.get("last_error") or "").strip()
    if last_error:
        return "Action Required", f"{remote_access_label(remote_call_mode)} inactive: {last_error}"

    public_client_url = str(
        public_state.get("public_client_url") or runtime_env.get("VIVENTIUM_PUBLIC_CLIENT_URL") or ""
    ).strip()
    if public_client_url:
        status = "Running" if probe_live and stack_should_be_live else "Configured"
        return status, f"{remote_access_label(remote_call_mode)}: {public_client_url}"

    if remote_call_mode == "tailscale_tailnet_https":
        return (
            "Configured",
            "Connect Tailscale on this Mac, then run bin/viventium start to publish the private device URL.",
        )
    if remote_call_mode == "public_https_edge":
        return (
            "Configured",
            "Run bin/viventium start, then bin/viventium status to see the exact outside URL.",
        )
    if remote_call_mode == "netbird_selfhosted_mesh":
        return "Configured", "Start Viventium after the mesh hostnames and local trust are ready."
    return "Configured", remote_access_label(remote_call_mode)


def pid_file_process_running(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        pid = int(raw)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def process_command_line(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            text=True,
            capture_output=True,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def cli_lock_owner_running(lock_dir: Path) -> bool:
    try:
        raw = (lock_dir / "pid").read_text(encoding="utf-8").strip()
        pid = int(raw)
        if pid <= 0:
            return False
    except Exception:
        return False
    if not pid_file_process_running(lock_dir / "pid"):
        return False

    current_command = process_command_line(pid)

    process_command_file = lock_dir / "process_command"
    if process_command_file.is_file():
        try:
            recorded_command = process_command_file.read_text(encoding="utf-8").strip()
        except Exception:
            recorded_command = ""
        if not current_command:
            return bool(recorded_command)
        return bool(recorded_command and current_command == recorded_command)

    if not current_command:
        return True

    # Legacy locks stored only a PID. Avoid treating a reused PID from an unrelated
    # macOS process as a live Viventium operation.
    return "bin/viventium" in current_command


def cli_operation_running(runtime_dir: Path | None) -> bool:
    if runtime_dir is None:
        return False
    lock_dir = runtime_dir.parent / "state" / "cli-operation.lock"
    if not lock_dir.is_dir():
        return False
    if not cli_lock_owner_running(lock_dir):
        return False

    command = ""
    try:
        command = (lock_dir / "command").read_text(encoding="utf-8").strip().lower()
    except Exception:
        command = ""

    startup_window_seconds = int(os.environ.get("VIVENTIUM_CLI_STARTUP_WINDOW_SECONDS") or "600")
    # Only startup commands get the stale-lock grace window. Other CLI operations still block
    # status until their process exits because they may intentionally hold a long-running lock.
    if command in {"start", "launch"} and startup_window_seconds > 0:
        try:
            lock_age_seconds = time.time() - max(
                (lock_dir / "pid").stat().st_mtime,
                (lock_dir / "command").stat().st_mtime,
            )
        except Exception:
            lock_age_seconds = 0
        if lock_age_seconds > startup_window_seconds:
            return False

    return True


def recent_log_text(path: Path, *, max_bytes: int = 65536) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def telegram_recent_runtime_issue(log_paths: list[Path]) -> tuple[str, str] | None:
    issue_checks: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (
            (
                "terminated by other getupdates request",
                "conflict:",
                "only one bot instance",
            ),
            "Running with issues",
            "Recent Telegram polling conflict detected. Stop the other bot process using the same BotFather token, then restart Viventium.",
        ),
        (
            (
                "credentials rejected",
                "connected-account refresh failed",
                "invalid_api_key",
                "authenticationerror",
                "unauthorized",
            ),
            "Running with issues",
            "Recent AI provider authentication failure detected. Refresh the connected account or API key, then restart Viventium.",
        ),
    )

    recovery_markers = (
        "starting polling mode",
        "application started",
        "telegram bot started",
    )

    for path in log_paths:
        text = recent_log_text(path).lower()
        if not text:
            continue
        latest_recovery = max((text.rfind(marker) for marker in recovery_markers), default=-1)
        if latest_recovery >= 0:
            text = text[latest_recovery:]
        for needles, status, detail in issue_checks:
            if any(needle in text for needle in needles):
                return status, detail
    return None


def telegram_service_status(
    *,
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    repo_root: Path | None,
    probe_live: bool,
    token_env_key: str,
    log_file_name: str,
    pid_file_name: str,
    running_detail: str,
    pending_pid_file_name: str | None = None,
    pending_marker_file_name: str | None = None,
    pending_detail: str | None = None,
    requires_lc_api: bool = False,
) -> tuple[str, str]:
    token = str(runtime_env.get(token_env_key, "") or "").strip()
    state_roots = runtime_state_root_candidates(config, runtime_env, runtime_dir, repo_root)
    log_detail = "Starts with Viventium"
    process_running = False
    pending_running = False
    log_paths: list[Path] = []

    if state_roots:
        log_detail = str(state_roots[0] / "logs" / log_file_name)

    for state_root in state_roots:
        log_detail = str(state_root / "logs" / log_file_name)
        log_paths.append(state_root / "logs" / log_file_name)
        pid_candidates = (
            state_root / pid_file_name,
            state_root / "logs" / pid_file_name,
        )
        process_running = any(pid_file_process_running(candidate) for candidate in pid_candidates)
        if process_running:
            break
        if pending_pid_file_name:
            pending_pid_candidates = (
                state_root / pending_pid_file_name,
                state_root / "logs" / pending_pid_file_name,
            )
            pending_running = pending_running or any(
                pid_file_process_running(candidate) for candidate in pending_pid_candidates
            )
        if not pending_running and pending_marker_file_name:
            pending_marker_candidates = (
                state_root / pending_marker_file_name,
                state_root / "logs" / pending_marker_file_name,
            )
            pending_running = any(candidate.is_file() for candidate in pending_marker_candidates)

    if process_running:
        issue = telegram_recent_runtime_issue(log_paths)
        if issue is not None:
            return issue
        if probe_live and requires_lc_api:
            lc_origin = str(runtime_env.get("VIVENTIUM_LIBRECHAT_ORIGIN") or "").strip().rstrip("/")
            api_port = runtime_port(config, runtime_env, "VIVENTIUM_LC_API_PORT", "lc_api_port", 3180)
            api_health_urls = (
                url_with_path(lc_origin, "/health") if lc_origin else "",
                url_with_path(lc_origin, "/api/health") if lc_origin else "",
                f"http://localhost:{api_port}/health",
                f"http://127.0.0.1:{api_port}/health",
                f"http://localhost:{api_port}/api/health",
                f"http://127.0.0.1:{api_port}/api/health",
            )
            if not any_http_ok(*api_health_urls):
                detail = lc_origin or f"http://127.0.0.1:{api_port}"
                return (
                    "Running with issues",
                    f"LibreChat API is unreachable at {detail}; Telegram cannot start new chats until it recovers.",
                )
        return "Running", running_detail

    if pending_running:
        return "Starting", pending_detail or "Waiting for Viventium to finish starting this service"

    if not token:
        detail = (
            f"Generated runtime is missing {token_env_key}. "
            "Run bin/viventium configure to add the BotFather token again."
        )
        return "Misconfigured", detail

    if not telegram_bot_token_looks_valid(token):
        return (
            "Misconfigured",
            "Invalid BotFather token. Run bin/viventium configure and re-copy the full <bot_id>:<secret> value from @BotFather.",
        )

    issue = telegram_recent_runtime_issue(log_paths)
    if probe_live and issue is not None:
        _status, detail = issue
        return "Action Required", detail

    if probe_live:
        return "Stopped", f"Check {log_detail}"
    return "Configured", "Starts with Viventium"


def mcp_service_status(
    *,
    url: str,
    start_enabled: bool,
    probe_live: bool,
    stack_should_be_live: bool,
    startup_in_progress: bool,
    default_detail: str,
) -> tuple[str, str]:
    detail = url or default_detail
    if probe_live and url:
        if http_endpoint_reachable(url):
            return "Running", detail
        if stack_should_be_live and start_enabled:
            if startup_in_progress:
                return "Starting", f"Waiting for {detail}"
            return "Action Required", f"Endpoint not reachable at {detail}"
    return "Configured", detail


def helper_config_path(runtime_dir: Path | None) -> Path | None:
    env_path = str(os.environ.get("VIVENTIUM_HELPER_CONFIG_FILE") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    if runtime_dir is not None:
        return runtime_dir.parent / "helper-config.json"
    return None


def macos_helper_status(
    *,
    runtime_dir: Path | None,
    probe_live: bool,
    stack_should_be_live: bool,
) -> tuple[str, str, str] | None:
    if sys.platform != "darwin":
        return None

    path = helper_config_path(runtime_dir)
    if path is None or not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (
            "macOS Status Bar Helper",
            "Action Required",
            "Helper config could not be read. Run bin/viventium launch to refresh it.",
        )

    if not isinstance(payload, dict):
        return (
            "macOS Status Bar Helper",
            "Action Required",
            "Helper config is invalid. Run bin/viventium launch to refresh it.",
        )

    show_in_status_bar = resolve_bool(payload.get("showInStatusBar"), True)
    if not show_in_status_bar:
        return (
            "macOS Status Bar Helper",
            "Hidden",
            "Configured to stay out of the macOS status bar",
        )

    if probe_live and process_running_by_name("ViventiumHelper"):
        return (
            "macOS Status Bar Helper",
            "Running",
            "Status bar menu is active",
        )

    if probe_live and stack_should_be_live:
        return (
            "macOS Status Bar Helper",
            "Action Required",
            "Configured to show in the status bar, but ViventiumHelper is not running. Run bin/viventium launch.",
        )

    return (
        "macOS Status Bar Helper",
        "Configured",
        "Launch Viventium when you want the status bar menu active",
    )


def local_network_host() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            host = sock.getsockname()[0]
            if host and not host.startswith("127.") and not host.startswith("169.254."):
                return host
    except OSError:
        return None
    return None


def voice_status(
    config: dict[str, Any], runtime_env: dict[str, str] | None = None
) -> str:
    runtime_env = runtime_env or {}
    if (
        str(runtime_env.get("VIVENTIUM_VOICE_DEGRADED_REASON") or "").strip()
        == "legacy_xai_voice_agent_route_retired"
    ):
        return (
            "Voice disabled: legacy xAI Voice Agent route retired; run Custom Settings Install "
            "to choose a supported voice provider."
        )
    voice = config.get("voice", {}) or {}
    mode = str(voice.get("mode") or "disabled").strip().lower()
    if mode == "local":
        return "Local voice on this Mac"
    if mode == "hosted":
        return "Hosted voice providers"
    return "Disabled"


def web_search_summary(config: dict[str, Any]) -> str:
    web_search = ((config.get("integrations") or {}).get("web_search") or {})
    search_provider = str(web_search.get("search_provider") or "searxng").strip().lower()
    scraper_provider = str(web_search.get("scraper_provider") or "firecrawl").strip().lower()

    search_label = "Local SearXNG" if search_provider == "searxng" else "Serper API"
    if scraper_provider == "firecrawl_api":
        scraper_label = "Firecrawl API"
    elif scraper_provider == "firecrawl":
        scraper_label = "Local Firecrawl"
    else:
        scraper_label = "No scraper"
    return f"{search_label} + {scraper_label}"


def transcript_source_dir(config: dict[str, Any], runtime_env: dict[str, str] | None = None) -> str:
    runtime_env = runtime_env or {}
    env_source = str(runtime_env.get("VIVENTIUM_MEMORY_TRANSCRIPTS_DIR") or "").strip()
    if env_source:
        return env_source
    transcripts = (
        ((config.get("runtime") or {}).get("memory_hardening") or {}).get("transcripts") or {}
    )
    return str(transcripts.get("source_dir") or "").strip()


def scheduler_mcp_url(runtime_env: dict[str, str]) -> str:
    explicit = str(runtime_env.get("SCHEDULING_MCP_URL") or "").strip()
    if explicit:
        return explicit
    port = str(
        runtime_env.get("VIVENTIUM_SCHEDULING_MCP_PORT")
        or runtime_env.get("SCHEDULING_MCP_PORT")
        or "7110"
    ).strip()
    if port.isdigit():
        return f"http://localhost:{port}/mcp"
    return ""


def scheduler_health_url(url: str) -> str:
    return url_with_path(url, "/health") if url else ""


def scheduler_db_path(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
) -> Path | None:
    explicit = str(runtime_env.get("SCHEDULING_DB_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    state_root = runtime_state_root(config, runtime_env, runtime_dir)
    if state_root is None:
        return None
    return state_root / "scheduling" / "schedules.db"


def _sqlite_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def scheduler_ledger_summary(path: Path | None) -> str:
    if path is None:
        return "ledger location pending"
    if not path.is_file():
        return "ledger pending"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except Exception:
        return "ledger unreadable"
    try:
        with conn:
            tables = _sqlite_table_names(conn)
            if "scheduled_tasks" not in tables:
                return "ledger schema pending"
            columns = _sqlite_columns(conn, "scheduled_tasks")
            active_count = None
            if "active" in columns:
                active_count = int(
                    conn.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE active = 1").fetchone()[0]
                )
            total_count = int(conn.execute("SELECT COUNT(*) FROM scheduled_tasks").fetchone()[0])
            count_summary = (
                f"{active_count} active / {total_count} total"
                if active_count is not None
                else f"{total_count} total"
            )
            wanted = [
                column
                for column in (
                    "last_status",
                    "last_delivery_outcome",
                    "last_delivery_at",
                    "last_run_at",
                    "next_run_at",
                )
                if column in columns
            ]
            if not wanted:
                return count_summary
            order_column = "last_delivery_at" if "last_delivery_at" in columns else "updated_at"
            if order_column not in columns:
                order_column = "created_at" if "created_at" in columns else "id"
            selected = ", ".join(wanted)
            row = conn.execute(
                f"SELECT {selected} FROM scheduled_tasks "
                f"ORDER BY COALESCE({order_column}, '') DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return count_summary
            values = dict(zip(wanted, row))
            status_bits: list[str] = []
            if values.get("last_status"):
                status_bits.append(f"last status {values['last_status']}")
            if values.get("last_delivery_outcome"):
                status_bits.append(f"delivery {values['last_delivery_outcome']}")
            if values.get("next_run_at"):
                status_bits.append(f"next {values['next_run_at']}")
            return f"{count_summary}; " + "; ".join(status_bits) if status_bits else count_summary
    except Exception:
        return "ledger unreadable"
    finally:
        conn.close()


def scheduler_ledger_has_latest_issue(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except Exception:
        return False
    try:
        with conn:
            if "scheduled_tasks" not in _sqlite_table_names(conn):
                return False
            columns = _sqlite_columns(conn, "scheduled_tasks")
            wanted = [
                column
                for column in ("last_status", "last_delivery_outcome", "last_delivery_at", "updated_at", "created_at")
                if column in columns
            ]
            if not {"last_status", "last_delivery_outcome"} & set(wanted):
                return False
            order_column = "last_delivery_at" if "last_delivery_at" in columns else "updated_at"
            if order_column not in columns:
                order_column = "created_at" if "created_at" in columns else "id"
            selected = ", ".join(column for column in ("last_status", "last_delivery_outcome") if column in columns)
            if not selected:
                return False
            row = conn.execute(
                f"SELECT {selected} FROM scheduled_tasks "
                f"ORDER BY COALESCE({order_column}, '') DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return False
            values = dict(zip(selected.split(", "), row))
            last_status = str(values.get("last_status") or "").strip().lower()
            last_delivery = str(values.get("last_delivery_outcome") or "").strip().lower()
            return last_status in {"error", "failed"} or last_delivery in {
                "failed",
                "dead_lettered",
                "error",
            }
    except Exception:
        return False
    finally:
        conn.close()


def scheduler_health_matches(url: str, db_path: Path | None) -> tuple[bool, str]:
    payload = http_json(url)
    if payload is None:
        return False, "Scheduler health endpoint is unavailable or invalid"
    if payload.get("status") != "ok":
        return False, "Scheduler health status is not ok"
    if payload.get("service") != "scheduling-cortex":
        return False, "Scheduler service identity does not match"
    if db_path is None:
        return False, "Scheduler ledger identity is unavailable"
    expected_db_hash = hashlib.sha256(
        str(db_path.expanduser().resolve()).encode("utf-8")
    ).hexdigest()
    if payload.get("db_path_sha256") != expected_db_hash:
        return False, "Scheduler ledger identity does not match"
    return True, ""


def scheduler_status_and_detail(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    *,
    probe_live: bool,
    stack_should_be_live: bool,
    startup_in_progress: bool,
) -> tuple[str, str]:
    start_enabled = resolve_bool(runtime_env.get("START_SCHEDULING_MCP"), True)
    url = scheduler_mcp_url(runtime_env)
    db_path = scheduler_db_path(config, runtime_env, runtime_dir)
    ledger = scheduler_ledger_summary(db_path)
    ledger_has_issue = scheduler_ledger_has_latest_issue(db_path)
    if probe_live and url:
        health_url = scheduler_health_url(url)
        healthy, health_reason = scheduler_health_matches(health_url, db_path)
        if healthy:
            if ledger_has_issue:
                return "Running with issues", f"{url} | {ledger}"
            return "Running", f"{url} | {ledger}"
        if stack_should_be_live and start_enabled:
            return (
                "Starting" if startup_in_progress else "Action Required",
                f"{health_reason} at {health_url or url} | {ledger}",
            )
        return "Configured", f"{health_reason} at {health_url or url} | {ledger}"
    return "Configured", f"{url or 'Local Scheduling Cortex MCP'} | {ledger}"


def memory_hardening_status_payload(
    *,
    repo_root: Path | None,
    runtime_dir: Path | None,
    runtime_env: dict[str, str],
) -> dict[str, Any] | None:
    if runtime_dir is None:
        return None
    resolved_repo_root = (repo_root or SCRIPT_DIR.parents[1]).expanduser().resolve()
    resolved_runtime_dir = runtime_dir.expanduser().resolve()
    app_support_dir = Path(
        runtime_env.get("VIVENTIUM_APP_SUPPORT_DIR") or resolved_runtime_dir.parent
    ).expanduser().resolve()
    script = resolved_repo_root / "scripts" / "viventium" / "memory_harden.py"
    if not script.is_file():
        return None
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--repo-root",
                str(resolved_repo_root),
                "--app-support-dir",
                str(app_support_dir),
                "--runtime-dir",
                str(resolved_runtime_dir),
                "status",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=12,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def secondary_ai_configured(config: dict[str, Any]) -> bool:
    llm = config.get("llm", {}) or {}
    secondary = llm.get("secondary", {}) or {}
    provider = str(secondary.get("provider") or "").strip().lower()
    if provider and provider != "none":
        return True
    extra_provider_keys = llm.get("extra_provider_keys", {}) or {}
    if not isinstance(extra_provider_keys, dict):
        return False
    return any(
        provider_name in {"openai", "anthropic", "x_ai", "xai"} and secret_node_configured(node)
        for provider_name, node in extra_provider_keys.items()
    )


def configured_unverified(detail: str) -> tuple[str, str]:
    """Report configured intent without claiming unobserved runtime success."""
    return "Configured", f"{detail}; verify with the live status or self-test before relying on it."


def brain_setup_state(
    key: str,
    config: dict[str, Any],
    runtime_env: dict[str, str],
) -> tuple[str, str]:
    integrations = config.get("integrations", {}) or {}
    runtime = config.get("runtime", {}) or {}
    personalization = runtime.get("personalization", {}) or {}
    voice = config.get("voice", {}) or {}

    if key == "core_app":
        return configured_unverified("Core app install is configured")
    if key == "scheduler":
        if resolve_bool((integrations.get("scheduling_cortex") or {}).get("enabled"), False):
            return configured_unverified("Scheduler enabled")
        return "Needs setup", feature_guidance(key)
    if key == "glasshive":
        if resolve_bool((integrations.get("glasshive") or {}).get("enabled"), False):
            return configured_unverified("GlassHive enabled")
        return "Needs setup", feature_guidance(key)
    if key == "prompt_workbench":
        if resolve_bool((runtime.get("prompt_workbench") or {}).get("enabled"), False):
            return configured_unverified("Prompt Workbench enabled")
        return "Needs setup", feature_guidance(key)
    if key == "nightly_reflection":
        nightly = runtime.get("nightly_routines") or {}
        seed = (runtime.get("prompt_workbench") or {}).get("seed_nightly") or {}
        if resolve_bool(nightly.get("enabled"), False) and resolve_bool(
            seed.get("enabled"), False
        ):
            return configured_unverified("Nightly Reflection enabled")
        return "Needs setup", feature_guidance(key)
    if key == "memory_hardening":
        if resolve_bool((runtime.get("memory_hardening") or {}).get("enabled"), False):
            return configured_unverified("Memory Hardening enabled")
        return "Needs setup", feature_guidance(key)
    if key == "primary_ai":
        if foundation_api_key_present(config):
            return configured_unverified("Foundation provider API-key fallback is configured")
        if any(
            foundation_connected_account_runtime_configured(config, runtime_env, provider)
            for provider in ("openai", "anthropic")
        ):
            return (
                "Needs setup",
                "Connected-account route is configured; create or sign in to the local account and verify the provider connection in Settings > Connected Accounts.",
            )
        return "Needs setup", feature_guidance(key)
    if key == "secondary_ai":
        if secondary_ai_configured(config):
            return (
                "Configured",
                "Fallback credential is present; validity is confirmed only by a live provider request.",
            )
        return "Needs setup", "No fallback configured; add one later if you want provider redundancy."
    if key == "transcript_ingest":
        source = transcript_source_dir(config, runtime_env)
        if source:
            return configured_unverified("Transcript source folder configured")
        return "Needs setup", feature_guidance(key)
    if key == "conversation_recall":
        if resolve_bool(personalization.get("default_conversation_recall"), False):
            return configured_unverified("Local recall/RAG enabled")
        return "Needs setup", feature_guidance(key)
    if key == "web_search":
        if resolve_bool((integrations.get("web_search") or {}).get("enabled"), False):
            return configured_unverified(web_search_summary(config))
        return "Needs setup", feature_guidance(key)
    if key == "voice":
        degraded_voice = str(
            runtime_env.get("VIVENTIUM_VOICE_DEGRADED_REASON") or ""
        ).strip()
        if degraded_voice == "legacy_xai_voice_agent_route_retired":
            return "Action Required", voice_status(config, runtime_env)
        mode = str(voice.get("mode") or "disabled").strip().lower()
        if mode in {"local", "hosted"}:
            return configured_unverified(voice_status(config, runtime_env))
        return "Needs setup", feature_guidance(key)
    if key == "telegram":
        if resolve_bool((integrations.get("telegram") or {}).get("enabled"), False):
            return configured_unverified("Telegram bridge configured")
        return "Needs setup", feature_guidance(key)
    if key == "telegram_codex":
        if resolve_bool((integrations.get("telegram_codex") or {}).get("enabled"), False):
            return configured_unverified("Telegram Codex configured")
        return "Needs setup", feature_guidance(key)
    if key == "google_workspace":
        if resolve_bool((integrations.get("google_workspace") or {}).get("enabled"), False):
            return configured_unverified("Google Workspace MCP configured")
        return "Needs setup", feature_guidance(key)
    if key == "ms365":
        if resolve_bool((integrations.get("ms365") or {}).get("enabled"), False):
            return configured_unverified("Microsoft 365 MCP configured")
        return "Needs setup", feature_guidance(key)
    if key in GUIDED_EXPRESS_KEYS:
        return "Needs setup", feature_guidance(key)
    if key in UNAVAILABLE_KEYS:
        return "Not available", feature_guidance(key)
    if key in ADVANCED_OFF_KEYS:
        enabled = False
        if key == "remote_access":
            enabled = normalize_remote_call_mode(config) != "disabled"
        else:
            enabled = resolve_bool((integrations.get(key) or {}).get("enabled"), False)
        if enabled:
            return configured_unverified("Explicitly enabled by this install")
        return "Disabled by choice", feature_guidance(key)
    return configured_unverified(
        FEATURE_BY_KEY.get(key).health_probe if key in FEATURE_BY_KEY else "Configuration present"
    )


def build_brain_setup_rows(
    config: dict[str, Any],
    runtime_env: dict[str, str],
) -> list[tuple[str, str, str]]:
    # Internal/lab-only features remain in the readiness registry for release gates, but exposing
    # an unavailable experiment in the user-facing Easy Install checklist adds noise and implies
    # that the user should care about it. Explicit legacy configuration still appears in the live
    # service summary so an existing operator receives honest repair guidance.
    keys = tuple(key for key in FEATURE_BY_KEY if key not in UNAVAILABLE_KEYS)
    return [
        (feature_label(key), *brain_setup_state(key, config, runtime_env))
        for key in keys
    ]


def build_service_rows(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    *,
    runtime_dir: Path | None = None,
    repo_root: Path | None = None,
    probe_live: bool,
) -> list[tuple[str, str, str]]:
    frontend_port = runtime_port(
        config,
        runtime_env,
        "VIVENTIUM_LC_FRONTEND_PORT",
        "lc_frontend_port",
        3190,
    )
    api_port = runtime_port(config, runtime_env, "VIVENTIUM_LC_API_PORT", "lc_api_port", 3180)
    playground_port = runtime_port(
        config,
        runtime_env,
        "VIVENTIUM_PLAYGROUND_PORT",
        "playground_port",
        3300,
    )

    frontend_url = f"http://localhost:{frontend_port}"
    api_url = f"http://localhost:{api_port}/api"
    playground_url = runtime_env.get("VIVENTIUM_PLAYGROUND_URL") or f"http://localhost:{playground_port}"
    install_experience = str(
        runtime_env.get("VIVENTIUM_INSTALL_EXPERIENCE")
        or (config.get("install", {}) or {}).get("experience")
        or "legacy"
    ).strip().lower()
    express_experience = install_experience == "express"
    livekit_url = runtime_env.get("LIVEKIT_URL", "ws://localhost:7880")
    stack_should_be_live = stack_expected_live(config, runtime_env, runtime_dir)
    startup_in_progress = cli_operation_running(runtime_dir)
    remote_status, remote_detail = remote_access_status_and_detail(
        config,
        runtime_env,
        runtime_dir,
        probe_live=probe_live,
        stack_should_be_live=stack_should_be_live,
    )
    auth_settings = resolve_runtime_auth(config, runtime_env)
    runtime = config.get("runtime", {}) or {}
    code_interpreter_url = runtime_env.get("LIBRECHAT_CODE_BASEURL", "")
    rag_api_url = runtime_env.get("RAG_API_URL", "")
    google_mcp_url = runtime_env.get("GOOGLE_WORKSPACE_MCP_URL", "")
    ms365_mcp_url = runtime_env.get("MS365_MCP_SERVER_URL", "")
    searxng_url = runtime_env.get("SEARXNG_INSTANCE_URL", "")
    firecrawl_url = runtime_env.get("FIRECRAWL_API_URL") or runtime_env.get("FIRECRAWL_BASE_URL", "")
    glasshive_url = runtime_env.get("GLASSHIVE_OPERATOR_BASE_URL") or runtime_env.get("GLASSHIVE_MCP_URL", "")
    glasshive_probe_url = glasshive_url
    if resolve_bool(runtime_env.get("GLASSHIVE_PUBLIC_LINKS_ONLY"), False):
        glasshive_ui_port = str(runtime_env.get("GLASSHIVE_UI_PORT") or "8780").strip()
        glasshive_probe_url = f"http://127.0.0.1:{glasshive_ui_port}"
    prompt_workbench_port = str(runtime_env.get("VIVENTIUM_PROMPT_WORKBENCH_PORT") or "8781").strip()
    prompt_workbench_url = f"http://localhost:{prompt_workbench_port}" if prompt_workbench_port else ""

    frontend_ok = (
        any_http_ok(
            f"http://localhost:{frontend_port}",
            f"http://127.0.0.1:{frontend_port}",
        )
        if probe_live
        else False
    )
    api_ok = (
        any_http_ok(
            f"http://localhost:{api_port}/api/health",
            f"http://127.0.0.1:{api_port}/api/health",
            f"http://localhost:{api_port}/health",
            f"http://127.0.0.1:{api_port}/health",
        )
        if probe_live
        else False
    )
    playground_ok = (
        any_http_ok(
            playground_url,
            url_with_path(playground_url, "/api/health"),
            f"http://127.0.0.1:{playground_port}/api/health",
        )
        if probe_live
        else False
    )
    missing_core_status = (
        "Starting"
        if probe_live and stack_should_be_live
        else "Configured"
    )

    voice_detail = voice_status(config, runtime_env)
    voice_degraded = (
        str(runtime_env.get("VIVENTIUM_VOICE_DEGRADED_REASON") or "").strip()
        == "legacy_xai_voice_agent_route_retired"
    )
    rows: list[tuple[str, str, str]] = [
        ("LibreChat Frontend", "Running" if frontend_ok else missing_core_status, frontend_url),
        ("LibreChat API", "Running" if api_ok else missing_core_status, api_url),
        (
            "Modern Playground",
            "Running" if playground_ok else ("Deferred" if express_experience else missing_core_status),
            playground_url
            if playground_ok or not express_experience
            else "Disabled by Easy Install; enable Voice when you want the playground.",
        ),
        (
            "Voice",
            "Action Required"
            if voice_degraded
            else ("Configured" if voice_detail != "Disabled" else "Disabled"),
            voice_detail,
        ),
        (
            "LiveKit",
            "Configured" if livekit_url else "Disabled",
            livekit_url or "Not configured",
        ),
        ("Remote Access", remote_status, remote_detail),
    ]

    scheduler_status, scheduler_detail = scheduler_status_and_detail(
        config,
        runtime_env,
        runtime_dir,
        probe_live=probe_live,
        stack_should_be_live=stack_should_be_live,
        startup_in_progress=startup_in_progress,
    )
    rows.append(("Scheduler", scheduler_status, scheduler_detail))

    integrations = config.get("integrations", {}) or {}
    primary = ((config.get("llm", {}) or {}).get("primary", {}) or {})
    primary_auth_mode = str(primary.get("auth_mode") or "api_key").strip().lower()
    primary_provider = str(primary.get("provider") or "").strip().lower()
    primary_label = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
    }.get(primary_provider, "your model provider")
    primary_status = "Configured"
    primary_detail = "API key"
    if primary_auth_mode == "connected_account":
        if foundation_api_key_present(config):
            primary_detail = f"{primary_label} connected account or API-key fallback"
        elif foundation_connected_account_runtime_configured(config, runtime_env, primary_provider):
            primary_detail = (
                f"{primary_label} account-scoped route configured; verify the signed-in user's "
                "Connected Accounts page for OAuth state"
            )
        else:
            primary_status = "Experimental setup" if express_experience else "Action Required"
            primary_detail = (
                f"Enable and connect the experimental {primary_label} account bridge in "
                "Settings > Account > Connected Accounts"
            )
    elif primary_auth_mode == "user_provided":
        primary_status = "Add in browser" if express_experience else "Action Required"
        primary_detail = (
            f"Add an {primary_label} API key in Settings > Account > Connected Accounts"
        )
    elif primary_auth_mode == "api_key" and not secret_node_configured(primary):
        primary_status = "Action Required"
        primary_detail = f"Add an {primary_label} API key with bin/viventium configure"
    rows.append(
        (
            "Primary AI",
            primary_status,
            primary_detail,
        )
    )
    rows.append(
        (
            "Account Sign-up",
            "Bootstrap Only"
            if auth_settings["allow_registration"] and auth_settings["bootstrap_registration_once"]
            else ("Open" if auth_settings["allow_registration"] else "Closed"),
            "Browser sign-up stays open only until the first account is created, then closes automatically"
            if auth_settings["allow_registration"] and auth_settings["bootstrap_registration_once"]
            else (
                "Anyone can create an account in the browser"
                if auth_settings["allow_registration"]
                else "Only existing accounts can sign in"
            ),
        )
    )
    rows.append(
        (
            "Password Reset",
            "Enabled" if auth_settings["allow_password_reset"] else "Disabled",
            "Public browser reset endpoint is enabled"
            if auth_settings["allow_password_reset"]
            else "Use bin/viventium password-reset-link <email> locally when you need a one-time reset link",
        )
    )

    if resolve_bool((integrations.get("glasshive") or {}).get("enabled"), False) or resolve_bool(runtime_env.get("START_GLASSHIVE"), False):
        glasshive_running = probe_live and glasshive_probe_url and any_http_ok(
            glasshive_probe_url,
            url_with_path(glasshive_probe_url, "/health"),
        )
        if glasshive_running:
            glasshive_status = "Running"
        elif probe_live and stack_should_be_live and resolve_bool(runtime_env.get("START_GLASSHIVE"), False):
            glasshive_status = "Starting" if startup_in_progress else "Action Required"
        else:
            glasshive_status = "Configured"
        worker_profile = runtime_env.get("GLASSHIVE_DEFAULT_WORKER_PROFILE") or "codex-cli"
        rows.append(
            (
                "GlassHive",
                glasshive_status,
                f"{glasshive_url or 'Local GlassHive runtime'} | default worker: {worker_profile}",
            )
        )

    if resolve_bool(((runtime.get("prompt_workbench") or {}).get("enabled")), False) or resolve_bool(runtime_env.get("START_PROMPT_WORKBENCH"), False):
        workbench_running = probe_live and prompt_workbench_url and any_http_ok(
            prompt_workbench_url,
            url_with_path(prompt_workbench_url, "/api/health"),
        )
        if workbench_running:
            workbench_status = "Running"
        elif probe_live and stack_should_be_live and resolve_bool(runtime_env.get("START_PROMPT_WORKBENCH"), False):
            workbench_status = "Starting" if startup_in_progress else "Action Required"
        else:
            workbench_status = "Configured"
        rows.append(("Prompt Workbench", workbench_status, prompt_workbench_url or "Local Prompt Workbench"))

    seed_nightly = (runtime.get("prompt_workbench") or {}).get("seed_nightly") or {}
    if resolve_bool(seed_nightly.get("enabled"), resolve_bool(runtime_env.get("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED"), False)):
        nightly_active = resolve_bool(seed_nightly.get("active"), resolve_bool(runtime_env.get("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE"), False))
        nightly_executor = (
            runtime_env.get("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR")
            or seed_nightly.get("executor")
            or "glasshive_host"
        )
        rows.append(
            (
                "Nightly Reflection",
                "Active" if nightly_active else "Configured",
                f"03:00 local Workbench schedule via {nightly_executor}; seeded for the first resolved local admin user",
            )
        )

    memory_hardening = runtime.get("memory_hardening") or {}
    if resolve_bool(memory_hardening.get("enabled"), resolve_bool(runtime_env.get("VIVENTIUM_MEMORY_HARDENING_ENABLED"), False)):
        memory_scope = "all memory-enabled users unless scoped in config"
        operator_scope = str(memory_hardening.get("operator_user_email") or "").strip()
        if operator_scope:
            memory_scope = "single configured operator user"
        dry_run_first = resolve_bool(
            runtime_env.get("VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST"),
            resolve_bool(memory_hardening.get("dry_run_first"), True),
        )
        memory_detail = (
            f"{runtime_env.get('VIVENTIUM_MEMORY_HARDENING_SCHEDULE') or memory_hardening.get('schedule') or '0 3 * * *'} local; "
            f"{memory_scope}; dry-run-first {'on' if dry_run_first else 'off'}"
        )
        memory_status = "Scheduled"
        if probe_live:
            hardening_status = memory_hardening_status_payload(
                repo_root=repo_root,
                runtime_dir=runtime_dir,
                runtime_env=runtime_env,
            )
            schedule_health = (
                hardening_status.get("schedule_health")
                if isinstance(hardening_status, dict)
                and isinstance(hardening_status.get("schedule_health"), dict)
                else {}
            )
            health_state = str(schedule_health.get("state") or "unavailable").strip().lower()
            memory_status = {
                "healthy": "Healthy",
                "running": "Running",
                "awaiting_first_run": "Scheduled",
                "retry_pending": "Retry Pending",
            }.get(health_state, "Action Required")
            memory_detail = f"{memory_detail}; health {health_state}"
        rows.append(
            (
                "Memory Hardening",
                memory_status,
                memory_detail,
            )
        )
        source_dir = transcript_source_dir(config, runtime_env)
        rows.append(
            (
                "Transcript Ingest",
                "Configured" if source_dir else "Needs setup",
                "Transcript source folder configured"
                if source_dir
                else "Choose a folder with bin/viventium transcripts source set <folder>; empty means pending, not failed",
            )
        )

    if resolve_bool((integrations.get("telegram") or {}).get("enabled"), False):
        telegram_status, telegram_detail = telegram_service_status(
            config=config,
            runtime_env=runtime_env,
            runtime_dir=runtime_dir,
            repo_root=repo_root,
            probe_live=probe_live,
            token_env_key="BOT_TOKEN",
            log_file_name="telegram_bot.log",
            pid_file_name="telegram_bot.pid",
            running_detail="Polling Telegram bridge on this Mac",
            pending_pid_file_name="telegram_bot_deferred.pid",
            pending_marker_file_name="telegram_bot_deferred.pending",
            pending_detail="Waiting for LibreChat API before first Telegram bridge start on this Mac",
            requires_lc_api=True,
        )
        rows.append(("Telegram Bridge", telegram_status, telegram_detail))
    if resolve_bool((integrations.get("telegram_codex") or {}).get("enabled"), False):
        telegram_codex_status, telegram_codex_detail = telegram_service_status(
            config=config,
            runtime_env=runtime_env,
            runtime_dir=runtime_dir,
            repo_root=repo_root,
            probe_live=probe_live,
            token_env_key="TELEGRAM_CODEX_BOT_TOKEN",
            log_file_name="telegram_codex.log",
            pid_file_name="telegram_codex.pid",
            running_detail="Polling Telegram Codex on this Mac",
        )
        rows.append(("Telegram Codex", telegram_codex_status, telegram_codex_detail))
    if resolve_bool((((config.get("runtime") or {}).get("personalization") or {}).get("default_conversation_recall")), False):
        conversation_recall_health_url = f"{rag_api_url.rstrip('/')}/health" if rag_api_url else ""
        conversation_recall_running = (
            probe_live
            and bool(rag_api_url)
            and http_json_status_up(conversation_recall_health_url)
        )
        if conversation_recall_running:
            conversation_recall_status = "Running"
        elif probe_live and stack_should_be_live and rag_api_url:
            conversation_recall_status = "Starting" if startup_in_progress else "Action Required"
        else:
            conversation_recall_status = "Configured"
        rows.append(
            (
                "Conversation Recall",
                conversation_recall_status,
                rag_api_url or "Local recall sidecar",
            )
        )
    if resolve_bool((integrations.get("web_search") or {}).get("enabled"), False):
        rows.append(("Web Search", "Configured", web_search_summary(config)))
        if searxng_url:
            searxng_live = probe_live and http_ok(searxng_url)
            if searxng_live:
                searxng_status = "Running"
            elif runtime_env.get("START_SEARXNG") == "true":
                searxng_status = "Starting" if startup_in_progress else "Action Required"
            else:
                searxng_status = "External"
            rows.append(
                (
                    "SearXNG",
                    searxng_status,
                    searxng_url,
                )
            )
        if firecrawl_url:
            firecrawl_live = probe_live and (http_ok(firecrawl_url) or port_open(3003))
            if firecrawl_live:
                firecrawl_status = "Running"
            elif runtime_env.get("START_FIRECRAWL") == "true":
                firecrawl_status = "Starting" if startup_in_progress else "Action Required"
            else:
                firecrawl_status = "External"
            firecrawl_detail = firecrawl_url
            memory_warning = local_firecrawl_memory_warning(config)
            if (
                probe_live
                and not firecrawl_live
                and runtime_env.get("START_FIRECRAWL") == "true"
                and not startup_in_progress
                and memory_warning
            ):
                firecrawl_status = "Needs Docker RAM"
                firecrawl_detail = memory_warning
            rows.append(("Firecrawl", firecrawl_status, firecrawl_detail))
    if resolve_bool((integrations.get("code_interpreter") or {}).get("enabled"), False):
        rows.append(
            (
                "Code Interpreter",
                "Running" if (probe_live and code_interpreter_url and http_ok(f"{code_interpreter_url}/health")) else "Configured",
                code_interpreter_url or "Local sandbox sidecar",
            )
        )
    if resolve_bool((integrations.get("google_workspace") or {}).get("enabled"), False):
        status, detail = mcp_service_status(
            url=google_mcp_url,
            start_enabled=resolve_bool(runtime_env.get("START_GOOGLE_MCP"), False),
            probe_live=probe_live,
            stack_should_be_live=stack_should_be_live,
            startup_in_progress=startup_in_progress,
            default_detail="Local MCP server",
        )
        rows.append(("Google Workspace MCP", status, detail))
    if resolve_bool((integrations.get("ms365") or {}).get("enabled"), False):
        status, detail = mcp_service_status(
            url=ms365_mcp_url,
            start_enabled=resolve_bool(runtime_env.get("START_MS365_MCP"), False),
            probe_live=probe_live,
            stack_should_be_live=stack_should_be_live,
            startup_in_progress=startup_in_progress,
            default_detail="Local MCP server",
        )
        rows.append(("Microsoft 365 MCP", status, detail))
    if resolve_bool((integrations.get("skyvern") or {}).get("enabled"), False):
        rows.append(("Skyvern", "Configured", "Local browser-agent service"))
    if resolve_bool((integrations.get("openclaw") or {}).get("enabled"), False):
        rows.append(
            (
                "OpenClaw",
                "Not available",
                "Public runtime integration is not shipped; remove the lab-only configuration.",
            )
        )

    helper_row = macos_helper_status(
        runtime_dir=runtime_dir,
        probe_live=probe_live,
        stack_should_be_live=stack_should_be_live,
    )
    if helper_row is not None:
        rows.append(helper_row)

    checkout_row = stack_owner_checkout_row(config, runtime_env, runtime_dir, repo_root)
    if checkout_row is not None:
        rows.insert(0, checkout_row)

    return rows


def live_core_services_ready(rows: list[tuple[str, str, str]]) -> bool:
    statuses = {name: status for name, status, _detail in rows}
    return (
        statuses.get("LibreChat Frontend") == "Running"
        and statuses.get("LibreChat API") == "Running"
        and statuses.get("Modern Playground") in {"Running", "Deferred"}
    )


def live_services_need_attention(rows: list[tuple[str, str, str]]) -> bool:
    attention_statuses = {
        "Action Required",
        "Misconfigured",
        "Stopped",
        "Needs Docker RAM",
        "Running with issues",
    }
    return any(status in attention_statuses for _name, status, _detail in rows)


def live_services_still_starting(rows: list[tuple[str, str, str]]) -> bool:
    return any(status == "Starting" for _name, status, _detail in rows)


def resolve_summary_heading(
    probe_live: bool,
    rows: list[tuple[str, str, str]],
    stack_should_be_live: bool,
) -> tuple[str, str, str]:
    if not probe_live:
        return (
            "Viventium is configured",
            "The table below shows the services this install is set up to run.",
            "Configured Services",
        )

    if live_core_services_ready(rows) and live_services_need_attention(rows):
        return (
            "Viventium needs attention",
            "The core web surfaces are reachable, but one or more enabled runtime surfaces are not healthy.",
            "Live Services",
        )

    if live_core_services_ready(rows) and live_services_still_starting(rows):
        return (
            "Viventium is still starting",
            "The core web surfaces are reachable, but one or more enabled runtime surfaces are still warming up.",
            "Live Services",
        )

    if live_core_services_ready(rows):
        return (
            "Viventium is ready",
            "The table below reflects the live surfaces Viventium can currently reach on this Mac.",
            "Live Services",
        )

    if not stack_should_be_live:
        return (
            "Viventium is configured",
            "The table below shows the services this install is set up to run. Start the stack when you want the local surfaces live on this Mac.",
            "Configured Services",
        )

    return (
        "Viventium is still starting",
        "The table below reflects the live surfaces Viventium can currently reach on this Mac. Core services are still warming up.",
        "Live Services",
    )


def build_setup_later_rows(config: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for label, state, action in build_brain_setup_rows(config, {}):
        if state == "Ready":
            continue
        if label == "Conversation Recall/RAG":
            retrieval_embeddings = resolve_retrieval_embeddings_settings(config)
            if retrieval_embeddings["provider"] == "ollama":
                action = (
                    "Docker Desktop and Ollama if you want local recall; "
                    f"first start pulls {retrieval_embeddings['model']}"
                )
        rows.append((label, action))
    return rows


def build_next_steps(
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None = None,
) -> list[str]:
    frontend_port = runtime_port(
        config,
        runtime_env,
        "VIVENTIUM_LC_FRONTEND_PORT",
        "lc_frontend_port",
        3190,
    )
    public_state = load_public_network_state(config, runtime_env, runtime_dir)
    remote_error = str(public_state.get("last_error") or "").strip()
    public_client_url = str(
        public_state.get("public_client_url") or runtime_env.get("VIVENTIUM_PUBLIC_CLIENT_URL") or ""
    ).strip()
    remote_call_mode = normalize_remote_call_mode(config)
    stack_should_be_live = stack_expected_live(config, runtime_env, runtime_dir)
    next_steps: list[str] = []
    if not stack_should_be_live:
        next_steps.append(
            f"Run [cyan]{stack_owner_command(config, runtime_env, runtime_dir)}[/cyan] to bring this configured install live on this Mac."
        )
    next_steps.extend(
        [
            "Run [cyan]bin/viventium status[/cyan] any time to recheck live service health.",
            f"Open [cyan]http://localhost:{frontend_port}[/cyan] on this Mac.",
        ]
    )
    if remote_error:
        next_steps.append(
            "Remote access could not start on this run. Fix the blocker shown in "
            f"[cyan]bin/viventium status[/cyan] and then rerun [cyan]bin/viventium start[/cyan]. ({remote_error})"
        )
    elif public_client_url:
        next_steps.append(
            f"Outside your local network, open [cyan]{public_client_url}[/cyan]."
        )
        next_steps.append(
            "Optional, after the directory website is deployed: run [cyan]bin/viventium register-link <username>[/cyan] to publish a redirect-only vanity link under [cyan]viventium.ai/u/<username>[/cyan]."
        )
    elif remote_call_mode == "tailscale_tailnet_https":
        next_steps.append(
            "After Tailscale is connected on this Mac, run [cyan]bin/viventium start[/cyan] and then [cyan]bin/viventium status[/cyan] to see the private device URL."
        )
    elif remote_call_mode == "public_https_edge":
        next_steps.append(
            "After [cyan]bin/viventium start[/cyan], run [cyan]bin/viventium status[/cyan] to see the exact outside URL Viventium published for this machine."
        )
    install_mode = str(((config.get("install") or {}).get("mode") or "native")).strip().lower()
    if install_mode == "native":
        next_steps.append(
            "Native installs run the core Viventium services as local background processes. Docker containers are only expected for Docker-backed features such as local SearXNG and Firecrawl."
        )
    next_steps.append(
        "Optional: run [cyan]bin/viventium shell-init[/cyan] for the one-line setup that adds "
        "[cyan]viventium[/cyan] and [cyan]viv[/cyan] as global commands."
    )
    next_steps.append(
        "Remote access is optional. For private-device or public-browser setup, see "
        "[cyan]docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md[/cyan]."
    )
    auth_settings = resolve_runtime_auth(config, runtime_env)
    if auth_settings["allow_registration"] and auth_settings["bootstrap_registration_once"]:
        next_steps.append(
            "Browser sign-up is in bootstrap-only mode for this install: it closes automatically after the first account is created."
        )
    next_steps.append(
        "Keep [cyan]ALLOW_PASSWORD_RESET[/cyan] off for public installs unless real email delivery is configured. For a one-time operator-issued reset link, run [cyan]bin/viventium password-reset-link <email>[/cyan] locally."
    )
    next_steps.append("Add or change features later with [cyan]bin/viventium configure[/cyan].")
    return next_steps


def build_connected_accounts_notice(config: dict[str, Any], runtime_env: dict[str, str] | None = None) -> str | None:
    runtime_env = runtime_env or {}
    integrations = config.get("integrations", {}) or {}
    foundation_needed = not foundation_api_key_present(config)
    google_workspace_enabled = resolve_bool(
        (integrations.get("google_workspace") or {}).get("enabled"),
        False,
    )
    ms365_enabled = resolve_bool((integrations.get("ms365") or {}).get("enabled"), False)

    if not foundation_needed and not google_workspace_enabled and not ms365_enabled:
        return None

    lines = [
        "After you create your account in the browser:",
        "1. Click your account in the left sidebar.",
        "2. Open [cyan]Settings -> Connected Accounts[/cyan].",
    ]
    next_step = 3

    if foundation_needed:
        foundation_labels = configured_foundation_account_labels(config)
        if not foundation_labels:
            foundation_labels = ["OpenAI", "Anthropic"]
        if len(foundation_labels) == 1:
            foundation_label = f"[bold]{foundation_labels[0]}[/bold]"
        else:
            foundation_label = " and ".join(f"[bold]{label}[/bold]" for label in foundation_labels)
        lines.append(
            f"{next_step}. Connect {foundation_label} so the shipped Viventium and background agents can run on this install."
        )
        next_step += 1

    workspace_accounts: list[str] = []
    if google_workspace_enabled:
        workspace_accounts.append("[bold]Google Workspace[/bold]")
    if ms365_enabled:
        workspace_accounts.append("[bold]Microsoft 365[/bold]")
    if workspace_accounts:
        if len(workspace_accounts) == 2:
            workspace_label = f"{workspace_accounts[0]} and {workspace_accounts[1]}"
        else:
            workspace_label = workspace_accounts[0]
        lines.append(
            f"{next_step}. Connect {workspace_label} if you want Gmail/Drive or Outlook/MS365 tasks on this user account."
        )
        lines.append(
            "Foundation-model auth and workspace OAuth are separate layers. Activation can succeed while tool execution still waits on a missing or expired service connection."
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the Viventium install or runtime summary.")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--runtime-dir", help="Path to generated runtime dir")
    parser.add_argument("--repo-root", help="Checkout running this summary command")
    parser.add_argument(
        "--stack-started",
        action="store_true",
        help="Legacy alias that also enables live health probes.",
    )
    parser.add_argument(
        "--probe-live",
        action="store_true",
        help="Probe local services and show live health status.",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config).expanduser().resolve())
    runtime_dir = Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else None
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else None
    runtime_env = load_runtime_env(runtime_dir)
    probe_live = args.probe_live or args.stack_started
    ui = InstallerUI()

    service_rows = build_service_rows(
        config,
        runtime_env,
        runtime_dir=runtime_dir,
        repo_root=repo_root,
        probe_live=probe_live,
    )
    heading, intro, table_title = resolve_summary_heading(
        probe_live,
        service_rows,
        stack_expected_live(config, runtime_env, runtime_dir),
    )
    ui.print_section(heading, intro, style="green")
    ui.print_table(
        table_title,
        ("Component", "Status", "Details"),
        service_rows,
        style="green",
    )

    brain_setup_rows = build_brain_setup_rows(config, runtime_env)
    if brain_setup_rows:
        ui.print_blank()
        ui.print_table(
            "Viventium Brain Setup",
            ("Surface", "State", "Next action"),
            brain_setup_rows,
            style="yellow",
        )

    connected_accounts_notice = build_connected_accounts_notice(config, runtime_env)
    if connected_accounts_notice:
        ui.print_blank()
        ui.print_section(
            "Connect AI Accounts First",
            connected_accounts_notice,
            style="yellow",
        )

    next_steps = build_next_steps(config, runtime_env, runtime_dir)

    ui.print_blank()
    ui.print_section("Next Steps", "\n".join(f"{index}. {step}" for index, step in enumerate(next_steps, start=1)), style="cyan")


if __name__ == "__main__":
    main()
