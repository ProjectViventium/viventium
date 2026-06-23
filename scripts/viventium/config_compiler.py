#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from telegram_tokens import telegram_bot_token_validation_error
from retrieval_config import resolve_retrieval_embeddings_settings
from prompt_registry import (
    PromptRegistryError,
    build_prompt_bundle,
    load_prompt_registry,
    render_prompt,
    resolve_prompt_refs,
)

CONFIG_VERSION = 1
DEFAULT_MAIN_AGENT_ID = "agent_viventium_main_95aeb3"
EXPERIMENTAL_LOCAL_TTS_PROVIDER = "local_chatterbox_turbo_mlx_8bit"
DEFAULT_LOCAL_VOICE_GATEWAY_TTS_PROVIDER = "openai"
DEFAULT_VOICE_FAST_LLM_PROVIDER = ""
DEFAULT_WEB_SEARCH_PROVIDER = "searxng"
DEFAULT_WEB_SCRAPER_PROVIDER = "firecrawl"
DEFAULT_FIRECRAWL_API_URL = "https://api.firecrawl.dev"
DEFAULT_OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_OPENAI_TTS_VOICE = "coral"
DEFAULT_OPENAI_TTS_SPEED = "1.12"
DEFAULT_OPENAI_TTS_INSTRUCTIONS = (
    "Speak naturally and warmly with clear pacing. Keep the delivery conversational, "
    "grounded, and human. Avoid robotic emphasis or exaggerated pauses."
)
DEFAULT_CARTESIA_API_VERSION = "2026-03-01"
DEFAULT_CARTESIA_MODEL_ID = "sonic-3"
DEFAULT_CARTESIA_VOICE_ID = "e8e5fffb-252c-436d-b842-8879b84445b6"
DEFAULT_CARTESIA_SAMPLE_RATE = "44100"
DEFAULT_CARTESIA_SPEED = "1.0"
DEFAULT_CARTESIA_VOLUME = "1.0"
DEFAULT_CARTESIA_EMOTION = "neutral"
DEFAULT_CARTESIA_LANGUAGE = "en"
DEFAULT_CARTESIA_MAX_BUFFER_DELAY_MS = "120"
DEFAULT_CARTESIA_SEGMENT_SILENCE_MS = "80"
DEFAULT_XAI_TTS_API = "tts"
DEFAULT_XAI_TTS_API_URL = "https://api.x.ai/v1/tts"
DEFAULT_XAI_TTS_WS_URL = "wss://api.x.ai/v1/tts"
DEFAULT_XAI_TTS_VOICE = "Sal"
DEFAULT_XAI_TTS_LANGUAGE = "en"
DEFAULT_XAI_TTS_SAMPLE_RATE = "24000"
DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY = "1"
DEFAULT_XAI_TTS_CODEC = "mp3"
DEFAULT_XAI_TTS_BIT_RATE = "128000"
DEFAULT_BACKGROUND_FOLLOWUP_WINDOW_S = "30"
DEFAULT_GLASSHIVE_FOLLOWUP_TIMEOUT_S = "600"
DEFAULT_GLASSHIVE_MCP_BLOCKING_WAIT_MAX_SEC = 1800
DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_BUFFER_SEC = 60
DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_MS = (
    DEFAULT_GLASSHIVE_MCP_BLOCKING_WAIT_MAX_SEC + DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_BUFFER_SEC
) * 1000
SUPPORTED_GLASSHIVE_WORKER_PROFILES = {"codex-cli", "claude-code", "openclaw-general"}
DEFAULT_CORTEX_PHASE_A_NOTICE_MODE = "any_activated_on_voice"
DEFAULT_VIVENTIUM_TIMEZONE = "America/Toronto"
MIN_GLASSHIVE_FOLLOWUP_TIMEOUT_S = 30
MAX_GLASSHIVE_FOLLOWUP_TIMEOUT_S = 86400
DEFAULT_ASSEMBLYAI_STT_MODEL = "u3-rt-pro"
DEFAULT_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD = "0.01"
DEFAULT_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS = "100"
DEFAULT_ASSEMBLYAI_MAX_TURN_SILENCE_MS = "1000"
SUPPORTED_TELEGRAM_STT_PROVIDERS = {"openai", "assemblyai", "whisper_local", "pywhispercpp", "local"}
DEFAULT_LOCAL_CODE_INTERPRETER_API_KEY = "viventium-local-code-access"
DEFAULT_LOCAL_FIRECRAWL_API_KEY = "viventium-local-firecrawl-access"
DEFAULT_AGENT_RECURSION_LIMIT = 2000
DEFAULT_LOCAL_SEARXNG_PORT = 8082
DEFAULT_LOCAL_FIRECRAWL_PORT = 3003
LIBRECHAT_YAML_VERSION = "1.3.6"
DEFAULT_MS365_MCP_SCOPE = (
    "User.Read Mail.ReadWrite Calendars.ReadWrite Files.ReadWrite.All Sites.Read.All "
    "Team.ReadBasic.All Channel.ReadBasic.All Tasks.ReadWrite Contacts.Read Notes.Read "
    "offline_access"
)
DEFAULT_GOOGLE_WORKSPACE_MCP_SCOPE = (
    "openid https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.send "
    "https://www.googleapis.com/auth/gmail.compose "
    "https://www.googleapis.com/auth/gmail.modify "
    "https://www.googleapis.com/auth/gmail.labels "
    "https://www.googleapis.com/auth/drive "
    "https://www.googleapis.com/auth/drive.readonly "
    "https://www.googleapis.com/auth/drive.file "
    "https://www.googleapis.com/auth/calendar "
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/documents.readonly "
    "https://www.googleapis.com/auth/documents "
    "https://www.googleapis.com/auth/spreadsheets.readonly "
    "https://www.googleapis.com/auth/spreadsheets "
    "https://www.googleapis.com/auth/chat.messages.readonly "
    "https://www.googleapis.com/auth/chat.messages "
    "https://www.googleapis.com/auth/chat.spaces "
    "https://www.googleapis.com/auth/forms.body "
    "https://www.googleapis.com/auth/forms.body.readonly "
    "https://www.googleapis.com/auth/forms.responses.readonly "
    "https://www.googleapis.com/auth/presentations "
    "https://www.googleapis.com/auth/presentations.readonly "
    "https://www.googleapis.com/auth/tasks "
    "https://www.googleapis.com/auth/tasks.readonly "
    "https://www.googleapis.com/auth/cse"
)
LOCAL_MCP_ALLOWED_DOMAINS = ["localhost", "127.0.0.1", "host.docker.internal"]
REPO_ROOT = SCRIPT_DIR.parent.parent
GLASSHIVE_RUNTIME_DIR = REPO_ROOT / "viventium_v0_4" / "GlassHive" / "runtime_phase1"
LIBRECHAT_UPLOADS_DIR = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "uploads"
CODEX_APP_CLI = Path("/Applications/Codex.app/Contents/Resources/codex")
LEGACY_CANONICAL_ENV_IMPORT_KEYS = (
    "AZURE_AI_FOUNDRY_API_KEY",
    "AZURE_AI_FOUNDRY_API_VERSION",
    "AZURE_OPENAI_API_INSTANCE_NAME",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME",
    "AZURE_AI_SEARCH_API_KEY",
    "AZURE_AI_SEARCH_API_VERSION",
    "AZURE_AI_SEARCH_INDEX_NAME",
    "AZURE_AI_SEARCH_SEARCH_OPTION_QUERY_TYPE",
    "AZURE_AI_SEARCH_SEARCH_OPTION_SELECT",
    "AZURE_AI_SEARCH_SEARCH_OPTION_TOP",
    "AZURE_AI_SEARCH_SERVICE_ENDPOINT",
    "COHERE_API_KEY",
    "DEPLOYMENT_NAME",
    "FIRECRAWL_API_KEY",
    "FIRECRAWL_API_URL",
    "FIRECRAWL_VERSION",
    "GOOGLE_API_KEY",
    "GOOGLE_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GROQ_API_KEY",
    "INSTANCE_NAME",
    "MS365_MCP_CLIENT_ID",
    "MS365_MCP_CLIENT_SECRET",
    "MS365_MCP_SCOPE",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODELS",
    "ANTHROPIC_REVERSE_PROXY",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "OPENAI_MODELS",
    "OPENAI_REVERSE_PROXY",
    "OPENROUTER_API_KEY",
    "PERPLEXITY_API_KEY",
    "PORTKEY_API_KEY",
    "PORTKEY_BASE_URL",
    "PORTKEY_CONFIG",
    "PORTKEY_PROVIDER",
    "PORTKEY_VIRTUAL_KEY",
    "SERPER_API_KEY",
    "VIVENTIUM_ANTHROPIC_MODE",
    "VIVENTIUM_FOUNDRY_ANTHROPIC_MODELS",
    "VIVENTIUM_FOUNDRY_ANTHROPIC_REVERSE_PROXY",
    "XAI_API_KEY",
)

KEYCHAIN_SERVICE_ENV_FALLBACKS = {
    "viventium/assemblyai_api_key": ("ASSEMBLYAI_API_KEY",),
    "viventium/anthropic_api_key": ("ANTHROPIC_API_KEY",),
    "viventium/call_session_secret": (
        "VIVENTIUM_CALL_SESSION_SECRET",
        "VIVENTIUM_SCHEDULER_SECRET",
        "LIVEKIT_API_SECRET",
    ),
    "viventium/cartesia_api_key": ("CARTESIA_API_KEY",),
    "viventium/elevenlabs_api_key": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
    "viventium/google_client_secret": ("GOOGLE_CLIENT_SECRET",),
    "viventium/google_refresh_token": ("GOOGLE_REFRESH_TOKEN",),
    "viventium/groq_api_key": ("GROQ_API_KEY",),
    "viventium/firecrawl_api_key": ("FIRECRAWL_API_KEY",),
    "viventium/ms365_client_secret": ("MS365_MCP_CLIENT_SECRET",),
    "viventium/serper_api_key": ("SERPER_API_KEY",),
    "viventium/openai_api_key": ("OPENAI_API_KEY",),
    "viventium/openrouter_api_key": ("OPENROUTER_API_KEY",),
    "viventium/perplexity_api_key": ("PERPLEXITY_API_KEY",),
    "viventium/portkey_api_key": ("PORTKEY_API_KEY",),
    "viventium/portkey_virtual_key": ("PORTKEY_VIRTUAL_KEY",),
    "viventium/skyvern_api_key": ("SKYVERN_API_KEY",),
    "viventium/telegram_bot_token": ("BOT_TOKEN",),
    "viventium/telegram_codex_bot_token": ("TELEGRAM_CODEX_BOT_TOKEN",),
    "viventium/x_ai_api_key": ("XAI_API_KEY",),
}


def glasshive_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    configured = resolve_bool((integrations.get("glasshive") or {}).get("enabled"), False)
    return configured and GLASSHIVE_RUNTIME_DIR.is_dir()


def glasshive_deployment_mode(config: dict[str, Any]) -> str:
    integrations = config.get("integrations", {}) or {}
    glasshive = integrations.get("glasshive") or {}
    mode = str(glasshive.get("deployment_mode") or glasshive.get("mode") or "local").strip().lower()
    return mode or "local"


def glasshive_azure_enterprise_enabled(config: dict[str, Any]) -> bool:
    return glasshive_deployment_mode(config) == "azure_enterprise_vm_docker"


def _reject_localhost_cloud_url(label: str, value: str) -> None:
    lowered = value.strip().lower()
    if any(token in lowered for token in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
        raise SystemExit(f"{label} must be a non-localhost URL for azure_enterprise_vm_docker")


def resolve_glasshive_enterprise_settings(config: dict[str, Any]) -> dict[str, Any]:
    integrations = config.get("integrations", {}) or {}
    glasshive = integrations.get("glasshive") or {}
    enterprise = glasshive.get("enterprise") or {}
    if not isinstance(enterprise, dict):
        enterprise = {}
    enabled = glasshive_azure_enterprise_enabled(config)
    auth = enterprise.get("auth") or {}
    if not isinstance(auth, dict):
        auth = {}
    idle = enterprise.get("idle") or {}
    if not isinstance(idle, dict):
        idle = {}
    quotas = enterprise.get("quotas") or {}
    if not isinstance(quotas, dict):
        quotas = {}
    provider_env = enterprise.get("provider_env") or {}
    if not isinstance(provider_env, dict):
        provider_env = {}
    oauth = enterprise.get("oauth") or {}
    if not isinstance(oauth, dict):
        oauth = {}
    owner_identity = enterprise.get("owner_identity") or auth.get("owner_identity") or {}
    if not isinstance(owner_identity, dict):
        owner_identity = {}
    workspace_links = enterprise.get("workspace_links") or {}
    if not isinstance(workspace_links, dict):
        workspace_links = {}
    oauth_enabled = resolve_bool(oauth.get("enabled"), False)
    if enabled and oauth_enabled:
        for key in ("authorization_url", "token_url", "redirect_uri"):
            value = str(oauth.get(key) or "").strip()
            if value and not value.startswith("${"):
                _reject_localhost_cloud_url(f"integrations.glasshive.enterprise.oauth.{key}", value)
    mcp_url = str(glasshive.get("mcp_url") or enterprise.get("mcp_url") or "http://127.0.0.1:8767/mcp").strip()
    operator_base_url = str(
        glasshive.get("operator_base_url") or enterprise.get("operator_base_url") or "http://127.0.0.1:8780"
    ).strip().rstrip("/")
    artifact_base_url = str(
        glasshive.get("artifact_base_url")
        or enterprise.get("artifact_base_url")
        or glasshive.get("runtime_public_base_url")
        or enterprise.get("runtime_public_base_url")
        or operator_base_url
    ).strip().rstrip("/")
    if enabled:
        _reject_localhost_cloud_url("integrations.glasshive.mcp_url", mcp_url)
        _reject_localhost_cloud_url("integrations.glasshive.operator_base_url", operator_base_url)
        _reject_localhost_cloud_url("integrations.glasshive.enterprise.artifact_base_url", artifact_base_url)
    tenant_id = str(enterprise.get("tenant_id") or auth.get("tenant_id") or "default").strip() or "default"
    auth_mode = str(auth.get("mode") or enterprise.get("auth_mode") or "first_party_assertion").strip().lower()
    service_token_env = str(auth.get("service_token_env") or "GLASSHIVE_MCP_SERVICE_TOKEN").strip() or "GLASSHIVE_MCP_SERVICE_TOKEN"
    service_token_delivery = str(
        auth.get("service_token_delivery")
        or enterprise.get("service_token_delivery")
        or "reverse_proxy"
    ).strip().lower()
    if service_token_delivery not in {"reverse_proxy", "client_header"}:
        raise SystemExit(
            "integrations.glasshive.enterprise.auth.service_token_delivery must be reverse_proxy or client_header"
        )
    service_token = optional_nested_secret(auth, "service_token") or optional_nested_secret(enterprise, "service_token")
    signed_link_secret = optional_nested_secret(enterprise, "signed_link_secret")
    upload_root = str(enterprise.get("uploads_root") or glasshive.get("uploads_root") or LIBRECHAT_UPLOADS_DIR).strip()
    source_roots = enterprise.get("bootstrap_source_roots")
    if isinstance(source_roots, list):
        source_root_value = os.pathsep.join(str(item).strip() for item in source_roots if str(item).strip())
    else:
        source_root_value = str(source_roots or upload_root).strip()
    worker_env_allowlist = provider_env.get("allowlist")
    if isinstance(worker_env_allowlist, list):
        worker_env_allowlist_value = ",".join(str(item).strip() for item in worker_env_allowlist if str(item).strip())
    else:
        worker_env_allowlist_value = str(worker_env_allowlist or "").strip()
    owner_identity_claims = owner_identity.get("claims")
    if isinstance(owner_identity_claims, list):
        owner_identity_claims_value = ",".join(str(item).strip() for item in owner_identity_claims if str(item).strip())
    else:
        owner_identity_claims_value = str(owner_identity_claims or "").strip()
    if owner_identity_claims_value:
        claim_names = {item.strip() for item in owner_identity_claims_value.split(",") if item.strip()}
        invalid_claims = claim_names - {"user_id", "email"}
        if invalid_claims:
            raise SystemExit(
                "integrations.glasshive.enterprise.owner_identity.claims may include only user_id and email"
            )
    owner_identity_aliases = owner_identity.get("aliases") or {}
    owner_identity_aliases_json = ""
    if owner_identity_aliases:
        if not isinstance(owner_identity_aliases, dict):
            raise SystemExit("integrations.glasshive.enterprise.owner_identity.aliases must be a mapping")
        cleaned_aliases: dict[str, list[str]] = {}
        for owner, aliases in owner_identity_aliases.items():
            owner_id = str(owner or "").strip()
            if not owner_id:
                continue
            raw_aliases = [aliases] if isinstance(aliases, str) else aliases
            if not isinstance(raw_aliases, list):
                raise SystemExit(
                    "integrations.glasshive.enterprise.owner_identity.aliases values must be strings or lists"
                )
            clean_values = [str(item).strip() for item in raw_aliases if str(item).strip()]
            if clean_values:
                cleaned_aliases[owner_id] = clean_values
        if cleaned_aliases:
            owner_identity_aliases_json = json.dumps(cleaned_aliases, sort_keys=True, separators=(",", ":"))
    owner_identity_aliases_file = str(owner_identity.get("aliases_file") or "").strip()
    return {
        "enabled": enabled,
        "mcp_url": mcp_url,
        "operator_base_url": operator_base_url,
        "artifact_base_url": artifact_base_url,
        "tenant_id": tenant_id,
        "auth_mode": auth_mode,
        "service_token": service_token,
        "service_token_env": service_token_env,
        "service_token_delivery": service_token_delivery,
        "signed_link_secret": signed_link_secret,
        "upload_root": upload_root,
        "source_roots": source_root_value,
        "idle_terminate_after_s": positive_int_or_default(idle.get("terminate_after_seconds"), 1800, "integrations.glasshive.enterprise.idle.terminate_after_seconds"),
        "idle_reaper_interval_s": positive_int_or_default(idle.get("reaper_interval_seconds"), 60, "integrations.glasshive.enterprise.idle.reaper_interval_seconds"),
        "max_active_workers_per_user": positive_int_or_default(
            quotas.get("max_active_workers_per_user"),
            3,
            "integrations.glasshive.enterprise.quotas.max_active_workers_per_user",
        ),
        "max_active_workers_per_tenant": positive_int_or_default(
            quotas.get("max_active_workers_per_tenant"),
            12,
            "integrations.glasshive.enterprise.quotas.max_active_workers_per_tenant",
        ),
        "max_workspaces_per_user": positive_int_or_default(
            quotas.get("max_workspaces_per_user"),
            20,
            "integrations.glasshive.enterprise.quotas.max_workspaces_per_user",
        ),
        "max_workspaces_per_tenant": positive_int_or_default(
            quotas.get("max_workspaces_per_tenant"),
            100,
            "integrations.glasshive.enterprise.quotas.max_workspaces_per_tenant",
        ),
        "artifact_download_max_bytes": positive_int_or_default(
            enterprise.get("artifact_download_max_bytes"),
            100 * 1024 * 1024,
            "integrations.glasshive.enterprise.artifact_download_max_bytes",
        ),
        "worker_env_allowlist": worker_env_allowlist_value,
        "workspace_link_auto_resume": resolve_bool(workspace_links.get("auto_resume_on_open"), False),
        "owner_identity_claims": owner_identity_claims_value,
        "owner_identity_aliases_json": owner_identity_aliases_json,
        "owner_identity_aliases_file": owner_identity_aliases_file,
        "oauth_enabled": oauth_enabled,
        "oauth": oauth,
    }


def explicit_url_port(value: str) -> str:
    """Return the explicit port from an HTTP(S) URL, if one was configured."""
    try:
        parsed = urlparse(str(value or "").strip())
        port = parsed.port
    except ValueError:
        return ""
    if port is None:
        return ""
    return str(port)


def _executable_path(path: Path) -> bool:
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


def resolve_host_cli_path(command: str, explicit_path: Any = None) -> str:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(str(explicit_path)).expanduser())
    discovered = shutil.which(command)
    if discovered:
        candidates.append(Path(discovered))
    if command == "codex":
        candidates.extend(codex_app_cli_candidates())
    for candidate in candidates:
        if _executable_path(candidate):
            return str(candidate)
    return ""


def resolve_glasshive_host_worker_settings(config: dict[str, Any]) -> dict[str, Any]:
    integrations = config.get("integrations", {}) or {}
    glasshive = integrations.get("glasshive") or {}
    host_worker = glasshive.get("host_worker") or {}
    mentions = host_worker.get("mentions") or {}
    destructive_confirmation = host_worker.get("destructive_confirmation") or {}
    advisory_reviewer = host_worker.get("advisory_reviewer") or {}
    prompt_visibility = host_worker.get("prompt_visibility") or {}
    runtime_requirements = host_worker.get("runtime_requirements") or {}
    workspace_root = str(host_worker.get("workspace_root") or "~/viventium").strip() or "~/viventium"
    enabled = resolve_bool(host_worker.get("enabled"), True)
    # Config-driven default worker profile. Defaults to codex-cli (prior behavior, no
    # change for anyone who does not set it). Local configs may opt into claude-code.
    # The runtime validates this against GLASSHIVE_ALLOWED_WORKER_PROFILES, so a default
    # that is not in an environment's allowlist (e.g. enterprise excludes claude-code)
    # fails closed at startup rather than silently using an unadvertised worker.
    default_worker_profile = str(host_worker.get("default_worker_profile") or "codex-cli").strip() or "codex-cli"
    if default_worker_profile not in SUPPORTED_GLASSHIVE_WORKER_PROFILES:
        allowed_profiles = ", ".join(sorted(SUPPORTED_GLASSHIVE_WORKER_PROFILES))
        raise SystemExit(
            "integrations.glasshive.host_worker.default_worker_profile must be one of "
            f"{allowed_profiles}"
        )
    default_execution_mode = str(host_worker.get("default_execution_mode") or "host").strip().lower()
    if default_execution_mode not in {"host", "docker"}:
        default_execution_mode = "host"
    if not enabled:
        default_execution_mode = "docker"
    if glasshive_azure_enterprise_enabled(config):
        enabled = False
        default_execution_mode = "docker"
    codex_cli_path = resolve_host_cli_path("codex", host_worker.get("codex_bin"))
    claude_cli_path = resolve_host_cli_path("claude", host_worker.get("claude_bin"))
    openclaw_cli_path = resolve_host_cli_path("openclaw", host_worker.get("openclaw_bin"))

    def optional_csv(value: Any, label: str) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, str):
            return value.strip()
        raise SystemExit(f"{label} must be a string or list of strings")

    requirements_json = runtime_requirements.get("json")
    if requirements_json is None:
        requirements_json = host_worker.get("runtime_requirements_json")
    if isinstance(requirements_json, (dict, list)):
        requirements_json_env = json.dumps(requirements_json, sort_keys=True, separators=(",", ":"))
    elif requirements_json is None:
        requirements_json_env = ""
    elif isinstance(requirements_json, str):
        requirements_json_env = requirements_json.strip()
    else:
        raise SystemExit("integrations.glasshive.host_worker.runtime_requirements.json must be an object, list, or JSON string")

    runtime_requirements_file = str(
        runtime_requirements.get("file") or host_worker.get("runtime_requirements_file") or ""
    ).strip()
    codex_native_mcp_allowlist = optional_csv(
        host_worker.get("codex_native_mcp_allowlist"),
        "integrations.glasshive.host_worker.codex_native_mcp_allowlist",
    )
    codex_disable_features = optional_csv(
        host_worker.get("codex_disable_features"),
        "integrations.glasshive.host_worker.codex_disable_features",
    )
    claude_effort = str(host_worker.get("claude_effort") or "").strip().lower()
    if claude_effort and claude_effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise SystemExit("integrations.glasshive.host_worker.claude_effort must be low, medium, high, xhigh, or max")
    codex_ignore_user_config = ""
    if "codex_ignore_user_config" in host_worker:
        codex_ignore_user_config = "true" if resolve_bool(host_worker.get("codex_ignore_user_config"), False) else "false"
    claude_enable_chrome = ""
    if "claude_enable_chrome" in host_worker:
        claude_enable_chrome = "true" if resolve_bool(host_worker.get("claude_enable_chrome"), True) else "false"

    return {
        "enabled": enabled,
        "workspace_root": workspace_root,
        "default_worker_profile": default_worker_profile,
        "default_execution_mode": default_execution_mode,
        "mentions": {
            "codex": str(mentions.get("codex") or "@codex"),
            "claude": str(mentions.get("claude") or "@claude"),
            "openclaw": str(mentions.get("openclaw") or "@openclaw"),
        },
        "destructive_confirmation_enabled": resolve_bool(destructive_confirmation.get("enabled"), True),
        "advisory_reviewer_enabled": resolve_bool(advisory_reviewer.get("enabled"), False),
        "advisory_reviewer_mode": str(advisory_reviewer.get("mode") or "review_final").strip() or "review_final",
        "prompt_visibility_enabled": resolve_bool(prompt_visibility.get("enabled"), True),
        "codex_cli_path": codex_cli_path,
        "claude_cli_path": claude_cli_path,
        "openclaw_cli_path": openclaw_cli_path,
        "runtime_requirements_json": requirements_json_env,
        "runtime_requirements_file": runtime_requirements_file,
        "codex_native_mcp_allowlist": codex_native_mcp_allowlist,
        "codex_plugin_cache": str(host_worker.get("codex_plugin_cache") or "").strip(),
        "codex_ignore_user_config": codex_ignore_user_config,
        "codex_disable_features": codex_disable_features,
        "claude_enable_chrome": claude_enable_chrome,
        "claude_effort": claude_effort,
        "codex_cli_available": bool(codex_cli_path),
        "claude_cli_available": bool(claude_cli_path),
        "openclaw_cli_available": bool(openclaw_cli_path),
    }

