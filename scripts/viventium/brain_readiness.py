#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BrainReadinessFeature:
    key: str
    label: str
    express_posture: str
    required_user_action: str
    machine_prerequisite: str
    config_paths: tuple[str, ...]
    generated_env_keys: tuple[str, ...]
    health_probe: str
    self_heal_action: str
    qa_owner: str
    public_safety_rule: str


FEATURES: tuple[BrainReadinessFeature, ...] = (
    BrainReadinessFeature(
        key="core_app",
        label="Core App",
        express_posture="installed",
        required_user_action="Create the first local browser account.",
        machine_prerequisite="Supported macOS host with the native runtime prerequisites.",
        config_paths=("runtime.*",),
        generated_env_keys=("VIVENTIUM_LC_API_PORT", "VIVENTIUM_LC_FRONTEND_PORT"),
        health_probe="LibreChat frontend/API health plus a successful optimized first answer.",
        self_heal_action="bin/viventium start or bin/viventium upgrade --restart",
        qa_owner="qa/installer-resilience/cases.md",
        public_safety_rule="Never publish local home paths, browser cookies, account emails, or App Support state.",
    ),
    BrainReadinessFeature(
        key="scheduler",
        label="Scheduler",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install; Scheduler is disabled in Easy Install today.",
        machine_prerequisite="Local Scheduling Cortex MCP process and writable scheduler state DB.",
        config_paths=("runtime.nightly_routines", "runtime.prompt_workbench.seed_nightly"),
        generated_env_keys=("START_SCHEDULING_MCP", "SCHEDULING_MCP_URL", "SCHEDULING_DB_PATH"),
        health_probe="Scheduling MCP endpoint plus sanitized ledger counts and last delivery state.",
        self_heal_action="Restart Viventium; keep ledger state, do not reset schedules.",
        qa_owner="qa/scheduling-cortex/cases.md",
        public_safety_rule="Do not publish prompt text, owner emails, callback payloads, or raw schedule goals.",
    ),
    BrainReadinessFeature(
        key="glasshive",
        label="GlassHive",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install and have Codex CLI or Claude CLI installed and signed in.",
        machine_prerequisite="At least one supported local worker CLI can run on this Mac.",
        config_paths=("integrations.glasshive.*",),
        generated_env_keys=("START_GLASSHIVE", "GLASSHIVE_OPERATOR_BASE_URL", "GLASSHIVE_DEFAULT_WORKER_PROFILE"),
        health_probe="GlassHive operator health plus default worker profile.",
        self_heal_action="Run the worker CLI login command, then bin/viventium start.",
        qa_owner="qa/glasshive/cases.md",
        public_safety_rule="Do not publish worker home paths, raw delegated prompts, or private result payloads.",
    ),
    BrainReadinessFeature(
        key="prompt_workbench",
        label="Prompt Workbench",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install; Prompt Workbench is disabled in Easy Install today.",
        machine_prerequisite="Local Workbench service and Scheduler callback route.",
        config_paths=("runtime.prompt_workbench.*",),
        generated_env_keys=("START_PROMPT_WORKBENCH", "VIVENTIUM_PROMPT_WORKBENCH_PORT"),
        health_probe="Workbench health endpoint, visible schedule state, callback completion.",
        self_heal_action="Restart Viventium and inspect Scheduler/GlassHive ledger rows.",
        qa_owner="qa/prompt-workbench/cases.md",
        public_safety_rule="Do not publish private prompt text, result bodies, or screenshots with private content.",
    ),
    BrainReadinessFeature(
        key="nightly_reflection",
        label="Nightly Reflection",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install with Scheduler, Prompt Workbench, and GlassHive enabled.",
        machine_prerequisite="Scheduler, Workbench, and GlassHive are healthy.",
        config_paths=("runtime.prompt_workbench.seed_nightly.*", "runtime.nightly_routines.*"),
        generated_env_keys=(
            "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED",
            "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE",
            "VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR",
        ),
        health_probe="scheduled prompt -> filled placeholders -> GlassHive run -> callback -> ledger -> Workbench completed.",
        self_heal_action="Rerun the due schedule or let the next safe nightly window prove delivery.",
        qa_owner="qa/prompt-workbench/cases.md",
        public_safety_rule="Use sanitized schedule metadata only; never publish the raw reflection result.",
    ),
    BrainReadinessFeature(
        key="memory_hardening",
        label="Memory Hardening",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install; scheduled memory hardening is disabled in Easy Install today.",
        machine_prerequisite="LaunchAgent/cron path and local memory store access.",
        config_paths=("runtime.memory_hardening.*",),
        generated_env_keys=("VIVENTIUM_MEMORY_HARDENING_ENABLED", "VIVENTIUM_MEMORY_HARDENING_SCHEDULE"),
        health_probe="latest run state, eligible-user count, skipped reason, and dry-run-first state.",
        self_heal_action="Fix eligibility/config, then let the next safe scheduled run prove non-empty work.",
        qa_owner="qa/memory-hardening/cases.md",
        public_safety_rule="Never publish owner memory contents, transcript text, user emails, or local App Support paths.",
    ),
    BrainReadinessFeature(
        key="transcript_ingest",
        label="Transcript Ingest",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install, then choose a local transcript folder.",
        machine_prerequisite="Readable local transcript source folder.",
        config_paths=("runtime.memory_hardening.transcripts.*",),
        generated_env_keys=("VIVENTIUM_MEMORY_HARDENING_TRANSCRIPTS_SOURCE_DIR",),
        health_probe="source configured, latest scan timestamp, summary/RAG artifact counts.",
        self_heal_action="Add or change the folder with bin/viventium configure; empty means pending, not failed.",
        qa_owner="qa/meeting-transcript-memory/cases.md",
        public_safety_rule="Do not publish raw transcript text, filenames, participant names, or source paths.",
    ),
    BrainReadinessFeature(
        key="conversation_recall",
        label="Conversation Recall/RAG",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install to opt in to Docker/Ollama-backed recall/RAG.",
        machine_prerequisite="Docker Desktop and Ollama/vector services for the local path.",
        config_paths=("runtime.personalization.default_conversation_recall", "runtime.retrieval.*"),
        generated_env_keys=("RAG_API_URL", "VIVENTIUM_RETRIEVAL_EMBEDDINGS_PROVIDER"),
        health_probe="RAG API health, vector DB health, model/provider readiness, browser recall answer.",
        self_heal_action="Install/start Docker and Ollama, then enable recall in configure.",
        qa_owner="qa/conversation-recall-rag/cases.md",
        public_safety_rule="Do not publish private conversations, vector contents, query text, or recall screenshots.",
    ),
    BrainReadinessFeature(
        key="web_search",
        label="Web Search",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install for local Docker search or hosted search/scraper keys.",
        machine_prerequisite="Docker Desktop for local SearXNG/Firecrawl, or valid hosted API keys.",
        config_paths=("integrations.web_search.*",),
        generated_env_keys=("SEARXNG_INSTANCE_URL", "FIRECRAWL_API_URL", "START_SEARXNG", "START_FIRECRAWL"),
        health_probe="configured provider plus exact degraded service when local search/scrape is down.",
        self_heal_action="Start local search services or add hosted keys with bin/viventium configure.",
        qa_owner="qa/web-search/cases.md",
        public_safety_rule="Do not publish private queries, result snippets from private pages, or API keys.",
    ),
    BrainReadinessFeature(
        key="primary_ai",
        label="Primary AI",
        express_posture="guided",
        required_user_action=(
            "Add an OpenAI API key in Settings > Account > Connected Accounts for the complete "
            "optimized Easy Install experience."
        ),
        machine_prerequisite="Encrypted user key or a deliberately enabled experimental account bridge.",
        config_paths=("llm.primary.*", "llm.extra_provider_keys.*"),
        generated_env_keys=("VIVENTIUM_OPENAI_AUTH_MODE", "VIVENTIUM_ANTHROPIC_AUTH_MODE"),
        health_probe=(
            "saved credential, live OpenAI probe, first visible Viventium answer, and restart "
            "persistence."
        ),
        self_heal_action="Open Settings -> Connected Accounts, or rerun configure for API-key fallback.",
        qa_owner="qa/connected-accounts/cases.md",
        public_safety_rule="Never publish account emails, OAuth tokens, API keys, or provider secret refs.",
    ),
    BrainReadinessFeature(
        key="secondary_ai",
        label="Secondary/Fallback AI",
        express_posture="guided",
        required_user_action="Optionally connect a second foundation provider.",
        machine_prerequisite="Provider account route or local secret in Keychain/config.",
        config_paths=("llm.secondary.*", "llm.extra_provider_keys.*"),
        generated_env_keys=("VIVENTIUM_OPENAI_AUTH_MODE", "VIVENTIUM_ANTHROPIC_AUTH_MODE"),
        health_probe="status distinguishes configured credentials from a fallback proven by a live provider request.",
        self_heal_action="Add a fallback provider later with bin/viventium configure.",
        qa_owner="qa/connected-accounts/cases.md",
        public_safety_rule="Never publish account emails, OAuth tokens, API keys, or provider secret refs.",
    ),
    BrainReadinessFeature(
        key="voice",
        label="Voice",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install; Voice and its playground are disabled in Easy Install today.",
        machine_prerequisite="Apple Silicon local voice stack, or hosted STT/TTS credentials.",
        config_paths=("voice.*",),
        generated_env_keys=("VIVENTIUM_VOICE_MODE", "VIVENTIUM_VOICE_TTS_PROVIDER"),
        health_probe="playground voice mode, provider readiness, delivered audio/transcript evidence.",
        self_heal_action="Choose local or hosted voice with bin/viventium configure.",
        qa_owner="qa/modern-playground-voice/cases.md",
        public_safety_rule="Do not publish private audio, voice transcripts, or provider keys.",
    ),
    BrainReadinessFeature(
        key="telegram",
        label="Telegram",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install, then paste a BotFather token for the Telegram bridge.",
        machine_prerequisite="Valid token stored in Keychain/config and no competing poller.",
        config_paths=("integrations.telegram.*",),
        generated_env_keys=("BOT_TOKEN",),
        health_probe="token format, polling process, recent conflict/auth errors.",
        self_heal_action="Stop the competing bot process or replace the token with bin/viventium configure.",
        qa_owner="qa/telegram-runtime/cases.md",
        public_safety_rule="Never publish BotFather tokens, chat IDs, usernames, or message text.",
    ),
    BrainReadinessFeature(
        key="telegram_codex",
        label="Telegram Codex",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install, then paste a separate BotFather token for the Codex sidecar.",
        machine_prerequisite="Valid separate token stored in Keychain/config.",
        config_paths=("integrations.telegram_codex.*",),
        generated_env_keys=("TELEGRAM_CODEX_BOT_TOKEN",),
        health_probe="token format, polling process, recent conflict/auth errors.",
        self_heal_action="Use a separate token and rerun bin/viventium configure.",
        qa_owner="qa/telegram-runtime/cases.md",
        public_safety_rule="Never publish BotFather tokens, chat IDs, usernames, or message text.",
    ),
    BrainReadinessFeature(
        key="google_workspace",
        label="Google Workspace MCP",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install, then connect Google OAuth for Gmail/Drive/Calendar tools.",
        machine_prerequisite="OAuth client/refresh token or connected-account flow.",
        config_paths=("integrations.google_workspace.*",),
        generated_env_keys=("START_GOOGLE_MCP", "GOOGLE_WORKSPACE_MCP_URL"),
        health_probe="MCP endpoint reachability plus OAuth action-required state.",
        self_heal_action="Finish Google OAuth in onboarding or rerun configure.",
        qa_owner="qa/mcp-oauth/cases.md",
        public_safety_rule="Never publish personal email, OAuth tokens, file names, or mailbox content.",
    ),
    BrainReadinessFeature(
        key="ms365",
        label="Microsoft 365 MCP",
        express_posture="custom_only",
        required_user_action="Use Custom Settings Install, then connect Microsoft/Azure credentials for MS365 tools.",
        machine_prerequisite="Azure app credentials and Docker-backed local sidecar.",
        config_paths=("integrations.ms365.*",),
        generated_env_keys=("START_MS365_MCP", "MS365_MCP_SERVER_URL"),
        health_probe="MCP endpoint reachability plus OAuth/action-required state.",
        self_heal_action="Finish Microsoft setup in onboarding or rerun configure.",
        qa_owner="qa/mcp-oauth/cases.md",
        public_safety_rule="Never publish business email, tenant IDs tied to private users, OAuth tokens, or mailbox content.",
    ),
    BrainReadinessFeature(
        key="whatsapp",
        label="WhatsApp",
        express_posture="unavailable",
        required_user_action="No user action yet; Viventium has no first-class WhatsApp integration today.",
        machine_prerequisite="Owning runtime integration, docs, and QA do not exist yet.",
        config_paths=(),
        generated_env_keys=(),
        health_probe="Not applicable until a first-class feature exists.",
        self_heal_action="Do not fake support; add docs/runtime/QA before exposing this.",
        qa_owner="qa/installer-resilience/cases.md",
        public_safety_rule="Do not imply or document private WhatsApp message access without a real audited integration.",
    ),
    BrainReadinessFeature(
        key="code_interpreter",
        label="Code Interpreter",
        express_posture="advanced_off",
        required_user_action="Optional; enable later through Custom Settings Install or bin/viventium configure.",
        machine_prerequisite="Docker sandbox service.",
        config_paths=("integrations.code_interpreter.enabled",),
        generated_env_keys=("LIBRECHAT_CODE_BASEURL",),
        health_probe="Sandbox health endpoint only when explicitly enabled.",
        self_heal_action="Enable through Custom Settings Install or bin/viventium configure.",
        qa_owner="qa/code-interpreter/cases.md",
        public_safety_rule="Do not publish executed code inputs, generated files, or sandbox state.",
    ),
    BrainReadinessFeature(
        key="skyvern",
        label="Skyvern",
        express_posture="advanced_off",
        required_user_action="Optional; enable later through Custom Settings Install or bin/viventium configure.",
        machine_prerequisite="Skyvern API key and Docker/browser automation stack.",
        config_paths=("integrations.skyvern.enabled",),
        generated_env_keys=("START_SKYVERN",),
        health_probe="Service health only when explicitly enabled.",
        self_heal_action="Enable through Custom Settings Install or bin/viventium configure.",
        qa_owner="qa/installer-resilience/cases.md",
        public_safety_rule="Do not publish browser session data, private URLs, credentials, or screenshots.",
    ),
    BrainReadinessFeature(
        key="openclaw",
        label="OpenClaw",
        express_posture="unavailable",
        required_user_action="No user action; OpenClaw is an internal lab-only candidate and is not exposed by the public installer.",
        machine_prerequisite="Authenticated client wiring, lifecycle ownership, and public QA are not shipped.",
        config_paths=("integrations.openclaw.enabled",),
        generated_env_keys=(),
        health_probe="Not applicable until authenticated client wiring and a real lifecycle probe ship.",
        self_heal_action="Do not expose it in Easy Install or Custom Settings Install before those gates pass.",
        qa_owner="qa/installer-resilience/cases.md",
        public_safety_rule="Do not publish exposure findings, account names, or monitored targets.",
    ),
    BrainReadinessFeature(
        key="remote_access",
        label="Remote Access",
        express_posture="advanced_off",
        required_user_action="Optional guided opt-in for personal devices or public browser access.",
        machine_prerequisite="Tailscale/NetBird/public-edge prerequisites for the chosen mode.",
        config_paths=("runtime.network.*",),
        generated_env_keys=("VIVENTIUM_PUBLIC_CLIENT_URL", "VIVENTIUM_PUBLIC_NETWORK_STATE_FILE"),
        health_probe="public/private URL state and last tunnel/router error.",
        self_heal_action="Use Custom Settings Install or bin/viventium configure; local-only stays the default.",
        qa_owner="qa/remote-access/cases.md",
        public_safety_rule="Do not publish private hostnames, tunnel URLs tied to a real user, or LAN IPs in public artifacts.",
    ),
)

