#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import platform
import secrets
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from installer_ui import CheckboxOption, InstallerUI, SelectOption
from retrieval_config import (
    DEFAULT_RETRIEVAL_EMBEDDINGS_MODEL,
    DEFAULT_RETRIEVAL_EMBEDDINGS_PROFILE,
    DEFAULT_RETRIEVAL_EMBEDDINGS_PROVIDER,
    DEFAULT_RETRIEVAL_OLLAMA_BASE_URL,
)
from telegram_tokens import telegram_bot_token_validation_error

LOCAL_TTS_PROVIDER = "local_chatterbox_turbo_mlx_8bit"
DEFAULT_WEB_SEARCH_PROVIDER = "searxng"
DEFAULT_WEB_SCRAPER_PROVIDER = "firecrawl"
CONNECTED_ACCOUNT_PROVIDERS = {"openai", "anthropic"}
DEFAULT_FIRECRAWL_API_URL = "https://api.firecrawl.dev"
SERPER_API_KEYS_URL = "https://serper.dev/api-keys"
FIRECRAWL_API_KEYS_URL = "https://docs.firecrawl.dev/introduction#api-key"
DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES = 4 * 1024 * 1024 * 1024
DOCKER_FEATURES = {"ms365", "conversation_recall", "code_interpreter", "skyvern"}
FEATURE_GUIDANCE = {
    "conversation_recall": "Docker Desktop and Ollama for local recall",
    "code_interpreter": "Docker Desktop for the sandbox service",
    "web_search": "Serper + Firecrawl APIs, or let Viventium install Docker Desktop for local SearXNG and Firecrawl",
    "telegram": "Bot token from @BotFather",
    "telegram_codex": "A separate BotFather token",
    "google_workspace": "Google OAuth client ID, secret, and refresh token",
    "ms365": "Azure app credentials and Docker",
    "skyvern": "Skyvern API key and Docker",
    "openclaw": "Enable later from configure when you need exposure monitoring",
}


def default_local_tts_provider() -> str:
    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        return LOCAL_TTS_PROVIDER
    return "openai"


def is_apple_silicon_mac() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def docker_app_search_roots() -> list[Path]:
    override = os.environ.get("VIVENTIUM_DOCKER_APP_DIRS", "").strip()
    if override:
        return [Path(entry).expanduser() for entry in override.split(os.pathsep) if entry.strip()]
    return [Path("/Applications"), Path.home() / "Applications"]


def docker_app_bundle_paths() -> list[Path]:
    return [root / "Docker.app" for root in docker_app_search_roots()]


def docker_desktop_installed() -> bool:
    return any(path.is_dir() for path in docker_app_bundle_paths())


def docker_total_memory_bytes() -> int | None:
    docker_cmd = shutil_which("docker")
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


def local_firecrawl_memory_note(docker_memory_bytes: int | None) -> str | None:
    if docker_memory_bytes is None or docker_memory_bytes >= DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES:
        return None
    current_gib = docker_memory_bytes / float(1024 * 1024 * 1024)
    recommended_gib = DOCKER_LOCAL_FIRECRAWL_RECOMMENDED_MEMORY_BYTES / float(1024 * 1024 * 1024)
    return (
        "Docker Desktop is currently limited to about "
        f"{current_gib:.1f} GB. Viventium now ships a bounded local Firecrawl profile, "
        f"but Firecrawl is more reliable with at least {recommended_gib:.0f} GB assigned. "
        "If you keep Docker smaller, prefer Firecrawl API for full-page scraping."
    )


def shutil_which(command: str) -> str | None:
    try:
        import shutil

        return shutil.which(command)
    except Exception:
        return None


KEYCHAIN_WRITES_ENABLED = True
KEYCHAIN_SKIP_NOTICE_EMITTED = False


def set_keychain_writes_enabled(enabled: bool) -> None:
    global KEYCHAIN_WRITES_ENABLED
    global KEYCHAIN_SKIP_NOTICE_EMITTED
    KEYCHAIN_WRITES_ENABLED = enabled
    KEYCHAIN_SKIP_NOTICE_EMITTED = False


def store_keychain_secret(service: str, value: str) -> str | None:
    global KEYCHAIN_SKIP_NOTICE_EMITTED
    if not KEYCHAIN_WRITES_ENABLED:
        if not KEYCHAIN_SKIP_NOTICE_EMITTED:
            print(
                "[wizard] INFO: non-interactive setup stores secrets in local config state for "
                "this machine instead of macOS Keychain.",
                file=sys.stderr,
            )
            KEYCHAIN_SKIP_NOTICE_EMITTED = True
        return None
    try:
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a",
                getpass.getuser(),
                "-s",
                service,
                "-w",
                value,
                "-U",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = " ".join(
            part.strip() for part in [exc.stdout or "", exc.stderr or ""] if part.strip()
        )
        message = (
            f"[wizard] WARN: failed to store {service} in macOS Keychain "
            f"(exit {exc.returncode}); keeping it in local config state for this machine."
        )
        if details:
            message = f"{message} Details: {details}"
        print(message, file=sys.stderr)
        return None
    return f"keychain://{service}"


def build_secret_node(service: str, value: str) -> dict[str, str]:
    secret_ref = store_keychain_secret(service, value)
    if secret_ref:
        return {"secret_ref": secret_ref}
    return {"secret_value": value}


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Config preset not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config preset must be a mapping: {path}")
    return data


def maybe_store_secret(node: dict[str, Any], service: str) -> None:
    if not isinstance(node, dict):
        return
    if node.get("secret_ref"):
        return
    secret_value = str(node.get("secret_value") or "").strip()
    if not secret_value:
        return
    secret_ref = store_keychain_secret(service, secret_value)
    if secret_ref:
        node["secret_ref"] = secret_ref
        node.pop("secret_value", None)