VOICE_PROVIDER_KEYCHAIN_SERVICES = {
    "assemblyai": "viventium/assemblyai_api_key",
    "cartesia": "viventium/cartesia_api_key",
    "elevenlabs": "viventium/elevenlabs_api_key",
    "xai": "viventium/x_ai_api_key",
}

MODEL_MAP = {
    "openai": {
        "conscious": "gpt-5.4",
        "background_analysis": "gpt-5.4",
        "confirmation_bias": "gpt-5.4",
        "red_team": "gpt-5.4",
        "deep_research": "gpt-5.4",
        "productivity": "gpt-5.4",
        "parietal": "gpt-5.4",
        "pattern_recognition": "gpt-5.4",
        "emotional_resonance": "gpt-5.4",
        "strategic_planning": "gpt-5.4",
        "support": "gpt-5.4",
        "memory": "gpt-5.4",
    },
    "anthropic": {
        "conscious": "claude-opus-4-8",
        "background_analysis": "claude-sonnet-4-5",
        "confirmation_bias": "claude-sonnet-4-5",
        "red_team": "claude-opus-4-8",
        "deep_research": "claude-opus-4-8",
        "productivity": "claude-sonnet-4-5",
        "parietal": "claude-sonnet-4-5",
        "pattern_recognition": "claude-sonnet-4-5",
        "emotional_resonance": "claude-sonnet-4-5",
        "strategic_planning": "claude-opus-4-8",
        "support": "claude-sonnet-4-5",
        "memory": "claude-sonnet-4-5",
    },
    "x_ai": {
        "conscious": "grok-4.3",
        "background_analysis": "grok-4.3",
        "confirmation_bias": "grok-4.3",
        "red_team": "grok-4.3",
        "deep_research": "grok-4.3",
        "productivity": "grok-4.3",
        "parietal": "grok-4.3",
        "pattern_recognition": "grok-4.3",
        "emotional_resonance": "grok-4.3",
        "strategic_planning": "grok-4.3",
        "support": "grok-4.3",
        "memory": "grok-4.3",
    },
}
AGENT_ASSIGNMENT_ROLES = {
    "conscious",
    "background_analysis",
    "confirmation_bias",
    "red_team",
    "deep_research",
    "productivity",
    "parietal",
    "pattern_recognition",
    "emotional_resonance",
    "strategic_planning",
    "support",
    "memory",
}

MEMORY_HARDENING_LAUNCH_READY_MODELS = {
    "anthropic": {"claude-opus-4-8"},
    "openai": {"gpt-5.5"},
}
DEFAULT_MEMORY_HARDENING = {
    "enabled": False,
    "schedule": "0 3 * * *",
    "timezone": "America/Toronto",
    "operator_user_email": "",
    "provider": "",
    "lookback_days": 7,
    "min_user_idle_minutes": 60,
    "max_changes_per_user": 3,
    "max_input_chars": 500000,
    "require_full_lookback": True,
    "dry_run_first": True,
    "min_apply_interval_seconds": 300,
    "provider_profile": "launch_ready_only",
    "anthropic_model": "claude-opus-4-8",
    "anthropic_effort": "xhigh",
    "openai_model": "gpt-5.5",
    "openai_reasoning_effort": "xhigh",
    "transcripts": {
        "source_dir": "",
        "ignore_globs": [],
        "max_files_per_run": 20,
        "min_files_per_run": 5,
        "max_batches_per_invocation": 1,
        "max_chars_per_file": 500000,
        "summary_max_chars": 32000,
        "reference_memory_max_chars": 24000,
        "reference_messages_max_chars": 36000,
        "stable_evidence_max_age_days": 90,
        "rag_mode": "detailed_summary_only",
    },
}

MEMORY_TRANSCRIPT_RAG_MODES = {"detailed_summary_only", "raw_and_summary", "raw_only"}

CURRENT_BACKGROUND_ACTIVATION_PROVIDER = "groq"
CURRENT_BACKGROUND_ACTIVATION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CURRENT_BACKGROUND_ACTIVATION_PROVIDER_ALIASES = {"groq"}
OPTIONAL_BACKGROUND_ACTIVATION_PROVIDER_ALIASES = {"xai", "x_ai"}
BACKGROUND_ACTIVATION_MODELS_BY_PROVIDER = {
    "groq": CURRENT_BACKGROUND_ACTIVATION_MODEL,
    "xai": "grok-4.20-non-reasoning",
}
XAI_GROK_43_MODEL_SPEC = {
    "name": "grok-4.3",
    "label": "Grok 4.3",
    "description": "xAI Grok",
    "group": "xai",
    "groupIcon": "xai",
    "iconURL": "xai",
    "preset": {
        "endpoint": "xai",
        "model": "grok-4.3",
    },
}

CURATED_ADDED_ENDPOINTS = [
    "agents",
    "openAI",
    "anthropic",
    "google",
    "groq",
    "xai",
    "perplexity",
    "openrouter",
    "custom",
]

CURATED_AGENT_CAPABILITIES = [
    "deferred_tools",
    "programmatic_tools",
    "execute_code",
    "file_search",
    "web_search",
    "artifacts",
    "actions",
    "context",
    "tools",
    "ocr",
    "chain",
]

CURATED_CUSTOM_ENDPOINTS = [
    {
        "name": "perplexity",
        "apiKeyEnv": "PERPLEXITY_API_KEY",
        "baseURL": "https://api.perplexity.ai/",
        "models": [
            "sonar-deep-research",
            "sonar-reasoning-pro",
            "sonar-reasoning",
            "sonar-pro",
            "sonar",
            "r1-1776",
        ],
        "titleModel": "sonar",
        "summaryModel": "sonar",
        "modelDisplayLabel": "Perplexity",
        "dropParams": ["stop", "frequency_penalty"],
        "forcePrompt": False,
    },
    {
        "name": "xai",
        "apiKeyEnv": "XAI_API_KEY",
        "baseURL": "https://api.x.ai/v1",
        "models": [
            "grok-4.3",
            "grok-4.20-non-reasoning",
            "grok-4.20-multi-agent-0309",
            "grok-4.20-0309-reasoning",
            "grok-4.20-0309-non-reasoning",
            "grok-2-vision-1212",
            "grok-2-image-1212",
        ],
        "titleModel": "grok-4.3",
        "summaryModel": "grok-4.3",
        "modelDisplayLabel": "Grok",
        "fetch": True,
        "titleMethod": "completion",
        "forcePrompt": False,
    },
    {
        "name": "openrouter",
        "apiKeyEnv": "OPENROUTER_API_KEY",
        "baseURL": "https://openrouter.ai/api/v1",
        "models": [
            "moonshotai/kimi-k2.5",
            "moonshotai/kimi-k2",
            "moonshotai/kimi-k2-0905",
        ],
        "titleModel": "moonshotai/kimi-k2.5",
        "summaryModel": "moonshotai/kimi-k2.5",
        "modelDisplayLabel": "OpenRouter (Kimi)",
        "dropParams": ["stop"],
        "fetch": False,
    },
    {
        "name": "groq",
        "apiKeyEnv": "GROQ_API_KEY",
        "baseURL": "https://api.groq.com/openai/v1/",
        "models": [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            "moonshotai/kimi-k2-instruct",
            "qwen/qwen3-32b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "groq/compound",
            "groq/compound-mini",
        ],
        "titleModel": "meta-llama/llama-4-scout-17b-16e-instruct",
        "summaryModel": "meta-llama/llama-4-scout-17b-16e-instruct",
        "modelDisplayLabel": "Groq",
        "fetch": True,
    },
]

PROFILE_DEFAULTS = {
    "isolated": {
        "lc_api_port": 3180,
        "lc_frontend_port": 3190,
        "playground_port": 3300,
        "voice_gateway_health_port": 8301,
        "mongo_port": 27117,
        "mongo_db": "LibreChatViventium",
        "meili_port": 7700,
        "google_mcp_port": 8111,
        "scheduling_mcp_port": 7110,
        "rag_api_port": 8110,
        "code_interpreter_port": 8101,
        "skyvern_api_port": 8200,
        "skyvern_ui_port": 8280,
        "livekit_http_port": 7888,
        "livekit_tcp_port": 7889,
        "livekit_udp_port": 7890,
    },
    "compat": {
        "lc_api_port": 3080,
        "lc_frontend_port": 3090,
        "playground_port": 3000,
        "voice_gateway_health_port": 8300,
        "mongo_port": 27017,
        "mongo_db": "LibreChat",
        "meili_port": 7701,
        "google_mcp_port": 8000,
        "scheduling_mcp_port": 7010,
        "rag_api_port": 8000,
        "code_interpreter_port": 8001,
        "skyvern_api_port": 8000,
        "skyvern_ui_port": 8080,
        "livekit_http_port": 7880,
        "livekit_tcp_port": 7881,
        "livekit_udp_port": 7882,
    },
}
DEV_ENV_SCHEDULING_MCP_PORT_OFFSET_BIAS = 100

RUNTIME_PORT_KEYS = {
    "lc_api_port",
    "lc_frontend_port",
    "playground_port",
    "voice_gateway_health_port",
    "mongo_port",
    "meili_port",
    "google_mcp_port",
    "scheduling_mcp_port",
    "rag_api_port",
    "code_interpreter_port",
    "skyvern_api_port",
    "skyvern_ui_port",
    "livekit_http_port",
    "livekit_tcp_port",
    "livekit_udp_port",
}

SOURCE_OF_TRUTH_LIBRECHAT_YAML = (
    Path(__file__).resolve().parents[2]
    / "viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml"
)
SOURCE_OF_TRUTH_AGENTS_BUNDLE = (
    Path(__file__).resolve().parents[2]
    / "viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml"
)
DEFAULT_VIVENTIUM_AGENT_ICON_URL = "/assets/logo.svg"
APP_SUPPORT_VIVENTIUM_DIR = Path.home() / "Library" / "Application Support" / "Viventium"
_SOURCE_PROMPT_REGISTRY_CACHE: dict[str, Any] | None = None
PROMPT_AFFECTING_RUNTIME_CONFIG_SECTIONS = (
    "version",
    "cache",
    "registration",
    "interface",
    "modelSpecs",
    "viventium",
    "mcpSettings",
    "mcpServers",
    "endpoints",
    "memory",
    "webSearch",
    "speech",
    "balance",
)
SECRET_CONFIG_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "apikey",
    "api_key",
    "clientsecret",
    "client_secret",
    "refreshtoken",
    "refresh_token",
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must be a mapping: {path}")
    return data


def validate_config(config: dict[str, Any], config_path: Path) -> None:
    if int(config.get("version", 0)) != CONFIG_VERSION:
        raise SystemExit(f"Unsupported config version in {config_path}")

    activation_provider = normalize_provider_name(config["llm"]["activation"].get("provider"))
    allowed_activation_providers = CURRENT_BACKGROUND_ACTIVATION_PROVIDER_ALIASES | OPTIONAL_BACKGROUND_ACTIVATION_PROVIDER_ALIASES
    if activation_provider not in allowed_activation_providers:
        raise SystemExit(
            "Activation provider must be Groq by default, or xAI only as an explicit override."
        )
    if not provider_secret(config["llm"]["activation"]):
        provider_label = "xAI" if activation_provider == "xai" else "Groq"
        raise SystemExit(f"Missing required {provider_label} activation credential.")


def is_generated_viventium_runtime_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(APP_SUPPORT_VIVENTIUM_DIR.resolve())
        return True
    except ValueError:
        return False


def _source_prompt_registry() -> dict[str, Any]:
    global _SOURCE_PROMPT_REGISTRY_CACHE
    if _SOURCE_PROMPT_REGISTRY_CACHE is None:
        try:
            _SOURCE_PROMPT_REGISTRY_CACHE = load_prompt_registry()
        except PromptRegistryError as exc:
            raise SystemExit(f"Prompt registry validation failed: {exc}") from exc
    return _SOURCE_PROMPT_REGISTRY_CACHE


def resolve_source_of_truth_librechat_yaml_candidates() -> list[Path]:
    candidates: list[Path] = []
    compile_phase = os.environ.get("VIVENTIUM_LIBRECHAT_SOURCE_PHASE", "").strip() == "compile"
    private = os.environ.get("VIVENTIUM_LIBRECHAT_PRIVATE_SOURCE_OF_TRUTH", "").strip()
    explicit = os.environ.get("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH", "").strip()

    def add_candidate(raw: str | Path) -> None:
        candidate = Path(raw).expanduser().resolve()
        if candidate not in candidates:
            candidates.append(candidate)

    if compile_phase:
        if private:
            add_candidate(private)
        add_candidate(SOURCE_OF_TRUTH_LIBRECHAT_YAML)
        if explicit:
            add_candidate(explicit)
    else:
        if explicit:
            add_candidate(explicit)
        add_candidate(SOURCE_OF_TRUTH_LIBRECHAT_YAML)

    rejected = [candidate for candidate in candidates if is_generated_viventium_runtime_path(candidate)]
    candidates = [candidate for candidate in candidates if candidate not in rejected]
    explicit_generated = False
    for raw in (private, explicit):
        if raw and is_generated_viventium_runtime_path(Path(raw).expanduser().resolve()):
            explicit_generated = True
            break
    if rejected and (explicit_generated or not candidates):
        rejected_text = ", ".join(str(path) for path in rejected)
        raise SystemExit(
            "Generated App Support runtime files are not valid source-of-truth inputs. "
            f"Rejected: {rejected_text}. Use "
            f"{SOURCE_OF_TRUTH_LIBRECHAT_YAML} or an approved private source path."
        )
    return candidates


def load_source_of_truth_librechat_yaml() -> dict[str, Any]:
    for candidate in resolve_source_of_truth_librechat_yaml_candidates():
        if candidate.is_file():
            return resolve_source_prompt_refs(load_yaml(candidate))
    return {}


def load_source_of_truth_agents_bundle() -> dict[str, Any]:
    if not SOURCE_OF_TRUTH_AGENTS_BUNDLE.is_file():
        return {}
    return resolve_source_prompt_refs(load_yaml(SOURCE_OF_TRUTH_AGENTS_BUNDLE))


def resolve_source_prompt_refs(value: Any, registry: dict[str, Any] | None = None) -> Any:
    registry = registry if registry is not None else _source_prompt_registry()
    if not registry:
        if _contains_prompt_ref(value):
            raise SystemExit(
                "Prompt reference resolution failed: source YAML contains promptRef entries, "
                "but the Viventium prompt registry is empty or missing."
            )
        return value
    try:
        return resolve_prompt_refs(value, registry)
    except PromptRegistryError as exc:
        raise SystemExit(f"Prompt reference resolution failed: {exc}") from exc