FEATURE_BY_KEY: dict[str, BrainReadinessFeature] = {feature.key: feature for feature in FEATURES}
FEATURE_GUIDANCE: dict[str, str] = {
    feature.key: feature.required_user_action for feature in FEATURES
}
FEATURE_LABELS: dict[str, str] = {feature.key: feature.label for feature in FEATURES}

CORE_EXPRESS_KEYS: tuple[str, ...] = tuple(
    feature.key for feature in FEATURES if feature.express_posture == "installed"
)
GUIDED_EXPRESS_KEYS: tuple[str, ...] = tuple(
    feature.key for feature in FEATURES if feature.express_posture in {"guided", "installed_or_guided"}
)
CUSTOM_SETTINGS_ONLY_KEYS: tuple[str, ...] = tuple(
    feature.key for feature in FEATURES if feature.express_posture == "custom_only"
)
ADVANCED_OFF_KEYS: tuple[str, ...] = tuple(
    feature.key for feature in FEATURES if feature.express_posture == "advanced_off"
)
UNAVAILABLE_KEYS: tuple[str, ...] = tuple(
    feature.key for feature in FEATURES if feature.express_posture == "unavailable"
)


def iter_features(keys: Iterable[str] | None = None) -> Iterable[BrainReadinessFeature]:
    if keys is None:
        return iter(FEATURES)
    return (FEATURE_BY_KEY[key] for key in keys if key in FEATURE_BY_KEY)


def feature_label(key: str) -> str:
    return FEATURE_LABELS.get(key, key)


def feature_guidance(key: str) -> str:
    return FEATURE_GUIDANCE.get(key, "Run bin/viventium configure later.")