def ensure_generated_secret(node: dict[str, Any], service: str, nbytes: int = 32) -> None:
    if not isinstance(node, dict):
        return
    if node.get("secret_ref"):
        return
    maybe_store_secret(node, service)
    if node.get("secret_ref"):
        return
    generated_value = str(node.get("secret_value") or "").strip()
    if not generated_value:
        generated_value = secrets.token_hex(nbytes)
    secret_ref = store_keychain_secret(service, generated_value)
    if secret_ref:
        node["secret_ref"] = secret_ref
        node.pop("secret_value", None)
    else:
        node["secret_value"] = generated_value


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


def secret_is_configured(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    return bool(
        str(node.get("secret_ref") or "").strip() or str(node.get("secret_value") or "").strip()
    )


def normalize_secret_node(value: Any, service: str) -> dict[str, Any]:
    if isinstance(value, dict):
        node = dict(value)
        maybe_store_secret(node, service)
        return node

    text = str(value or "").strip()
    if not text:
        return {}
    if text.startswith("keychain://"):
        return {"secret_ref": text}
    secret_ref = store_keychain_secret(service, text)
    if secret_ref:
        return {"secret_ref": secret_ref}
    return {"secret_value": text}


def validate_non_interactive_integrations(config: dict[str, Any]) -> None:
    integrations = config.get("integrations", {}) or {}

    for key, label in (
        ("telegram", "Telegram"),
        ("telegram_codex", "Telegram Codex"),
    ):
        integration = integrations.get(key, {}) or {}
        if not secret_is_configured(integration):
            continue
        if resolve_bool(integration.get("enabled"), False):
            continue
        if resolve_bool(integration.get("allow_disabled_secret"), False):
            continue
        raise SystemExit(
            f"Preset config stores a {label} secret while integrations.{key}.enabled is false. "
            f"Either set integrations.{key}.enabled: true, remove the secret, or set "
            f"integrations.{key}.allow_disabled_secret: true if that dormant-secret state is intentional."
        )


def normalize_preset(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.setdefault("runtime", {})
    runtime.setdefault("profile", "isolated")
    runtime.setdefault("playground_variant", "modern")
    network = runtime.setdefault("network", {})
    network.setdefault("remote_call_mode", "disabled")
    network.setdefault("public_client_origin", "")
    network.setdefault("public_api_origin", "")
    network.setdefault("public_playground_origin", "")
    network.setdefault("public_livekit_url", "")
    network.setdefault("livekit_node_ip", "")
    auth = runtime.setdefault("auth", {})
    auth.setdefault("allow_registration", True)
    auth.setdefault("bootstrap_registration_once", False)
    auth.setdefault("allow_password_reset", False)
    personalization = runtime.setdefault("personalization", {})
    personalization.setdefault("default_conversation_recall", False)
    retrieval = runtime.setdefault("retrieval", {})
    embeddings = retrieval.setdefault("embeddings", {})
    embeddings.setdefault("provider", DEFAULT_RETRIEVAL_EMBEDDINGS_PROVIDER)
    embeddings.setdefault("model", DEFAULT_RETRIEVAL_EMBEDDINGS_MODEL)
    embeddings.setdefault("profile", DEFAULT_RETRIEVAL_EMBEDDINGS_PROFILE)
    embeddings.setdefault("ollama_base_url", DEFAULT_RETRIEVAL_OLLAMA_BASE_URL)
    llm = config.setdefault("llm", {})
    activation = llm.setdefault("activation", {})
    primary = llm.setdefault("primary", {})
    secondary = llm.setdefault("secondary", {})
    voice = config.setdefault("voice", {})
    voice_mode = str(voice.get("mode") or "").strip().lower()
    if voice_mode == "local" and "wing_mode" not in voice and "shadow_mode" not in voice:
        voice["wing_mode"] = {"default_enabled": False}
    integrations = config.setdefault("integrations", {})
    integrations.setdefault("code_interpreter", {}).setdefault("enabled", False)
    web_search = integrations.setdefault("web_search", {})
    web_search.setdefault("enabled", False)
    web_search.setdefault("search_provider", DEFAULT_WEB_SEARCH_PROVIDER)
    web_search.setdefault("scraper_provider", DEFAULT_WEB_SCRAPER_PROVIDER)
    maybe_store_secret(web_search.setdefault("serper_api_key", {}), "viventium/serper_api_key")
    maybe_store_secret(web_search.setdefault("firecrawl_api_key", {}), "viventium/firecrawl_api_key")

    maybe_store_secret(activation, "viventium/groq_api_key")

    primary_provider = str(primary.get("provider") or "").strip().lower()
    if primary_provider:
        maybe_store_secret(primary, f"viventium/{primary_provider}_api_key")

    secondary_provider = str(secondary.get("provider") or "").strip().lower()
    if secondary_provider and secondary_provider != "none":
        maybe_store_secret(secondary, f"viventium/{secondary_provider}_api_key")

    telegram = integrations.setdefault("telegram", {})
    maybe_store_secret(telegram, "viventium/telegram_bot_token")
    telegram_codex = integrations.setdefault("telegram_codex", {})
    maybe_store_secret(telegram_codex, "viventium/telegram_codex_bot_token")

    extra_provider_keys = llm.get("extra_provider_keys") or {}
    if isinstance(extra_provider_keys, dict):
        for provider_name, secret_value in list(extra_provider_keys.items()):
            value = str(secret_value or "").strip()
            if not value or value.startswith("keychain://"):
                continue
            secret_ref = store_keychain_secret(f"viventium/{provider_name}_api_key", value)
            if secret_ref:
                extra_provider_keys[provider_name] = secret_ref

    ensure_generated_secret(
        runtime.setdefault("call_session_secret", {}),
        "viventium/call_session_secret",
    )

    stt_provider = str(voice.get("stt_provider") or "").strip().lower()
    if stt_provider == "assemblyai":
        maybe_store_secret(voice.setdefault("stt", {}), "viventium/assemblyai_api_key")

    tts_provider = str(voice.get("tts_provider") or "").strip().lower()
    if tts_provider == "elevenlabs":
        maybe_store_secret(voice.setdefault("tts", {}), "viventium/elevenlabs_api_key")
    elif tts_provider == "cartesia":
        maybe_store_secret(voice.setdefault("tts", {}), "viventium/cartesia_api_key")

    provider_keys = voice.get("provider_keys") or {}
    if not isinstance(provider_keys, dict):
        provider_keys = {}

    if stt_provider == "assemblyai" and secret_is_configured(voice.get("stt")):
        provider_keys.setdefault("assemblyai", dict(voice.get("stt") or {}))
    if tts_provider == "elevenlabs" and secret_is_configured(voice.get("tts")):
        provider_keys.setdefault("elevenlabs", dict(voice.get("tts") or {}))
    if tts_provider == "cartesia" and secret_is_configured(voice.get("tts")):
        provider_keys.setdefault("cartesia", dict(voice.get("tts") or {}))

    normalized_provider_keys: dict[str, Any] = {}
    for provider_name, service in (
        ("assemblyai", "viventium/assemblyai_api_key"),
        ("elevenlabs", "viventium/elevenlabs_api_key"),
        ("cartesia", "viventium/cartesia_api_key"),
    ):
        configured_value = provider_keys.get(provider_name)
        if not configured_value:
            continue
        normalized_node = normalize_secret_node(configured_value, service)
        if normalized_node:
            normalized_provider_keys[provider_name] = normalized_node

    if normalized_provider_keys:
        voice["provider_keys"] = normalized_provider_keys

    google_workspace = integrations.setdefault("google_workspace", {})
    maybe_store_secret(
        google_workspace.setdefault("client_secret", {}), "viventium/google_client_secret"
    )
    maybe_store_secret(
        google_workspace.setdefault("refresh_token", {}), "viventium/google_refresh_token"
    )

    ms365 = integrations.setdefault("ms365", {})
    maybe_store_secret(ms365.setdefault("client_secret", {}), "viventium/ms365_client_secret")

    skyvern = integrations.setdefault("skyvern", {})
    maybe_store_secret(skyvern.setdefault("api_key", {}), "viventium/skyvern_api_key")

    return config


def build_base_config(
    install_mode: str,
    primary_provider: str,
    auth_mode: str,
    secondary_provider: str,
) -> dict[str, object]:
    return {
        "version": 1,
        "install": {"mode": install_mode},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "playground_variant": "modern",
            "network": {
                "remote_call_mode": "disabled",
                "public_client_origin": "",
                "public_api_origin": "",
                "public_playground_origin": "",
                "public_livekit_url": "",
                "livekit_node_ip": "",
            },
            "auth": {
                "allow_registration": True,
                "bootstrap_registration_once": False,
                "allow_password_reset": False,
            },
            "personalization": {"default_conversation_recall": False},
            "retrieval": {
                "embeddings": {
                    "provider": DEFAULT_RETRIEVAL_EMBEDDINGS_PROVIDER,
                    "model": DEFAULT_RETRIEVAL_EMBEDDINGS_MODEL,
                    "profile": DEFAULT_RETRIEVAL_EMBEDDINGS_PROFILE,
                    "ollama_base_url": DEFAULT_RETRIEVAL_OLLAMA_BASE_URL,
                }
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
            },
            "primary": {
                "provider": primary_provider,
                "auth_mode": auth_mode,
            },
            "secondary": {
                "provider": secondary_provider,
                "auth_mode": "api_key" if secondary_provider != "none" else "disabled",
            },
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "disabled",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
            "tts_provider_fallback": "",
            "wing_mode": {"default_enabled": False},
        },
        "integrations": {
            "code_interpreter": {"enabled": False},
            "web_search": {
                "enabled": False,
                "search_provider": DEFAULT_WEB_SEARCH_PROVIDER,
                "scraper_provider": DEFAULT_WEB_SCRAPER_PROVIDER,
                "firecrawl_api_url": DEFAULT_FIRECRAWL_API_URL,
            },
            "telegram": {"enabled": False},
            "telegram_codex": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "glasshive": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }


def normalize_public_app_hostname(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"https://{raw}"
    try:
        parsed = urllib.parse.urlparse(candidate)
    except Exception as exc:
        raise ValueError("Enter a hostname like app.example.com, not a full path.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a hostname like app.example.com.")
    if parsed.port is not None:
        raise ValueError("Do not include a port. Enter only the public app hostname.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Enter only the hostname, without a path or query string.")
    return parsed.hostname.strip().lower()


def apply_remote_access_choice(
    config: dict[str, Any],
    *,
    remote_call_mode: str,
    public_app_hostname: str = "",
) -> None:
    runtime = config.setdefault("runtime", {})
    network = runtime.setdefault("network", {})
    network["remote_call_mode"] = remote_call_mode
    network["livekit_node_ip"] = ""
    network["public_client_origin"] = ""
    network["public_api_origin"] = ""
    network["public_playground_origin"] = ""
    network["public_livekit_url"] = ""

    if remote_call_mode != "custom_domain":
        return

    host = normalize_public_app_hostname(public_app_hostname)
    if not host:
        return

    network["public_client_origin"] = f"https://{host}"
    network["public_api_origin"] = f"https://api.{host}"
    network["public_playground_origin"] = f"https://playground.{host}"
    network["public_livekit_url"] = f"wss://livekit.{host}"


def prompt_remote_access(ui: InstallerUI, config: dict[str, Any]) -> None:
    remote_access_goal = ui.select(
        "Where do you need to use Viventium?",
        [
            SelectOption(
                "local_only",
                "Only on this Mac",
                "Keep the install local-only. Simplest and safest default.",
            ),
            SelectOption(
                "personal_devices",
                "My own phone or laptop",
                "Private device access with Tailscale on the devices you own.",
            ),
            SelectOption(
                "public_browser",
                "Any browser anywhere",
                "Public browser access for normal phones, tablets, and laptops.",
            ),
        ],
        default="local_only",
    )

    if remote_access_goal == "local_only":
        apply_remote_access_choice(config, remote_call_mode="disabled")
        ui.print_note("Remote access will stay off. You can enable it later with bin/viventium configure.")
        return

    if remote_access_goal == "personal_devices":
        apply_remote_access_choice(config, remote_call_mode="tailscale_tailnet_https")
        ui.print_note(
            "Viventium will publish a private Tailscale URL after startup. Install Tailscale on this Mac and on the phone or laptop you want to use."
        )
        return

    while True:
        public_app_hostname = ui.text(
            "Public app hostname (leave blank for a temporary bootstrap URL)",
            default="",
            allow_empty=True,
        )
        try:
            apply_remote_access_choice(
                config,
                remote_call_mode="custom_domain",
                public_app_hostname=public_app_hostname,
            )
        except ValueError as exc:
            ui.print_error(str(exc))
            continue
        break

    network = config.setdefault("runtime", {}).setdefault("network", {})
    public_client_origin = str(network.get("public_client_origin") or "").strip()
    if public_client_origin:
        ui.print_note(
            "Viventium will use the public app hostname you gave it and automatically derive the matching API, playground, and LiveKit hostnames."
        )
    else:
        ui.print_note(
            "Viventium will start with a temporary outside URL first and show it in bin/viventium status. You can add your real domain later without changing the product code."
        )
    ui.print_note(
        "Viventium will try to request and renew the needed router mappings automatically while it stays running. If your router refuses, the docs cover the manual fallback."
    )


def prompt_browser_auth_controls(ui: InstallerUI, config: dict[str, Any]) -> None:
    runtime = config.setdefault("runtime", {})
    network = runtime.setdefault("network", {})
    remote_call_mode = str(network.get("remote_call_mode") or "disabled").strip().lower()
    if remote_call_mode == "disabled":
        return

    auth = runtime.setdefault("auth", {})
    current_allow_registration = bool(auth.get("allow_registration", True))
    current_bootstrap_registration_once = bool(
        auth.get("bootstrap_registration_once", remote_call_mode == "custom_domain")
    )
    current_allow_password_reset = bool(auth.get("allow_password_reset", False))

    ui.print_note(
        "If this is the first account on this install, leave browser sign-up on until you create it. After that, close sign-up for safer remote access."
    )
    auth["allow_registration"] = ui.confirm(
        "Keep browser sign-up open?",
        default=current_allow_registration,
    )

    if remote_call_mode == "custom_domain" and auth["allow_registration"]:
        ui.print_note(
            "Public browser installs can automatically close sign-up after the first real account is created."
        )
        auth["bootstrap_registration_once"] = ui.confirm(
            "Auto-close browser sign-up after the first account?",
            default=current_bootstrap_registration_once,
        )
    else:
        auth["bootstrap_registration_once"] = False

    ui.print_note(
        "Leave browser password reset off unless real email delivery is configured. You can always issue a one-time reset link locally with bin/viventium password-reset-link <email>."
    )
    auth["allow_password_reset"] = ui.confirm(
        "Enable browser password reset?",
        default=current_allow_password_reset,
    )


def feature_options(*, docker_installed: bool) -> list[CheckboxOption]:
    return [
        CheckboxOption(
            group="Voice & Communication",
            value="voice",
            label="Voice Playground",
            note="On-device speech and text on this Mac",
            checked=True,
        ),
        CheckboxOption(
            group="Voice & Communication",
            value="telegram",
            label="Telegram Bridge",
            note="Optional bot for chatting from Telegram",
            checked=False,
        ),
        CheckboxOption(
            group="Voice & Communication",
            value="telegram_codex",
            label="Telegram Codex",
            note="Separate Telegram sidecar bot",
            checked=False,
        ),
        CheckboxOption(
            group="Productivity Integrations",
            value="google_workspace",
            label="Google Workspace",
            note="Gmail, Calendar, and Drive via OAuth",
            checked=False,
        ),
        CheckboxOption(
            group="Productivity Integrations",
            value="ms365",
            label="Microsoft 365",
            note="Requires Docker Desktop",
            checked=False,
        ),
        CheckboxOption(
            group="Advanced Features",
            value="conversation_recall",
            label="Conversation Recall",
            note="Search past conversations locally; requires Docker and Ollama",
            checked=docker_installed,
        ),
        CheckboxOption(
            group="Advanced Features",
            value="web_search",
            label="Web Search",
            note="Default on with Docker, or switch to Serper + Firecrawl APIs",
            checked=docker_installed,
        ),
        CheckboxOption(
            group="Advanced Features",
            value="code_interpreter",
            label="Code Interpreter",
            note="Local sandbox service; requires Docker",
            checked=False,
        ),
        CheckboxOption(
            group="Advanced Features",
            value="skyvern",
            label="Skyvern",
            note="Browser automation; requires Docker and an API key",
            checked=False,
        ),
        CheckboxOption(
            group="Advanced Features",
            value="openclaw",
            label="OpenClaw Exposure",
            note="Exposure monitoring integration",
            checked=False,
        ),
    ]


def print_feature_overview(ui: InstallerUI, *, docker_installed: bool) -> None:
    by_group: dict[str, list[tuple[str, str, str]]] = {}
    for feature in feature_options(docker_installed=docker_installed):
        by_group.setdefault(feature.group, []).append(
            (
                feature.label,
                feature.note or "",
                "Yes" if feature.value in DOCKER_FEATURES else "No",
            )
        )
    for group, rows in by_group.items():
        ui.print_table(group, ("Feature", "What it does", "Needs Docker"), rows, style="cyan")
        ui.print_blank()


def set_local_voice_defaults(config: dict[str, Any]) -> None:
    voice = config["voice"]
    voice["mode"] = "local"
    voice["stt_provider"] = "whisper_local"
    voice["tts_provider"] = default_local_tts_provider()
    voice["tts_provider_fallback"] = (
        "openai" if voice["tts_provider"] == LOCAL_TTS_PROVIDER else ""
    )


def set_web_search_defaults(
    config: dict[str, Any],
    *,
    search_provider: str,
    scraper_provider: str,
) -> None:
    web_search = config["integrations"]["web_search"]
    web_search["enabled"] = True
    web_search["search_provider"] = search_provider
    web_search["scraper_provider"] = scraper_provider
    if scraper_provider != "firecrawl_api":
        web_search.pop("firecrawl_api_key", None)
        web_search["firecrawl_api_url"] = DEFAULT_FIRECRAWL_API_URL
    if search_provider != "serper":
        web_search.pop("serper_api_key", None)


def prompt_web_search(
    ui: InstallerUI,
    config: dict[str, Any],
    deferred: list[str],
    *,
    easy: bool,
    docker_installed: bool,
    docker_memory_bytes: int | None = None,
) -> None:
    web_search = config["integrations"]["web_search"]

    if easy and docker_installed:
        set_web_search_defaults(
            config,
            search_provider=DEFAULT_WEB_SEARCH_PROVIDER,
            scraper_provider=DEFAULT_WEB_SCRAPER_PROVIDER,
        )
        ui.print_note(
            "Web search will be enabled automatically with local SearXNG + Firecrawl through Docker Desktop."
        )
        memory_note = local_firecrawl_memory_note(docker_memory_bytes)
        if memory_note:
            ui.print_note(memory_note)
        return

    ui.print_section(
        "Web Search",
        (
            "Web search is a core Viventium capability.\n"
            "You can run it fully locally with Docker Desktop, or use hosted providers instead."
        ),
        style="cyan",
    )
    if not docker_installed:
        ui.print_note(
            "Choose the local SearXNG or Firecrawl options if you want Viventium to install Docker Desktop during preflight and finish the local web-search setup for you."
        )
        ui.print_note(
            f"Hosted path: Serper keys -> {SERPER_API_KEYS_URL} | Firecrawl keys -> {FIRECRAWL_API_KEYS_URL}"
        )

    search_provider = ui.select(
        "How should Viventium search the web?",
        [
            SelectOption(
                "searxng",
                "Local SearXNG (Docker)" if docker_installed else "Local SearXNG (install Docker automatically)",
                "Private web search on this Mac",
            ),
            SelectOption(
                "serper",
                "Serper API",
                f"No Docker needed. Get a key at {SERPER_API_KEYS_URL}",
            ),
            SelectOption(
                "later",
                "Set this up later",
                "Finish install now and enable web search when you are ready",
            ),
        ],
        default="searxng" if docker_installed else "serper",
    )
    if search_provider == "later":
        disable_feature(config, "web_search", deferred)
        return

    if search_provider == "serper":
        ui.print_note(f"Serper powers live web search results without Docker. Key page: {SERPER_API_KEYS_URL}")
        secret_node = prompt_optional_secret(ui, "Serper API key", "viventium/serper_api_key")
        if not secret_node:
            disable_feature(config, "web_search", deferred)
            return
        web_search["serper_api_key"] = secret_node
    elif not docker_installed:
        ui.print_note(
            "Viventium will install Docker Desktop during preflight, then start and configure local SearXNG automatically."
        )

    scraper_provider = ui.select(
        "How should Viventium fetch full page content?",
        [
            SelectOption(
                "firecrawl",
                "Local Firecrawl (Docker)" if docker_installed else "Local Firecrawl (install Docker automatically)",
                "Private page scraping on this Mac",
            ),
            SelectOption(
                "firecrawl_api",
                "Firecrawl API",
                f"No Docker needed. Key docs: {FIRECRAWL_API_KEYS_URL}",
            ),
            SelectOption(
                "later",
                "Set this up later",
                "Skip web search for now instead of leaving it half-configured",
            ),
        ],
        default="firecrawl" if docker_installed else "firecrawl_api",
    )
    if scraper_provider == "later":
        disable_feature(config, "web_search", deferred)
        return

    if scraper_provider == "firecrawl_api":
        ui.print_note(
            f"Firecrawl fetches the full page content behind search results so Viventium can answer with real page context. Key docs: {FIRECRAWL_API_KEYS_URL}"
        )
        secret_node = prompt_optional_secret(
            ui,
            "Firecrawl API key",
            "viventium/firecrawl_api_key",
        )
        if not secret_node:
            disable_feature(config, "web_search", deferred)
            return
        web_search["firecrawl_api_key"] = secret_node
        firecrawl_api_url = ui.text(
            "Firecrawl API URL",
            default=DEFAULT_FIRECRAWL_API_URL,
            allow_empty=True,
        )
        web_search["firecrawl_api_url"] = firecrawl_api_url or DEFAULT_FIRECRAWL_API_URL
    elif not docker_installed:
        ui.print_note(
            "Viventium will install Docker Desktop during preflight, then start and configure local Firecrawl automatically."
        )
    else:
        memory_note = local_firecrawl_memory_note(docker_memory_bytes)
        if memory_note:
            ui.print_note(memory_note)

    set_web_search_defaults(
        config,
        search_provider=search_provider,
        scraper_provider=scraper_provider,
    )
    if search_provider == "serper":
        web_search["serper_api_key"] = web_search.get("serper_api_key", {})
    if scraper_provider == "firecrawl_api":
        web_search["firecrawl_api_key"] = web_search.get("firecrawl_api_key", {})
        web_search["firecrawl_api_url"] = (
            str(web_search.get("firecrawl_api_url") or DEFAULT_FIRECRAWL_API_URL).strip()
            or DEFAULT_FIRECRAWL_API_URL
        )


def prompt_optional_secret(
    ui: InstallerUI,
    prompt: str,
    service: str,
    validator: Callable[[str], str] | None = None,
) -> dict[str, str] | None:
    while True:
        value = ui.password(prompt, allow_empty=True)
        if not value:
            return None
        if validator is not None:
            validation_error = validator(value)
            if validation_error:
                ui.print_error(validation_error)
                continue
        return build_secret_node(service, value)


def mark_deferred(deferred: list[str], key: str) -> None:
    if key not in deferred:
        deferred.append(key)


def disable_feature(config: dict[str, Any], key: str, deferred: list[str]) -> None:
    integrations = config.get("integrations", {}) or {}
    if key == "conversation_recall":
        runtime = config.get("runtime", {}) or {}
        personalization = runtime.get("personalization", {}) or {}
        personalization["default_conversation_recall"] = False
    elif key == "voice":
        voice = config.get("voice", {}) or {}
        voice["mode"] = "disabled"
        voice["stt_provider"] = "whisper_local"
        voice["tts_provider"] = "browser"
        voice["tts_provider_fallback"] = ""
    elif key in integrations:
        integrations[key]["enabled"] = False
    mark_deferred(deferred, key)


def prompt_voice_settings(ui: InstallerUI, config: dict[str, Any], advanced: bool) -> None:
    if not advanced:
        if is_apple_silicon_mac():
            set_local_voice_defaults(config)
        else:
            config["voice"]["mode"] = "disabled"
        return

    default_mode = "local" if is_apple_silicon_mac() else "hosted"
    voice_mode = ui.select(
        "How should voice work?",
        [
            SelectOption("local", "Local voice on this Mac", "Best on Apple Silicon"),
            SelectOption("hosted", "Hosted voice providers", "Use cloud STT/TTS providers"),
        ],
        default=default_mode,
    )
    if voice_mode == "local":
        set_local_voice_defaults(config)
        return

    voice = config["voice"]
    voice["mode"] = "hosted"
    voice["stt_provider"] = ui.select(
        "Hosted speech-to-text provider",
        [
            SelectOption("openai", "OpenAI"),
            SelectOption("assemblyai", "AssemblyAI"),
            SelectOption("whisper_local", "Local Whisper"),
        ],
        default="openai",
    )
    voice["tts_provider"] = ui.select(
        "Hosted text-to-speech provider",
        [
            SelectOption("x_ai", "xAI"),
            SelectOption("openai", "OpenAI"),
            SelectOption("elevenlabs", "ElevenLabs"),
            SelectOption("cartesia", "Cartesia"),
        ],
        default="x_ai",
    )
    if voice["stt_provider"] == "assemblyai":
        secret_node = prompt_optional_secret(
            ui,
            "AssemblyAI API key",
            "viventium/assemblyai_api_key",
        )
        if secret_node:
            voice["stt"] = secret_node
    if voice["tts_provider"] == "elevenlabs":
        secret_node = prompt_optional_secret(
            ui,
            "ElevenLabs API key",
            "viventium/elevenlabs_api_key",
        )
        if secret_node:
            voice["tts"] = secret_node
    elif voice["tts_provider"] == "cartesia":
        secret_node = prompt_optional_secret(
            ui,
            "Cartesia API key",
            "viventium/cartesia_api_key",
        )
        if secret_node:
            voice["tts"] = secret_node


def prompt_google_workspace(ui: InstallerUI, config: dict[str, Any], deferred: list[str]) -> None:
    ui.print_section(
        "Google Workspace",
        "Add your Google OAuth details now, or leave the first field blank to set this up later.",
        style="cyan",
    )
    client_id = ui.text("Google OAuth client ID", allow_empty=True)
    if not client_id:
        disable_feature(config, "google_workspace", deferred)
        return
    client_secret = prompt_optional_secret(
        ui,
        "Google OAuth client secret",
        "viventium/google_client_secret",
    )
    refresh_token = prompt_optional_secret(
        ui,
        "Google refresh token",
        "viventium/google_refresh_token",
    )
    if not client_secret or not refresh_token:
        disable_feature(config, "google_workspace", deferred)
        return
    google = config["integrations"]["google_workspace"]
    google["enabled"] = True
    google["client_id"] = client_id
    google["client_secret"] = client_secret
    google["refresh_token"] = refresh_token


def prompt_ms365(ui: InstallerUI, config: dict[str, Any], deferred: list[str]) -> None:
    ui.print_section(
        "Microsoft 365",
        "Add your Azure app details now, or leave the client ID blank to set this up later.",
        style="cyan",
    )
    client_id = ui.text("Microsoft 365 client ID", allow_empty=True)
    if not client_id:
        disable_feature(config, "ms365", deferred)
        return
    tenant_id = ui.text("Microsoft 365 tenant ID", allow_empty=False)
    business_email = ui.text("Microsoft 365 business email", allow_empty=False)
    client_secret = prompt_optional_secret(
        ui,
        "Microsoft 365 client secret",
        "viventium/ms365_client_secret",
    )
    if not client_secret:
        disable_feature(config, "ms365", deferred)
        return
    ms365 = config["integrations"]["ms365"]
    ms365["enabled"] = True
    ms365["client_id"] = client_id
    ms365["tenant_id"] = tenant_id
    ms365["business_email"] = business_email
    ms365["client_secret"] = client_secret


def prompt_skyvern(ui: InstallerUI, config: dict[str, Any], deferred: list[str]) -> None:
    ui.print_section(
        "Skyvern",
        "Add your Skyvern API key now, or leave it blank to set this up later.",
        style="cyan",
    )
    secret_node = prompt_optional_secret(
        ui,
        "Skyvern API key",
        "viventium/skyvern_api_key",
    )
    if not secret_node:
        disable_feature(config, "skyvern", deferred)
        return
    skyvern = config["integrations"]["skyvern"]
    skyvern["enabled"] = True
    skyvern["api_key"] = secret_node
    base_url = ui.text("Skyvern base URL", default="http://localhost:8200", allow_empty=True)
    if base_url:
        skyvern["base_url"] = base_url


def prompt_telegram(ui: InstallerUI, config: dict[str, Any], deferred: list[str], easy: bool) -> None:
    prompt = "Telegram bot token" if easy else "Telegram bot token (leave blank to set up later)"
    secret_node = prompt_optional_secret(
        ui,
        prompt,
        "viventium/telegram_bot_token",
        validator=telegram_bot_token_validation_error,
    )
    if not secret_node:
        disable_feature(config, "telegram", deferred)
        return
    telegram = config["integrations"]["telegram"]
    telegram["enabled"] = True
    telegram.update(secret_node)


def prompt_telegram_codex(ui: InstallerUI, config: dict[str, Any], deferred: list[str]) -> None:
    secret_node = prompt_optional_secret(
        ui,
        "Telegram Codex bot token (leave blank to set up later)",
        "viventium/telegram_codex_bot_token",
        validator=telegram_bot_token_validation_error,
    )
    if not secret_node:
        disable_feature(config, "telegram_codex", deferred)
        return
    telegram_codex = config["integrations"]["telegram_codex"]
    telegram_codex["enabled"] = True
    telegram_codex.update(secret_node)
    bot_username = ui.text("Telegram Codex bot username", allow_empty=True).lstrip("@")
    if bot_username:
        telegram_codex["bot_username"] = bot_username
    telegram_codex["private_chat_only"] = True


def summarize_setup_later(ui: InstallerUI, deferred: list[str]) -> None:
    if not deferred:
        return
    rows = [
        (
            {
                "conversation_recall": "Conversation Recall",
                "code_interpreter": "Code Interpreter",
                "web_search": "Web Search",
                "telegram": "Telegram",
                "telegram_codex": "Telegram Codex",
                "google_workspace": "Google Workspace",
                "ms365": "Microsoft 365",
                "skyvern": "Skyvern",
                "openclaw": "OpenClaw Exposure",
            }.get(key, key),
            FEATURE_GUIDANCE.get(key, "Run bin/viventium configure later"),
        )
        for key in deferred
    ]
    ui.print_blank()
    ui.print_table("Set Up Later", ("Feature", "What you will need"), rows, style="yellow")


def configure_easy_install(ui: InstallerUI) -> tuple[dict[str, Any], list[str]]:
    config = build_base_config("native", "openai", "connected_account", "none")
    ensure_generated_secret(
        config["runtime"].setdefault("call_session_secret", {}),
        "viventium/call_session_secret",
    )
    config["llm"]["activation"].update(
        build_secret_node(
            "viventium/groq_api_key",
            ui.password("Groq API key (required)"),
        )
    )
    prompt_voice_settings(ui, config, advanced=False)
    docker_installed = docker_desktop_installed()
    deferred = [
        "conversation_recall",
        "code_interpreter",
        "telegram_codex",
        "google_workspace",
        "ms365",
        "skyvern",
        "openclaw",
    ]
    if docker_installed:
        prompt_web_search(
            ui,
            config,
            deferred,
            easy=True,
            docker_installed=True,
            docker_memory_bytes=docker_total_memory_bytes(),
        )
        ui.print_note(
            "Conversation Recall stays off in Easy Install. Turn it on later from bin/viventium configure when you are ready to add the local Docker + Ollama path."
        )
    else:
        ui.print_note(
            "Easy Install keeps Web Search and Conversation Recall off until Docker Desktop is installed. Turn them on later from bin/viventium configure."
        )
        disable_feature(config, "web_search", deferred)
    if not resolve_bool((config["integrations"]["web_search"]).get("enabled"), False):
        mark_deferred(deferred, "web_search")
    if ui.confirm("Connect a Telegram bot now?", default=False):
        prompt_telegram(ui, config, deferred, easy=True)
        if not resolve_bool((config["integrations"]["telegram"]).get("enabled"), False):
            mark_deferred(deferred, "telegram")
    else:
        mark_deferred(deferred, "telegram")
    if ui.confirm("Need to use Viventium from another device?", default=False):
        prompt_remote_access(ui, config)
        prompt_browser_auth_controls(ui, config)
    return config, deferred


def configure_advanced_setup(ui: InstallerUI) -> tuple[dict[str, Any], list[str]]:
    install_mode = ui.select(
        "How should Viventium run on this Mac?",
        [
            SelectOption(
                "native",
                "Native on this Mac",
                "Recommended. Docker only comes up if you enable a feature that needs it.",
            ),
            SelectOption(
                "docker",
                "Docker workspace",
                "Keep more services inside Docker from the start.",
            ),
        ],
        default="native",
    )
    primary_provider = ui.select(
        "Primary AI provider",
        [
            SelectOption("openai", "OpenAI"),
            SelectOption("anthropic", "Anthropic"),
        ],
        default="openai",
    )
    auth_options = [SelectOption("api_key", "API key", "Bring your own provider key")]
    auth_default = "api_key"
    if primary_provider in CONNECTED_ACCOUNT_PROVIDERS:
        auth_options.insert(
            0,
            SelectOption(
                "connected_account",
                "Connected account",
                "Best user experience when the provider supports it",
            ),
        )
        auth_default = "connected_account"
    auth_mode = ui.select(
        "How should the primary provider authenticate?",
        auth_options,
        default=auth_default,
    )
    secondary_provider = ui.select(
        "Optional secondary provider",
        [
            SelectOption("none", "None"),
            SelectOption("openai", "OpenAI"),
            SelectOption("anthropic", "Anthropic"),
            SelectOption("x_ai", "xAI"),
        ],
        default="none",
    )

    config = build_base_config(install_mode, primary_provider, auth_mode, secondary_provider)
    ensure_generated_secret(
        config["runtime"].setdefault("call_session_secret", {}),
        "viventium/call_session_secret",
    )
    config["llm"]["activation"].update(
        build_secret_node(
            "viventium/groq_api_key",
            ui.password("Groq API key (required)"),
        )
    )

    if auth_mode == "api_key":
        config["llm"]["primary"].update(
            build_secret_node(
                f"viventium/{primary_provider}_api_key",
                ui.password(f"{primary_provider} API key"),
            )
        )

    if secondary_provider != "none" and ui.confirm(
        f"Store a {secondary_provider} API key now?",
        default=False,
    ):
        config["llm"]["secondary"].update(
            build_secret_node(
                f"viventium/{secondary_provider}_api_key",
                ui.password(f"{secondary_provider} API key"),
            )
        )

    ui.print_section(
        "Advanced Setup",
        "Choose what you want right now. Anything you skip can be enabled later with bin/viventium configure.",
        style="cyan",
    )
    docker_installed = docker_desktop_installed()
    print_feature_overview(ui, docker_installed=docker_installed)
    selected = set(
        ui.checkbox(
            "Choose the features you want to configure now",
            feature_options(docker_installed=docker_installed),
        )
    )
    deferred: list[str] = []

    if install_mode == "native":
        selected_docker_features = [feature for feature in selected if feature in DOCKER_FEATURES]
        if selected_docker_features and not docker_installed:
            docker_feature_names = ", ".join(
                {
                    "conversation_recall": "Conversation Recall",
                    "code_interpreter": "Code Interpreter",
                    "web_search": "Web Search",
                    "ms365": "Microsoft 365",
                    "skyvern": "Skyvern",
                }[feature]
                for feature in sorted(selected_docker_features)
            )
            ui.print_section(
                "Docker Required",
                f"{docker_feature_names} need Docker Desktop in native mode.\n"
                "If you skip Docker for now, those features will be moved to setup later instead of blocking this install.",
                style="yellow",
            )
            if not ui.confirm("Install Docker Desktop when preflight reaches it?", default=True):
                for feature in list(selected_docker_features):
                    selected.discard(feature)
                    mark_deferred(deferred, feature)

    if "voice" in selected:
        prompt_voice_settings(ui, config, advanced=True)
    else:
        disable_feature(config, "voice", deferred)

    runtime = config["runtime"]
    personalization = runtime["personalization"]
    personalization["default_conversation_recall"] = "conversation_recall" in selected
    if "conversation_recall" not in selected:
        mark_deferred(deferred, "conversation_recall")

    config["integrations"]["code_interpreter"]["enabled"] = "code_interpreter" in selected
    if "code_interpreter" not in selected:
        mark_deferred(deferred, "code_interpreter")

    if "web_search" in selected:
        prompt_web_search(
            ui,
            config,
            deferred,
            easy=False,
            docker_installed=docker_installed,
            docker_memory_bytes=docker_total_memory_bytes() if docker_installed else None,
        )
    else:
        mark_deferred(deferred, "web_search")

    config["integrations"]["openclaw"]["enabled"] = "openclaw" in selected
    if "openclaw" not in selected:
        mark_deferred(deferred, "openclaw")

    if "telegram" in selected:
        prompt_telegram(ui, config, deferred, easy=False)
    else:
        mark_deferred(deferred, "telegram")

    if "telegram_codex" in selected:
        prompt_telegram_codex(ui, config, deferred)
    else:
        mark_deferred(deferred, "telegram_codex")

    if "google_workspace" in selected:
        prompt_google_workspace(ui, config, deferred)
    else:
        mark_deferred(deferred, "google_workspace")

    if "ms365" in selected:
        prompt_ms365(ui, config, deferred)
    else:
        mark_deferred(deferred, "ms365")

    if "skyvern" in selected:
        prompt_skyvern(ui, config, deferred)
    else:
        mark_deferred(deferred, "skyvern")

    prompt_remote_access(ui, config)
    prompt_browser_auth_controls(ui, config)

    return config, deferred


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive Viventium config wizard.")
    parser.add_argument("--output", required=True, help="Path to config.yaml to write")
    parser.add_argument("--preset", help="Optional YAML config preset for non-interactive setup")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Require --preset and skip prompts entirely",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    preset_path = Path(args.preset).expanduser().resolve() if args.preset else None
    if args.non_interactive and preset_path is None:
        raise SystemExit("--non-interactive requires --preset")

    set_keychain_writes_enabled(not (args.non_interactive or not sys.stdin.isatty()))

    if preset_path is not None and (args.non_interactive or not sys.stdin.isatty()):
        config = normalize_preset(load_yaml_file(preset_path))
        validate_non_interactive_integrations(config)
        output_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        print(f"Wrote {output_path}")
        return

    ui = InstallerUI()
    ui.print_banner()
    ui.print_note(
        "Easy Install keeps the first run fast. Advanced Setup lets you choose more features now without losing the option to configure things later."
    )
    setup_profile = ui.select(
        "How would you like to set up Viventium?",
        [
            SelectOption(
                "recommended",
                "Easy Install",
                "Fastest path. Only asks for Groq and optional Telegram.",
            ),
            SelectOption(
                "advanced",
                "Advanced Setup",
                "Choose providers, features, and optional integrations now.",
            ),
        ],
        default="recommended",
    )

    if setup_profile == "recommended":
        config, deferred = configure_easy_install(ui)
    else:
        config, deferred = configure_advanced_setup(ui)

    config = normalize_preset(config)
    output_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    ui.print_blank()
    ui.print_success(f"Saved your configuration to {output_path}")
    summarize_setup_later(ui, deferred)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user.")
