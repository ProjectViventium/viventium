#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from telegram_tokens import telegram_bot_token_validation_error
from retrieval_config import resolve_retrieval_embeddings_settings

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
DEFAULT_BACKGROUND_FOLLOWUP_WINDOW_S = "30"
DEFAULT_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD = "0.01"
DEFAULT_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS = "100"
DEFAULT_ASSEMBLYAI_MAX_TURN_SILENCE_MS = "1000"
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
    "OPENROUTER_API_KEY",
    "PERPLEXITY_API_KEY",
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
    "viventium/skyvern_api_key": ("SKYVERN_API_KEY",),
    "viventium/telegram_bot_token": ("BOT_TOKEN",),
    "viventium/telegram_codex_bot_token": ("TELEGRAM_CODEX_BOT_TOKEN",),
    "viventium/x_ai_api_key": ("XAI_API_KEY",),
}


def glasshive_enabled(config: dict[str, Any]) -> bool:
    integrations = config.get("integrations", {}) or {}
    configured = resolve_bool((integrations.get("glasshive") or {}).get("enabled"), False)
    return configured and GLASSHIVE_RUNTIME_DIR.is_dir()

VOICE_PROVIDER_KEYCHAIN_SERVICES = {
    "assemblyai": "viventium/assemblyai_api_key",
    "cartesia": "viventium/cartesia_api_key",
    "elevenlabs": "viventium/elevenlabs_api_key",
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
        "conscious": "claude-opus-4-7",
        "background_analysis": "claude-sonnet-4-6",
        "confirmation_bias": "claude-sonnet-4-6",
        "red_team": "claude-opus-4-7",
        "deep_research": "claude-opus-4-7",
        "productivity": "claude-sonnet-4-6",
        "parietal": "claude-sonnet-4-6",
        "pattern_recognition": "claude-sonnet-4-6",
        "emotional_resonance": "claude-sonnet-4-6",
        "strategic_planning": "claude-opus-4-7",
        "support": "claude-sonnet-4-6",
        "memory": "claude-sonnet-4-6",
    },
    "x_ai": {
        "conscious": "grok-4-1-fast-non-reasoning",
        "background_analysis": "grok-4-1-fast-non-reasoning",
        "confirmation_bias": "grok-4-1-fast-non-reasoning",
        "red_team": "grok-4-1-fast-non-reasoning",
        "deep_research": "grok-4-1-fast-non-reasoning",
        "productivity": "grok-4-1-fast-non-reasoning",
        "parietal": "grok-4-1-fast-non-reasoning",
        "pattern_recognition": "grok-4-1-fast-non-reasoning",
        "emotional_resonance": "grok-4-1-fast-non-reasoning",
        "strategic_planning": "grok-4-1-fast-non-reasoning",
        "support": "grok-4-1-fast-non-reasoning",
        "memory": "grok-4-1-fast-non-reasoning",
    },
}

MEMORY_HARDENING_LAUNCH_READY_MODELS = {
    "anthropic": {"claude-opus-4-7", "claude-sonnet-4-6"},
    "openai": {"gpt-5.4"},
}
DEFAULT_MEMORY_HARDENING = {
    "enabled": False,
    "schedule": "0 5 * * *",
    "timezone": "America/Toronto",
    "lookback_days": 7,
    "min_user_idle_minutes": 60,
    "max_changes_per_user": 3,
    "max_input_chars": 500000,
    "require_full_lookback": True,
    "dry_run_first": True,
    "provider_profile": "launch_ready_only",
    "anthropic_model": "claude-opus-4-7",
    "openai_model": "gpt-5.4",
}

CURRENT_BACKGROUND_ACTIVATION_PROVIDER = "groq"
CURRENT_BACKGROUND_ACTIVATION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

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
            "grok-4-1-fast-non-reasoning",
            "grok-4-1-fast-reasoning",
            "grok-4-fast-non-reasoning",
            "grok-4-fast-reasoning",
            "grok-4-0709",
            "grok-code-fast-1",
            "grok-3-mini",
            "grok-3",
            "grok-2-vision-1212",
            "grok-2-image-1212",
        ],
        "titleModel": "grok-4-1-fast-non-reasoning",
        "summaryModel": "grok-4-1-fast-non-reasoning",
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


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must be a mapping: {path}")
    return data


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
        return candidates

    if explicit:
        add_candidate(explicit)
    add_candidate(SOURCE_OF_TRUTH_LIBRECHAT_YAML)
    return candidates


def load_source_of_truth_librechat_yaml() -> dict[str, Any]:
    for candidate in resolve_source_of_truth_librechat_yaml_candidates():
        if candidate.is_file():
            return load_yaml(candidate)
    return {}


