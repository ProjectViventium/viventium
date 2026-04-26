#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from installer_ui import InstallerUI  # noqa: E402
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


def configured_foundation_connected_account_labels(config: dict[str, Any]) -> list[str]:
    llm = config.get("llm", {}) or {}
    primary = llm.get("primary", {}) or {}
    secondary = llm.get("secondary", {}) or {}
    labels: list[str] = []
    for node in (primary, secondary):
        provider = str(node.get("provider") or "").strip().lower()
        auth_mode = str(node.get("auth_mode") or "").strip().lower()
        if auth_mode != "connected_account":
            continue
        label = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
        }.get(provider)
        if label and label not in labels:
            labels.append(label)
    return labels


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


def any_http_ok(*urls: str) -> bool:
    return any(url and http_ok(url) for url in urls)


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
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
    if runtime_dir is None:
        return None
    return runtime_dir.parent / "state" / "runtime" / runtime_profile_name(config, runtime_env)


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


def telegram_service_status(
    *,
    config: dict[str, Any],
    runtime_env: dict[str, str],
    runtime_dir: Path | None,
    probe_live: bool,
    token_env_key: str,
    log_file_name: str,
    pid_file_name: str,
    running_detail: str,
    pending_pid_file_name: str | None = None,
    pending_marker_file_name: str | None = None,
    pending_detail: str | None = None,
) -> tuple[str, str]:
    token = str(runtime_env.get(token_env_key, "") or "").strip()
    state_root = runtime_state_root(config, runtime_env, runtime_dir)
    log_detail = "Starts with Viventium"
    process_running = False
    pending_running = False

    if state_root is not None:
        log_detail = str(state_root / "logs" / log_file_name)
        pid_candidates = (
            state_root / pid_file_name,
            state_root / "logs" / pid_file_name,
        )
        process_running = any(pid_file_process_running(candidate) for candidate in pid_candidates)
        if pending_pid_file_name:
            pending_pid_candidates = (
                state_root / pending_pid_file_name,
                state_root / "logs" / pending_pid_file_name,
            )
            pending_running = any(pid_file_process_running(candidate) for candidate in pending_pid_candidates)
        if not pending_running and pending_marker_file_name:
            pending_marker_candidates = (
                state_root / pending_marker_file_name,
                state_root / "logs" / pending_marker_file_name,
            )
            pending_running = any(candidate.is_file() for candidate in pending_marker_candidates)

    if process_running:
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

    if probe_live:
        return "Stopped", f"Check {log_detail}"
    return "Configured", "Starts with Viventium"


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