def _contains_prompt_ref(value: Any) -> bool:
    if isinstance(value, dict):
        if "promptRef" in value or "promptRefs" in value:
            return True
        return any(_contains_prompt_ref(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_prompt_ref(nested) for nested in value)
    return False


def source_prompt_text(
    prompt_id: str,
    fallback: str,
    *,
    variables: dict[str, Any] | None = None,
) -> str:
    try:
        registry = _source_prompt_registry()
        if not registry:
            return fallback
        return render_prompt(prompt_id, registry, variables=variables or {}).strip()
    except PromptRegistryError as exc:
        raise SystemExit(f"Prompt registry validation failed for {prompt_id}: {exc}") from exc


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge_dicts(existing, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def merge_named_dict_list(
    preferred: list[dict[str, Any]],
    fallback: list[dict[str, Any]],
    *,
    key: str = "name",
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_items(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> None:
        for item in primary:
            name = str(item.get(key) or "").strip()
            if not name or name in seen:
                continue
            secondary_match = next(
                (
                    candidate
                    for candidate in secondary
                    if str(candidate.get(key) or "").strip() == name
                ),
                None,
            )
            payload = deep_merge_dicts(secondary_match or {}, item)
            merged.append(payload)
            seen.add(name)

    add_items(preferred, fallback)
    add_items(fallback, preferred)
    return merged


def merge_added_endpoints(preferred: list[str], fallback: list[str]) -> list[str]:
    merged: list[str] = []
    for candidate in [*preferred, *fallback]:
        normalized = str(candidate or "").strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def portable_agent_icon_url(agent: dict[str, Any]) -> str:
    avatar = agent.get("avatar")
    if not isinstance(avatar, dict):
        return DEFAULT_VIVENTIUM_AGENT_ICON_URL
    filepath = str(avatar.get("filepath") or "").strip()
    if (
        filepath.startswith("/assets/")
        or filepath.startswith("http://")
        or filepath.startswith("https://")
        or filepath.startswith("data:")
    ):
        return filepath
    return DEFAULT_VIVENTIUM_AGENT_ICON_URL


def build_built_in_agent_model_specs(default_main_agent_id: str) -> list[dict[str, Any]]:
    bundle = load_source_of_truth_agents_bundle()
    entries: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    def add_agent(agent: dict[str, Any], *, is_default: bool = False) -> None:
        if not isinstance(agent, dict):
            return
        agent_id = str(agent.get("id") or "").strip()
        if not agent_id or agent.get("missing") is True:
            return
        spec_name = "viventium" if is_default else agent_id
        if spec_name in seen_names:
            return
        entry: dict[str, Any] = {
            "name": spec_name,
            "label": str(agent.get("name") or agent_id).strip() or agent_id,
            "description": str(agent.get("description") or "").strip(),
            "iconURL": portable_agent_icon_url(agent),
            "preset": {
                "endpoint": "agents",
                "agent_id": default_main_agent_id if is_default else agent_id,
            },
        }
        if is_default:
            entry["default"] = True
        seen_names.add(spec_name)
        entries.append(entry)

    main_agent = bundle.get("mainAgent") if isinstance(bundle, dict) else {}
    add_agent(main_agent if isinstance(main_agent, dict) else {}, is_default=True)

    background_agents = bundle.get("backgroundAgents") if isinstance(bundle, dict) else []
    if isinstance(background_agents, list):
        for agent in background_agents:
            if not isinstance(agent, dict):
                continue
            add_agent(agent)

    return entries


def merge_model_specs(
    existing: dict[str, Any],
    generated: dict[str, Any],
    default_main_agent_id: str,
) -> dict[str, Any]:
    merged = deep_merge_dicts(existing, generated)
    existing_list = existing.get("list") if isinstance(existing.get("list"), list) else []
    generated_list = generated.get("list") if isinstance(generated.get("list"), list) else []
    merged["list"] = merge_named_dict_list(generated_list, existing_list)

    vivantium_found = False
    for entry in merged["list"]:
        if str(entry.get("name") or "").strip().lower() != "viventium":
            continue
        vivantium_found = True
        entry["default"] = True
        preset = entry.get("preset")
        if not isinstance(preset, dict):
            preset = {}
            entry["preset"] = preset
        preset["endpoint"] = "agents"
        preset["agent_id"] = default_main_agent_id
        if not str(entry.get("iconURL") or "").strip():
            entry["iconURL"] = DEFAULT_VIVENTIUM_AGENT_ICON_URL
        break

    if not vivantium_found:
        merged["list"] = [
            {
                "name": "viventium",
                "label": "Viventium",
                "description": "Main AI Agent",
                "default": True,
                "iconURL": DEFAULT_VIVENTIUM_AGENT_ICON_URL,
                "preset": {
                    "endpoint": "agents",
                    "agent_id": default_main_agent_id,
                },
            },
            *merged["list"],
        ]

    merged["addedEndpoints"] = merge_added_endpoints(
        existing.get("addedEndpoints", []) if isinstance(existing.get("addedEndpoints"), list) else [],
        generated.get("addedEndpoints", []) if isinstance(generated.get("addedEndpoints"), list) else [],
    )
    return merged
def has_non_placeholder_env(env: dict[str, str], key: str) -> bool:
    value = str(env.get(key, "") or "").strip()
    if not value:
        return False
    if value == "user_provided":
        return False
    if value.startswith("${") and value.endswith("}"):
        return False
    return True


def prune_unavailable_source_defaults(payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    cleaned = copy.deepcopy(payload)

    azure_foundry_available = all(
        has_non_placeholder_env(env, key)
        for key in ("AZURE_AI_FOUNDRY_API_KEY", "INSTANCE_NAME", "DEPLOYMENT_NAME")
    )
    anthropic_api_key_value = str(env.get("ANTHROPIC_API_KEY", "") or "").strip()
    anthropic_connected_account_available = resolve_bool(
        env.get("VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH"), False
    ) and anthropic_api_key_value == "user_provided"
    anthropic_endpoint_available = has_non_placeholder_env(
        env, "ANTHROPIC_API_KEY"
    ) or anthropic_connected_account_available
    azure_speech_available = all(
        has_non_placeholder_env(env, key)
        for key in ("AZURE_OPENAI_API_INSTANCE_NAME", "AZURE_OPENAI_API_KEY")
    )

    endpoints = cleaned.get("endpoints")
    if isinstance(endpoints, dict) and not azure_foundry_available:
        endpoints.pop("azureOpenAI", None)
    if isinstance(endpoints, dict):
        anthropic_endpoint = endpoints.get("anthropic")
        if anthropic_endpoint is not None and not anthropic_endpoint_available:
            endpoints.pop("anthropic", None)

    model_specs = cleaned.get("modelSpecs")
    if isinstance(model_specs, dict):
        entries = model_specs.get("list")
        if isinstance(entries, list):
            normalized_entries: list[dict[str, Any]] = []
            seen_names: set[str] = set()
            for entry in entries:
                preset = entry.get("preset") if isinstance(entry.get("preset"), dict) else {}
                endpoint = str(preset.get("endpoint") or "").strip()
                if endpoint == "azureOpenAI" and not azure_foundry_available:
                    continue
                if endpoint == "anthropic" and not anthropic_endpoint_available:
                    continue
                name = str(entry.get("name") or "").strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                normalized_entries.append(entry)
            model_specs["list"] = normalized_entries
        added_endpoints = model_specs.get("addedEndpoints")
        if isinstance(added_endpoints, list) and not anthropic_endpoint_available:
            model_specs["addedEndpoints"] = [
                endpoint
                for endpoint in added_endpoints
                if str(endpoint or "").strip() != "anthropic"
            ]

    speech = cleaned.get("speech")
    if isinstance(speech, dict):
        tts = speech.get("tts")
        if isinstance(tts, dict) and not azure_speech_available:
            tts.pop("azureOpenAI", None)
        stt = speech.get("stt")
        if isinstance(stt, dict) and not azure_speech_available:
            stt.pop("azureOpenAI", None)

    mcp_servers = cleaned.get("mcpServers")
    if isinstance(mcp_servers, dict):
        if not resolve_bool(env.get("START_MS365_MCP"), False) and not resolve_bool(
            env.get("VIVENTIUM_SHARED_MS365_MCP"),
            False,
        ):
            mcp_servers.pop("ms-365", None)
        if not resolve_bool(env.get("START_GOOGLE_MCP"), False) and not resolve_bool(
            env.get("VIVENTIUM_SHARED_GOOGLE_MCP"),
            False,
        ):
            mcp_servers.pop("google_workspace", None)
        if not resolve_bool(env.get("START_GLASSHIVE"), False):
            mcp_servers.pop("glasshive-workers-projects", None)
        ms365_server = mcp_servers.get("ms-365")
        if isinstance(ms365_server, dict):
            oauth = ms365_server.get("oauth")
            if isinstance(oauth, dict):
                for field, env_key in {
                    "client_id": "MS365_MCP_CLIENT_ID",
                    "client_secret": "MS365_MCP_CLIENT_SECRET",
                }.items():
                    if not has_non_placeholder_env(env, env_key):
                        oauth[field] = ""

    web_search = cleaned.get("webSearch")
    if isinstance(web_search, dict):
        optional_env_fields = {
            "searxngInstanceUrl": "SEARXNG_INSTANCE_URL",
            "serperApiKey": "SERPER_API_KEY",
            "firecrawlApiKey": "FIRECRAWL_API_KEY",
            "firecrawlApiUrl": "FIRECRAWL_API_URL",
            "firecrawlVersion": "FIRECRAWL_VERSION",
            "cohereApiKey": "COHERE_API_KEY",
        }
        for field, env_key in optional_env_fields.items():
            if not has_non_placeholder_env(env, env_key):
                web_search.pop(field, None)

        if "searxngInstanceUrl" not in web_search and web_search.get("searchProvider") == "searxng":
            web_search.pop("searchProvider", None)
        scraper_selector_key = "scraperProvider" if "scraperProvider" in web_search else "scraperType"
        if "firecrawlApiKey" not in web_search and web_search.get(scraper_selector_key) == "firecrawl":
            web_search.pop(scraper_selector_key, None)
        if "cohereApiKey" not in web_search and web_search.get("rerankerType") == "cohere":
            web_search.pop("rerankerType", None)

        if "scraperProvider" in web_search:
            web_search.pop("scraperType", None)

        if not web_search:
            cleaned.pop("webSearch", None)

    return cleaned


def positive_int(value: Any, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be an integer, got {value!r}") from exc
    if number <= 0:
        raise SystemExit(f"{label} must be greater than zero, got {value!r}")
    return number


def string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raise SystemExit(f"{label} must be a list or comma-separated string when provided")
    items: list[str] = []
    for item in raw_items:
        normalized = str(item).strip()
        if normalized:
            items.append(normalized)
    return items


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


def resolve_runtime_profile(config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    runtime = config.get("runtime", {}) or {}
    runtime_profile = str(runtime.get("profile", "isolated") or "isolated").strip().lower()
    profile = dict(PROFILE_DEFAULTS.get(runtime_profile, PROFILE_DEFAULTS["isolated"]))
    port_overrides = runtime.get("ports", {}) or {}
    if port_overrides and not isinstance(port_overrides, dict):
        raise SystemExit("runtime.ports must be a mapping when provided")
    for key, value in port_overrides.items():
        if key not in RUNTIME_PORT_KEYS or value in (None, ""):
            continue
        profile[key] = positive_int(value, f"runtime.ports.{key}")
    dev_env = runtime.get("dev_env", {}) or {}
    if isinstance(dev_env, dict) and resolve_bool(dev_env.get("enabled"), False):
        offset_raw = dev_env.get("port_offset")
        if "scheduling_mcp_port" not in port_overrides and offset_raw not in (None, ""):
            try:
                offset = int(offset_raw)
            except (TypeError, ValueError) as exc:
                raise SystemExit(
                    f"runtime.dev_env.port_offset must be an integer, got {offset_raw!r}"
                ) from exc
            scheduling_port = (
                profile["scheduling_mcp_port"]
                + offset
                + DEV_ENV_SCHEDULING_MCP_PORT_OFFSET_BIAS
            )
            if scheduling_port <= 0:
                raise SystemExit(
                    "runtime.dev_env.port_offset produced an invalid scheduling_mcp_port"
                )
            profile["scheduling_mcp_port"] = scheduling_port
    return runtime_profile, profile


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        parsed = value.strip()
        if len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in {"'", '"'}:
            parsed = parsed[1:-1]
        values[key] = parsed
    return values


def resolve_canonical_env_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def resolve_runtime_env_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("VIVENTIUM_ENV_FILE", "VIVENTIUM_ENV_LOCAL_FILE"):
        explicit = os.environ.get(env_name, "").strip()
        if explicit:
            candidates.append(Path(explicit).expanduser().resolve())

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def build_legacy_env_imports(config: dict[str, Any]) -> dict[str, str]:
    runtime = config.get("runtime", {}) or {}
    extra_env = runtime.get("extra_env", {}) or {}
    if extra_env and not isinstance(extra_env, dict):
        raise SystemExit("runtime.extra_env must be a mapping when provided")

    resolved: dict[str, str] = {}
    for key, value in extra_env.items():
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            resolved_value = resolve_secret(value.get("secret_ref") or value.get("secret_value") or "")
        else:
            resolved_value = resolve_secret(value)
        if resolved_value:
            resolved[str(key)] = resolved_value

    for key in LEGACY_CANONICAL_ENV_IMPORT_KEYS:
        env_value = os.environ.get(key, "").strip()
        if env_value:
            resolved.setdefault(key, env_value)

    for candidate in resolve_canonical_env_candidates():
        file_values = parse_env_file(candidate)
        for key in LEGACY_CANONICAL_ENV_IMPORT_KEYS:
            if key in resolved:
                continue
            file_value = file_values.get(key, "").strip()
            if file_value:
                resolved[key] = file_value

    return resolved


def keychain_service_env_keys(service: str) -> list[str]:
    normalized = service.strip().lower()
    if not normalized:
        return []

    candidates: list[str] = list(KEYCHAIN_SERVICE_ENV_FALLBACKS.get(normalized, ()))
    basename = normalized.split("/")[-1]
    generic = basename.upper().replace("-", "_")
    if generic:
        candidates.append(generic)
    if generic == "TELEGRAM_BOT_TOKEN":
        candidates.append("BOT_TOKEN")
    if generic == "X_AI_API_KEY":
        candidates.append("XAI_API_KEY")

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def resolve_keychain_secret_fallback(service: str) -> str:
    env_keys = keychain_service_env_keys(service)
    if not env_keys:
        return ""

    for env_key in env_keys:
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            return env_value

    for candidate in resolve_runtime_env_candidates():
        file_values = parse_env_file(candidate)
        for env_key in env_keys:
            file_value = file_values.get(env_key, "").strip()
            if file_value:
                return file_value

    for candidate in resolve_canonical_env_candidates():
        file_values = parse_env_file(candidate)
        for env_key in env_keys:
            file_value = file_values.get(env_key, "").strip()
            if file_value:
                return file_value

    return ""


def resolve_secret(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        if value.startswith("keychain://"):
            service = value[len("keychain://") :]
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                fallback_value = resolve_keychain_secret_fallback(service)
                if fallback_value:
                    return fallback_value
                raise SystemExit(f"Failed to resolve Keychain secret: {service}")
            return result.stdout.strip()
        return value
    raise SystemExit(f"Unsupported secret value: {value!r}")


def resolve_optional_secret(value: Any) -> str:
    try:
        return resolve_secret(value)
    except SystemExit:
        return ""


def provider_secret(node: dict[str, Any]) -> str:
    return resolve_secret(node.get("secret_ref") or node.get("secret_value") or "")


def normalize_provider_name(provider: Any) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized in {"x_ai", "grok", "xai_grok_voice"}:
        return "xai"
    return normalized


def current_background_activation_secret(config: dict[str, Any]) -> str:
    """Return only the configured primary activation credential.

    Fallback provider keys live under ``llm.extra_provider_keys`` and are exported independently.
    They must not silently replace the Groq-first activation credential because that masks VPN or
    provider-routing failures as a product routing change.
    """
    llm = config.get("llm", {}) or {}
    activation = llm.get("activation", {}) or {}
    return provider_secret(activation)


def validated_telegram_bot_token(node: dict[str, Any], integration_key: str) -> str:
    token = provider_secret(node)
    validation_error = telegram_bot_token_validation_error(token)
    if validation_error:
        raise SystemExit(
            f"{integration_key} is enabled, but its Telegram bot token is invalid. {validation_error}"
        )
    return token


def nested_secret(node: dict[str, Any], key: str) -> str:
    value = node.get(key, "")
    if isinstance(value, dict):
        return resolve_secret(value.get("secret_ref") or value.get("secret_value") or "")
    return resolve_secret(value)


def optional_nested_secret(node: dict[str, Any], key: str) -> str:
    value = node.get(key, "")
    if isinstance(value, dict):
        return resolve_optional_secret(value.get("secret_ref") or value.get("secret_value") or "")
    return resolve_optional_secret(value)


def scoped_secret(base_secret: str, scope: str) -> str:
    seed = f"viventium:{scope}:v1:{base_secret}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def positive_int_or_default(value: Any, default: int, label: str) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be an integer") from exc
    if parsed < 1:
        raise SystemExit(f"{label} must be greater than 0")
    return parsed


def bounded_int_or_default(value: Any, default: int, label: str, *, minimum: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise SystemExit(f"{label} must be between {minimum} and {maximum}")
    return parsed


def resolve_voice_provider_secret(
    voice: dict[str, Any],
    resolved_voice: dict[str, str],
    provider_name: str,
) -> str:
    provider_name = normalize_voice_tts_provider(provider_name)
    provider_keys = voice.get("provider_keys", {}) or {}
    if isinstance(provider_keys, dict):
        key_candidates = [provider_name]
        if provider_name == "xai":
            key_candidates.extend(["x_ai", "grok", "xai_grok_voice"])
        configured = next(
            (provider_keys.get(candidate) for candidate in key_candidates if provider_keys.get(candidate)),
            None,
        )
        if isinstance(configured, dict):
            resolved = resolve_optional_secret(
                configured.get("secret_ref") or configured.get("secret_value") or ""
            )
            if resolved:
                return resolved
        elif configured:
            resolved = resolve_optional_secret(configured)
            if resolved:
                return resolved

    if provider_name == "assemblyai" and resolved_voice["stt_provider"] == "assemblyai":
        resolved = optional_nested_secret(voice, "stt")
        if resolved:
            return resolved

    if provider_name == "elevenlabs" and resolved_voice["tts_provider"] == "elevenlabs":
        resolved = optional_nested_secret(voice, "tts")
        if resolved:
            return resolved

    if provider_name == "cartesia" and resolved_voice["tts_provider"] == "cartesia":
        resolved = optional_nested_secret(voice, "tts")
        if resolved:
            return resolved

    if provider_name == "xai" and resolved_voice["tts_provider"] == "xai":
        resolved = optional_nested_secret(voice, "tts")
        if resolved:
            return resolved

    service = VOICE_PROVIDER_KEYCHAIN_SERVICES.get(provider_name)
    if not service:
        return ""
    return resolve_optional_secret(f"keychain://{service}")


def cartesia_tts_settings(tts_config: dict[str, Any]) -> dict[str, Any]:
    """Return Cartesia-specific TTS settings while preserving legacy voice.tts shape."""
    if not isinstance(tts_config, dict):
        return {}
    nested = tts_config.get("cartesia")
    if isinstance(nested, dict):
        merged = dict(tts_config)
        merged.update(nested)
        return merged
    return tts_config


def xai_tts_settings(tts_config: dict[str, Any]) -> dict[str, Any]:
    """Return xAI-specific TTS settings while preserving legacy voice.tts shape."""
    if not isinstance(tts_config, dict):
        return {}
    nested = tts_config.get("xai") or tts_config.get("x_ai")
    if isinstance(nested, dict):
        merged = dict(tts_config)
        merged.update(nested)
        return merged
    return tts_config


def cartesia_voice_id_from_settings(settings: dict[str, Any]) -> str:
    raw_voice_id = settings.get("voice_id")
    if isinstance(raw_voice_id, str) and raw_voice_id.strip():
        return raw_voice_id.strip()

    raw_voice = settings.get("voice")
    if isinstance(raw_voice, dict):
        mode = str(raw_voice.get("mode", "id") or "id").strip().lower()
        if mode != "id":
            raise SystemExit("voice.tts.voice.mode currently supports only 'id' for Cartesia")
        voice_id = str(raw_voice.get("id", "") or "").strip()
        if voice_id:
            return voice_id
    elif isinstance(raw_voice, str) and raw_voice.strip():
        return raw_voice.strip()

    return DEFAULT_CARTESIA_VOICE_ID


def provider_available(node: dict[str, Any]) -> bool:
    provider = (node.get("provider") or "").strip()
    if not provider or provider == "none":
        return False
    auth_mode = node.get("auth_mode", "api_key")
    if auth_mode == "connected_account":
        return True
    return bool(provider_secret(node))


def enabled_provider_names(config: dict[str, Any]) -> list[str]:
    llm = config.get("llm", {}) or {}
    enabled: list[str] = []
    for node in (llm.get("primary", {}), llm.get("secondary", {})):
        provider = (node.get("provider") or "").strip()
        if provider and provider != "none" and provider_available(node):
            enabled.append(provider)
    for provider_name, secret_value in (llm.get("extra_provider_keys") or {}).items():
        if resolve_secret(secret_value or ""):
            enabled.append(str(provider_name))
    return list(dict.fromkeys(enabled))


def ensure_user_provided_endpoint_surfaces(env: dict[str, str]) -> None:
    env.setdefault("OPENAI_API_KEY", "user_provided")
    env.setdefault("ANTHROPIC_API_KEY", "user_provided")
    env.setdefault("GOOGLE_KEY", env.get("GOOGLE_API_KEY", "user_provided"))
    env.setdefault("GOOGLE_API_KEY", env.get("GOOGLE_KEY", "user_provided"))
    env.setdefault("XAI_API_KEY", "user_provided")
    env.setdefault("OPENROUTER_API_KEY", "user_provided")
    env.setdefault("PERPLEXITY_API_KEY", "user_provided")


def build_model_specs(_default_main_agent_id: str) -> dict[str, Any]:
    return {
        "prioritize": False,
        "addedEndpoints": CURATED_ADDED_ENDPOINTS,
        "list": [
            *build_built_in_agent_model_specs(_default_main_agent_id),
            copy.deepcopy(XAI_GROK_43_MODEL_SPEC),
        ],
    }


def build_custom_endpoints() -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for definition in CURATED_CUSTOM_ENDPOINTS:
        payload = {
            "name": definition["name"],
            "apiKey": f"${{{definition['apiKeyEnv']}}}",
            "baseURL": definition["baseURL"],
            "models": {
                "default": definition["models"],
                "fetch": definition.get("fetch", False),
            },
            "titleConvo": True,
            "titleModel": definition["titleModel"],
            "summarize": False,
            "summaryModel": definition["summaryModel"],
            "modelDisplayLabel": definition["modelDisplayLabel"],
        }
        if definition.get("titleMethod"):
            payload["titleMethod"] = definition["titleMethod"]
        if definition.get("dropParams"):
            payload["dropParams"] = definition["dropParams"]
        if definition.get("forcePrompt") is not None:
            payload["forcePrompt"] = definition["forcePrompt"]
        endpoints.append(payload)
    return endpoints


def choose_provider(available: list[str], preferred: list[str], fallback: str) -> str:
    for provider in preferred:
        if provider in available:
            return provider
    return fallback


def model_override_for(config: dict[str, Any], provider: str, role: str) -> str:
    overrides = (config.get("llm", {}) or {}).get("model_overrides") or {}
    provider_overrides = overrides.get(provider) or {}
    if isinstance(provider_overrides, str):
        return provider_overrides.strip()
    if not isinstance(provider_overrides, dict):
        return ""
    role_value = provider_overrides.get(role)
    if role_value is not None:
        return str(role_value).strip()
    default_value = provider_overrides.get("default")
    return str(default_value).strip() if default_value is not None else ""


def assignment_model(config: dict[str, Any], provider: str, role: str) -> str:
    override = model_override_for(config, provider, role)
    return override or MODEL_MAP[provider][role]


def has_model_overrides(config: dict[str, Any]) -> bool:
    overrides = (config.get("llm", {}) or {}).get("model_overrides") or {}
    if not isinstance(overrides, dict):
        return False
    for provider_overrides in overrides.values():
        if isinstance(provider_overrides, str) and provider_overrides.strip():
            return True
        if not isinstance(provider_overrides, dict):
            continue
        for role, value in provider_overrides.items():
            if role != "default" and role not in AGENT_ASSIGNMENT_ROLES:
                continue
            if str(value or "").strip():
                return True
    return False


def runtime_model_lists(
    config: dict[str, Any],
    assignments: dict[str, tuple[str, str]],
) -> dict[str, list[str]]:
    provider_env_keys = {
        "openai": "OPENAI_MODELS",
        "anthropic": "ANTHROPIC_MODELS",
    }
    model_lists: dict[str, list[str]] = {}
    for role, (provider, model) in assignments.items():
        env_key = provider_env_keys.get(provider)
        if not env_key or not model:
            continue
        if not model_override_for(config, provider, role):
            continue
        models = model_lists.setdefault(env_key, [])
        if model not in models:
            models.append(model)
    return model_lists


def worker_runtime_model_env(config: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    openai_model = model_override_for(config, "openai", "glasshive_codex") or model_override_for(config, "openai", "default")
    if openai_model:
        values["WPR_MODEL_CODEX_CLI"] = openai_model
        values["WPR_MODEL_OPENCLAW_CODEX"] = openai_model
    anthropic_model = model_override_for(config, "anthropic", "glasshive_claude") or model_override_for(config, "anthropic", "default")
    if anthropic_model:
        values["WPR_MODEL_CLAUDE_CODE"] = anthropic_model
        values["WPR_MODEL_OPENCLAW_CLAUDE"] = anthropic_model
    return values


def apply_provider_endpoint_env_aliases(env: dict[str, str]) -> None:
    if env.get("OPENAI_BASE_URL"):
        env.setdefault("OPENAI_REVERSE_PROXY", env["OPENAI_BASE_URL"])
    elif env.get("OPENAI_API_BASE"):
        env.setdefault("OPENAI_REVERSE_PROXY", env["OPENAI_API_BASE"])
    if env.get("ANTHROPIC_BASE_URL"):
        env.setdefault("ANTHROPIC_REVERSE_PROXY", env["ANTHROPIC_BASE_URL"])


def build_agent_assignments(config: dict[str, Any]) -> dict[str, tuple[str, str]]:
    primary = config["llm"]["primary"]
    secondary = config["llm"].get("secondary", {})
    available = []
    if provider_available(primary):
        available.append(primary["provider"])
    if provider_available(secondary):
        available.append(secondary["provider"])
    for provider_name, node in (config["llm"].get("extra_provider_keys") or {}).items():
        if resolve_secret(node or ""):
            available.append(provider_name)
    available = list(dict.fromkeys(available))
    if not available:
        raise SystemExit("At least one non-Groq LLM provider must be configured.")

    foundation_available = [provider for provider in available if provider in {"openai", "anthropic"}]
    if not foundation_available:
        raise SystemExit(
            "At least one of OpenAI or Anthropic must be configured for Viventium main/background agents."
        )

    foundation_fallback = foundation_available[0]
    conscious_provider = choose_provider(foundation_available, ["anthropic", "openai"], foundation_fallback)
    reflective_provider = choose_provider(foundation_available, ["anthropic", "openai"], foundation_fallback)
    analytical_provider = choose_provider(foundation_available, ["openai", "anthropic"], foundation_fallback)
    emotional_provider = choose_provider(foundation_available, ["anthropic", "openai"], foundation_fallback)
    support_provider = choose_provider(foundation_available, ["anthropic", "openai"], foundation_fallback)
    memory_provider = choose_provider(foundation_available, ["anthropic", "openai"], foundation_fallback)

    return {
        "conscious": (conscious_provider, assignment_model(config, conscious_provider, "conscious")),
        "background_analysis": (
            reflective_provider,
            assignment_model(config, reflective_provider, "background_analysis"),
        ),
        "confirmation_bias": (
            reflective_provider,
            assignment_model(config, reflective_provider, "confirmation_bias"),
        ),
        "red_team": (analytical_provider, assignment_model(config, analytical_provider, "red_team")),
        "deep_research": (
            analytical_provider,
            assignment_model(config, analytical_provider, "deep_research"),
        ),
        "productivity": (analytical_provider, assignment_model(config, analytical_provider, "productivity")),
        "parietal": (analytical_provider, assignment_model(config, analytical_provider, "parietal")),
        "pattern_recognition": (
            reflective_provider,
            assignment_model(config, reflective_provider, "pattern_recognition"),
        ),
        "emotional_resonance": (
            emotional_provider,
            assignment_model(config, emotional_provider, "emotional_resonance"),
        ),
        "strategic_planning": (
            emotional_provider,
            assignment_model(config, emotional_provider, "strategic_planning"),
        ),
        "support": (support_provider, assignment_model(config, support_provider, "support")),
        "memory": (memory_provider, assignment_model(config, memory_provider, "memory")),
    }


def apply_memory_assignment(
    payload: dict[str, Any],
    assignments: dict[str, tuple[str, str]],
) -> None:
    memory = payload.get("memory")
    if not isinstance(memory, dict):
        return
    agent = memory.get("agent")
    if not isinstance(agent, dict):
        return
    provider, model = assignments["memory"]
    agent["provider"] = provider
    agent["model"] = model


def normalize_anthropic_title_endpoint(payload: dict[str, Any]) -> None:
    endpoints = payload.get("endpoints")
    if not isinstance(endpoints, dict):
        return
    anthropic_endpoint = endpoints.get("anthropic")
    if not isinstance(anthropic_endpoint, dict):
        return
    anthropic_endpoint["titleEndpoint"] = "anthropic"
    anthropic_endpoint["titleModel"] = str(
        anthropic_endpoint.get("summaryModel") or MODEL_MAP["anthropic"]["background_analysis"]
    ).strip()


def host_supports_local_tts() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def normalize_telegram_stt_provider(value: Any, field_path: str) -> str:
    provider = str(value or "").strip().lower()
    if not provider:
        return ""
    if provider not in SUPPORTED_TELEGRAM_STT_PROVIDERS:
        allowed = ", ".join(sorted(SUPPORTED_TELEGRAM_STT_PROVIDERS))
        raise SystemExit(f"{field_path} must be one of: {allowed}")
    return provider


def normalize_voice_tts_provider(value: Any) -> str:
    provider = str(value or "").strip().lower()
    if provider in {"x_ai", "grok", "xai_grok_voice"}:
        return "xai"
    return provider


def resolve_voice_settings(config: dict[str, Any]) -> dict[str, str]:
    voice = config.get("voice", {}) or {}
    voice_mode = str(voice.get("mode", "disabled") or "disabled").strip().lower()
    raw_stt_provider = str(voice.get("stt_provider", "") or "").strip().lower()
    stt_provider = raw_stt_provider or "whisper_local"
    stt_model = str(voice.get("stt_model", "") or "").strip()
    tts_provider = normalize_voice_tts_provider(voice.get("tts_provider", ""))
    tts_provider_fallback = normalize_voice_tts_provider(voice.get("tts_provider_fallback", ""))

    if voice_mode == "local":
        # `browser` is a user-facing/client-side intent, not an instruction to silently route the
        # server-side voice gateway through experimental local MLX TTS. Keep the default stable
        # unless the user explicitly asks for local automatic or the direct local MLX provider.
        if not tts_provider or tts_provider == "browser":
            tts_provider = DEFAULT_LOCAL_VOICE_GATEWAY_TTS_PROVIDER
        elif tts_provider in {"local_automatic", "automatic", "auto"}:
            tts_provider = (
                EXPERIMENTAL_LOCAL_TTS_PROVIDER
                if host_supports_local_tts()
                else DEFAULT_LOCAL_VOICE_GATEWAY_TTS_PROVIDER
            )
        elif tts_provider == EXPERIMENTAL_LOCAL_TTS_PROVIDER and not host_supports_local_tts():
            # Intel Macs and non-macOS hosts cannot install MLX-Audio. Convert an explicit local
            # Chatterbox request into the configured hosted fallback so clean installs still ship a
            # working voice worker instead of dying during dependency bootstrap.
            tts_provider = tts_provider_fallback or DEFAULT_LOCAL_VOICE_GATEWAY_TTS_PROVIDER
            tts_provider_fallback = ""
        if not tts_provider_fallback and tts_provider == EXPERIMENTAL_LOCAL_TTS_PROVIDER:
            tts_provider_fallback = "openai"
    elif voice_mode == "hosted":
        if not tts_provider or tts_provider == "browser":
            tts_provider = "openai"
    else:
        if not tts_provider:
            tts_provider = "browser"
    # Legacy compatibility: older configs may still carry `voice.fast_llm_provider`, but the
    # Voice Call LLM is now owned by the agent primary model plus optional explicit agent voice
    # override fields. Compiler-managed voice config remains responsible only for STT/TTS routing.

    return {
        "mode": voice_mode,
        "stt_provider": stt_provider,
        "stt_model": stt_model,
        "tts_provider": tts_provider,
        "tts_provider_fallback": tts_provider_fallback,
    }


def normalize_remote_call_mode(network: dict[str, Any]) -> str:
    mode = str(network.get("remote_call_mode", "disabled") or "disabled").strip().lower()
    if not mode or mode == "auto":
        # `auto` was the legacy quick-tunnel experiment. Local installs should not silently expose
        # remote voice surfaces anymore; operators must opt in explicitly.
        return "disabled"
    if mode in {"custom_domain", "custom_domain_public_edge", "public_custom_domain"}:
        return "public_https_edge"
    return mode


def code_interpreter_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    code_interpreter = integrations.get("code_interpreter", {}) or {}
    return resolve_bool(code_interpreter.get("enabled"), False)


def web_search_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    return resolve_bool(web_search.get("enabled"), False)


def resolve_web_search_settings(config: dict[str, Any]) -> dict[str, str]:
    integrations = config.get("integrations", {}) or {}
    web_search = integrations.get("web_search", {}) or {}
    enabled = resolve_bool(web_search.get("enabled"), False)

    search_provider = str(
        web_search.get("search_provider", DEFAULT_WEB_SEARCH_PROVIDER) or DEFAULT_WEB_SEARCH_PROVIDER
    ).strip().lower()
    if search_provider in {"local", "searxng"}:
        search_provider = "searxng"
    elif search_provider != "serper":
        search_provider = DEFAULT_WEB_SEARCH_PROVIDER

    scraper_provider = str(
        web_search.get("scraper_provider", DEFAULT_WEB_SCRAPER_PROVIDER)
        or DEFAULT_WEB_SCRAPER_PROVIDER
    ).strip().lower()
    if scraper_provider in {"local", "firecrawl"}:
        scraper_provider = "firecrawl"
    elif scraper_provider in {"api", "firecrawl_api"}:
        scraper_provider = "firecrawl_api"
    elif scraper_provider == "none":
        scraper_provider = "none"
    else:
        scraper_provider = DEFAULT_WEB_SCRAPER_PROVIDER

    firecrawl_api_url = str(
        web_search.get("firecrawl_api_url", DEFAULT_FIRECRAWL_API_URL) or DEFAULT_FIRECRAWL_API_URL
    ).strip() or DEFAULT_FIRECRAWL_API_URL

    return {
        "enabled": "true" if enabled else "false",
        "search_provider": search_provider,
        "scraper_provider": scraper_provider,
        "serper_api_key": optional_nested_secret(web_search, "serper_api_key"),
        "firecrawl_api_key": optional_nested_secret(web_search, "firecrawl_api_key"),
        "firecrawl_api_url": firecrawl_api_url,
    }


def web_search_local_services_requested(config: dict[str, Any]) -> bool:
    web_search = resolve_web_search_settings(config)
    if web_search["enabled"] != "true":
        return False
    return web_search["search_provider"] == "searxng" or web_search["scraper_provider"] == "firecrawl"


SHARED_SINGLETON_SERVICE_ALIASES = {
    "recall_rag": {"recall_rag", "rag", "rag_api", "conversation_recall"},
    "searxng": {"searxng", "web_search_searxng"},
    "firecrawl": {"firecrawl", "web_search_firecrawl"},
    "google_workspace_mcp": {"google_workspace_mcp", "google_workspace", "google_mcp"},
    "ms365_mcp": {"ms365_mcp", "ms365", "microsoft_365_mcp"},
}


def runtime_dev_env_settings(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {}) or {}
    dev_env = runtime.get("dev_env", {}) or {}
    if not isinstance(dev_env, dict):
        return {"enabled": False, "name": "", "shared_singleton_services": set()}
    shared_raw = dev_env.get("shared_singleton_services", []) or []
    shared: set[str] = set()
    if isinstance(shared_raw, list):
        for item in shared_raw:
            token = str(item or "").strip().lower()
            for canonical, aliases in SHARED_SINGLETON_SERVICE_ALIASES.items():
                if token in aliases:
                    shared.add(canonical)
    return {
        "enabled": resolve_bool(dev_env.get("enabled"), False),
        "name": str(dev_env.get("name") or "").strip(),
        "shared_singleton_services": shared,
    }


def dev_env_shares_service(config: dict[str, Any], service: str) -> bool:
    settings = runtime_dev_env_settings(config)
    return bool(settings["enabled"] and service in settings["shared_singleton_services"])


def conversation_recall_enabled(config: dict[str, Any]) -> bool:
    runtime = config.get("runtime", {}) or {}
    personalization = runtime.get("personalization", {}) or {}
    return resolve_bool(personalization.get("default_conversation_recall"), False)


def resolve_memory_hardening_settings(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {}) or {}
    raw = runtime.get("memory_hardening", {}) or {}
    if raw and not isinstance(raw, dict):
        raise SystemExit("runtime.memory_hardening must be a mapping when provided")

    settings = copy.deepcopy(DEFAULT_MEMORY_HARDENING)
    settings.update(raw)
    raw_transcripts = raw.get("transcripts", {}) if isinstance(raw, dict) else {}
    if raw_transcripts and not isinstance(raw_transcripts, dict):
        raise SystemExit("runtime.memory_hardening.transcripts must be a mapping when provided")
    transcripts = dict(DEFAULT_MEMORY_HARDENING["transcripts"])
    transcripts.update(raw_transcripts or {})
    settings["enabled"] = resolve_bool(settings.get("enabled"), False)
    settings["dry_run_first"] = resolve_bool(settings.get("dry_run_first"), True)
    settings["require_full_lookback"] = resolve_bool(settings.get("require_full_lookback"), True)
    settings["operator_user_email"] = str(settings.get("operator_user_email") or "").strip()
    settings["provider"] = str(settings.get("provider") or "").strip().lower()
    if settings["provider"] and settings["provider"] not in {"anthropic", "openai"}:
        raise SystemExit("runtime.memory_hardening.provider must be anthropic, openai, or empty")
    settings["schedule"] = str(settings.get("schedule") or DEFAULT_MEMORY_HARDENING["schedule"])
    settings["timezone"] = str(settings.get("timezone") or DEFAULT_MEMORY_HARDENING["timezone"])
    settings["provider_profile"] = str(
        settings.get("provider_profile") or DEFAULT_MEMORY_HARDENING["provider_profile"]
    )
    settings["lookback_days"] = positive_int(
        settings.get("lookback_days"), "runtime.memory_hardening.lookback_days"
    )
    settings["min_user_idle_minutes"] = positive_int(
        settings.get("min_user_idle_minutes"), "runtime.memory_hardening.min_user_idle_minutes"
    )
    settings["max_changes_per_user"] = positive_int(
        settings.get("max_changes_per_user"), "runtime.memory_hardening.max_changes_per_user"
    )
    settings["max_input_chars"] = positive_int(
        settings.get("max_input_chars"), "runtime.memory_hardening.max_input_chars"
    )
    settings["min_apply_interval_seconds"] = positive_int(
        settings.get("min_apply_interval_seconds"),
        "runtime.memory_hardening.min_apply_interval_seconds",
    )
    settings["anthropic_model"] = str(
        settings.get("anthropic_model") or DEFAULT_MEMORY_HARDENING["anthropic_model"]
    )
    settings["anthropic_effort"] = str(
        settings.get("anthropic_effort") or DEFAULT_MEMORY_HARDENING["anthropic_effort"]
    )
    settings["openai_model"] = str(settings.get("openai_model") or DEFAULT_MEMORY_HARDENING["openai_model"])
    settings["openai_reasoning_effort"] = str(
        settings.get("openai_reasoning_effort")
        or DEFAULT_MEMORY_HARDENING["openai_reasoning_effort"]
    )
    transcripts["source_dir"] = str(transcripts.get("source_dir") or "").strip()
    transcripts["ignore_globs"] = string_list(
        transcripts.get("ignore_globs"),
        "runtime.memory_hardening.transcripts.ignore_globs",
    )
    transcripts["max_files_per_run"] = positive_int(
        transcripts.get("max_files_per_run"),
        "runtime.memory_hardening.transcripts.max_files_per_run",
    )
    transcripts["min_files_per_run"] = positive_int(
        transcripts.get("min_files_per_run"),
        "runtime.memory_hardening.transcripts.min_files_per_run",
    )
    transcripts["max_batches_per_invocation"] = positive_int(
        transcripts.get("max_batches_per_invocation"),
        "runtime.memory_hardening.transcripts.max_batches_per_invocation",
    )
    transcripts["max_chars_per_file"] = positive_int(
        transcripts.get("max_chars_per_file"),
        "runtime.memory_hardening.transcripts.max_chars_per_file",
    )
    transcripts["summary_max_chars"] = positive_int(
        transcripts.get("summary_max_chars"),
        "runtime.memory_hardening.transcripts.summary_max_chars",
    )
    transcripts["reference_memory_max_chars"] = positive_int(
        transcripts.get("reference_memory_max_chars"),
        "runtime.memory_hardening.transcripts.reference_memory_max_chars",
    )
    transcripts["reference_messages_max_chars"] = positive_int(
        transcripts.get("reference_messages_max_chars"),
        "runtime.memory_hardening.transcripts.reference_messages_max_chars",
    )
    transcripts["stable_evidence_max_age_days"] = positive_int(
        transcripts.get("stable_evidence_max_age_days"),
        "runtime.memory_hardening.transcripts.stable_evidence_max_age_days",
    )
    transcripts["rag_mode"] = str(
        transcripts.get("rag_mode") or DEFAULT_MEMORY_HARDENING["transcripts"]["rag_mode"]
    )
    if transcripts["rag_mode"] not in MEMORY_TRANSCRIPT_RAG_MODES:
        raise SystemExit(
            "runtime.memory_hardening.transcripts.rag_mode must be detailed_summary_only, raw_and_summary, or raw_only"
        )
    settings["transcripts"] = transcripts

    if settings["provider_profile"] != "launch_ready_only":
        raise SystemExit(
            "runtime.memory_hardening.provider_profile must be launch_ready_only for public builds"
        )
    if settings["anthropic_model"] not in MEMORY_HARDENING_LAUNCH_READY_MODELS["anthropic"]:
        raise SystemExit(
            "runtime.memory_hardening.anthropic_model must stay in launch-ready Anthropic families"
        )
    if settings["openai_model"] not in MEMORY_HARDENING_LAUNCH_READY_MODELS["openai"]:
        raise SystemExit("runtime.memory_hardening.openai_model must stay in launch-ready OpenAI families")
    if settings["anthropic_effort"] != "xhigh":
        raise SystemExit("runtime.memory_hardening.anthropic_effort must stay xhigh for public builds")
    if settings["openai_reasoning_effort"] != "xhigh":
        raise SystemExit(
            "runtime.memory_hardening.openai_reasoning_effort must stay xhigh for public builds"
        )

    return settings


def resolve_memory_hardening_model_tuple(
    config: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, str]:
    explicit_provider = str(settings.get("provider") or "").strip().lower()
    if explicit_provider == "anthropic":
        return {
            "provider": "anthropic",
            "model": settings["anthropic_model"],
            "effort": settings["anthropic_effort"],
            "effort_env": "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT",
        }
    if explicit_provider == "openai":
        return {
            "provider": "openai",
            "model": settings["openai_model"],
            "effort": settings["openai_reasoning_effort"],
            "effort_env": "VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT",
        }
    available = [provider for provider in enabled_provider_names(config) if provider in {"anthropic", "openai"}]
    provider = choose_provider(available, ["anthropic", "openai"], available[0] if available else "")
    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "model": settings["anthropic_model"],
            "effort": settings["anthropic_effort"],
            "effort_env": "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT",
        }
    if provider == "openai":
        return {
            "provider": "openai",
            "model": settings["openai_model"],
            "effort": settings["openai_reasoning_effort"],
            "effort_env": "VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT",
        }
    return {"provider": "", "model": "", "effort": "", "effort_env": ""}


def resolve_auth_settings(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {}) or {}
    auth = runtime.get("auth", {}) or {}
    openid = auth.get("openid") or {}
    if not isinstance(openid, dict):
        openid = {}
    openid_enabled = resolve_bool(openid.get("enabled"), False)
    openid_client_secret = optional_nested_secret(openid, "client_secret") if openid_enabled else ""
    openid_session_secret = optional_nested_secret(openid, "session_secret") if openid_enabled else ""
    return {
        "allow_email_login": resolve_bool(auth.get("allow_email_login"), True),
        "allow_registration": resolve_bool(auth.get("allow_registration"), True),
        "bootstrap_registration_once": resolve_bool(
            auth.get("bootstrap_registration_once"), False
        ),
        "allow_password_reset": resolve_bool(auth.get("allow_password_reset"), False),
        "connected_accounts_return_origin": str(
            auth.get("connected_accounts_return_origin", "") or ""
        )
        .strip()
        .rstrip("/"),
        "openid": {
            "enabled": openid_enabled,
            "client_id": str(openid.get("client_id") or "").strip(),
            "client_secret": openid_client_secret,
            "issuer": str(openid.get("issuer") or "").strip().rstrip("/"),
            "session_secret": openid_session_secret,
            "scope": str(openid.get("scope") or "openid profile email").strip(),
            "callback_url": str(openid.get("callback_url") or "/oauth/openid/callback").strip(),
            "button_label": str(openid.get("button_label") or "Continue with OpenID").strip(),
            "image_url": str(openid.get("image_url") or "").strip(),
            "auto_redirect": resolve_bool(openid.get("auto_redirect"), False),
            "use_pkce": resolve_bool(openid.get("use_pkce"), True),
            "reuse_tokens": resolve_bool(openid.get("reuse_tokens"), False),
            "email_claim": str(openid.get("email_claim") or "").strip(),
            "username_claim": str(openid.get("username_claim") or "").strip(),
            "name_claim": str(openid.get("name_claim") or "").strip(),
            "required_role": str(openid.get("required_role") or "").strip(),
            "required_role_parameter_path": str(openid.get("required_role_parameter_path") or "").strip(),
            "required_role_token_kind": str(openid.get("required_role_token_kind") or "").strip(),
            "admin_role": str(openid.get("admin_role") or "").strip(),
            "admin_role_parameter_path": str(openid.get("admin_role_parameter_path") or "").strip(),
            "admin_role_token_kind": str(openid.get("admin_role_token_kind") or "").strip(),
        },
    }


def telegram_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    telegram = integrations.get("telegram", {}) or {}
    return resolve_bool(telegram.get("enabled"), False)


def telegram_codex_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    telegram_codex = integrations.get("telegram_codex", {}) or {}
    return resolve_bool(telegram_codex.get("enabled"), False)


def build_agent_capabilities(code_interpreter_is_enabled: bool) -> list[str]:
    if code_interpreter_is_enabled:
        return list(CURATED_AGENT_CAPABILITIES)
    return [capability for capability in CURATED_AGENT_CAPABILITIES if capability != "execute_code"]


def render_runtime_env(config: dict[str, Any], assignments: dict[str, tuple[str, str]]) -> dict[str, str]:
    llm = config["llm"]
    voice = config.get("voice", {})
    tts_config = voice.get("tts", {}) or {}
    stt_config = voice.get("stt", {}) or {}
    if not isinstance(stt_config, dict):
        stt_config = {}
    integrations = config.get("integrations", {})
    runtime = config.get("runtime", {})
    network = runtime.get("network", {}) or {}
    prompt_workbench = runtime.get("prompt_workbench", config.get("prompt_workbench", {}) or {}) or {}
    agents = config.get("agents", {}) or {}
    resolved_voice = resolve_voice_settings(config)
    call_session_secret = nested_secret(runtime, "call_session_secret")
    runtime_profile, profile = resolve_runtime_profile(config)
    playground_variant = str(runtime.get("playground_variant", "modern") or "modern").strip().lower()
    if playground_variant not in {"modern", "classic"}:
        playground_variant = "modern"
    livekit_http_port = str(profile["livekit_http_port"])
    default_main_agent_id = str(
        agents.get("default_main_agent_id") or DEFAULT_MAIN_AGENT_ID
    ).strip() or DEFAULT_MAIN_AGENT_ID
    default_conversation_recall = conversation_recall_enabled(config)
    memory_hardening = resolve_memory_hardening_settings(config)
    memory_hardening_model = resolve_memory_hardening_model_tuple(config, memory_hardening)
    global_settings = config.get("settings", {}) if isinstance(config.get("settings"), dict) else {}
    default_timezone = str(
        global_settings.get("timezone")
        or memory_hardening.get("timezone")
        or DEFAULT_VIVENTIUM_TIMEZONE
    ).strip() or DEFAULT_VIVENTIUM_TIMEZONE
    retrieval_embeddings = resolve_retrieval_embeddings_settings(config)
    auth_settings = resolve_auth_settings(config)
    openid_settings = auth_settings["openid"]
    transcripts_source_dir = memory_hardening["transcripts"]["source_dir"]
    dev_env = runtime_dev_env_settings(config)
    shared_services = dev_env["shared_singleton_services"]
    shared_rag_api = "recall_rag" in shared_services
    shared_searxng = "searxng" in shared_services
    shared_firecrawl = "firecrawl" in shared_services
    shared_google_mcp = "google_workspace_mcp" in shared_services
    shared_ms365_mcp = "ms365_mcp" in shared_services
    start_rag_api = (
        "true"
        if (default_conversation_recall or transcripts_source_dir) and not shared_rag_api
        else "false"
    )
    code_interpreter_is_enabled = code_interpreter_enabled(config)
    web_search_settings = resolve_web_search_settings(config)
    web_search_is_enabled = web_search_settings["enabled"] == "true"
    start_searxng = (
        web_search_is_enabled
        and web_search_settings["search_provider"] == "searxng"
        and not shared_searxng
    )
    start_firecrawl = (
        web_search_is_enabled
        and web_search_settings["scraper_provider"] == "firecrawl"
        and not shared_firecrawl
    )
    telegram_is_enabled = telegram_enabled(config)
    glasshive_is_enabled = glasshive_enabled(config)
    glasshive_host_worker = resolve_glasshive_host_worker_settings(config)
    glasshive_enterprise = resolve_glasshive_enterprise_settings(config)
    feature_request_pr = config.get("feature_requests", {}).get("pr", {}) or {}
    feature_request_pr_after_approval = resolve_bool(
        feature_request_pr.get("create_after_user_approval"),
        True,
    )
    prompt_workbench_enabled = resolve_bool(prompt_workbench.get("enabled"), False)
    seed_nightly = prompt_workbench.get("seed_nightly", {}) if isinstance(prompt_workbench, dict) else {}
    if not isinstance(seed_nightly, dict):
        seed_nightly = {}
    seed_nightly_enabled = resolve_bool(seed_nightly.get("enabled"), prompt_workbench_enabled)
    seed_nightly_active = resolve_bool(seed_nightly.get("active"), prompt_workbench_enabled)
    seed_nightly_executor = str(seed_nightly.get("executor") or "glasshive_host").strip() or "glasshive_host"
    if seed_nightly_executor not in {"glasshive_host", "viventium_agent"}:
        raise SystemExit("runtime.prompt_workbench.seed_nightly.executor must be glasshive_host or viventium_agent")

    env: dict[str, str] = {
        "VIVENTIUM_CONFIG_VERSION": str(CONFIG_VERSION),
        "VIVENTIUM_INSTALL_MODE": config["install"]["mode"],
        "VIVENTIUM_RUNTIME_PROFILE": runtime_profile,
        "VIVENTIUM_PLAYGROUND_VARIANT": playground_variant,
        "PLAYGROUND_VARIANT": playground_variant,
        "VIVENTIUM_LOG_LEVEL": runtime.get("log_level", "info"),
        "VIVENTIUM_DEFAULT_TIMEZONE": default_timezone,
        "VIVENTIUM_USE_GENERATED_LIBRECHAT_YAML": "1",
        "VIVENTIUM_LC_API_PORT": str(profile["lc_api_port"]),
        "VIVENTIUM_LC_FRONTEND_PORT": str(profile["lc_frontend_port"]),
        "VIVENTIUM_PLAYGROUND_PORT": str(profile["playground_port"]),
        "VIVENTIUM_VOICE_GATEWAY_HEALTH_PORT": str(profile["voice_gateway_health_port"]),
        "VIVENTIUM_LOCAL_MONGO_PORT": str(profile["mongo_port"]),
        "VIVENTIUM_LOCAL_MONGO_DB": str(profile["mongo_db"]),
        "VIVENTIUM_LOCAL_MEILI_PORT": str(profile["meili_port"]),
        "VIVENTIUM_GOOGLE_MCP_PORT": str(profile["google_mcp_port"]),
        "VIVENTIUM_SCHEDULING_MCP_PORT": str(profile["scheduling_mcp_port"]),
        "VIVENTIUM_RAG_API_PORT": str(profile["rag_api_port"]),
        "VIVENTIUM_DEV_ENV_ENABLED": "true" if dev_env["enabled"] else "false",
        "VIVENTIUM_DEV_ENV_NAME": str(dev_env["name"]),
        "VIVENTIUM_PROMPT_WORKBENCH_ENABLED": "true"
        if prompt_workbench_enabled
        else "false",
        "START_PROMPT_WORKBENCH": "true" if prompt_workbench_enabled else "false",
        "VIVENTIUM_PROMPT_WORKBENCH_PORT": str(profile.get("prompt_workbench_port") or 8781),
        "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED": "true"
        if seed_nightly_enabled
        else "false",
        "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE": "true"
        if seed_nightly_active
        else "false",
        "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR": seed_nightly_executor,
        "VIVENTIUM_SHARED_SINGLETON_SERVICES": ",".join(sorted(shared_services)),
        "VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL": "true"
        if feature_request_pr_after_approval
        else "false",
        "VIVENTIUM_FEATURE_REQUEST_CREATE_PR_AFTER_USER_APPROVAL": "true"
        if feature_request_pr_after_approval
        else "false",
        "RAG_API_URL": f"http://localhost:{profile['rag_api_port']}"
        if (start_rag_api == "true" or (default_conversation_recall and shared_rag_api))
        else "",
        "VIVENTIUM_CODE_INTERPRETER_PORT": str(profile["code_interpreter_port"]),
        "VIVENTIUM_SKYVERN_API_PORT": str(profile["skyvern_api_port"]),
        "VIVENTIUM_SKYVERN_UI_PORT": str(profile["skyvern_ui_port"]),
        "VIVENTIUM_PLAYGROUND_URL": f"http://localhost:{profile['playground_port']}",
        "LIVEKIT_HTTP_PORT": livekit_http_port,
        "LIVEKIT_TCP_PORT": str(profile["livekit_tcp_port"]),
        "LIVEKIT_UDP_PORT": str(profile["livekit_udp_port"]),
        "LIVEKIT_API_KEY": "viventium-local",
        "LIVEKIT_API_SECRET": call_session_secret,
        "LIVEKIT_URL": f"ws://localhost:{livekit_http_port}",
        "LIVEKIT_API_HOST": f"http://localhost:{livekit_http_port}",
        "NEXT_PUBLIC_LIVEKIT_URL": f"ws://localhost:{livekit_http_port}",
        "SAFE_MODE": "1",
        "VIVENTIUM_ENABLE_SUBCONSCIOUS": "1",
        "VIVENTIUM_SUBCONSCIOUS_ENABLE": "all",
        "VIVENTIUM_PRIMARY_PROVIDER": llm["primary"]["provider"],
        "VIVENTIUM_PRIMARY_AUTH_MODE": llm["primary"]["auth_mode"],
        "VIVENTIUM_SECONDARY_PROVIDER": llm.get("secondary", {}).get("provider", "none"),
        "VIVENTIUM_SECONDARY_AUTH_MODE": llm.get("secondary", {}).get("auth_mode", "disabled"),
        "VIVENTIUM_ALLOW_RUNTIME_MODEL_OVERRIDES": "true"
        if has_model_overrides(config)
        else "false",
        "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        "VIVENTIUM_DEFAULT_CONVERSATION_RECALL": "true"
        if default_conversation_recall
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_ENABLED": "true"
        if memory_hardening["enabled"]
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": memory_hardening["schedule"],
        "VIVENTIUM_MEMORY_HARDENING_TIMEZONE": memory_hardening["timezone"],
        "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": memory_hardening["operator_user_email"],
        "VIVENTIUM_MEMORY_HARDENING_LOOKBACK_DAYS": str(memory_hardening["lookback_days"]),
        "VIVENTIUM_MEMORY_HARDENING_MIN_USER_IDLE_MINUTES": str(
            memory_hardening["min_user_idle_minutes"]
        ),
        "VIVENTIUM_MEMORY_HARDENING_MAX_CHANGES_PER_USER": str(
            memory_hardening["max_changes_per_user"]
        ),
        "VIVENTIUM_MEMORY_HARDENING_MAX_INPUT_CHARS": str(memory_hardening["max_input_chars"]),
        "VIVENTIUM_MEMORY_HARDENING_REQUIRE_FULL_LOOKBACK": "true"
        if memory_hardening["require_full_lookback"]
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "true"
        if memory_hardening["dry_run_first"]
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_MIN_APPLY_INTERVAL_SECONDS": str(
            memory_hardening["min_apply_interval_seconds"]
        ),
        "VIVENTIUM_MEMORY_HARDENING_PROVIDER_PROFILE": memory_hardening["provider_profile"],
        "VIVENTIUM_MEMORY_HARDENING_CONFIGURED_PROVIDER": memory_hardening["provider"],
        "VIVENTIUM_MEMORY_HARDENING_PROVIDER": memory_hardening_model["provider"],
        "VIVENTIUM_MEMORY_HARDENING_MODEL": memory_hardening_model["model"],
        "VIVENTIUM_MEMORY_HARDENING_EFFORT": memory_hardening_model["effort"],
        "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL": memory_hardening["anthropic_model"],
        "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT": memory_hardening["anthropic_effort"],
        "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL": memory_hardening["openai_model"],
        "VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT": memory_hardening[
            "openai_reasoning_effort"
        ],
        "VIVENTIUM_MEMORY_TRANSCRIPTS_DIR": transcripts_source_dir,
        "VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS": ",".join(
            memory_hardening["transcripts"]["ignore_globs"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_FILES_PER_RUN": str(
            memory_hardening["transcripts"]["max_files_per_run"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN": str(
            memory_hardening["transcripts"]["min_files_per_run"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION": str(
            memory_hardening["transcripts"]["max_batches_per_invocation"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_CHARS_PER_FILE": str(
            memory_hardening["transcripts"]["max_chars_per_file"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_SUMMARY_MAX_CHARS": str(
            memory_hardening["transcripts"]["summary_max_chars"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_REFERENCE_MEMORY_MAX_CHARS": str(
            memory_hardening["transcripts"]["reference_memory_max_chars"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_REFERENCE_MESSAGES_MAX_CHARS": str(
            memory_hardening["transcripts"]["reference_messages_max_chars"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_STABLE_EVIDENCE_MAX_AGE_DAYS": str(
            memory_hardening["transcripts"]["stable_evidence_max_age_days"]
        ),
        "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE": memory_hardening["transcripts"]["rag_mode"],
        "VIVENTIUM_BUILTIN_AGENT_PUBLIC_ROLE": "owner",
        "VIVENTIUM_TELEGRAM_BACKEND": "librechat",
        "VIVENTIUM_TELEGRAM_AGENT_ID": default_main_agent_id,
        "VIVENTIUM_MAIN_AGENT_ID": default_main_agent_id,
        "START_GOOGLE_MCP": "true" if integrations.get("google_workspace", {}).get("enabled") and not shared_google_mcp else "false",
        "START_MS365_MCP": "true" if integrations.get("ms365", {}).get("enabled") and not shared_ms365_mcp else "false",
        "VIVENTIUM_SHARED_GOOGLE_MCP": "true" if shared_google_mcp else "false",
        "VIVENTIUM_SHARED_MS365_MCP": "true" if shared_ms365_mcp else "false",
        "VIVENTIUM_SHARED_RAG_API": "true" if shared_rag_api else "false",
        "VIVENTIUM_SHARED_SEARXNG": "true" if shared_searxng else "false",
        "VIVENTIUM_SHARED_FIRECRAWL": "true" if shared_firecrawl else "false",
        "START_GLASSHIVE": "true" if glasshive_is_enabled else "false",
        "START_SCHEDULING_MCP": "true",
        "START_RAG_API": start_rag_api,
        "START_SKYVERN": "true" if integrations.get("skyvern", {}).get("enabled") else "false",
        "START_TELEGRAM": "true" if telegram_is_enabled else "false",
        "START_TELEGRAM_CODEX": "true" if telegram_codex_enabled(config) else "false",
        "START_CODE_INTERPRETER": "true" if code_interpreter_is_enabled else "false",
        "START_SEARXNG": "true" if start_searxng else "false",
        "START_FIRECRAWL": "true" if start_firecrawl else "false",
        "VIVENTIUM_WEB_SEARCH_ENABLED": "true" if web_search_is_enabled else "false",
        "VIVENTIUM_OPENCLAW_ENABLED": "true" if integrations.get("openclaw", {}).get("enabled") else "false",
        "ALLOW_EMAIL_LOGIN": "true" if auth_settings["allow_email_login"] else "false",
        "ALLOW_REGISTRATION": "true" if auth_settings["allow_registration"] else "false",
        "VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE": "true"
        if auth_settings["bootstrap_registration_once"]
        else "false",
        "ALLOW_PASSWORD_RESET": "true" if auth_settings["allow_password_reset"] else "false",
        "VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN": auth_settings[
            "connected_accounts_return_origin"
        ],
        "VIVENTIUM_PROMPT_FRAME_FILE_LOG": "0",
        "ALLOW_SOCIAL_LOGIN": "true" if openid_settings["enabled"] else "false",
        "ALLOW_SOCIAL_REGISTRATION": "false",
        "ALLOW_UNVERIFIED_EMAIL_LOGIN": "true",
        "VIVENTIUM_REGISTRATION_APPROVAL": "false",
        "VIVENTIUM_CALL_SESSION_SECRET": call_session_secret,
        "VIVENTIUM_TELEGRAM_SECRET": call_session_secret,
        "VIVENTIUM_SCHEDULER_SECRET": call_session_secret,
        "VIVENTIUM_LIBRECHAT_ORIGIN": f"http://127.0.0.1:{profile['lc_api_port']}",
        "SCHEDULING_MCP_URL": f"http://localhost:{profile['scheduling_mcp_port']}/mcp",
        "GLASSHIVE_MCP_URL": "http://127.0.0.1:8767/mcp",
        "GOOGLE_WORKSPACE_MCP_URL": f"http://localhost:{profile['google_mcp_port']}/mcp",
        "GOOGLE_WORKSPACE_MCP_AUTH_URL": f"http://localhost:{profile['google_mcp_port']}/authorize",
        "GOOGLE_WORKSPACE_MCP_TOKEN_URL": f"http://localhost:{profile['google_mcp_port']}/token",
        "GOOGLE_WORKSPACE_MCP_SCOPE": DEFAULT_GOOGLE_WORKSPACE_MCP_SCOPE,
        "MS365_MCP_SERVER_URL": "http://localhost:6274/mcp",
        "MS365_MCP_AUTH_URL": "http://localhost:6274/authorize",
        "MS365_MCP_TOKEN_URL": "http://localhost:6274/token",
        "MS365_MCP_SCOPE": DEFAULT_MS365_MCP_SCOPE,
        "EMBEDDINGS_PROVIDER": retrieval_embeddings["provider"],
        "EMBEDDINGS_MODEL": retrieval_embeddings["model"],
        "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER": retrieval_embeddings["provider"],
        "VIVENTIUM_RAG_EMBEDDINGS_MODEL": retrieval_embeddings["model"],
        "VIVENTIUM_RAG_EMBEDDINGS_PROFILE": retrieval_embeddings["profile"],
    }

    if openid_settings["enabled"]:
        required_openid = {
            "runtime.auth.openid.client_id": openid_settings["client_id"],
            "runtime.auth.openid.client_secret": openid_settings["client_secret"],
            "runtime.auth.openid.issuer": openid_settings["issuer"],
            "runtime.auth.openid.session_secret": openid_settings["session_secret"],
        }
        missing_openid = [label for label, value in required_openid.items() if not str(value or "").strip()]
        if missing_openid:
            raise SystemExit(
                "runtime.auth.openid.enabled requires "
                + ", ".join(missing_openid)
            )
        env.update(
            {
                "OPENID_CLIENT_ID": openid_settings["client_id"],
                "OPENID_CLIENT_SECRET": openid_settings["client_secret"],
                "OPENID_ISSUER": openid_settings["issuer"],
                "OPENID_SESSION_SECRET": openid_settings["session_secret"],
                "OPENID_SCOPE": openid_settings["scope"],
                "OPENID_CALLBACK_URL": openid_settings["callback_url"],
                "OPENID_BUTTON_LABEL": openid_settings["button_label"],
                "OPENID_IMAGE_URL": openid_settings["image_url"],
                "OPENID_AUTO_REDIRECT": "true" if openid_settings["auto_redirect"] else "false",
                "OPENID_USE_PKCE": "true" if openid_settings["use_pkce"] else "false",
                "OPENID_REUSE_TOKENS": "true" if openid_settings["reuse_tokens"] else "false",
            }
        )
        optional_openid_env = {
            "OPENID_EMAIL_CLAIM": openid_settings["email_claim"],
            "OPENID_USERNAME_CLAIM": openid_settings["username_claim"],
            "OPENID_NAME_CLAIM": openid_settings["name_claim"],
            "OPENID_REQUIRED_ROLE": openid_settings["required_role"],
            "OPENID_REQUIRED_ROLE_PARAMETER_PATH": openid_settings["required_role_parameter_path"],
            "OPENID_REQUIRED_ROLE_TOKEN_KIND": openid_settings["required_role_token_kind"],
            "OPENID_ADMIN_ROLE": openid_settings["admin_role"],
            "OPENID_ADMIN_ROLE_PARAMETER_PATH": openid_settings["admin_role_parameter_path"],
            "OPENID_ADMIN_ROLE_TOKEN_KIND": openid_settings["admin_role_token_kind"],
        }
        env.update({key: value for key, value in optional_openid_env.items() if value})

    activation_node = llm["activation"]
    activation_provider = normalize_provider_name(activation_node.get("provider"))
    activation_secret = current_background_activation_secret(config)
    if activation_provider == "groq" and activation_secret:
        env["GROQ_API_KEY"] = activation_secret
    elif activation_provider == "xai" and activation_secret:
        env["XAI_API_KEY"] = activation_secret

    if retrieval_embeddings["provider"] == "ollama":
        env["OLLAMA_BASE_URL"] = retrieval_embeddings["ollama_base_url"]

    if glasshive_is_enabled:
        glasshive_operator_base_url = str(
            glasshive_enterprise["operator_base_url"]
            if glasshive_enterprise["enabled"]
            else integrations.get("glasshive", {}).get("operator_base_url") or "http://127.0.0.1:8780"
        ).rstrip("/")
        if glasshive_enterprise["enabled"]:
            env["GLASSHIVE_MCP_URL"] = str(glasshive_enterprise["mcp_url"])
            mcp_port = explicit_url_port(str(glasshive_enterprise["mcp_url"]))
            if mcp_port:
                env["GLASSHIVE_MCP_PORT"] = mcp_port
            ui_port = explicit_url_port(glasshive_operator_base_url)
            if ui_port:
                env["GLASSHIVE_UI_PORT"] = ui_port
        env["GLASSHIVE_OPERATOR_BASE_URL"] = glasshive_operator_base_url
        env["GLASSHIVE_DEFAULT_LAUNCH_SURFACE"] = "desktop"
        env["GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP"] = "true"
        env["WPR_IDLE_DESKTOP_PRIME_BROWSER"] = "true"
        env["GLASSHIVE_HOST_WORKERS_ENABLED"] = "true" if glasshive_host_worker["enabled"] else "false"
        env["GLASSHIVE_DEFAULT_WORKER_PROFILE"] = str(glasshive_host_worker["default_worker_profile"])
        env["WPR_HOST_WORKSPACE_ROOT"] = str(glasshive_host_worker["workspace_root"])
        env["GLASSHIVE_DEFAULT_EXECUTION_MODE"] = str(glasshive_host_worker["default_execution_mode"])
        env["WPR_DEFAULT_EXECUTION_MODE"] = str(glasshive_host_worker["default_execution_mode"])
        env["WPR_HOST_DESTRUCTIVE_CONFIRMATION"] = "true" if glasshive_host_worker["destructive_confirmation_enabled"] else "false"
        env["WPR_HOST_ADVISORY_REVIEWER_ENABLED"] = "true" if glasshive_host_worker["advisory_reviewer_enabled"] else "false"
        env["WPR_HOST_ADVISORY_REVIEWER_MODE"] = str(glasshive_host_worker["advisory_reviewer_mode"])
        env["WPR_HOST_PROMPT_VISIBILITY"] = "true" if glasshive_host_worker["prompt_visibility_enabled"] else "false"
        env["WPR_HOST_MENTION_CODEX"] = str(glasshive_host_worker["mentions"]["codex"])
        env["WPR_HOST_MENTION_CLAUDE"] = str(glasshive_host_worker["mentions"]["claude"])
        env["WPR_HOST_MENTION_OPENCLAW"] = str(glasshive_host_worker["mentions"]["openclaw"])
        env["WPR_HOST_CODEX_CLI_AVAILABLE"] = "true" if glasshive_host_worker["codex_cli_available"] else "false"
        env["WPR_HOST_CLAUDE_CLI_AVAILABLE"] = "true" if glasshive_host_worker["claude_cli_available"] else "false"
        env["WPR_HOST_OPENCLAW_CLI_AVAILABLE"] = "true" if glasshive_host_worker["openclaw_cli_available"] else "false"
        if glasshive_host_worker["codex_cli_path"]:
            env["WPR_CODEX_BIN"] = str(glasshive_host_worker["codex_cli_path"])
        if glasshive_host_worker["claude_cli_path"]:
            env["WPR_CLAUDE_CODE_BIN"] = str(glasshive_host_worker["claude_cli_path"])
        if glasshive_host_worker["openclaw_cli_path"]:
            env["WPR_OPENCLAW_BIN"] = str(glasshive_host_worker["openclaw_cli_path"])
        if glasshive_host_worker["runtime_requirements_json"]:
            env["GLASSHIVE_HOST_RUNTIME_REQUIREMENTS_JSON"] = str(glasshive_host_worker["runtime_requirements_json"])
        if glasshive_host_worker["runtime_requirements_file"]:
            env["GLASSHIVE_HOST_RUNTIME_REQUIREMENTS_FILE"] = str(glasshive_host_worker["runtime_requirements_file"])
        if glasshive_host_worker["codex_native_mcp_allowlist"]:
            env["GLASSHIVE_HOST_CODEX_NATIVE_MCP_ALLOWLIST"] = str(glasshive_host_worker["codex_native_mcp_allowlist"])
        if glasshive_host_worker["codex_plugin_cache"]:
            env["GLASSHIVE_HOST_CODEX_PLUGIN_CACHE"] = str(glasshive_host_worker["codex_plugin_cache"])
        if glasshive_host_worker["codex_ignore_user_config"]:
            env["WPR_CODEX_CLI_IGNORE_USER_CONFIG"] = str(glasshive_host_worker["codex_ignore_user_config"])
        if glasshive_host_worker["codex_disable_features"]:
            env["WPR_CODEX_CLI_DISABLE_FEATURES"] = str(glasshive_host_worker["codex_disable_features"])
        if glasshive_host_worker["claude_enable_chrome"]:
            env["WPR_CLAUDE_CODE_ENABLE_CHROME"] = str(glasshive_host_worker["claude_enable_chrome"])
        if glasshive_host_worker["claude_effort"]:
            env["WPR_CLAUDE_CODE_EFFORT"] = str(glasshive_host_worker["claude_effort"])
        if not glasshive_enterprise["enabled"]:
            env["WPR_DB_PATH"] = str(
                APP_SUPPORT_VIVENTIUM_DIR
                / "state"
                / "runtime"
                / runtime_profile
                / "glasshive"
                / "runtime_phase1.db"
            )
        env["WPR_LIBRECHAT_UPLOADS_ROOT"] = str(LIBRECHAT_UPLOADS_DIR)
        env["WPR_BOOTSTRAP_SOURCE_ROOTS"] = str(LIBRECHAT_UPLOADS_DIR)
        env["VIVENTIUM_GLASSHIVE_CALLBACK_URL"] = f"http://localhost:{profile['lc_api_port']}/api/viventium/glasshive/callback"
        env["VIVENTIUM_GLASSHIVE_CALLBACK_SECRET"] = scoped_secret(call_session_secret, "glasshive-callback")
        env["VIVENTIUM_GLASSHIVE_CAPABILITY_BROKER_SECRET"] = scoped_secret(
            call_session_secret,
            "glasshive-capability-broker",
        )
        if glasshive_enterprise["enabled"]:
            enterprise_public_api_origin = str(network.get("public_api_origin", "") or "").strip()
            env["GLASSHIVE_ENTERPRISE_MODE"] = "true"
            env["GLASSHIVE_AUTH_MODE"] = str(glasshive_enterprise["auth_mode"])
            env["GLASSHIVE_ENTERPRISE_TENANT_ID"] = str(glasshive_enterprise["tenant_id"])
            env["GLASSHIVE_ARTIFACT_BASE_URL"] = str(glasshive_enterprise["artifact_base_url"])
            signed_link_secret = str(glasshive_enterprise["signed_link_secret"] or "").strip() or scoped_secret(
                call_session_secret,
                f"glasshive-signed-link:{glasshive_enterprise['tenant_id']}",
            )
            if glasshive_enterprise["service_token"] and signed_link_secret == glasshive_enterprise["service_token"]:
                raise SystemExit(
                    "integrations.glasshive.enterprise.signed_link_secret must differ from the service token"
                )
            env["GLASSHIVE_SIGNED_LINK_SECRET"] = signed_link_secret
            env["GLASSHIVE_PROJECT_PROVIDER_ENV"] = "true"
            env["GLASSHIVE_IDLE_TERMINATE_AFTER_S"] = str(glasshive_enterprise["idle_terminate_after_s"])
            env["GLASSHIVE_IDLE_REAPER_INTERVAL_S"] = str(glasshive_enterprise["idle_reaper_interval_s"])
            env["GLASSHIVE_WORKSPACE_LINK_AUTO_RESUME"] = (
                "true" if glasshive_enterprise["workspace_link_auto_resume"] else "false"
            )
            env["GLASSHIVE_MAX_ACTIVE_WORKERS_PER_USER"] = str(glasshive_enterprise["max_active_workers_per_user"])
            env["GLASSHIVE_MAX_ACTIVE_WORKERS_PER_TENANT"] = str(glasshive_enterprise["max_active_workers_per_tenant"])
            env["GLASSHIVE_MAX_WORKSPACES_PER_USER"] = str(glasshive_enterprise["max_workspaces_per_user"])
            env["GLASSHIVE_MAX_WORKSPACES_PER_TENANT"] = str(glasshive_enterprise["max_workspaces_per_tenant"])
            env["GLASSHIVE_ARTIFACT_DOWNLOAD_MAX_BYTES"] = str(glasshive_enterprise["artifact_download_max_bytes"])
            if glasshive_enterprise["owner_identity_claims"]:
                env["GLASSHIVE_OWNER_IDENTITY_CLAIMS"] = str(glasshive_enterprise["owner_identity_claims"])
            if glasshive_enterprise["owner_identity_aliases_json"]:
                env["GLASSHIVE_OWNER_IDENTITY_ALIASES_JSON"] = str(glasshive_enterprise["owner_identity_aliases_json"])
            if glasshive_enterprise["owner_identity_aliases_file"]:
                env["GLASSHIVE_OWNER_IDENTITY_ALIASES_FILE"] = str(glasshive_enterprise["owner_identity_aliases_file"])
            if env.get("OPENAI_BASE_URL"):
                env.setdefault("WPR_OPENCLAW_USE_CUSTOM_PROVIDER", "1")
                env.setdefault("WPR_OPENCLAW_WIRE_API", "openai-completions")
            env["WPR_LIBRECHAT_UPLOADS_ROOT"] = str(glasshive_enterprise["upload_root"])
            env["WPR_BOOTSTRAP_SOURCE_ROOTS"] = str(glasshive_enterprise["source_roots"])
            env["VIVENTIUM_GLASSHIVE_CALLBACK_URL"] = (
                f"{enterprise_public_api_origin.rstrip('/')}/api/viventium/glasshive/callback"
                if enterprise_public_api_origin
                else ""
            )
            if glasshive_enterprise["worker_env_allowlist"]:
                env["GLASSHIVE_WORKER_ENV_ALLOWLIST"] = str(glasshive_enterprise["worker_env_allowlist"])
            if glasshive_enterprise["service_token"]:
                env[str(glasshive_enterprise["service_token_env"])] = str(glasshive_enterprise["service_token"])
                env["WPR_API_TOKEN"] = str(glasshive_enterprise["service_token"])

    public_client_origin = str(network.get("public_client_origin", "") or "").strip()
    public_api_origin = str(network.get("public_api_origin", "") or "").strip()
    public_playground_origin = str(network.get("public_playground_origin", "") or "").strip()
    public_livekit_url = str(network.get("public_livekit_url", "") or "").strip()
    livekit_node_ip = str(network.get("livekit_node_ip", "") or "").strip()
    remote_call_mode = normalize_remote_call_mode(network)

    if remote_call_mode:
        env["VIVENTIUM_REMOTE_CALL_MODE"] = remote_call_mode
    if public_client_origin:
        env["VIVENTIUM_PUBLIC_CLIENT_URL"] = public_client_origin
        env["VIVENTIUM_TELEGRAM_LINK_BASE_URL"] = public_client_origin
        env["VIVENTIUM_GATEWAY_LINK_BASE_URL"] = public_client_origin
    if public_api_origin:
        env["VIVENTIUM_PUBLIC_SERVER_URL"] = public_api_origin
    if public_playground_origin:
        env["VIVENTIUM_PUBLIC_PLAYGROUND_URL"] = public_playground_origin
    if public_livekit_url:
        env["VIVENTIUM_PUBLIC_LIVEKIT_URL"] = public_livekit_url
    if livekit_node_ip:
        env["LIVEKIT_NODE_IP"] = livekit_node_ip

    primary = llm["primary"]
    secondary = llm.get("secondary", {})
    if primary["provider"] == "openai" and primary["auth_mode"] == "api_key":
        env["OPENAI_API_KEY"] = provider_secret(primary)
    if secondary.get("provider") == "openai" and secondary.get("auth_mode") == "api_key":
        env["OPENAI_API_KEY"] = provider_secret(secondary)
    if primary["provider"] == "anthropic" and primary["auth_mode"] == "api_key":
        env["ANTHROPIC_API_KEY"] = provider_secret(primary)
    if secondary.get("provider") == "anthropic" and secondary.get("auth_mode") == "api_key":
        env["ANTHROPIC_API_KEY"] = provider_secret(secondary)
    if primary["provider"] == "x_ai" and primary["auth_mode"] == "api_key":
        env["XAI_API_KEY"] = provider_secret(primary)
    if secondary.get("provider") == "x_ai" and secondary.get("auth_mode") == "api_key":
        env["XAI_API_KEY"] = provider_secret(secondary)

    if primary["provider"] == "openai" and primary["auth_mode"] == "connected_account":
        env["VIVENTIUM_OPENAI_AUTH_MODE"] = "connected_account"
    elif primary["provider"] == "openai":
        env["VIVENTIUM_OPENAI_AUTH_MODE"] = primary["auth_mode"]
    if primary["provider"] == "anthropic" and primary["auth_mode"] == "connected_account":
        env["VIVENTIUM_ANTHROPIC_AUTH_MODE"] = "connected_account"
    elif primary["provider"] == "anthropic":
        env["VIVENTIUM_ANTHROPIC_AUTH_MODE"] = primary["auth_mode"]
    if secondary.get("provider") == "openai" and secondary.get("auth_mode"):
        env.setdefault("VIVENTIUM_OPENAI_AUTH_MODE", secondary["auth_mode"])
    if secondary.get("provider") == "anthropic" and secondary.get("auth_mode"):
        env.setdefault("VIVENTIUM_ANTHROPIC_AUTH_MODE", secondary["auth_mode"])

    if telegram_is_enabled:
        env["BOT_TOKEN"] = validated_telegram_bot_token(
            integrations["telegram"],
            "integrations.telegram",
        )
        telegram_settings = integrations.get("telegram", {}) or {}
        telegram_stt_provider = normalize_telegram_stt_provider(
            telegram_settings.get("stt_provider", ""),
            "integrations.telegram.stt_provider",
        )
        if not telegram_stt_provider:
            # Telegram must stay in STT parity with the configured voice route by default.
            # Operators can override Telegram only through integrations.telegram.stt_provider;
            # the compiler must not silently remap local Whisper to a hosted provider.
            telegram_stt_provider = resolved_voice["stt_provider"]
        env["VIVENTIUM_TELEGRAM_STT_PROVIDER"] = telegram_stt_provider
        telegram_local_bot_api = telegram_settings.get("local_bot_api", {}) or {}
        telegram_local_bot_api_enabled = resolve_bool(
            telegram_local_bot_api.get("enabled"),
            False,
        )
        bot_api_origin = str(telegram_settings.get("bot_api_origin", "") or "").strip()
        bot_api_base_url = str(telegram_settings.get("bot_api_base_url", "") or "").strip()
        bot_api_base_file_url = str(
            telegram_settings.get("bot_api_base_file_url", "") or ""
        ).strip()
        if telegram_local_bot_api_enabled and (
            bot_api_origin or bot_api_base_url or bot_api_base_file_url
        ):
            raise SystemExit(
                "integrations.telegram.local_bot_api.enabled cannot be combined with "
                "integrations.telegram.bot_api_origin/bot_api_base_url/bot_api_base_file_url"
            )
        telegram_max_file_size = positive_int_or_default(
            telegram_settings.get("max_file_size_bytes"),
            104_857_600 if telegram_local_bot_api_enabled else 10_485_760,
            "integrations.telegram.max_file_size_bytes",
        )
        env["VIVENTIUM_TELEGRAM_MAX_FILE_SIZE"] = str(telegram_max_file_size)
        if telegram_local_bot_api_enabled:
            local_host = str(telegram_local_bot_api.get("host", "") or "").strip() or "127.0.0.1"
            local_port = positive_int_or_default(
                telegram_local_bot_api.get("port"),
                8084,
                "integrations.telegram.local_bot_api.port",
            )
            local_binary_path = str(
                telegram_local_bot_api.get("binary_path", "") or ""
            ).strip()
            local_api_id = resolve_secret(telegram_local_bot_api.get("api_id") or "")
            local_api_hash = resolve_secret(telegram_local_bot_api.get("api_hash") or "")
            env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED"] = "true"
            env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST"] = local_host
            env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT"] = str(local_port)
            env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID"] = local_api_id
            env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH"] = local_api_hash
            if local_binary_path:
                env["VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH"] = local_binary_path
            bot_api_origin = f"http://{local_host}:{local_port}"
        if bot_api_origin:
            env["VIVENTIUM_TELEGRAM_BOT_API_ORIGIN"] = bot_api_origin
        if bot_api_base_url:
            env["VIVENTIUM_TELEGRAM_BOT_API_BASE_URL"] = bot_api_base_url
        if bot_api_base_file_url:
            env["VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL"] = bot_api_base_file_url

    telegram_codex = integrations.get("telegram_codex", {}) or {}
    if telegram_codex_enabled(config):
        env["TELEGRAM_CODEX_BOT_TOKEN"] = validated_telegram_bot_token(
            telegram_codex,
            "integrations.telegram_codex",
        )
        bot_username = str(telegram_codex.get("bot_username", "") or "").strip().lstrip("@")
        if bot_username:
            env["TELEGRAM_CODEX_BOT_USERNAME"] = bot_username

    google_workspace = integrations.get("google_workspace", {}) or {}
    if google_workspace.get("enabled"):
        env["GOOGLE_CLIENT_ID"] = str(google_workspace.get("client_id", "")).strip()
        env["GOOGLE_CLIENT_SECRET"] = nested_secret(google_workspace, "client_secret")
        env["GOOGLE_REFRESH_TOKEN"] = nested_secret(google_workspace, "refresh_token")

    ms365 = integrations.get("ms365", {}) or {}
    if ms365.get("enabled"):
        env["MS365_MCP_CLIENT_ID"] = str(ms365.get("client_id", "")).strip()
        env["MS365_MCP_CLIENT_SECRET"] = nested_secret(ms365, "client_secret")
        env["MS365_MCP_TENANT_ID"] = str(ms365.get("tenant_id", "")).strip()
        env["MS365_BUSINESS_EMAIL"] = str(ms365.get("business_email", "")).strip()

    skyvern = integrations.get("skyvern", {}) or {}
    if skyvern.get("enabled"):
        env["SKYVERN_API_KEY"] = nested_secret(skyvern, "api_key")
        if skyvern.get("base_url"):
            env["SKYVERN_BASE_URL"] = str(skyvern.get("base_url", "")).strip()
        if skyvern.get("app_url"):
            env["SKYVERN_APP_URL"] = str(skyvern.get("app_url", "")).strip()

    configured_background_followup_window_s = runtime.get("background_followup_window_s")
    background_followup_window_s = (
        DEFAULT_BACKGROUND_FOLLOWUP_WINDOW_S
        if configured_background_followup_window_s in (None, "")
        else str(configured_background_followup_window_s).strip()
    )
    glasshive_followup_timeout_s = str(
        bounded_int_or_default(
            runtime.get("glasshive_followup_timeout_s"),
            int(DEFAULT_GLASSHIVE_FOLLOWUP_TIMEOUT_S),
            "runtime.glasshive_followup_timeout_s",
            minimum=MIN_GLASSHIVE_FOLLOWUP_TIMEOUT_S,
            maximum=MAX_GLASSHIVE_FOLLOWUP_TIMEOUT_S,
        )
    )
    env["VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S"] = background_followup_window_s
    env["VIVENTIUM_VOICE_FOLLOWUP_GRACE_S"] = background_followup_window_s
    env["VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S"] = background_followup_window_s
    env["VIVENTIUM_WEB_GLASSHIVE_TIMEOUT_S"] = glasshive_followup_timeout_s
    env["VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S"] = glasshive_followup_timeout_s
    env["VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S"] = glasshive_followup_timeout_s
    # Voice Phase A defaults are runtime outputs, not hand-maintained App Support edits. The default
    # keeps Phase A activation awareness in the main-response path, but releases early on the first
    # true voice activation instead of waiting for every detector.
    env["VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE"] = DEFAULT_CORTEX_PHASE_A_NOTICE_MODE
    # Background Activation Detection — two INDEPENDENT modes (voice, text). Each mode owns its own
    # async flag and its own detection time budget; neither flag affects the other mode. See
    # docs/requirements_and_learnings/02_Background_Agents.md.
    #   async OFF (default both modes): detection blocks up to the mode budget, early-exits the moment
    #     all activation results are in, then Phase A runs with that knowledge.
    #   async ON: the main answer and detection run in parallel; if a cortex activates within budget,
    #     the speculative answer is cancelled ("nevermind") and Phase A is re-run with cortex knowledge;
    #     otherwise the speculative answer stands. Phase B (non-blocked follow-up) is unchanged.
    # Budgets — owner decision 2026-05-30: text = 1300ms, voice = 690ms (Groq classifier ~0.6-1.3s, so
    # slow activations time out and surface via the follow-up turn). Voice async is ON (owner target):
    # the nevermind+redo orchestrator was verified live via text chat (shared agent-pipeline code, parity)
    # 2026-05-30 — clean commit-path stream + activation-path nevermind -> cortex-aware Phase A + cards.
    # Text async stays default OFF (token-cautious); flip the text flag to enable it.
    # Owner decision 2026-05-30: voice mode stays async even when a configured direct-action
    # tool-hold cortex is present. The main answer should not wait on classifier/tool-hold
    # bookkeeping; late or side-effecting work must surface through Phase B/follow-up evidence.
    env["VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC"] = "true"
    env["VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC"] = "false"
    env["VIVENTIUM_VOICE_PHASE_A_AWAIT_MS"] = "690"
    env["VIVENTIUM_TEXT_PHASE_A_AWAIT_MS"] = "1300"
    env["VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS"] = "2000"
    env["VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD"] = "true"
    env["VIVENTIUM_VOICE_LOG_LATENCY"] = "1"
    # Enable LibreChat structured/redacted/rotated debug logs (debug-YYYY-MM-DD.log). Without this,
    # winston (packages/data-schemas/src/config/winston.ts:58) only writes error-*.log and the per-day
    # debug file stays empty, leaving QA/RCA without the structured trace sink. Matches upstream
    # .env.example default DEBUG_LOGGING=true.
    env["DEBUG_LOGGING"] = "true"

    env["VIVENTIUM_FC_CONSCIOUS_LLM_PROVIDER"], env["VIVENTIUM_FC_CONSCIOUS_LLM_MODEL"] = assignments["conscious"]
    env["VIVENTIUM_CORTEX_BACKGROUND_ANALYSIS_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_BACKGROUND_ANALYSIS_LLM_MODEL"] = assignments["background_analysis"]
    env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_LLM_MODEL"] = assignments["confirmation_bias"]
    env["VIVENTIUM_CORTEX_RED_TEAM_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_RED_TEAM_LLM_MODEL"] = assignments["red_team"]
    env["VIVENTIUM_CORTEX_DEEP_RESEARCH_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_DEEP_RESEARCH_LLM_MODEL"] = assignments["deep_research"]
    env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_MODEL"] = assignments["productivity"]
    env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_LLM_MODEL"] = assignments["parietal"]
    env["VIVENTIUM_CORTEX_PATTERN_RECOGNITION_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_PATTERN_RECOGNITION_LLM_MODEL"] = assignments["pattern_recognition"]
    env["VIVENTIUM_CORTEX_EMOTIONAL_RESONANCE_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_EMOTIONAL_RESONANCE_LLM_MODEL"] = assignments["emotional_resonance"]
    env["VIVENTIUM_CORTEX_STRATEGIC_PLANNING_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_STRATEGIC_PLANNING_LLM_MODEL"] = assignments["strategic_planning"]
    env["VIVENTIUM_CORTEX_SUPPORT_LLM_PROVIDER"], env["VIVENTIUM_CORTEX_SUPPORT_LLM_MODEL"] = assignments["support"]
    env["OTUC_LLM_PROVIDER"], env["OTUC_LLM_MODEL"] = assignments["productivity"]
    activation_runtime_provider = (
        activation_provider
        if activation_provider in BACKGROUND_ACTIVATION_MODELS_BY_PROVIDER
        else CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    )
    activation_runtime_model = BACKGROUND_ACTIVATION_MODELS_BY_PROVIDER[activation_runtime_provider]
    env["VIVENTIUM_BACKGROUND_ACTIVATION_PROVIDER"] = activation_runtime_provider
    env["VIVENTIUM_BACKGROUND_ACTIVATION_MODEL"] = activation_runtime_model
    env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_ACTIVATION_LLM_PROVIDER"] = activation_runtime_provider
    env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_ACTIVATION_LLM_MODEL"] = activation_runtime_model
    env["VIVENTIUM_CORTEX_DEEP_RESEARCH_ACTIVATION_LLM_PROVIDER"] = activation_runtime_provider
    env["VIVENTIUM_CORTEX_DEEP_RESEARCH_ACTIVATION_LLM_MODEL"] = activation_runtime_model
    env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_ACTIVATION_LLM_PROVIDER"] = activation_runtime_provider
    env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_ACTIVATION_LLM_MODEL"] = activation_runtime_model
    env["OTUC_ACTIVATION_PROVIDER"] = activation_runtime_provider
    env["OTUC_ACTIVATION_LLM"] = activation_runtime_model

    voice_mode = resolved_voice["mode"]
    env["VIVENTIUM_VOICE_ENABLED"] = "true" if voice_mode != "disabled" else "false"
    env["VIVENTIUM_STT_PROVIDER"] = resolved_voice["stt_provider"]
    if resolved_voice.get("stt_model"):
        env["VIVENTIUM_STT_MODEL"] = resolved_voice["stt_model"]
    env["VIVENTIUM_TTS_PROVIDER"] = resolved_voice["tts_provider"]
    env["TTS_PROVIDER_PRIMARY"] = resolved_voice["tts_provider"]
    turn_handling = voice.get("turn_handling", {}) or {}
    if not isinstance(turn_handling, dict):
        turn_handling = {}
    voice_worker = voice.get("worker", {}) or {}
    if not isinstance(voice_worker, dict):
        voice_worker = {}
    configured_turn_detection = str(voice.get("turn_detection", "") or "").strip()
    if configured_turn_detection:
        env["VIVENTIUM_TURN_DETECTION"] = configured_turn_detection
    if turn_handling.get("min_interruption_duration_s") not in (None, ""):
        env["VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S"] = str(
            turn_handling.get("min_interruption_duration_s")
        ).strip()
    if turn_handling.get("min_interruption_words") not in (None, ""):
        env["VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS"] = str(
            turn_handling.get("min_interruption_words")
        ).strip()
    if turn_handling.get("min_endpointing_delay_s") not in (None, ""):
        env["VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S"] = str(
            turn_handling.get("min_endpointing_delay_s")
        ).strip()
    if turn_handling.get("max_endpointing_delay_s") not in (None, ""):
        env["VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S"] = str(
            turn_handling.get("max_endpointing_delay_s")
        ).strip()
    if turn_handling.get("false_interruption_timeout_s") not in (None, ""):
        env["VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S"] = str(
            turn_handling.get("false_interruption_timeout_s")
        ).strip()
    if "resume_false_interruption" in turn_handling:
        env["VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION"] = (
            "true" if resolve_bool(turn_handling.get("resume_false_interruption"), True) else "false"
        )
    if turn_handling.get("min_consecutive_speech_delay_s") not in (None, ""):
        env["VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S"] = str(
            turn_handling.get("min_consecutive_speech_delay_s")
        ).strip()
    if turn_handling.get("aec_warmup_duration_s") not in (None, ""):
        env["VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S"] = str(
            turn_handling.get("aec_warmup_duration_s")
        ).strip()
    if voice_worker.get("initialize_process_timeout_s") not in (None, ""):
        env["VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S"] = str(
            voice_worker.get("initialize_process_timeout_s")
        ).strip()
    if voice_worker.get("idle_processes") not in (None, ""):
        env["VIVENTIUM_VOICE_IDLE_PROCESSES"] = str(
            voice_worker.get("idle_processes")
        ).strip()
    if voice_worker.get("load_threshold") not in (None, ""):
        env["VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD"] = str(
            voice_worker.get("load_threshold")
        ).strip()
    if voice_worker.get("job_memory_warn_mb") not in (None, ""):
        env["VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB"] = str(
            voice_worker.get("job_memory_warn_mb")
        ).strip()
    if voice_worker.get("job_memory_limit_mb") not in (None, ""):
        env["VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB"] = str(
            voice_worker.get("job_memory_limit_mb")
        ).strip()
    if "prewarm_local_tts" in voice_worker:
        env["VIVENTIUM_VOICE_PREWARM_LOCAL_TTS"] = (
            "true" if resolve_bool(voice_worker.get("prewarm_local_tts"), True) else "false"
        )
    wing_mode = voice.get("wing_mode", voice.get("shadow_mode", {})) or {}
    wing_mode_default_enabled = "true" if wing_mode.get("default_enabled") is True else "false"
    env["VIVENTIUM_WING_MODE_DEFAULT_ENABLED"] = wing_mode_default_enabled
    env["VIVENTIUM_SHADOW_MODE_DEFAULT_ENABLED"] = wing_mode_default_enabled
    wing_mode_prompt = str(wing_mode.get("prompt", "") or "").strip()
    if wing_mode_prompt:
        env["VIVENTIUM_WING_MODE_PROMPT"] = wing_mode_prompt
        env["VIVENTIUM_SHADOW_MODE_PROMPT"] = wing_mode_prompt
    if resolved_voice["tts_provider_fallback"]:
        env["VIVENTIUM_TTS_PROVIDER_FALLBACK"] = resolved_voice["tts_provider_fallback"]
        env["TTS_PROVIDER_FALLBACK"] = resolved_voice["tts_provider_fallback"]
    else:
        env.pop("TTS_PROVIDER_FALLBACK", None)
    if "openai" in {resolved_voice["tts_provider"], resolved_voice["tts_provider_fallback"]}:
        env["VIVENTIUM_OPENAI_TTS_MODEL"] = DEFAULT_OPENAI_TTS_MODEL
        env["TTS_MODEL"] = DEFAULT_OPENAI_TTS_MODEL
        raw_openai_tts_voice = tts_config.get("voice", "")
        configured_openai_tts_voice = (
            raw_openai_tts_voice.strip() if isinstance(raw_openai_tts_voice, str) else ""
        )
        configured_openai_tts_speed = str(tts_config.get("speed", "") or "").strip()
        env["VIVENTIUM_OPENAI_TTS_VOICE"] = (
            configured_openai_tts_voice or DEFAULT_OPENAI_TTS_VOICE
        )
        if configured_openai_tts_speed:
            env["VIVENTIUM_OPENAI_TTS_SPEED"] = configured_openai_tts_speed
        else:
            env["VIVENTIUM_OPENAI_TTS_SPEED"] = DEFAULT_OPENAI_TTS_SPEED
        configured_openai_tts_instructions = str(tts_config.get("instructions", "") or "").strip()
        env["VIVENTIUM_OPENAI_TTS_INSTRUCTIONS"] = (
            configured_openai_tts_instructions or DEFAULT_OPENAI_TTS_INSTRUCTIONS
        )
    if "cartesia" in {resolved_voice["tts_provider"], resolved_voice["tts_provider_fallback"]}:
        cartesia_config = cartesia_tts_settings(tts_config)
        configured_model_id = str(
            cartesia_config.get("model_id") or cartesia_config.get("model") or ""
        ).strip()
        if configured_model_id and configured_model_id != DEFAULT_CARTESIA_MODEL_ID:
            raise SystemExit("Cartesia voice calls support only model_id 'sonic-3'")
        configured_api_version = str(cartesia_config.get("api_version", "") or "").strip()
        configured_sample_rate = str(cartesia_config.get("sample_rate", "") or "").strip()
        configured_speed = str(cartesia_config.get("speed", "") or "").strip()
        configured_volume = str(cartesia_config.get("volume", "") or "").strip()
        configured_emotion = str(cartesia_config.get("emotion", "") or "").strip()
        configured_language = str(cartesia_config.get("language", "") or "").strip()
        configured_max_buffer_delay_ms = str(
            cartesia_config.get("max_buffer_delay_ms", "") or ""
        ).strip()
        configured_segment_silence_ms = str(
            cartesia_config.get("segment_silence_ms", "") or ""
        ).strip()
        env["VIVENTIUM_CARTESIA_API_VERSION"] = (
            configured_api_version or DEFAULT_CARTESIA_API_VERSION
        )
        env["VIVENTIUM_CARTESIA_MODEL_ID"] = DEFAULT_CARTESIA_MODEL_ID
        env["VIVENTIUM_CARTESIA_VOICE_ID"] = cartesia_voice_id_from_settings(cartesia_config)
        env["VIVENTIUM_CARTESIA_SAMPLE_RATE"] = (
            configured_sample_rate or DEFAULT_CARTESIA_SAMPLE_RATE
        )
        env["VIVENTIUM_CARTESIA_SPEED"] = configured_speed or DEFAULT_CARTESIA_SPEED
        env["VIVENTIUM_CARTESIA_VOLUME"] = configured_volume or DEFAULT_CARTESIA_VOLUME
        env["VIVENTIUM_CARTESIA_EMOTION"] = configured_emotion or DEFAULT_CARTESIA_EMOTION
        env["VIVENTIUM_CARTESIA_LANGUAGE"] = configured_language or DEFAULT_CARTESIA_LANGUAGE
        env["VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS"] = (
            configured_max_buffer_delay_ms or DEFAULT_CARTESIA_MAX_BUFFER_DELAY_MS
        )
        env["VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS"] = (
            configured_segment_silence_ms or DEFAULT_CARTESIA_SEGMENT_SILENCE_MS
        )
    xai_voice_key = ""
    if "xai" in {resolved_voice["tts_provider"], resolved_voice["tts_provider_fallback"]}:
        xai_config = xai_tts_settings(tts_config)
        configured_tts_api = str(xai_config.get("tts_api", "") or "").strip().lower()
        if configured_tts_api and configured_tts_api not in {"tts", "voice_agent"}:
            raise SystemExit("xAI voice calls support tts_api values 'tts' or 'voice_agent'")
        configured_voice = str(
            xai_config.get("voice_id") or xai_config.get("voice") or ""
        ).strip()
        configured_language = str(xai_config.get("language", "") or "").strip()
        configured_sample_rate = str(xai_config.get("sample_rate", "") or "").strip()
        output_format = xai_config.get("output_format")
        if not isinstance(output_format, dict):
            output_format = {}
        configured_tts_codec = str(
            xai_config.get("codec") or output_format.get("codec") or ""
        ).strip()
        configured_tts_sample_rate = str(
            xai_config.get("tts_sample_rate")
            or xai_config.get("output_sample_rate")
            or output_format.get("sample_rate")
            or ""
        ).strip()
        configured_tts_bit_rate = str(
            xai_config.get("bit_rate") or output_format.get("bit_rate") or ""
        ).strip()
        configured_api_url = str(xai_config.get("api_url", "") or "").strip()
        configured_ws_url = str(xai_config.get("ws_url", "") or "").strip()
        configured_optimize_streaming_latency_raw = xai_config.get(
            "optimize_streaming_latency"
        )
        if configured_optimize_streaming_latency_raw in (None, ""):
            configured_optimize_streaming_latency_raw = xai_config.get(
                "streaming_latency_optimization"
            )
        if configured_optimize_streaming_latency_raw in (None, ""):
            configured_optimize_streaming_latency = (
                DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY
            )
        else:
            if isinstance(configured_optimize_streaming_latency_raw, bool):
                configured_optimize_streaming_latency_int = (
                    1 if configured_optimize_streaming_latency_raw else 0
                )
            else:
                try:
                    configured_optimize_streaming_latency_int = int(
                        float(str(configured_optimize_streaming_latency_raw).strip())
                    )
                except ValueError as exc:
                    raise SystemExit(
                        "xAI voice calls support optimize_streaming_latency values 0 or 1"
                    ) from exc
            if configured_optimize_streaming_latency_int not in {0, 1}:
                raise SystemExit(
                    "xAI voice calls support optimize_streaming_latency values 0 or 1"
                )
            configured_optimize_streaming_latency = str(
                configured_optimize_streaming_latency_int
            )
        env["VIVENTIUM_XAI_TTS_API"] = configured_tts_api or DEFAULT_XAI_TTS_API
        env["VIVENTIUM_XAI_TTS_API_URL"] = configured_api_url or DEFAULT_XAI_TTS_API_URL
        env["VIVENTIUM_XAI_TTS_WS_URL"] = configured_ws_url or DEFAULT_XAI_TTS_WS_URL
        env["VIVENTIUM_XAI_VOICE"] = configured_voice or DEFAULT_XAI_TTS_VOICE
        env["VIVENTIUM_XAI_LANGUAGE"] = configured_language or DEFAULT_XAI_TTS_LANGUAGE
        env["VIVENTIUM_XAI_SAMPLE_RATE"] = (
            configured_sample_rate or DEFAULT_XAI_TTS_SAMPLE_RATE
        )
        env["VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY"] = (
            configured_optimize_streaming_latency
        )
        env["VIVENTIUM_XAI_TTS_CODEC"] = configured_tts_codec or DEFAULT_XAI_TTS_CODEC
        env["VIVENTIUM_XAI_TTS_SAMPLE_RATE"] = (
            configured_tts_sample_rate
            or configured_sample_rate
            or DEFAULT_XAI_TTS_SAMPLE_RATE
        )
        env["VIVENTIUM_XAI_TTS_BIT_RATE"] = configured_tts_bit_rate or DEFAULT_XAI_TTS_BIT_RATE
    assemblyai_key = resolve_voice_provider_secret(voice, resolved_voice, "assemblyai")
    if assemblyai_key:
        env["ASSEMBLYAI_API_KEY"] = assemblyai_key
    # Engine selection: canonical `voice.stt.model` picks the AssemblyAI streaming model; default to
    # the proven Universal-3 Pro streaming engine. The worker re-normalizes unknown values, so this
    # stays a soft default rather than a hard validation gate.
    env["VIVENTIUM_ASSEMBLYAI_STT_MODEL"] = (
        DEFAULT_ASSEMBLYAI_STT_MODEL
        if stt_config.get("model") in (None, "")
        else str(stt_config.get("model")).strip()
    )
    env["VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD"] = (
        DEFAULT_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD
        if stt_config.get("end_of_turn_confidence_threshold") in (None, "")
        else str(stt_config.get("end_of_turn_confidence_threshold")).strip()
    )
    env["VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS"] = (
        DEFAULT_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS
        if stt_config.get("min_end_of_turn_silence_when_confident_ms") in (None, "")
        else str(stt_config.get("min_end_of_turn_silence_when_confident_ms")).strip()
    )
    env["VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS"] = (
        DEFAULT_ASSEMBLYAI_MAX_TURN_SILENCE_MS
        if stt_config.get("max_turn_silence_ms") in (None, "")
        else str(stt_config.get("max_turn_silence_ms")).strip()
    )
    if "format_turns" in stt_config:
        env["VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS"] = (
            "true" if resolve_bool(stt_config.get("format_turns"), False) else "false"
        )
    if stt_config.get("vad_min_speech_s") not in (None, ""):
        env["VIVENTIUM_STT_VAD_MIN_SPEECH"] = str(stt_config.get("vad_min_speech_s")).strip()
    if stt_config.get("vad_min_silence_s") not in (None, ""):
        env["VIVENTIUM_STT_VAD_MIN_SILENCE"] = str(stt_config.get("vad_min_silence_s")).strip()
    if stt_config.get("vad_activation_threshold") not in (None, ""):
        env["VIVENTIUM_STT_VAD_ACTIVATION"] = str(
            stt_config.get("vad_activation_threshold")
        ).strip()

    eleven_key = resolve_voice_provider_secret(voice, resolved_voice, "elevenlabs")
    if eleven_key:
        env["ELEVENLABS_API_KEY"] = eleven_key
        env["ELEVEN_API_KEY"] = eleven_key

    cartesia_key = resolve_voice_provider_secret(voice, resolved_voice, "cartesia")
    if cartesia_key:
        env["CARTESIA_API_KEY"] = cartesia_key

    voice_provider_keys = voice.get("provider_keys", {}) or {}
    has_xai_voice_provider_key = (
        isinstance(voice_provider_keys, dict)
        and any(alias in voice_provider_keys for alias in ("xai", "x_ai", "grok", "xai_grok_voice"))
    )
    if "xai" in {resolved_voice["tts_provider"], resolved_voice["tts_provider_fallback"]} or has_xai_voice_provider_key:
        xai_voice_key = resolve_voice_provider_secret(voice, resolved_voice, "xai")
        if xai_voice_key:
            env["VIVENTIUM_XAI_TTS_API_KEY"] = xai_voice_key

    for provider_name, secret_value in (llm.get("extra_provider_keys") or {}).items():
        resolved = resolve_secret(secret_value)
        if not resolved:
            continue
        if provider_name == "openai":
            env.setdefault("OPENAI_API_KEY", resolved)
        elif provider_name == "anthropic":
            env.setdefault("ANTHROPIC_API_KEY", resolved)
        elif provider_name in {"x_ai", "xai"}:
            env.setdefault("XAI_API_KEY", resolved)
        elif provider_name == "openrouter":
            env["OPENROUTER_API_KEY"] = resolved
        elif provider_name == "perplexity":
            env["PERPLEXITY_API_KEY"] = resolved
        elif provider_name == "google":
            env["GOOGLE_API_KEY"] = resolved
            env["GOOGLE_KEY"] = resolved
            env["VIVENTIUM_GOOGLE_PROVIDER_ENABLED"] = "true"
        elif provider_name == "cohere":
            env["COHERE_API_KEY"] = resolved

    for key, value in build_legacy_env_imports(config).items():
        env.setdefault(key, value)
    apply_provider_endpoint_env_aliases(env)
    if glasshive_enterprise["enabled"] and env.get("OPENAI_BASE_URL"):
        env.setdefault("WPR_OPENCLAW_USE_CUSTOM_PROVIDER", "1")
        env.setdefault("WPR_OPENCLAW_WIRE_API", "openai-completions")
    if glasshive_enterprise["enabled"] and env.get("ANTHROPIC_API_KEY"):
        env.setdefault("WPR_CLAUDE_CODE_USE_API_KEY", "1")
    if has_model_overrides(config):
        for key, models in runtime_model_lists(config, assignments).items():
            env.setdefault(key, ",".join(models))
        for key, value in worker_runtime_model_env(config).items():
            env.setdefault(key, value)

    if xai_voice_key:
        env.setdefault("XAI_API_KEY", xai_voice_key)

    if code_interpreter_is_enabled:
        env.setdefault("LIBRECHAT_CODE_BASEURL", f"http://localhost:{profile['code_interpreter_port']}")
        env.setdefault("LIBRECHAT_CODE_API_KEY", DEFAULT_LOCAL_CODE_INTERPRETER_API_KEY)
        env.setdefault("CODE_API_KEY", env["LIBRECHAT_CODE_API_KEY"])
    else:
        env.pop("LIBRECHAT_CODE_BASEURL", None)
        env.pop("LIBRECHAT_CODE_API_KEY", None)
        env.pop("CODE_API_KEY", None)
    if web_search_is_enabled and web_search_settings["search_provider"] == "searxng":
        env.setdefault("SEARXNG_INSTANCE_URL", f"http://localhost:{DEFAULT_LOCAL_SEARXNG_PORT}")
        env.setdefault("SEARXNG_BASE_URL", f"http://localhost:{DEFAULT_LOCAL_SEARXNG_PORT}/")
    else:
        env.pop("SEARXNG_INSTANCE_URL", None)
        env.pop("SEARXNG_BASE_URL", None)

    if web_search_is_enabled and web_search_settings["search_provider"] == "serper":
        serper_api_key = web_search_settings["serper_api_key"]
        if serper_api_key:
            env["SERPER_API_KEY"] = serper_api_key
    else:
        env.pop("SERPER_API_KEY", None)

    if web_search_is_enabled and web_search_settings["scraper_provider"] == "firecrawl":
        env.setdefault("FIRECRAWL_API_KEY", DEFAULT_LOCAL_FIRECRAWL_API_KEY)
        env.setdefault("FIRECRAWL_BASE_URL", f"http://localhost:{DEFAULT_LOCAL_FIRECRAWL_PORT}")
        env.setdefault("FIRECRAWL_API_URL", env["FIRECRAWL_BASE_URL"])
        env.setdefault("FIRECRAWL_VERSION", "v2")
    elif web_search_is_enabled and web_search_settings["scraper_provider"] == "firecrawl_api":
        firecrawl_api_key = web_search_settings["firecrawl_api_key"]
        if firecrawl_api_key:
            env["FIRECRAWL_API_KEY"] = firecrawl_api_key
        env["FIRECRAWL_API_URL"] = web_search_settings["firecrawl_api_url"]
        env["FIRECRAWL_VERSION"] = "v2"
        env.pop("FIRECRAWL_BASE_URL", None)
    else:
        env.pop("FIRECRAWL_API_KEY", None)
        env.pop("FIRECRAWL_BASE_URL", None)
        env.pop("FIRECRAWL_API_URL", None)
        env.pop("FIRECRAWL_VERSION", None)

    if env.get("GOOGLE_API_KEY") and not env.get("GOOGLE_KEY"):
        env["GOOGLE_KEY"] = env["GOOGLE_API_KEY"]
    if env.get("GOOGLE_KEY") and not env.get("GOOGLE_API_KEY"):
        env["GOOGLE_API_KEY"] = env["GOOGLE_KEY"]
    ensure_user_provided_endpoint_surfaces(env)

    return env


def dump_env(path: Path, env: dict[str, str]) -> None:
    lines = [f"{key}={shlex.quote(str(value))}" for key, value in sorted(env.items()) if value is not None]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def build_interface_config(
    default_main_agent_id: str,
    code_interpreter_is_enabled: bool,
    web_search_is_enabled: bool,
) -> dict[str, Any]:
    return {
        "customWelcome": "Welcome to Viventium",
        "endpointsMenu": True,
        "modelSelect": True,
        "parameters": True,
        "sidePanel": True,
        "presets": True,
        "runCode": code_interpreter_is_enabled,
        "prompts": {
            "use": True,
            "create": True,
            "share": False,
            "public": False,
        },
        "bookmarks": True,
        "multiConvo": True,
        "memories": True,
        "temporaryChat": True,
        "temporaryChatRetention": 24,
        "agents": {
            "use": True,
            "create": True,
            "share": False,
            "public": False,
        },
        "peoplePicker": {
            "users": False,
            "groups": False,
            "roles": False,
        },
        "marketplace": {
            "use": False,
        },
        "fileCitations": True,
        "webSearch": web_search_is_enabled,
        "fileSearch": True,
        "defaultAgent": default_main_agent_id,
        "remoteAgents": {
            "use": False,
            "create": False,
            "share": False,
            "public": False,
        },
        "mcpServers": {
            "placeholder": "Integrations",
            "use": True,
            "create": True,
            "share": False,
            "public": False,
            "trustCheckbox": {
                "label": {"en": "I understand and want to continue"},
                "subLabel": {
                    "en": (
                        "Only connect MCP servers you trust. Unreviewed servers can expose "
                        "data or trigger unintended actions."
                    )
                },
            },
        },
    }


def build_mcp_servers(
    config: dict[str, Any],
    profile: dict[str, int],
    default_main_agent_id: str,
) -> dict[str, Any]:
    integrations = config.get("integrations", {}) or {}
    lc_api_port = profile["lc_api_port"]
    servers: dict[str, Any] = {
        "sequential-thinking": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "timeout": 300000,
            "chatMenu": True,
        },
        "scheduling-cortex": {
            "type": "streamable-http",
            "url": "${SCHEDULING_MCP_URL}",
            "headers": {
                "X-Viventium-User-Id": "{{LIBRECHAT_USER_ID}}",
                "X-Viventium-Agent-Id": default_main_agent_id,
            },
            "startup": False,
            "chatMenu": True,
            "timeout": 120000,
            "serverInstructions": True,
            "viventiumTrustedServerInstructions": True,
        },
    }

    if glasshive_enabled(config):
        glasshive_enterprise = resolve_glasshive_enterprise_settings(config)
        glasshive_headers = {
            "X-Viventium-User-Id": "{{LIBRECHAT_USER_ID}}",
            "X-Viventium-Agent-Id": default_main_agent_id,
            "X-Viventium-Conversation-Id": "{{LIBRECHAT_BODY_CONVERSATIONID}}",
            "X-Viventium-Parent-Message-Id": "{{LIBRECHAT_BODY_PARENTMESSAGEID}}",
            "X-Viventium-Message-Id": "{{LIBRECHAT_BODY_MESSAGEID}}",
            "X-Viventium-Surface": "{{LIBRECHAT_BODY_VIVENTIUMSURFACE}}",
            "X-Viventium-Input-Mode": "{{LIBRECHAT_BODY_VIVENTIUMINPUTMODE}}",
            "X-Viventium-Stream-Id": "{{LIBRECHAT_BODY_VIVENTIUMSTREAMID}}",
            "X-Viventium-Voice-Call-Session-Id": "{{LIBRECHAT_BODY_VIVENTIUMVOICECALLSESSIONID}}",
            "X-Viventium-Voice-Request-Id": "{{LIBRECHAT_BODY_VIVENTIUMVOICEREQUESTID}}",
            "X-Viventium-Telegram-Chat-Id": "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMCHATID}}",
            "X-Viventium-Telegram-User-Id": "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMUSERID}}",
            "X-Viventium-Telegram-Message-Id": "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMMESSAGEID}}",
            "X-Viventium-Request-Files": "{{LIBRECHAT_BODY_FILES_JSON_B64}}",
            "X-Viventium-Request-Attachments": "{{LIBRECHAT_BODY_ATTACHMENTS_JSON_B64}}",
            "X-Viventium-Tool-Resources": "{{LIBRECHAT_BODY_TOOL_RESOURCES_JSON_B64}}",
            "X-Viventium-File-Ids": "{{LIBRECHAT_BODY_FILE_IDS_JSON_B64}}",
        }
        if glasshive_enterprise["enabled"]:
            glasshive_headers["X-Viventium-Tenant-Id"] = str(glasshive_enterprise["tenant_id"])
            glasshive_headers["X-Viventium-User-Email"] = "{{LIBRECHAT_USER_EMAIL}}"
            glasshive_headers["X-Viventium-User-Role"] = "{{LIBRECHAT_USER_ROLE}}"
            if glasshive_enterprise["service_token_delivery"] == "client_header":
                glasshive_headers["X-WPR-Token"] = "${" + str(glasshive_enterprise["service_token_env"]) + "}"
        glasshive_server = {
            "type": "streamable-http",
            "url": "${GLASSHIVE_MCP_URL}",
            "viventiumRequestContext": True,
            "headers": glasshive_headers,
            "startup": False,
            "chatMenu": True,
            "timeout": DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_MS,
            "serverInstructions": True,
            "viventiumTrustedServerInstructions": True,
        }
        if glasshive_enterprise["enabled"] and glasshive_enterprise["oauth_enabled"]:
            oauth = glasshive_enterprise["oauth"]
            public_api_origin = str(((config.get("runtime") or {}).get("network") or {}).get("public_api_origin") or "").rstrip("/")
            default_redirect_uri = (
                f"{public_api_origin}/api/mcp/glasshive-workers-projects/oauth/callback"
                if public_api_origin
                else "${VIVENTIUM_PUBLIC_SERVER_URL}/api/mcp/glasshive-workers-projects/oauth/callback"
            )
            glasshive_server["requiresOAuth"] = True
            glasshive_server["oauth"] = {
                "authorization_url": str(oauth.get("authorization_url") or "${GLASSHIVE_OAUTH_AUTHORIZATION_URL}"),
                "token_url": str(oauth.get("token_url") or "${GLASSHIVE_OAUTH_TOKEN_URL}"),
                "redirect_uri": str(oauth.get("redirect_uri") or default_redirect_uri),
                "client_id": str(oauth.get("client_id") or "${GLASSHIVE_OAUTH_CLIENT_ID}"),
                "client_secret": str(oauth.get("client_secret") or "${GLASSHIVE_OAUTH_CLIENT_SECRET}"),
                "scope": str(oauth.get("scope") or "openid profile email offline_access"),
            }
        servers["glasshive-workers-projects"] = glasshive_server

    if integrations.get("ms365", {}).get("enabled"):
        servers["ms-365"] = {
            "type": "streamable-http",
            "url": "${MS365_MCP_SERVER_URL}",
            "startup": False,
            "chatMenu": True,
            "timeout": 120000,
            "requiresOAuth": True,
            "oauth": {
                "authorization_url": "${MS365_MCP_AUTH_URL}",
                "token_url": "${MS365_MCP_TOKEN_URL}",
                "redirect_uri": f"http://localhost:{lc_api_port}/api/mcp/ms-365/oauth/callback",
                "client_id": "${MS365_MCP_CLIENT_ID}",
                "client_secret": "${MS365_MCP_CLIENT_SECRET}",
                "scope": "${MS365_MCP_SCOPE}",
            },
            "serverInstructions": source_prompt_text(
                "mcp.ms365.server",
                (
                    "Microsoft 365 owns authenticated Outlook mail, calendar, OneDrive files, "
                    "Excel ranges, search, Teams/contacts/tasks/notes where exposed by tool schemas, "
                    "and verified Microsoft productivity facts. Use it when the user asks about "
                    "Outlook, Microsoft calendar, OneDrive, Excel, Microsoft search, or a general "
                    "productivity check where the available evidence may live in MS365. Do not use it "
                    "for Google Workspace, web/news/weather facts, local files, or schedule/reminder "
                    "management owned by another MCP. Inputs come from the user request, current "
                    "conversation, current date/time/timezone, authenticated LibreChat user, and the "
                    "tool schemas; do not assume another account or tenant. Default to read-only "
                    "inspection for mail, calendar, files, and search. Send, delete, move, invite, "
                    "edit, or otherwise mutate only when the user explicitly asks, the tool supports "
                    "the mutation, and impact is clear; draft or summarize when confirmation is "
                    "needed. Return concise user-facing verified results, not API fields, OAuth "
                    "details, server names, or plumbing. If auth is missing/expired, scope is "
                    "insufficient, rate limits hit, an item is not found, or a tool errors, report the "
                    "specific limitation plainly and do not fabricate. Prevent duplicates by "
                    "checking/listing/searching existing items and using structured IDs/metadata when "
                    "available before creating or updating. Prefer exact tool outputs over memory. Do "
                    "not branch on prompt text, display names, provider labels, or user identity; use "
                    "declared capabilities, structured fields, IDs, timestamps, and tool evidence."
                ),
            ),
        }

    if integrations.get("google_workspace", {}).get("enabled"):
        servers["google_workspace"] = {
            "type": "streamable-http",
            "url": "${GOOGLE_WORKSPACE_MCP_URL}",
            "startup": False,
            "chatMenu": True,
            "timeout": 120000,
            "requiresOAuth": True,
            "oauth": {
                "authorization_url": "${GOOGLE_WORKSPACE_MCP_AUTH_URL}",
                "token_url": "${GOOGLE_WORKSPACE_MCP_TOKEN_URL}",
                "redirect_uri": (
                    f"http://localhost:{lc_api_port}/api/mcp/google_workspace/oauth/callback"
                ),
                "scope": "${GOOGLE_WORKSPACE_MCP_SCOPE}",
            },
            "serverInstructions": source_prompt_text(
                "mcp.google_workspace.server",
                (
                    "Google Workspace owns authenticated Gmail, Google Calendar, Drive, Docs, Sheets, "
                    "Slides, Tasks, Forms, Chat where exposed by tool schemas, and verified Google "
                    "productivity facts. Use it when the user asks about Gmail, Google Calendar, "
                    "Drive, Docs, Sheets, Slides, or a general productivity check where the available "
                    "evidence may live in Google Workspace. Do not use it for Microsoft 365, "
                    "web/news/weather facts, local files, or schedule/reminder management owned by "
                    "another MCP. Inputs come from the user request, current conversation, current "
                    "date/time/timezone, authenticated LibreChat user, and the tool schemas; do not "
                    "assume another Google account or workspace. Default to read-only inspection for "
                    "mail, calendar, files, docs, sheets, slides, and search. Send, delete, share, "
                    "invite, edit, or otherwise mutate only when the user explicitly asks, the tool "
                    "supports the mutation, and impact is clear; draft or summarize when confirmation "
                    "is needed. Return concise user-facing verified results, not API fields, OAuth "
                    "details, server names, or plumbing. If auth is missing/expired, scope is "
                    "insufficient, rate limits hit, an item is not found, or a tool errors, report the "
                    "specific limitation plainly and do not fabricate. Prevent duplicates by "
                    "checking/listing/searching existing items and using structured IDs/metadata when "
                    "available before creating or updating. Prefer exact tool outputs over memory. Do "
                    "not branch on prompt text, display names, provider labels, or user identity; use "
                    "declared capabilities, structured fields, IDs, timestamps, and tool evidence."
                ),
            ),
        }

    return servers


def build_mcp_allowed_domains(config: dict[str, Any]) -> list[str]:
    allowed: list[str] = list(LOCAL_MCP_ALLOWED_DOMAINS)

    def add_url_host(value: object) -> None:
        text = str(value or "").strip()
        if not text or text.startswith("${"):
            return
        parsed = urlparse(text)
        host = parsed.hostname or ""
        if host and host not in allowed:
            allowed.append(host)

    if glasshive_enabled(config):
        glasshive_enterprise = resolve_glasshive_enterprise_settings(config)
        add_url_host(glasshive_enterprise["mcp_url"])
        add_url_host(glasshive_enterprise["operator_base_url"])
        add_url_host(glasshive_enterprise["artifact_base_url"])
    return allowed


def render_librechat_yaml(
    config: dict[str, Any],
    assignments: dict[str, tuple[str, str]],
    env: dict[str, str],
) -> str:
    llm = config["llm"]
    agents = config.get("agents", {}) or {}
    _, profile = resolve_runtime_profile(config)
    default_main_agent_id = str(
        agents.get("default_main_agent_id") or DEFAULT_MAIN_AGENT_ID
    ).strip() or DEFAULT_MAIN_AGENT_ID
    code_interpreter_is_enabled = code_interpreter_enabled(config)
    web_search_settings = resolve_web_search_settings(config)
    web_search_is_enabled = web_search_settings["enabled"] == "true"
    auth_settings = resolve_auth_settings(config)
    social_logins = ["openid"] if auth_settings["openid"]["enabled"] else []
    generated = {
        "version": LIBRECHAT_YAML_VERSION,
        "cache": True,
        "registration": {"socialLogins": social_logins},
        "interface": build_interface_config(
            default_main_agent_id,
            code_interpreter_is_enabled,
            web_search_is_enabled,
        ),
        "modelSpecs": build_model_specs(default_main_agent_id),
        "viventium": {
            "configVersion": CONFIG_VERSION,
            "primaryProvider": llm["primary"]["provider"],
            "installMode": config["install"]["mode"],
            "consciousAgent": {
                "provider": assignments["conscious"][0],
                "model": assignments["conscious"][1],
            },
        },
        "mcpSettings": {
            "allowedDomains": build_mcp_allowed_domains(config),
        },
        "mcpServers": build_mcp_servers(config, profile, default_main_agent_id),
        "endpoints": {
            "agents": {
                "disableBuilder": False,
                "capabilities": build_agent_capabilities(code_interpreter_is_enabled),
                "defaultId": default_main_agent_id,
                "recursionLimit": DEFAULT_AGENT_RECURSION_LIMIT,
                "maxRecursionLimit": DEFAULT_AGENT_RECURSION_LIMIT,
            },
            "custom": build_custom_endpoints(),
        },
    }
    source_template = load_source_of_truth_librechat_yaml()
    payload = copy.deepcopy(source_template) if source_template else {}

    payload["version"] = LIBRECHAT_YAML_VERSION
    payload["cache"] = True
    payload["registration"] = generated["registration"]
    payload["interface"] = deep_merge_dicts(
        payload.get("interface", {}) if isinstance(payload.get("interface"), dict) else {},
        generated["interface"],
    )
    payload["modelSpecs"] = merge_model_specs(
        payload.get("modelSpecs", {}) if isinstance(payload.get("modelSpecs"), dict) else {},
        generated["modelSpecs"],
        default_main_agent_id,
    )
    payload["viventium"] = deep_merge_dicts(
        payload.get("viventium", {}) if isinstance(payload.get("viventium"), dict) else {},
        generated["viventium"],
    )
    payload["mcpSettings"] = deep_merge_dicts(
        payload.get("mcpSettings", {}) if isinstance(payload.get("mcpSettings"), dict) else {},
        generated["mcpSettings"],
    )
    payload["mcpServers"] = deep_merge_dicts(
        payload.get("mcpServers", {}) if isinstance(payload.get("mcpServers"), dict) else {},
        generated["mcpServers"],
    )
    if web_search_is_enabled:
        web_search_payload: dict[str, Any] = {
            "safeSearch": 1,
            "scraperTimeout": 7500,
        }
        if web_search_settings["search_provider"] == "serper":
            web_search_payload["searchProvider"] = "serper"
            web_search_payload["serperApiKey"] = "${SERPER_API_KEY}"
        else:
            web_search_payload["searchProvider"] = "searxng"
            web_search_payload["searxngInstanceUrl"] = "${SEARXNG_INSTANCE_URL}"
        if web_search_settings["scraper_provider"] in {"firecrawl", "firecrawl_api"}:
            web_search_payload["scraperProvider"] = "firecrawl"
            web_search_payload["firecrawlApiKey"] = "${FIRECRAWL_API_KEY}"
            web_search_payload["firecrawlApiUrl"] = "${FIRECRAWL_API_URL}"
            web_search_payload["firecrawlVersion"] = "${FIRECRAWL_VERSION}"
        payload["webSearch"] = deep_merge_dicts(
            payload.get("webSearch", {}) if isinstance(payload.get("webSearch"), dict) else {},
            web_search_payload,
        )
        if isinstance(payload["webSearch"], dict):
            payload["webSearch"].pop("scraperType", None)
    else:
        payload.pop("webSearch", None)

    endpoints = (
        copy.deepcopy(payload.get("endpoints"))
        if isinstance(payload.get("endpoints"), dict)
        else {}
    )
    endpoints["agents"] = deep_merge_dicts(
        endpoints.get("agents", {}) if isinstance(endpoints.get("agents"), dict) else {},
        generated["endpoints"]["agents"],
    )
    existing_custom = endpoints.get("custom")
    generated_custom = generated["endpoints"]["custom"]
    if isinstance(existing_custom, list):
        endpoints["custom"] = merge_named_dict_list(existing_custom, generated_custom)
    else:
        endpoints["custom"] = copy.deepcopy(generated_custom)
    payload["endpoints"] = endpoints
    apply_memory_assignment(payload, assignments)
    normalize_anthropic_title_endpoint(payload)
    payload = prune_unavailable_source_defaults(payload, env)
    return yaml.safe_dump(payload, sort_keys=False)


def render_service_envs(output_dir: Path, env: dict[str, str]) -> None:
    service_dir = output_dir / "service-env"
    service_dir.mkdir(parents=True, exist_ok=True)

    librechat_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "XAI_API_KEY",
        "GROQ_API_KEY",
        "MONGO_URI",
        "ALLOW_EMAIL_LOGIN",
        "ALLOW_REGISTRATION",
        "ALLOW_SOCIAL_LOGIN",
        "DEBUG_LOGGING",
        "RAG_API_URL",
        "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL",
        "VIVENTIUM_MEMORY_HARDENING_MIN_APPLY_INTERVAL_SECONDS",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_DIR",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_FILES_PER_RUN",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_CHARS_PER_FILE",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_SUMMARY_MAX_CHARS",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_STABLE_EVIDENCE_MAX_AGE_DAYS",
        "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE",
        "VIVENTIUM_FC_CONSCIOUS_LLM_PROVIDER",
        "VIVENTIUM_FC_CONSCIOUS_LLM_MODEL",
        "VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE",
        "VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC",
        "VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC",
        "VIVENTIUM_VOICE_PHASE_A_AWAIT_MS",
        "VIVENTIUM_TEXT_PHASE_A_AWAIT_MS",
        "VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS",
        "VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD",
        "VIVENTIUM_VOICE_LOG_LATENCY",
        "OPENID_CLIENT_ID",
        "OPENID_CLIENT_SECRET",
        "OPENID_ISSUER",
        "OPENID_SESSION_SECRET",
        "OPENID_SCOPE",
        "OPENID_CALLBACK_URL",
        "OPENID_REQUIRED_ROLE",
        "OPENID_REQUIRED_ROLE_TOKEN_KIND",
        "OPENID_REQUIRED_ROLE_PARAMETER_PATH",
        "OPENID_ADMIN_ROLE",
        "OPENID_ADMIN_ROLE_PARAMETER_PATH",
        "OPENID_ADMIN_ROLE_TOKEN_KIND",
        "OPENID_USERNAME_CLAIM",
        "OPENID_NAME_CLAIM",
        "OPENID_EMAIL_CLAIM",
        "OPENID_BUTTON_LABEL",
        "OPENID_IMAGE_URL",
        "OPENID_AUTO_REDIRECT",
        "OPENID_USE_PKCE",
        "OPENID_REUSE_TOKENS",
    ]
    telegram_keys = [
        "BOT_TOKEN",
        "VIVENTIUM_TELEGRAM_BACKEND",
        "VIVENTIUM_TELEGRAM_AGENT_ID",
        "VIVENTIUM_LIBRECHAT_ORIGIN",
        "VIVENTIUM_TELEGRAM_SECRET",
        "VIVENTIUM_CALL_SESSION_SECRET",
        "VIVENTIUM_TELEGRAM_STT_PROVIDER",
        "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE",
        "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN",
        "VIVENTIUM_TELEGRAM_BOT_API_BASE_URL",
        "VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_BINARY_PATH",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID",
        "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH",
        "XAI_API_KEY",
        "VIVENTIUM_XAI_TTS_API_KEY",
        "VIVENTIUM_XAI_TTS_API_URL",
        "VIVENTIUM_XAI_VOICE",
        "VIVENTIUM_XAI_LANGUAGE",
        "VIVENTIUM_XAI_SAMPLE_RATE",
        "VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY",
        "VIVENTIUM_XAI_TTS_CODEC",
        "VIVENTIUM_XAI_TTS_SAMPLE_RATE",
        "VIVENTIUM_XAI_TTS_BIT_RATE",
    ]
    telegram_codex_keys = ["TELEGRAM_CODEX_BOT_TOKEN", "TELEGRAM_CODEX_BOT_USERNAME"]
    skyvern_keys = ["START_SKYVERN"]

    dump_env(service_dir / "librechat.env", {key: env.get(key, "") for key in librechat_keys})
    dump_env(service_dir / "telegram.config.env", {key: env.get(key, "") for key in telegram_keys})
    dump_env(service_dir / "telegram-codex.env", {key: env.get(key, "") for key in telegram_codex_keys})
    dump_env(service_dir / "skyvern.env", {key: env.get(key, "") for key in skyvern_keys})


def _telegram_codex_default_model_name() -> str:
    machine = platform.machine().lower()
    if machine == "x86_64":
        return "small"
    return "large-v3-turbo"


def _telegram_codex_default_threads() -> int:
    machine = platform.machine().lower()
    if machine == "x86_64":
        return 2
    return 8


def render_telegram_codex_settings(config: dict[str, Any], output_dir: Path) -> str:
    runtime_profile, _profile = resolve_runtime_profile(config)
    integrations = config.get("integrations", {}) or {}
    telegram_codex = integrations.get("telegram_codex", {}) or {}
    app_support_dir = output_dir.parent
    state_root = app_support_dir / "state" / "runtime" / runtime_profile / "telegram-codex"
    stable_pairing_root = app_support_dir / "state" / "telegram-codex" / "paired-users"

    payload = {
        "bot": {
            "env_file": str(output_dir / "service-env" / "telegram-codex.env"),
            "private_chat_only": resolve_bool(telegram_codex.get("private_chat_only"), True),
        },
        "pairing": {
            "host": "127.0.0.1",
            "port": 8765,
            "link_ttl_minutes": 15,
            "bootstrap_if_empty": True,
        },
        "codex": {
            "command": "codex",
            "model": "gpt-5.4",
            "sandbox": "workspace-write",
            "approval_policy": "never",
            "skip_git_repo_check": False,
        },
        "transcription": {
            "whisper_mode": "pywhispercpp",
            "language": "en",
            "model_name": _telegram_codex_default_model_name(),
            "model_path": "",
            "threads": _telegram_codex_default_threads(),
        },
        "runtime": {
            "logs_dir": str(state_root / "logs"),
            "sessions_path": str(state_root / "state" / "chat_sessions.json"),
            "pending_pairs_path": str(state_root / "state" / "pair_tokens.json"),
            "stable_pairing_root": str(stable_pairing_root),
            "legacy_paired_users_path": str(state_root / "state" / "paired_users.json"),
        },
        "projects": {
            "registry_file": str(output_dir / "telegram-codex" / "projects.yaml"),
        },
    }
    return yaml.safe_dump(payload, sort_keys=False)


def render_telegram_codex_projects() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    telegram_codex_dir = repo_root / "viventium_v0_4" / "telegram-codex"
    payload = {
        "default_project": "viventium_core",
        "projects": {
            "viventium_core": {
                "path": str(repo_root),
                "description": "Main Viventium workspace",
            },
            "telegram_codex": {
                "path": str(telegram_codex_dir),
                "description": "Standalone Telegram Codex service",
            },
        },
    }
    return yaml.safe_dump(payload, sort_keys=False)


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def default_live_prompt_bundle_candidates() -> list[Path]:
    candidates: list[Path] = []

    def add(raw: str | Path) -> None:
        path = Path(raw).expanduser().resolve()
        if path not in candidates:
            candidates.append(path)

    env_path = os.environ.get("VIVENTIUM_PROMPT_BUNDLE_PATH", "").strip()
    if env_path:
        add(env_path)

    state_root = os.environ.get("VIVENTIUM_STATE_ROOT", "").strip()
    if state_root:
        add(Path(state_root) / "prompt-bundle.json")

    runtime_profiles: list[str] = []
    env_profile = os.environ.get("VIVENTIUM_RUNTIME_PROFILE", "").strip()
    for profile_name in (env_profile, "isolated", "compat"):
        if profile_name and profile_name not in runtime_profiles:
            runtime_profiles.append(profile_name)

    common_names = [
        APP_SUPPORT_VIVENTIUM_DIR / "runtime" / "prompt-bundle.json",
    ]
    for profile_name in runtime_profiles:
        common_names.extend(
            [
                APP_SUPPORT_VIVENTIUM_DIR / "runtime" / profile_name / "prompt-bundle.json",
                APP_SUPPORT_VIVENTIUM_DIR / "state" / "runtime" / profile_name / "prompt-bundle.json",
                REPO_ROOT / ".viventium" / "runtime" / profile_name / "prompt-bundle.json",
            ]
        )
    for path in common_names:
        add(path)

    if APP_SUPPORT_VIVENTIUM_DIR.exists():
        for path in sorted(APP_SUPPORT_VIVENTIUM_DIR.rglob("prompt-bundle.json")):
            add(path)
    return candidates


def load_live_prompt_bundle(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Unable to read live prompt bundle {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Live prompt bundle is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("prompts"), dict):
        raise SystemExit(f"Live prompt bundle has invalid shape: {path}")
    return payload


def prompt_bundle_hashes(bundle: dict[str, Any]) -> dict[str, str]:
    prompts = bundle.get("prompts") if isinstance(bundle, dict) else {}
    if not isinstance(prompts, dict):
        return {}
    hashes: dict[str, str] = {}
    for prompt_id, prompt in prompts.items():
        if isinstance(prompt, dict):
            content_hash = str(prompt.get("content_hash") or "").strip()
            if content_hash:
                hashes[str(prompt_id)] = content_hash
    return hashes


def check_prompt_bundle_drift(
    *,
    live_bundle_path: Path | None = None,
    compare_reviewed: bool = False,
) -> dict[str, Any]:
    candidates = [live_bundle_path.expanduser().resolve()] if live_bundle_path else []
    if not candidates:
        candidates = default_live_prompt_bundle_candidates()

    live_path = next((path for path in candidates if path.is_file()), None)
    source_bundle = build_prompt_bundle()
    report: dict[str, Any] = {
        "check": "prompt_bundle_drift",
        "status": "blocked",
        "compare_reviewed": compare_reviewed,
        "live_path": str(live_path) if live_path else "",
        "candidate_count": len(candidates),
        "source": {
            "prompt_count": source_bundle.get("prompt_count", 0),
            "bundle_hash": _json_hash(source_bundle),
        },
        "live": {},
        "diff": {
            "added": [],
            "removed": [],
            "changed": [],
        },
    }

    if not live_path:
        report["reason"] = "no_live_prompt_bundle_found"
        return report

    live_bundle = load_live_prompt_bundle(live_path)
    source_hashes = prompt_bundle_hashes(source_bundle)
    live_hashes = prompt_bundle_hashes(live_bundle)
    source_ids = set(source_hashes)
    live_ids = set(live_hashes)
    changed = sorted(
        prompt_id
        for prompt_id in source_ids & live_ids
        if source_hashes.get(prompt_id) != live_hashes.get(prompt_id)
    )
    diff = {
        "added": sorted(source_ids - live_ids),
        "removed": sorted(live_ids - source_ids),
        "changed": changed,
    }
    report["live"] = {
        "prompt_count": live_bundle.get("prompt_count", len(live_hashes)),
        "bundle_hash": _json_hash(live_bundle),
    }
    report["diff"] = diff
    drift_count = len(diff["added"]) + len(diff["removed"]) + len(diff["changed"])
    report["drift_count"] = drift_count
    if drift_count:
        report["status"] = "reviewed_drift" if compare_reviewed else "blocked"
        report["reason"] = "prompt_bundle_drift"
    else:
        report["status"] = "ok"
        report["reason"] = "none"
    return report


def default_live_runtime_config_candidates() -> list[Path]:
    candidates: list[Path] = []

    def add(raw: str | Path) -> None:
        path = Path(raw).expanduser().resolve()
        if path not in candidates:
            candidates.append(path)

    for env_name in (
        "CONFIG_PATH",
        "VIVENTIUM_LIBRECHAT_CONFIG_PATH",
        "VIVENTIUM_RUNTIME_CONFIG_PATH",
    ):
        env_path = os.environ.get(env_name, "").strip()
        if env_path:
            add(env_path)

    runtime_dir = os.environ.get("VIVENTIUM_RUNTIME_DIR", "").strip()
    if runtime_dir:
        add(Path(runtime_dir) / "librechat.yaml")

    state_root = os.environ.get("VIVENTIUM_STATE_ROOT", "").strip()
    if state_root:
        add(Path(state_root) / "librechat.yaml")
        add(Path(state_root) / "librechat.generated.yaml")

    runtime_profiles: list[str] = []
    env_profile = os.environ.get("VIVENTIUM_RUNTIME_PROFILE", "").strip()
    for profile_name in (env_profile, "isolated", "compat"):
        if profile_name and profile_name not in runtime_profiles:
            runtime_profiles.append(profile_name)

    add(APP_SUPPORT_VIVENTIUM_DIR / "runtime" / "librechat.yaml")
    for profile_name in runtime_profiles:
        add(APP_SUPPORT_VIVENTIUM_DIR / "runtime" / profile_name / "librechat.yaml")
        add(APP_SUPPORT_VIVENTIUM_DIR / "state" / "runtime" / profile_name / "librechat.yaml")
        add(
            APP_SUPPORT_VIVENTIUM_DIR
            / "state"
            / "runtime"
            / profile_name
            / "librechat.generated.yaml"
        )
        add(REPO_ROOT / ".viventium" / "runtime" / profile_name / "librechat.yaml")

    return candidates


def load_live_runtime_config(path: Path) -> dict[str, Any]:
    try:
        payload = load_yaml(path)
    except OSError as exc:
        raise SystemExit(f"Unable to read live runtime config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Live runtime config has invalid shape: {path}")
    return payload


def _redacted_runtime_config_value(value: Any, key_path: tuple[str, ...] = ()) -> Any:
    current_key = key_path[-1].lower() if key_path else ""
    normalized_key = current_key.replace("-", "_")
    compact_key = normalized_key.replace("_", "")
    if isinstance(value, dict):
        return {
            str(key): _redacted_runtime_config_value(item, (*key_path, str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redacted_runtime_config_value(item, key_path) for item in value]
    if isinstance(value, str) and any(
        fragment in normalized_key or fragment in compact_key
        for fragment in SECRET_CONFIG_KEY_FRAGMENTS
    ):
        return "<redacted>" if value else ""
    return value


def normalize_prompt_affecting_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for section in PROMPT_AFFECTING_RUNTIME_CONFIG_SECTIONS:
        if section in payload:
            normalized[section] = _redacted_runtime_config_value(payload[section], (section,))
    return normalized


def runtime_config_section_hashes(payload: dict[str, Any]) -> dict[str, str]:
    normalized = normalize_prompt_affecting_runtime_config(payload)
    return {section: _json_hash(value) for section, value in sorted(normalized.items())}


def _section_hash_report(payload: dict[str, Any]) -> dict[str, Any]:
    hashes = runtime_config_section_hashes(payload)
    return {
        "section_count": len(hashes),
        "hash": _json_hash(normalize_prompt_affecting_runtime_config(payload)),
        "section_hashes": hashes,
    }


def _diff_section_hashes(
    left_hashes: dict[str, str],
    right_hashes: dict[str, str],
) -> dict[str, Any]:
    left_sections = set(left_hashes)
    right_sections = set(right_hashes)
    changed = sorted(
        section
        for section in left_sections & right_sections
        if left_hashes.get(section) != right_hashes.get(section)
    )
    diff = {
        "added": sorted(left_sections - right_sections),
        "removed": sorted(right_sections - left_sections),
        "changed": changed,
    }
    diff["drift_count"] = len(diff["added"]) + len(diff["removed"]) + len(diff["changed"])
    return diff


def render_current_librechat_config(
    *,
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    config = load_yaml(config_path)
    validate_config(config, config_path)
    assignments = build_agent_assignments(config)
    env = render_runtime_env(config, assignments)
    prompt_bundle_path = (output_dir or APP_SUPPORT_VIVENTIUM_DIR / "runtime") / "prompt-bundle.json"
    env["VIVENTIUM_PROMPT_BUNDLE_PATH"] = str(prompt_bundle_path)
    return yaml.safe_load(render_librechat_yaml(config, assignments, env)) or {}


def check_runtime_config_drift(
    *,
    config_path: Path,
    live_runtime_config_path: Path | None = None,
    compare_reviewed: bool = False,
) -> dict[str, Any]:
    candidates = [live_runtime_config_path.expanduser().resolve()] if live_runtime_config_path else []
    if not candidates:
        candidates = default_live_runtime_config_candidates()

    live_path = next((path for path in candidates if path.is_file()), None)
    compiled_output_dir = live_path.parent if live_path else APP_SUPPORT_VIVENTIUM_DIR / "runtime"
    compiled_now = render_current_librechat_config(
        config_path=config_path.expanduser().resolve(),
        output_dir=compiled_output_dir,
    )
    source = load_source_of_truth_librechat_yaml()
    report: dict[str, Any] = {
        "check": "runtime_config_drift",
        "status": "blocked",
        "compare_reviewed": compare_reviewed,
        "config_path": str(config_path),
        "live_path": str(live_path) if live_path else "",
        "candidate_count": len(candidates),
        "source": _section_hash_report(source),
        "compiled_now": _section_hash_report(compiled_now),
        "live": {},
        "diff": {
            "live_vs_source": {"added": [], "removed": [], "changed": [], "drift_count": 0},
            "live_vs_compiled": {"added": [], "removed": [], "changed": [], "drift_count": 0},
            "source_vs_compiled": _diff_section_hashes(
                runtime_config_section_hashes(source),
                runtime_config_section_hashes(compiled_now),
            ),
        },
    }

    if not live_path:
        report["reason"] = "no_live_runtime_config_found"
        return report

    live = load_live_runtime_config(live_path)
    report["live"] = _section_hash_report(live)
    live_hashes = runtime_config_section_hashes(live)
    report["diff"]["live_vs_source"] = _diff_section_hashes(
        live_hashes,
        runtime_config_section_hashes(source),
    )
    report["diff"]["live_vs_compiled"] = _diff_section_hashes(
        live_hashes,
        runtime_config_section_hashes(compiled_now),
    )
    drift_count = report["diff"]["live_vs_compiled"]["drift_count"]
    report["drift_count"] = drift_count
    if drift_count:
        report["status"] = "reviewed_drift" if compare_reviewed else "blocked"
        report["reason"] = "runtime_config_drift"
    else:
        report["status"] = "ok"
        report["reason"] = "none"
    return report


def drift_report_allows_success(report: dict[str, Any], compare_reviewed: bool) -> bool:
    return report["status"] == "ok" or (
        report["status"] == "reviewed_drift" and compare_reviewed
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Viventium config.yaml into runtime files.")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--output-dir", help="Directory for generated files")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print summary without writing files")
    parser.add_argument(
        "--check-prompt-drift",
        action="store_true",
        help="Compare the live installed prompt-bundle.json against the current source registry.",
    )
    parser.add_argument(
        "--prompt-bundle-path",
        help="Explicit live prompt-bundle.json path for --check-prompt-drift.",
    )
    parser.add_argument(
        "--check-runtime-config-drift",
        action="store_true",
        help=(
            "Compare the live installed librechat.yaml prompt-affecting sections against "
            "a fresh compile from config/source."
        ),
    )
    parser.add_argument(
        "--runtime-config-path",
        "--live-runtime-config-path",
        dest="runtime_config_path",
        help="Explicit live librechat.yaml path for --check-runtime-config-drift.",
    )
    parser.add_argument(
        "--compare-reviewed",
        action="store_true",
        help="Allow a drift check with known drift to exit successfully after human review.",
    )
    args = parser.parse_args()

    if args.check_prompt_drift or args.check_runtime_config_drift:
        reports: list[dict[str, Any]] = []
        if args.check_prompt_drift:
            reports.append(
                check_prompt_bundle_drift(
                    live_bundle_path=Path(args.prompt_bundle_path).expanduser().resolve()
                    if args.prompt_bundle_path
                    else None,
                    compare_reviewed=args.compare_reviewed,
                )
            )
        if args.check_runtime_config_drift:
            if not args.config:
                parser.error("--config is required with --check-runtime-config-drift")
            reports.append(
                check_runtime_config_drift(
                    config_path=Path(args.config).expanduser().resolve(),
                    live_runtime_config_path=Path(args.runtime_config_path).expanduser().resolve()
                    if args.runtime_config_path
                    else None,
                    compare_reviewed=args.compare_reviewed,
                )
            )
        if len(reports) == 1:
            print(json.dumps(reports[0], indent=2, sort_keys=True))
        else:
            print(
                json.dumps(
                    {
                        "status": "ok"
                        if all(
                            drift_report_allows_success(report, args.compare_reviewed)
                            for report in reports
                        )
                        else "blocked",
                        "checks": reports,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        if all(drift_report_allows_success(report, args.compare_reviewed) for report in reports):
            return
        raise SystemExit(1)

    if not args.config or not args.output_dir:
        parser.error("--config and --output-dir are required unless a drift check is used")

    config_path = Path(args.config).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    config = load_yaml(config_path)
    validate_config(config, config_path)

    assignments = build_agent_assignments(config)
    env = render_runtime_env(config, assignments)
    prompt_bundle_path = output_dir / "prompt-bundle.json"
    env["VIVENTIUM_PROMPT_BUNDLE_PATH"] = str(prompt_bundle_path)
    prompt_bundle = build_prompt_bundle()
    librechat_yaml = render_librechat_yaml(config, assignments, env)
    summary = {
        "config": str(config_path),
        "output_dir": str(output_dir),
        "install_mode": config["install"]["mode"],
        "voice_mode": config.get("voice", {}).get("mode", "disabled"),
        "primary_provider": config["llm"]["primary"]["provider"],
        "telegram_codex_enabled": telegram_codex_enabled(config),
        "prompt_registry": {
            "prompt_count": prompt_bundle["prompt_count"],
            "prompt_bundle": str(prompt_bundle_path),
        },
        "assignments": assignments,
    }

    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    dump_env(output_dir / "runtime.env", env)
    dump_env(output_dir / "runtime.local.env", {})
    (output_dir / "librechat.yaml").write_text(librechat_yaml, encoding="utf-8")
    prompt_bundle_path.write_text(
        json.dumps(prompt_bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prompt_bundle_path.chmod(0o600)
    render_service_envs(output_dir, env)
    telegram_codex_dir = output_dir / "telegram-codex"
    telegram_codex_dir.mkdir(parents=True, exist_ok=True)
    (telegram_codex_dir / "settings.yaml").write_text(
        render_telegram_codex_settings(config, output_dir),
        encoding="utf-8",
    )
    (telegram_codex_dir / "projects.yaml").write_text(
        render_telegram_codex_projects(),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote runtime files to {output_dir}")


if __name__ == "__main__":
    main()