def load_source_of_truth_agents_bundle() -> dict[str, Any]:
    if not SOURCE_OF_TRUTH_AGENTS_BUNDLE.is_file():
        return {}
    return load_yaml(SOURCE_OF_TRUTH_AGENTS_BUNDLE)


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
        if not resolve_bool(env.get("START_MS365_MCP"), False):
            mcp_servers.pop("ms-365", None)
        if not resolve_bool(env.get("START_GOOGLE_MCP"), False):
            mcp_servers.pop("google_workspace", None)
        if not resolve_bool(env.get("START_GLASSHIVE"), False):
            mcp_servers.pop("glasshive-workers-projects", None)

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


def resolve_voice_provider_secret(
    voice: dict[str, Any],
    resolved_voice: dict[str, str],
    provider_name: str,
) -> str:
    provider_keys = voice.get("provider_keys", {}) or {}
    if isinstance(provider_keys, dict):
        configured = provider_keys.get(provider_name)
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
        "list": build_built_in_agent_model_specs(_default_main_agent_id),
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
        "conscious": (conscious_provider, MODEL_MAP[conscious_provider]["conscious"]),
        "background_analysis": (
            reflective_provider,
            MODEL_MAP[reflective_provider]["background_analysis"],
        ),
        "confirmation_bias": (
            reflective_provider,
            MODEL_MAP[reflective_provider]["confirmation_bias"],
        ),
        "red_team": (analytical_provider, MODEL_MAP[analytical_provider]["red_team"]),
        "deep_research": (
            analytical_provider,
            MODEL_MAP[analytical_provider]["deep_research"],
        ),
        "productivity": (analytical_provider, MODEL_MAP[analytical_provider]["productivity"]),
        "parietal": (analytical_provider, MODEL_MAP[analytical_provider]["parietal"]),
        "pattern_recognition": (
            reflective_provider,
            MODEL_MAP[reflective_provider]["pattern_recognition"],
        ),
        "emotional_resonance": (
            emotional_provider,
            MODEL_MAP[emotional_provider]["emotional_resonance"],
        ),
        "strategic_planning": (
            emotional_provider,
            MODEL_MAP[emotional_provider]["strategic_planning"],
        ),
        "support": (support_provider, MODEL_MAP[support_provider]["support"]),
        "memory": (memory_provider, MODEL_MAP[memory_provider]["memory"]),
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


def resolve_voice_settings(config: dict[str, Any]) -> dict[str, str]:
    voice = config.get("voice", {}) or {}
    voice_mode = str(voice.get("mode", "disabled") or "disabled").strip().lower()
    raw_stt_provider = str(voice.get("stt_provider", "") or "").strip().lower()
    stt_provider = raw_stt_provider or "whisper_local"
    tts_provider = str(voice.get("tts_provider", "") or "").strip().lower()
    tts_provider_fallback = str(voice.get("tts_provider_fallback", "") or "").strip().lower()

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


def conversation_recall_enabled(config: dict[str, Any]) -> bool:
    runtime = config.get("runtime", {}) or {}
    personalization = runtime.get("personalization", {}) or {}
    return resolve_bool(personalization.get("default_conversation_recall"), False)


def resolve_memory_hardening_settings(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {}) or {}
    raw = runtime.get("memory_hardening", {}) or {}
    if raw and not isinstance(raw, dict):
        raise SystemExit("runtime.memory_hardening must be a mapping when provided")

    settings = dict(DEFAULT_MEMORY_HARDENING)
    settings.update(raw)
    settings["enabled"] = resolve_bool(settings.get("enabled"), False)
    settings["dry_run_first"] = resolve_bool(settings.get("dry_run_first"), True)
    settings["require_full_lookback"] = resolve_bool(settings.get("require_full_lookback"), True)
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
    settings["anthropic_model"] = str(
        settings.get("anthropic_model") or DEFAULT_MEMORY_HARDENING["anthropic_model"]
    )
    settings["openai_model"] = str(settings.get("openai_model") or DEFAULT_MEMORY_HARDENING["openai_model"])

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

    return settings


