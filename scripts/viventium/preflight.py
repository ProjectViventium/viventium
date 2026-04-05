#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from installer_ui import InstallerUI


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"

MANUAL_RECHECK_POLL_SECONDS = 5
MANUAL_RECHECK_PROGRESS_SECONDS = 15
MANUAL_RECHECK_TIMEOUT_SECONDS = 300
DEFAULT_DOCKER_READINESS_TIMEOUT_SECONDS = 3.0
DEFAULT_DOCKER_AUTOSTART_GRACE_SECONDS = 12.0
DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES = 4 * 1024 * 1024 * 1024


@dataclass
class PreflightItem:
    key: str
    label: str
    category: str
    reason: str
    status: str
    install_kind: str = "none"
    formula: str = ""
    cask: str = ""
    command: str = ""
    manual_command: str = ""


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def style(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"{code}{text}{RESET}"


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return data


def resolve_bool(value: Any, default: bool) -> bool:
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


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_checked(
    args: list[str], *, timeout_seconds: float | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout="",
            stderr=f"Timed out after {timeout_seconds:.1f}s",
        )


def docker_app_search_roots() -> list[Path]:
    override = os.environ.get("VIVENTIUM_DOCKER_APP_DIRS", "").strip()
    if override:
        roots = [Path(entry).expanduser() for entry in override.split(os.pathsep) if entry.strip()]
    else:
        roots = [Path("/Applications"), Path.home() / "Applications"]
    return roots


def docker_app_bundle_paths() -> list[Path]:
    return [root / "Docker.app" for root in docker_app_search_roots()]


def docker_cli_candidates() -> list[Path]:
    candidates: list[Path] = []
    for bundle in docker_app_bundle_paths():
        candidates.extend(
            [
                bundle / "Contents/Resources/bin/docker",
                bundle / "Contents/MacOS/com.docker.cli",
            ]
        )
    return candidates


def docker_cli_path() -> str | None:
    resolved = shutil.which("docker")
    if resolved:
        return resolved
    for candidate in docker_cli_candidates():
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def docker_desktop_installed() -> bool:
    if docker_cli_path():
        return True
    if any(bundle.is_dir() for bundle in docker_app_bundle_paths()):
        return True
    return brew_cask_installed("docker")


def docker_daemon_ready() -> bool:
    docker_cmd = docker_cli_path()
    if not docker_cmd:
        return False
    timeout_seconds = DEFAULT_DOCKER_READINESS_TIMEOUT_SECONDS
    raw_timeout = os.environ.get(
        "VIVENTIUM_DOCKER_READINESS_TIMEOUT_SECONDS",
        str(DEFAULT_DOCKER_READINESS_TIMEOUT_SECONDS),
    ).strip()
    try:
        parsed_timeout = float(raw_timeout)
    except ValueError:
        parsed_timeout = DEFAULT_DOCKER_READINESS_TIMEOUT_SECONDS
    if parsed_timeout > 0:
        timeout_seconds = parsed_timeout
    return run_checked([docker_cmd, "ps"], timeout_seconds=timeout_seconds).returncode == 0


def docker_total_memory_bytes() -> int | None:
    docker_cmd = docker_cli_path()
    if not docker_cmd:
        return None
    result = run_checked(
        [docker_cmd, "info", "--format", "{{.MemTotal}}"],
        timeout_seconds=DEFAULT_DOCKER_READINESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    return int(raw) if raw.isdigit() else None


def gibibytes(value: int) -> float:
    return value / float(1024 * 1024 * 1024)


def app_support_dir_for_config(config_path: Path) -> Path:
    return config_path.expanduser().resolve().parent


def local_web_search_prewarm_targets(config: dict[str, Any]) -> list[tuple[str, Path]]:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    if not resolve_bool(web_search.get("enabled"), False):
        return []

    repo_root = SCRIPT_DIR.parent.parent
    search_provider = str(web_search.get("search_provider") or "searxng").strip().lower()
    scraper_provider = str(web_search.get("scraper_provider") or "firecrawl").strip().lower()
    targets: list[tuple[str, Path]] = []

    if search_provider in {"local", "searxng"}:
        targets.append(
            ("searxng", repo_root / "viventium_v0_4" / "docker" / "searxng" / "docker-compose.yml")
        )
    if scraper_provider in {"local", "firecrawl"}:
        targets.append(
            ("firecrawl", repo_root / "viventium_v0_4" / "docker" / "firecrawl" / "docker-compose.yml")
        )
    return targets


def prewarm_pid_file(app_support_dir: Path, service: str) -> Path:
    return app_support_dir / "state" / "install" / f"docker-prewarm-{service}.pid"


def prewarm_log_file(app_support_dir: Path, service: str) -> Path:
    return app_support_dir / "logs" / f"docker-prewarm-{service}.log"


def process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def docker_prewarm_running(app_support_dir: Path, service: str) -> bool:
    pid_file = prewarm_pid_file(app_support_dir, service)
    if not pid_file.is_file():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False
    if process_running(pid):
        return True
    pid_file.unlink(missing_ok=True)
    return False


def queue_local_web_search_prewarm(config_path: Path, config: dict[str, Any]) -> None:
    if not docker_daemon_ready():
        return

    app_support_dir = app_support_dir_for_config(config_path)
    for service, compose_file in local_web_search_prewarm_targets(config):
        if not compose_file.is_file() or docker_prewarm_running(app_support_dir, service):
            continue

        pid_file = prewarm_pid_file(app_support_dir, service)
        log_file = prewarm_log_file(app_support_dir, service)
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        script = "\n".join(
            [
                "set -euo pipefail",
                f"pid_file={shlex.quote(str(pid_file))}",
                f"compose_file={shlex.quote(str(compose_file))}",
                "trap 'rm -f \"$pid_file\"' EXIT",
                'printf "%s\\n" "$$" >"$pid_file"',
                'docker compose -f "$compose_file" pull',
            ]
        )

        with log_file.open("ab", buffering=0) as log_handle:
            subprocess.Popen(
                ["/bin/bash", "-lc", script],
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )


def node_major_version() -> int | None:
    if not command_exists("node"):
        return None
    result = run_checked(["node", "--version"])
    if result.returncode != 0:
        return None
    raw = result.stdout.strip().lstrip("v")
    major = raw.split(".", 1)[0]
    return int(major) if major.isdigit() else None


def node_runtime_supported() -> bool:
    major = node_major_version()
    return major == 20


def python_version(command: str) -> tuple[int, int] | None:
    if not command_exists(command):
        return None
    result = run_checked(
        [
            command,
            "-c",
            "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
        ]
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    major, _, minor = raw.partition(".")
    if not (major.isdigit() and minor.isdigit()):
        return None
    return int(major), int(minor)


def modern_voice_python_ready() -> bool:
    for command in ("python3.12", "python3.11", "python3.10"):
        version = python_version(command)
        if version is not None and version >= (3, 10):
            return True
    return False


def brew_available() -> bool:
    return command_exists("brew")


def brew_formula_installed(formula: str) -> bool:
    if not brew_available():
        return False
    result = run_checked(["brew", "list", "--versions", formula])
    return result.returncode == 0 and bool(result.stdout.strip())


def brew_cask_installed(cask: str) -> bool:
    if not brew_available():
        return False
    result = run_checked(["brew", "list", "--cask", "--versions", cask])
    return result.returncode == 0 and bool(result.stdout.strip())


def xcode_cli_tools_installed() -> bool:
    return run_checked(["xcode-select", "-p"]).returncode == 0


def normalize_remote_call_mode(network: dict[str, Any]) -> str:
    mode = str(network.get("remote_call_mode", "disabled") or "disabled").strip().lower()
    if not mode or mode == "auto":
        return "disabled"
    return mode


def runtime_network_config(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {}) or {}
    network = runtime.get("network", {}) or {}
    return network if isinstance(network, dict) else {}


def tailscale_service_ready() -> bool:
    if not command_exists("tailscale"):
        return False
    return run_checked(["tailscale", "status", "--json"], timeout_seconds=3).returncode == 0


def netbird_missing_remote_origin_fields(config: dict[str, Any]) -> list[str]:
    network = runtime_network_config(config)
    missing = [
        field
        for field in ("public_client_origin", "public_api_origin")
        if not str(network.get(field, "") or "").strip()
    ]
    voice_mode = str(config.get("voice", {}).get("mode", "disabled")).strip().lower() or "disabled"
    if voice_mode != "disabled":
        missing.extend(
            field
            for field in ("public_playground_origin", "public_livekit_url")
            if not str(network.get(field, "") or "").strip()
        )
    return missing


def netbird_livekit_node_ip_ready(config: dict[str, Any]) -> bool:
    network = runtime_network_config(config)
    explicit_node_ip = str(network.get("livekit_node_ip", "") or "").strip()
    if explicit_node_ip:
        return True

    public_livekit_url = str(network.get("public_livekit_url", "") or "").strip()
    if not public_livekit_url:
        return False

    parsed = urllib.parse.urlparse(public_livekit_url)
    hostname = str(parsed.hostname or "").strip()
    if not hostname:
        return False

    try:
        socket.gethostbyname(hostname)
    except Exception:
        return False
    return True


def code_interpreter_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    code_interpreter = integrations.get("code_interpreter", {}) or {}
    return resolve_bool(code_interpreter.get("enabled"), False)


def conversation_recall_enabled(config: dict[str, Any]) -> bool:
    runtime = config.get("runtime", {}) or {}
    personalization = runtime.get("personalization", {}) or {}
    return resolve_bool(personalization.get("default_conversation_recall"), False)


def web_search_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    return resolve_bool(web_search.get("enabled"), False)


def web_search_local_services_requested(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    if not resolve_bool(web_search.get("enabled"), False):
        return False

    search_provider = str(web_search.get("search_provider") or "searxng").strip().lower()
    scraper_provider = str(web_search.get("scraper_provider") or "firecrawl").strip().lower()
    return search_provider in {"local", "searxng"} or scraper_provider in {"local", "firecrawl"}


def local_firecrawl_requested(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    if not resolve_bool(web_search.get("enabled"), False):
        return False
    scraper_provider = str(web_search.get("scraper_provider") or "firecrawl").strip().lower()
    return scraper_provider in {"local", "firecrawl"}


def local_firecrawl_memory_warning(config: dict[str, Any]) -> str | None:
    if not local_firecrawl_requested(config):
        return None
    docker_memory = docker_total_memory_bytes()
    if docker_memory is None or docker_memory >= DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES:
        return None
    current_gib = gibibytes(docker_memory)
    recommended_gib = gibibytes(DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES)
    return (
        "Local Firecrawl is enabled, but Docker Desktop is currently limited to about "
        f"{current_gib:.1f} GB. Viventium now ships a lower-memory Firecrawl profile, "
        f"but it is more reliable with at least {recommended_gib:.0f} GB assigned to Docker Desktop. "
        "If Firecrawl still restarts, raise Docker Desktop memory or switch the scraper to Firecrawl API."
    )


def compute_install_context(config: dict[str, Any]) -> dict[str, Any]:
    install_mode = str(config.get("install", {}).get("mode", "docker")).strip().lower() or "docker"
    voice_mode = str(config.get("voice", {}).get("mode", "disabled")).strip().lower() or "disabled"
    runtime = config.get("runtime", {}) or {}
    network = runtime.get("network", {}) or {}
    remote_call_mode = normalize_remote_call_mode(network)
    integrations = config.get("integrations", {}) or {}
    return {
        "install_mode": install_mode,
        "voice_mode": voice_mode,
        "remote_call_mode": remote_call_mode,
        "conversation_recall": conversation_recall_enabled(config),
        "run_code": code_interpreter_enabled(config),
        "web_search": web_search_enabled(config),
        "web_search_local_services": web_search_local_services_requested(config),
        "google_workspace": resolve_bool((integrations.get("google_workspace") or {}).get("enabled"), False),
        "ms365": resolve_bool((integrations.get("ms365") or {}).get("enabled"), False),
        "telegram": resolve_bool((integrations.get("telegram") or {}).get("enabled"), False),
        "skyvern": resolve_bool((integrations.get("skyvern") or {}).get("enabled"), False),
    }


def build_preflight_items(config: dict[str, Any]) -> list[PreflightItem]:
    refresh_brew_paths()
    ctx = compute_install_context(config)
    items: list[PreflightItem] = []

    items.append(
        PreflightItem(
            key="git",
            label="git",
            category="core",
            reason="clone and update the Viventium workspace",
            status="ok" if command_exists("git") else "missing",
            command="git",
        )
    )
    items.append(
        PreflightItem(
            key="security",
            label="macOS Keychain CLI",
            category="core",
            reason="store generated and transferred secrets safely on this Mac",
            status="ok" if command_exists("security") else "missing",
            command="security",
        )
    )

    if platform.system() == "Darwin":
        xcode_ready = xcode_cli_tools_installed()
        items.append(
            PreflightItem(
                key="xcode_cli_tools",
                label="Xcode Command Line Tools",
                category="system",
                reason="required by Homebrew and common native build tooling",
                status="ok" if xcode_ready else "missing",
                install_kind="manual" if not xcode_ready else "none",
                manual_command="xcode-select --install" if not xcode_ready else "",
            )
        )

    node_ok = node_runtime_supported()
    items.append(
        PreflightItem(
            key="node20",
            label="node@20",
            category="runtime",
            reason="run LibreChat and the modern playground on the validated Node runtime",
            status="ok" if node_ok else "missing",
            install_kind="brew_formula" if not node_ok else "none",
            formula="node@20" if not node_ok else "",
            command="node",
        )
    )
    items.append(
        PreflightItem(
            key="pnpm",
            label="pnpm",
            category="runtime",
            reason="install and manage JS workspaces",
            status="ok" if command_exists("pnpm") else "missing",
            install_kind="brew_formula" if not command_exists("pnpm") else "none",
            formula="pnpm" if not command_exists("pnpm") else "",
            command="pnpm",
        )
    )
    items.append(
        PreflightItem(
            key="uv",
            label="uv",
            category="runtime",
            reason="run MCP and Python service environments",
            status="ok" if command_exists("uv") else "missing",
            install_kind="brew_formula" if not command_exists("uv") else "none",
            formula="uv" if not command_exists("uv") else "",
            command="uv",
        )
    )
    if ctx["telegram"]:
        items.append(
            PreflightItem(
                key="ffmpeg",
                label="ffmpeg",
                category="telegram media",
                reason=(
                    "Telegram voice notes and video notes need ffmpeg so local transcription and "
                    "video-audio extraction work on a clean Mac"
                ),
                status="ok" if command_exists("ffmpeg") else "missing",
                install_kind="brew_formula" if not command_exists("ffmpeg") else "none",
                formula="ffmpeg" if not command_exists("ffmpeg") else "",
                command="ffmpeg",
            )
        )

    install_mode = ctx["install_mode"]
    voice_enabled = ctx["voice_mode"] != "disabled"
    remote_call_mode = ctx["remote_call_mode"]
    cloudflare_remote_voice_requested = voice_enabled and remote_call_mode == "cloudflare_quick_tunnel"
    tailscale_remote_requested = remote_call_mode == "tailscale_tailnet_https"
    netbird_remote_requested = remote_call_mode == "netbird_selfhosted_mesh"

    if install_mode == "native":
        items.extend(
            [
                PreflightItem(
                    key="mongod",
                    label="mongodb-community@8.0",
                    category="native services",
                    reason="local LibreChat and Viventium state storage",
                    status="ok" if command_exists("mongod") else "missing",
                    install_kind="brew_formula" if not command_exists("mongod") else "none",
                    formula="mongodb/brew/mongodb-community@8.0" if not command_exists("mongod") else "",
                    command="mongod",
                ),
                PreflightItem(
                    key="meilisearch",
                    label="meilisearch",
                    category="native services",
                    reason="local conversation and search indexing",
                    status="ok" if command_exists("meilisearch") else "missing",
                    install_kind="brew_formula" if not command_exists("meilisearch") else "none",
                    formula="meilisearch" if not command_exists("meilisearch") else "",
                    command="meilisearch",
                ),
            ]
        )
        docker_features: list[str] = []
        if ctx["ms365"]:
            docker_features.append("MS365")
        if ctx["conversation_recall"]:
            docker_features.append("Conversation Recall")
        if ctx["run_code"]:
            docker_features.append("Code Interpreter")
        if ctx["web_search_local_services"]:
            docker_features.append("Web Search")
        if ctx["skyvern"]:
            docker_features.append("Skyvern")
        if docker_features:
            docker_cli_ready = docker_desktop_installed()
            if len(docker_features) == 1:
                feature_label = docker_features[0]
                docker_reason = (
                    f"{feature_label} is enabled, and the current local {feature_label.lower()} service "
                    "still runs through the Docker-backed path even when the rest of the install is native"
                )
            else:
                feature_label = " and ".join(docker_features)
                docker_reason = (
                    f"{feature_label} are enabled, and their current local services still run through "
                    "Docker-backed paths even when the rest of the install is native"
                )
            items.append(
                PreflightItem(
                    key="docker",
                    label="Docker Desktop",
                    category="local docker services",
                    reason=docker_reason,
                    status="ok" if docker_cli_ready else "missing",
                    install_kind="brew_cask" if not docker_cli_ready else "none",
                    cask="docker" if not docker_cli_ready else "",
                    command=docker_cli_path() or "docker",
                )
            )
            if docker_cli_ready:
                if not docker_daemon_ready():
                    items.append(
                        PreflightItem(
                            key="docker_daemon",
                            label="Docker daemon running",
                            category="local docker services",
                            reason=(
                                f"{feature_label} startup still requires Docker Desktop running before "
                                "Viventium starts the local Docker-backed services"
                            ),
                            status="missing",
                            install_kind="manual",
                            manual_command="open -a Docker",
                        )
                    )
        if voice_enabled:
            python_ready = modern_voice_python_ready()
            items.append(
                PreflightItem(
                    key="python312",
                    label="python@3.12",
                    category="native services",
                    reason="local voice gateway dependencies require Python 3.10+ on macOS",
                    status="ok" if python_ready else "missing",
                    install_kind="brew_formula" if not python_ready else "none",
                    formula="python@3.12" if not python_ready else "",
                    command="python3.12",
                )
            )
            livekit_ready = command_exists("livekit") or command_exists("livekit-server")
            items.append(
                PreflightItem(
                    key="livekit",
                    label="livekit",
                    category="native services",
                    reason="local voice call signaling and session dispatch",
                    status="ok" if livekit_ready else "missing",
                    install_kind="brew_formula" if not livekit_ready else "none",
                    formula="livekit" if not livekit_ready else "",
                    command="livekit",
                )
            )
    elif install_mode == "docker":
        docker_cli_ready = docker_desktop_installed()
        items.append(
            PreflightItem(
                key="docker",
                label="Docker Desktop",
                category="container runtime",
                reason="run Docker-mode services",
                status="ok" if docker_cli_ready else "missing",
                install_kind="brew_cask" if not docker_cli_ready else "none",
                cask="docker" if not docker_cli_ready else "",
                command=docker_cli_path() or "docker",
            )
        )
        if docker_cli_ready:
            if not docker_daemon_ready():
                items.append(
                    PreflightItem(
                        key="docker_daemon",
                        label="Docker daemon running",
                        category="container runtime",
                        reason="Docker mode needs the Docker daemon reachable before start",
                        status="missing",
                        install_kind="manual",
                        manual_command="open -a Docker",
                    )
                )

    if cloudflare_remote_voice_requested:
        cloudflared_ready = command_exists("cloudflared")
        items.append(
            PreflightItem(
                key="cloudflared",
                label="cloudflared",
                category="remote voice",
                reason="secure call links for phones and other devices on local installs",
                status="ok" if cloudflared_ready else "missing",
                install_kind="brew_formula" if not cloudflared_ready else "none",
                formula="cloudflared" if not cloudflared_ready else "",
                command="cloudflared",
            )
        )

    if tailscale_remote_requested:
        tailscale_ready = command_exists("tailscale")
        items.append(
            PreflightItem(
                key="tailscale",
                label="tailscale",
                category="remote access",
                reason="tailnet-only HTTPS access for the full Viventium browser surface and modern voice playground",
                status="ok" if tailscale_ready else "missing",
                install_kind="brew_formula" if not tailscale_ready else "none",
                formula="tailscale" if not tailscale_ready else "",
                command="tailscale",
            )
        )
        if tailscale_ready:
            signed_in = tailscale_service_ready()
            items.append(
                PreflightItem(
                    key="tailscale_tailnet",
                    label="Tailscale tailnet connected",
                    category="remote access",
                    reason="tailnet-only Viventium links only work after this Mac is signed in to your Tailscale tailnet",
                    status="ok" if signed_in else "missing",
                    install_kind="manual" if not signed_in else "none",
                    manual_command="Open Tailscale and join this Mac to your tailnet, or run `tailscale up`"
                    if not signed_in
                    else "",
                    command="tailscale",
                )
            )

    if netbird_remote_requested:
        netbird_ready = command_exists("netbird")
        items.append(
            PreflightItem(
                key="netbird",
                label="NetBird client",
                category="remote access",
                reason="join this Mac to your self-hosted NetBird mesh before exposing Viventium on private mesh hostnames",
                status="ok" if netbird_ready else "missing",
                install_kind="manual" if not netbird_ready else "none",
                manual_command="Install the NetBird client/CLI for your self-hosted mesh, then connect this Mac to that mesh"
                if not netbird_ready
                else "",
                command="netbird",
            )
        )
        caddy_ready = command_exists("caddy")
        items.append(
            PreflightItem(
                key="caddy",
                label="caddy",
                category="remote access",
                reason="terminate browser-trusted HTTPS/WSS for the private NetBird mesh browser surface",
                status="ok" if caddy_ready else "missing",
                install_kind="brew_formula" if not caddy_ready else "none",
                formula="caddy" if not caddy_ready else "",
                command="caddy",
            )
        )
        missing_origin_fields = netbird_missing_remote_origin_fields(config)
        if missing_origin_fields:
            field_list = ", ".join(missing_origin_fields)
            items.append(
                PreflightItem(
                    key="netbird_origins",
                    label="NetBird remote origins",
                    category="remote access",
                    reason=(
                        "private-mesh browser access still needs explicit HTTPS/WSS origins for the app, API, "
                        "and any enabled voice surfaces"
                    ),
                    status="missing",
                    install_kind="manual",
                    manual_command=(
                        "Set runtime.network."
                        + field_list.replace(", ", ", runtime.network.")
                        + " in config.yaml, then rerun preflight"
                    ),
                )
            )
        if voice_enabled and not netbird_livekit_node_ip_ready(config):
            items.append(
                PreflightItem(
                    key="netbird_livekit_node_ip",
                    label="NetBird LiveKit node IP",
                    category="remote access",
                    reason=(
                        "LiveKit media still needs a mesh-reachable node IP after secure signaling; "
                        "set runtime.network.livekit_node_ip or make the LiveKit hostname resolve on this Mac"
                    ),
                    status="missing",
                    install_kind="manual",
                    manual_command=(
                        "Set runtime.network.livekit_node_ip to this Mac's NetBird mesh IP, or make "
                        "runtime.network.public_livekit_url resolve locally before startup"
                    ),
                )
            )

    need_brew = any(item.status == "missing" and item.install_kind.startswith("brew_") for item in items)
    if need_brew:
        items.append(
            PreflightItem(
                key="homebrew",
                label="Homebrew",
                category="system",
                reason="install the missing native toolchain in one batch",
                status="ok" if brew_available() else "missing",
                install_kind="manual" if not brew_available() else "none",
                manual_command='/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
                if not brew_available()
                else "",
                command="brew",
            )
        )

    return items


def missing_items(items: list[PreflightItem]) -> list[PreflightItem]:
    return [item for item in items if item.status != "ok"]


def manual_missing_items(items: list[PreflightItem]) -> list[PreflightItem]:
    return [item for item in missing_items(items) if item.install_kind == "manual"]


def install_action(item: PreflightItem) -> str:
    if item.install_kind == "brew_formula":
        return f"brew install {item.formula}"
    if item.install_kind == "brew_cask":
        return f"brew install --cask {item.cask}"
    if item.install_kind == "manual":
        return item.manual_command
    return ""


def print_summary(ui: InstallerUI, config: dict[str, Any], items: list[PreflightItem]) -> None:
    ctx = compute_install_context(config)
    missing = missing_items(items)
    mode_label = "Native on this Mac" if ctx["install_mode"] == "native" else "Docker workspace"
    voice_label = {
        "local": "Local voice",
        "hosted": "Hosted voice",
        "disabled": "Voice off",
    }.get(ctx["voice_mode"], ctx["voice_mode"])
    remote_call_mode = ctx["remote_call_mode"]
    ui.print_section(
        "Viventium Preflight",
        f"Runtime: {mode_label}\nVoice: {voice_label}\nRemote calls: {remote_call_mode}",
        style="cyan",
    )
    if not missing:
        ui.print_success("Everything required for this install path is already available on this Mac.")
        return

    lightweight_rows: list[tuple[str, str, str]] = []
    docker_rows: list[tuple[str, str, str]] = []
    manual_rows: list[tuple[str, str, str]] = []

    for item in missing:
        row = (item.label, item.reason, install_action(item) or "Checked automatically")
        if item.key.startswith("docker") or item.install_kind == "brew_cask":
            docker_rows.append(row)
        elif item.install_kind == "manual":
            manual_rows.append(row)
        else:
            lightweight_rows.append(row)

    if lightweight_rows:
        ui.print_table(
            "Mac Prerequisites",
            ("Tool", "Why you need it", "How Viventium installs it"),
            lightweight_rows,
            style="cyan",
        )
        ui.print_blank()

    if docker_rows:
        ui.print_table(
            "Docker-Backed Features",
            ("Item", "Why it matters", "Install or next step"),
            docker_rows,
            style="yellow",
        )
        ui.print_blank()

    if manual_rows:
        ui.print_table(
            "Manual Attention",
            ("Item", "Why it matters", "What to do"),
            manual_rows,
            style="yellow",
        )
        ui.print_blank()

    firecrawl_warning = local_firecrawl_memory_warning(config)
    if firecrawl_warning:
        ui.print_warning(firecrawl_warning)
        ui.print_blank()

    ui.print_note(
        "Viventium installs the lightweight Mac tools first. Docker is handled separately so turning on one optional feature does not quietly pull it in with everything else."
    )


def refresh_brew_paths() -> None:
    if os.environ.get("VIVENTIUM_PREFLIGHT_DISABLE_HOST_PATH_DISCOVERY") == "1":
        return
    candidates = [
        "/opt/homebrew/opt/node@20/bin",
        "/usr/local/opt/node@20/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
        "/opt/homebrew/opt/python@3.12/libexec/bin",
        "/usr/local/opt/python@3.12/libexec/bin",
        "/Applications/Docker.app/Contents/Resources/bin",
        "/Applications/Docker.app/Contents/MacOS",
        str(Path.home() / "Applications" / "Docker.app" / "Contents" / "Resources" / "bin"),
        str(Path.home() / "Applications" / "Docker.app" / "Contents" / "MacOS"),
    ]
    current_path = os.environ.get("PATH", "")
    parts = current_path.split(os.pathsep) if current_path else []
    for candidate in reversed(candidates):
        if os.path.isdir(candidate) and candidate not in parts:
            parts.insert(0, candidate)
    os.environ["PATH"] = os.pathsep.join(parts)


def install_homebrew() -> None:
    if brew_available():
        return
    subprocess.run(
        [
            "/bin/bash",
            "-c",
            "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
        ],
        check=True,
        env={**os.environ, "NONINTERACTIVE": "1", "CI": "1"},
    )
    refresh_brew_paths()


def install_brew_casks(casks: list[str], ui: InstallerUI | None = None) -> None:
    ui = ui or InstallerUI()
    for cask in casks:
        ui.print_note(f"Installing {cask}...")
        completed = run_checked(["brew", "install", "--cask", cask])
        if completed.returncode == 0:
            ui.print_success(f"{cask} is ready.")
            continue
        if cask == "docker" and docker_desktop_installed():
            ui.print_warning(
                "Docker Desktop already exists outside Homebrew, so Viventium will use that install."
            )
            refresh_brew_paths()
            continue
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        raise SystemExit(
            f"Homebrew could not finish installing {cask}. Fix the issue above, then rerun the Viventium installer."
        )


def formula_usable(formula: str) -> bool:
    refresh_brew_paths()
    checks: dict[str, Any] = {
        "node@20": node_runtime_supported,
        "pnpm": lambda: command_exists("pnpm"),
        "uv": lambda: command_exists("uv"),
        "ffmpeg": lambda: command_exists("ffmpeg"),
        "mongodb/brew/mongodb-community@8.0": lambda: command_exists("mongod"),
        "meilisearch": lambda: command_exists("meilisearch"),
        "python@3.12": modern_voice_python_ready,
        "livekit": lambda: command_exists("livekit") or command_exists("livekit-server"),
        "cloudflared": lambda: command_exists("cloudflared"),
    }
    check = checks.get(formula)
    if check is not None:
        return bool(check())
    return brew_formula_installed(formula)


def install_brew_formulas(formulas: list[str], ui: InstallerUI | None = None) -> None:
    ui = ui or InstallerUI()
    for formula in formulas:
        ui.print_note(f"Installing {formula}...")
        completed = run_checked(["brew", "install", formula])
        if completed.returncode == 0:
            refresh_brew_paths()
            ui.print_success(f"{formula} is ready.")
            continue
        if formula_usable(formula):
            ui.print_warning(
                f"{formula} finished with warnings, but the required runtime is usable, so Viventium will continue."
            )
            continue
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        raise SystemExit(
            f"Homebrew could not finish installing {formula}. Fix the issue above, then rerun the Viventium installer."
        )


def auto_start_safe_manual_items(items: list[PreflightItem]) -> None:
    manual_keys = {item.key for item in manual_missing_items(items)}
    if "docker_daemon" not in manual_keys:
        return
    subprocess.run(["open", "-a", "Docker"], check=False)
    docker_cmd = docker_cli_path()
    if not docker_cmd:
        return
    grace_seconds = DEFAULT_DOCKER_AUTOSTART_GRACE_SECONDS
    raw_grace = os.environ.get(
        "VIVENTIUM_PREFLIGHT_DOCKER_AUTOSTART_GRACE_SECONDS",
        str(DEFAULT_DOCKER_AUTOSTART_GRACE_SECONDS),
    ).strip()
    try:
        parsed_grace = float(raw_grace)
    except ValueError:
        parsed_grace = DEFAULT_DOCKER_AUTOSTART_GRACE_SECONDS
    if parsed_grace > 0:
        grace_seconds = parsed_grace

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if docker_daemon_ready():
            return
        time.sleep(2)


def manual_wait_instructions(items: list[PreflightItem]) -> list[str]:
    instructions: list[str] = []
    for item in items:
        action = install_action(item)
        detail = f"{item.label}: {item.reason}"
        if action:
            detail = f"{detail}\nDo this now: {action}"
        if item.key == "docker_daemon":
            detail = (
                f"{detail}\nIf Docker Desktop shows a first-launch window, finish that setup "
                "and leave Docker running. Viventium will keep checking automatically."
            )
        instructions.append(detail)
    return instructions


def wait_for_manual_items(
    ui: InstallerUI,
    config: dict[str, Any],
    items: list[PreflightItem],
    non_interactive: bool,
) -> None:
    pending = manual_missing_items(items)
    if not pending:
        return

    if non_interactive:
        instructions = " | ".join(
            detail.replace("\n", " ") for detail in manual_wait_instructions(pending)
        )
        raise SystemExit(
            "Manual prerequisites still need attention. "
            f"Complete these steps, then rerun the Viventium installer: {instructions}"
        )

    ui.print_section(
        "Finish Setup To Continue",
        "Viventium will stay here, keep checking automatically, and continue as soon as the required Mac step is finished.",
        style="yellow",
    )
    for detail in manual_wait_instructions(pending):
        ui.print_note(detail)
        ui.print_blank()

    while True:
        auto_start_safe_manual_items(pending)
        deadline = time.time() + MANUAL_RECHECK_TIMEOUT_SECONDS
        next_progress = 0.0
        while time.time() < deadline:
            refreshed_items = build_preflight_items(config)
            pending = manual_missing_items(refreshed_items)
            if not pending:
                ui.print_success("Manual setup finished. Continuing the Viventium install.")
                return

            now = time.time()
            if now >= next_progress:
                labels = ", ".join(item.label for item in pending)
                ui.print_note(
                    f"Still waiting for: {labels}. Finish the on-screen Mac step if one is open."
                )
                next_progress = now + MANUAL_RECHECK_PROGRESS_SECONDS
            time.sleep(MANUAL_RECHECK_POLL_SECONDS)

        ui.print_warning(
            "Viventium is still waiting on the required Mac step."
        )
        for detail in manual_wait_instructions(pending):
            ui.print_note(detail)
        if not ui.confirm("Keep waiting and rechecking automatically?", default=True):
            instructions = " | ".join(
                detail.replace("\n", " ") for detail in manual_wait_instructions(pending)
            )
            raise SystemExit(
                "Stopped while waiting for the required manual step. "
                f"Complete these steps, then rerun the Viventium installer: {instructions}"
            )
        ui.print_blank()


def apply_missing_items(
    ui: InstallerUI,
    config: dict[str, Any],
    items: list[PreflightItem],
    non_interactive: bool,
) -> None:
    missing = missing_items(items)
    if not missing:
        return

    xcode_needed = any(item.key == "xcode_cli_tools" and item.status != "ok" for item in missing)
    if xcode_needed:
        subprocess.run(["xcode-select", "--install"], check=False)
        raise SystemExit(
            "Xcode Command Line Tools installation was triggered. Finish that install, then rerun the Viventium installer."
        )

    if any(item.install_kind.startswith("brew_") and item.status != "ok" for item in missing):
        install_homebrew()

    formulas = sorted({item.formula for item in missing if item.install_kind == "brew_formula" and item.formula})
    casks = sorted({item.cask for item in missing if item.install_kind == "brew_cask" and item.cask})
    if formulas:
        if non_interactive or ui.confirm("Install the Mac prerequisites now?", default=True):
            install_brew_formulas(formulas, ui)
        else:
            raise SystemExit("Skipped installing the required Mac prerequisites.")
    if casks:
        cask_labels = ", ".join(casks)
        ctx = compute_install_context(config)
        explanation = (
            "Docker Desktop is only needed for the features you selected."
            if ctx["install_mode"] == "native"
            else "Docker Desktop is required for Docker mode."
        )
        ui.print_section("Docker", explanation, style="yellow")
        if non_interactive or ui.confirm(f"Install {cask_labels} now?", default=True):
            install_brew_casks(casks, ui)
        else:
            raise SystemExit(
                "Skipped Docker Desktop. Re-run the installer after enabling Docker, or turn off the Docker-backed features in bin/viventium configure."
            )
    auto_start_safe_manual_items(items)
    wait_for_manual_items(ui, config, build_preflight_items(config), non_interactive)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate and optionally install Viventium prerequisites.")
    parser.add_argument("--config", required=True, help="Path to Viventium config.yaml")
    parser.add_argument("--apply", action="store_true", help="Install missing prerequisites after confirmation")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; if combined with --apply, auto-approve the batch install",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    ui = InstallerUI()

    items = build_preflight_items(config)
    missing = missing_items(items)

    if args.json:
        payload = {
            "config": str(config_path),
            "context": compute_install_context(config),
            "items": [asdict(item) for item in items],
            "missing": [asdict(item) for item in missing],
        }
        print(json.dumps(payload, indent=2))
        raise SystemExit(0 if not missing else 1)

    print_summary(ui, config, items)

    if not missing:
        raise SystemExit(0)

    if not args.apply:
        raise SystemExit(1)

    if not args.non_interactive and not sys.stdin.isatty():
        raise SystemExit(
            "Missing prerequisites detected. Re-run interactively or set VIVENTIUM_AUTO_APPROVE_PREREQS=true."
        )

    apply_missing_items(ui, config, items, args.non_interactive)
    queue_local_web_search_prewarm(config_path, config)

    refreshed_items = build_preflight_items(config)
    refreshed_missing = missing_items(refreshed_items)
    ui.print_blank()
    print_summary(ui, config, refreshed_items)
    raise SystemExit(0 if not refreshed_missing else 1)


if __name__ == "__main__":
    main()