def voice_status(config: dict[str, Any]) -> str:
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
    lan_host = local_network_host()
    lan_url = f"http://{lan_host}:{frontend_port}" if lan_host else ""
    api_url = f"http://localhost:{api_port}/api"
    playground_url = runtime_env.get("VIVENTIUM_PLAYGROUND_URL") or f"http://localhost:{playground_port}"
    livekit_url = runtime_env.get("LIVEKIT_URL", "ws://localhost:7880")
    stack_should_be_live = stack_expected_live(config, runtime_env, runtime_dir)
    remote_status, remote_detail = remote_access_status_and_detail(
        config,
        runtime_env,
        runtime_dir,
        probe_live=probe_live,
        stack_should_be_live=stack_should_be_live,
    )
    auth_settings = resolve_runtime_auth(config, runtime_env)
    code_interpreter_url = runtime_env.get("LIBRECHAT_CODE_BASEURL", "")
    rag_api_url = runtime_env.get("RAG_API_URL", "")
    google_mcp_url = runtime_env.get("GOOGLE_WORKSPACE_MCP_URL", "")
    ms365_mcp_url = runtime_env.get("MS365_MCP_SERVER_URL", "")
    searxng_url = runtime_env.get("SEARXNG_INSTANCE_URL", "")
    firecrawl_url = runtime_env.get("FIRECRAWL_API_URL") or runtime_env.get("FIRECRAWL_BASE_URL", "")

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
            f"http://127.0.0.1:{playground_port}",
        )
        if probe_live
        else False
    )
    missing_core_status = (
        "Starting"
        if probe_live and stack_should_be_live
        else ("Configured" if probe_live else "Ready")
    )

    frontend_detail = frontend_url
    if lan_url:
        frontend_detail = f"Local: {frontend_url} | Network: {lan_url}"

    rows: list[tuple[str, str, str]] = [
        ("LibreChat Frontend", "Running" if frontend_ok else missing_core_status, frontend_detail),
        ("LibreChat API", "Running" if api_ok else missing_core_status, api_url),
        (
            "Modern Playground",
            "Running" if playground_ok else missing_core_status,
            playground_url,
        ),
        (
            "Voice",
            "Configured" if voice_status(config) != "Disabled" else "Disabled",
            voice_status(config),
        ),
        (
            "LiveKit",
            "Configured" if livekit_url else "Disabled",
            livekit_url or "Not configured",
        ),
        ("Remote Access", remote_status, remote_detail),
    ]

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
        else:
            primary_status = "Action Required"
            primary_detail = (
                f"Connect {primary_label} in Settings > Account > Connected Accounts"
            )
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

    if resolve_bool((integrations.get("telegram") or {}).get("enabled"), False):
        telegram_status, telegram_detail = telegram_service_status(
            config=config,
            runtime_env=runtime_env,
            runtime_dir=runtime_dir,
            probe_live=probe_live,
            token_env_key="BOT_TOKEN",
            log_file_name="telegram_bot.log",
            pid_file_name="telegram_bot.pid",
            running_detail="Polling Telegram bridge on this Mac",
            pending_pid_file_name="telegram_bot_deferred.pid",
            pending_marker_file_name="telegram_bot_deferred.pending",
            pending_detail="Waiting for LibreChat API before first Telegram bridge start on this Mac",
        )
        rows.append(("Telegram Bridge", telegram_status, telegram_detail))
    if resolve_bool((integrations.get("telegram_codex") or {}).get("enabled"), False):
        telegram_codex_status, telegram_codex_detail = telegram_service_status(
            config=config,
            runtime_env=runtime_env,
            runtime_dir=runtime_dir,
            probe_live=probe_live,
            token_env_key="TELEGRAM_CODEX_BOT_TOKEN",
            log_file_name="telegram_codex.log",
            pid_file_name="telegram_codex.pid",
            running_detail="Polling Telegram Codex on this Mac",
        )
        rows.append(("Telegram Codex", telegram_codex_status, telegram_codex_detail))
    if resolve_bool((((config.get("runtime") or {}).get("personalization") or {}).get("default_conversation_recall")), False):
        conversation_recall_running = probe_live and rag_api_url and http_ok(rag_api_url)
        conversation_recall_status = (
            "Running"
            if conversation_recall_running
            else ("Starting" if probe_live and stack_should_be_live and rag_api_url else "Configured")
        )
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
            rows.append(
                (
                    "SearXNG",
                    "Running" if (probe_live and http_ok(searxng_url)) else ("Configured" if runtime_env.get("START_SEARXNG") == "true" else "External"),
                    searxng_url,
                )
            )
        if firecrawl_url:
            firecrawl_live = probe_live and (http_ok(firecrawl_url) or port_open(3003))
            firecrawl_status = "Running" if firecrawl_live else (
                "Configured" if runtime_env.get("START_FIRECRAWL") == "true" else "External"
            )
            firecrawl_detail = firecrawl_url
            memory_warning = local_firecrawl_memory_warning(config)
            if (
                probe_live
                and not firecrawl_live
                and runtime_env.get("START_FIRECRAWL") == "true"
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
        rows.append(("Google Workspace MCP", "Configured", google_mcp_url or "Local MCP server"))
    if resolve_bool((integrations.get("ms365") or {}).get("enabled"), False):
        rows.append(("Microsoft 365 MCP", "Configured", ms365_mcp_url or "Local MCP server"))
    if resolve_bool((integrations.get("skyvern") or {}).get("enabled"), False):
        rows.append(("Skyvern", "Configured", "Local browser-agent service"))
    if resolve_bool((integrations.get("openclaw") or {}).get("enabled"), False):
        rows.append(("OpenClaw", "Configured", "Exposure monitoring integration"))

    checkout_row = stack_owner_checkout_row(config, runtime_env, runtime_dir, repo_root)
    if checkout_row is not None:
        rows.insert(0, checkout_row)

    return rows


def live_core_services_ready(rows: list[tuple[str, str, str]]) -> bool:
    statuses = {name: status for name, status, _detail in rows}
    return all(
        statuses.get(name) == "Running"
        for name in ("LibreChat Frontend", "LibreChat API", "Modern Playground")
    )


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
    integrations = config.get("integrations", {}) or {}
    runtime = config.get("runtime", {}) or {}
    personalization = runtime.get("personalization", {}) or {}

    rows: list[tuple[str, str]] = []
    if not resolve_bool(personalization.get("default_conversation_recall"), False):
        retrieval_embeddings = resolve_retrieval_embeddings_settings(config)
        if retrieval_embeddings["provider"] == "ollama":
            rows.append(
                (
                    "Conversation Recall",
                    f"Docker Desktop and Ollama if you want local recall; first start pulls {retrieval_embeddings['model']}",
                )
            )
        else:
            rows.append(("Conversation Recall", "Docker Desktop if you want local recall"))
    if not resolve_bool((integrations.get("web_search") or {}).get("enabled"), False):
        rows.append(
            (
                "Web Search",
                "Serper API key plus Firecrawl API key, or Docker Desktop for local SearXNG + Firecrawl",
            )
        )
    if not resolve_bool((integrations.get("code_interpreter") or {}).get("enabled"), False):
        rows.append(("Code Interpreter", "Docker Desktop for the sandbox service"))
    if not resolve_bool((integrations.get("telegram") or {}).get("enabled"), False):
        rows.append(("Telegram", "Bot token from @BotFather"))
    if not resolve_bool((integrations.get("telegram_codex") or {}).get("enabled"), False):
        rows.append(("Telegram Codex", "A separate BotFather token"))
    if not resolve_bool((integrations.get("google_workspace") or {}).get("enabled"), False):
        rows.append(("Google Workspace", "OAuth client ID, client secret, and refresh token"))
    if not resolve_bool((integrations.get("ms365") or {}).get("enabled"), False):
        rows.append(("Microsoft 365", "Azure app credentials; Docker for the local sidecar"))
    if not resolve_bool((integrations.get("skyvern") or {}).get("enabled"), False):
        rows.append(("Skyvern", "Skyvern API key and Docker"))
    if not resolve_bool((integrations.get("openclaw") or {}).get("enabled"), False):
        rows.append(("OpenClaw Exposure", "Enable it later from the configure flow"))
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
    lan_host = local_network_host()
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
    if lan_host:
        next_steps.append(
            f"Open [cyan]http://{lan_host}:{frontend_port}[/cyan] from another device on your local network."
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


def build_connected_accounts_notice(config: dict[str, Any]) -> str | None:
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
        foundation_labels = configured_foundation_connected_account_labels(config)
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

    setup_later_rows = build_setup_later_rows(config)
    if setup_later_rows:
        ui.print_blank()
        ui.print_table(
            "Set Up Later",
            ("Feature", "What you will need"),
            setup_later_rows,
            style="yellow",
        )

    connected_accounts_notice = build_connected_accounts_notice(config)
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