def resolve_auth_settings(config: dict[str, Any]) -> dict[str, bool]:
    runtime = config.get("runtime", {}) or {}
    auth = runtime.get("auth", {}) or {}
    return {
        "allow_registration": resolve_bool(auth.get("allow_registration"), True),
        "bootstrap_registration_once": resolve_bool(
            auth.get("bootstrap_registration_once"), False
        ),
        "allow_password_reset": resolve_bool(auth.get("allow_password_reset"), False),
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
    retrieval_embeddings = resolve_retrieval_embeddings_settings(config)
    auth_settings = resolve_auth_settings(config)
    start_rag_api = "true" if default_conversation_recall else "false"
    code_interpreter_is_enabled = code_interpreter_enabled(config)
    web_search_settings = resolve_web_search_settings(config)
    web_search_is_enabled = web_search_settings["enabled"] == "true"
    start_searxng = web_search_is_enabled and web_search_settings["search_provider"] == "searxng"
    start_firecrawl = web_search_is_enabled and web_search_settings["scraper_provider"] == "firecrawl"
    telegram_is_enabled = telegram_enabled(config)
    glasshive_is_enabled = glasshive_enabled(config)

    env: dict[str, str] = {
        "VIVENTIUM_CONFIG_VERSION": str(CONFIG_VERSION),
        "VIVENTIUM_INSTALL_MODE": config["install"]["mode"],
        "VIVENTIUM_RUNTIME_PROFILE": runtime_profile,
        "VIVENTIUM_PLAYGROUND_VARIANT": playground_variant,
        "PLAYGROUND_VARIANT": playground_variant,
        "VIVENTIUM_LOG_LEVEL": runtime.get("log_level", "info"),
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
        "GROQ_API_KEY": provider_secret(llm["activation"]),
        "VIVENTIUM_PRIMARY_PROVIDER": llm["primary"]["provider"],
        "VIVENTIUM_PRIMARY_AUTH_MODE": llm["primary"]["auth_mode"],
        "VIVENTIUM_SECONDARY_PROVIDER": llm.get("secondary", {}).get("provider", "none"),
        "VIVENTIUM_SECONDARY_AUTH_MODE": llm.get("secondary", {}).get("auth_mode", "disabled"),
        "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        "VIVENTIUM_DEFAULT_CONVERSATION_RECALL": "true"
        if default_conversation_recall
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_ENABLED": "true"
        if memory_hardening["enabled"]
        else "false",
        "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": memory_hardening["schedule"],
        "VIVENTIUM_MEMORY_HARDENING_TIMEZONE": memory_hardening["timezone"],
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
        "VIVENTIUM_MEMORY_HARDENING_PROVIDER_PROFILE": memory_hardening["provider_profile"],
        "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL": memory_hardening["anthropic_model"],
        "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL": memory_hardening["openai_model"],
        "VIVENTIUM_BUILTIN_AGENT_PUBLIC_ROLE": "owner",
        "VIVENTIUM_TELEGRAM_BACKEND": "librechat",
        "VIVENTIUM_TELEGRAM_AGENT_ID": default_main_agent_id,
        "VIVENTIUM_MAIN_AGENT_ID": default_main_agent_id,
        "START_GOOGLE_MCP": "true" if integrations.get("google_workspace", {}).get("enabled") else "false",
        "START_MS365_MCP": "true" if integrations.get("ms365", {}).get("enabled") else "false",
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
        "ALLOW_EMAIL_LOGIN": "true",
        "ALLOW_REGISTRATION": "true" if auth_settings["allow_registration"] else "false",
        "VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE": "true"
        if auth_settings["bootstrap_registration_once"]
        else "false",
        "ALLOW_PASSWORD_RESET": "true" if auth_settings["allow_password_reset"] else "false",
        "ALLOW_SOCIAL_LOGIN": "false",
        "ALLOW_SOCIAL_REGISTRATION": "false",
        "ALLOW_UNVERIFIED_EMAIL_LOGIN": "true",
        "VIVENTIUM_REGISTRATION_APPROVAL": "false",
        "VIVENTIUM_CALL_SESSION_SECRET": call_session_secret,
        "VIVENTIUM_TELEGRAM_SECRET": call_session_secret,
        "VIVENTIUM_SCHEDULER_SECRET": call_session_secret,
        "VIVENTIUM_LIBRECHAT_ORIGIN": f"http://localhost:{profile['lc_api_port']}",
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

    if retrieval_embeddings["provider"] == "ollama":
        env["OLLAMA_BASE_URL"] = retrieval_embeddings["ollama_base_url"]

    if glasshive_is_enabled:
        env["GLASSHIVE_DEFAULT_LAUNCH_SURFACE"] = "desktop"
        env["GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP"] = "true"
        env["WPR_IDLE_DESKTOP_PRIME_BROWSER"] = "true"

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
    env["VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S"] = background_followup_window_s
    env["VIVENTIUM_VOICE_FOLLOWUP_GRACE_S"] = background_followup_window_s
    env["VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S"] = background_followup_window_s

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
    env["VIVENTIUM_BACKGROUND_ACTIVATION_PROVIDER"] = CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    env["VIVENTIUM_BACKGROUND_ACTIVATION_MODEL"] = CURRENT_BACKGROUND_ACTIVATION_MODEL
    env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_ACTIVATION_LLM_PROVIDER"] = CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_ACTIVATION_LLM_MODEL"] = CURRENT_BACKGROUND_ACTIVATION_MODEL
    env["VIVENTIUM_CORTEX_DEEP_RESEARCH_ACTIVATION_LLM_PROVIDER"] = CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    env["VIVENTIUM_CORTEX_DEEP_RESEARCH_ACTIVATION_LLM_MODEL"] = CURRENT_BACKGROUND_ACTIVATION_MODEL
    env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_ACTIVATION_LLM_PROVIDER"] = CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_ACTIVATION_LLM_MODEL"] = CURRENT_BACKGROUND_ACTIVATION_MODEL
    env["OTUC_ACTIVATION_PROVIDER"] = CURRENT_BACKGROUND_ACTIVATION_PROVIDER
    env["OTUC_ACTIVATION_LLM"] = CURRENT_BACKGROUND_ACTIVATION_MODEL

    voice_mode = resolved_voice["mode"]
    env["VIVENTIUM_VOICE_ENABLED"] = "true" if voice_mode != "disabled" else "false"
    env["VIVENTIUM_STT_PROVIDER"] = resolved_voice["stt_provider"]
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
    assemblyai_key = resolve_voice_provider_secret(voice, resolved_voice, "assemblyai")
    if assemblyai_key:
        env["ASSEMBLYAI_API_KEY"] = assemblyai_key
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

    for provider_name, secret_value in (llm.get("extra_provider_keys") or {}).items():
        resolved = resolve_secret(secret_value)
        if not resolved:
            continue
        if provider_name == "openai":
            env["OPENAI_API_KEY"] = resolved
        elif provider_name == "anthropic":
            env["ANTHROPIC_API_KEY"] = resolved
        elif provider_name == "x_ai":
            env["XAI_API_KEY"] = resolved
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
            "serverInstructions": (
                "Scheduling Cortex MCP for reminders, recurring jobs, and schedule management."
            ),
        },
    }

    if glasshive_enabled(config):
        servers["glasshive-workers-projects"] = {
            "type": "streamable-http",
            "url": "${GLASSHIVE_MCP_URL}",
            "headers": {
                "X-Viventium-User-Id": "{{LIBRECHAT_USER_ID}}",
                "X-Viventium-Agent-Id": default_main_agent_id,
            },
            "startup": False,
            "chatMenu": True,
            "timeout": 120000,
            "serverInstructions": (
                "GlassHive MCP for persistent projects, resumable workers, workstation "
                "sandboxes, and live operator takeover. Use it when work needs delegation, "
                "persistence, or a human handoff into a live sandbox."
            ),
        }

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
            "serverInstructions": (
                "This MCP server provides access to Microsoft 365 mail, calendar, files, "
                "teams, contacts, tasks, and notes using the authenticated user account."
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
            "serverInstructions": (
                "This MCP server provides access to Google Workspace mail, calendar, drive, "
                "docs, sheets, slides, tasks, forms, and chat using the authenticated user."
            ),
        }

    return servers


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
    generated = {
        "version": LIBRECHAT_YAML_VERSION,
        "cache": True,
        "registration": {"socialLogins": []},
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
            "allowedDomains": LOCAL_MCP_ALLOWED_DOMAINS,
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
        "VIVENTIUM_FC_CONSCIOUS_LLM_PROVIDER",
        "VIVENTIUM_FC_CONSCIOUS_LLM_MODEL",
    ]
    telegram_keys = [
        "BOT_TOKEN",
        "VIVENTIUM_TELEGRAM_BACKEND",
        "VIVENTIUM_TELEGRAM_AGENT_ID",
        "VIVENTIUM_LIBRECHAT_ORIGIN",
        "VIVENTIUM_TELEGRAM_SECRET",
        "VIVENTIUM_CALL_SESSION_SECRET",
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
        return "tiny.en"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Viventium config.yaml into runtime files.")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print summary without writing files")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    config = load_yaml(config_path)

    if int(config.get("version", 0)) != CONFIG_VERSION:
        raise SystemExit(f"Unsupported config version in {config_path}")

    if config["llm"]["activation"].get("provider") != "groq":
        raise SystemExit("Activation provider must remain Groq.")
    if not provider_secret(config["llm"]["activation"]):
        raise SystemExit("Missing required Groq credential.")

    assignments = build_agent_assignments(config)
    env = render_runtime_env(config, assignments)
    librechat_yaml = render_librechat_yaml(config, assignments, env)
    summary = {
        "config": str(config_path),
        "output_dir": str(output_dir),
        "install_mode": config["install"]["mode"],
        "voice_mode": config.get("voice", {}).get("mode", "disabled"),
        "primary_provider": config["llm"]["primary"]["provider"],
        "telegram_codex_enabled": telegram_codex_enabled(config),
        "assignments": assignments,
    }

    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    dump_env(output_dir / "runtime.env", env)
    dump_env(output_dir / "runtime.local.env", {})
    (output_dir / "librechat.yaml").write_text(librechat_yaml, encoding="utf-8")
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
