from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_OF_TRUTH_AGENTS_BUNDLE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.viventium-agents.yaml"
)
BACKGROUND_CORTEX_SERVICE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "BackgroundCortexService.js"
)
BREWING_HOLD_SERVICE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "brewingHold.js"
)
PRODUCTIVITY_SPECIALIST_CONTEXT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "productivitySpecialistContext.js"
)
VOICE_PHASE_A_POLICY = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "voicePhaseAPolicy.js"
)
BACKGROUND_CORTEX_FOLLOW_UP_SERVICE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "BackgroundCortexFollowUpService.js"
)
SYNC_AGENTS_SCRIPT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "scripts"
    / "viventium-sync-agents.js"
)
CONFIG_COMPILER = REPO_ROOT / "scripts" / "viventium" / "config_compiler.py"
LIBRECHAT_YAML = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "librechat.yaml"
)


def _load_activation_by_agent_id() -> dict[str, dict]:
    bundle = yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    cortices = bundle["mainAgent"]["background_cortices"]
    return {entry["agent_id"]: entry["activation"] for entry in cortices}


def _load_background_agents_by_id() -> dict[str, dict]:
    bundle = yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in bundle["backgroundAgents"]}


def test_productivity_activation_models_follow_documented_local_recommendation() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    for agent_id in (
        "agent_viventium_online_tool_use_95aeb3",
        "agent_8Y1d7JNhpubtvzYz3hvEv",
    ):
        activation = activation_by_agent_id[agent_id]
        assert activation["provider"] == "groq"
        assert activation["model"] == "meta-llama/llama-4-scout-17b-16e-instruct"
        assert isinstance(activation["fallbacks"], list)
        assert len(activation["fallbacks"]) >= 2


def test_source_of_truth_bundle_does_not_embed_owner_specific_identity() -> None:
    bundle = yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    owner = bundle["meta"]["user"]

    assert owner["email"] == "user@viventium.local"
    assert owner["id"] == "placeholder-owner"


def test_productivity_activation_configs_define_explicit_scope_keys() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    assert (
        activation_by_agent_id["agent_viventium_online_tool_use_95aeb3"]["intent_scope"]
        == "productivity_ms365"
    )
    assert (
        activation_by_agent_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["intent_scope"]
        == "productivity_google_workspace"
    )


def test_productivity_activation_prompts_define_chat_format_negative_boundary() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    for agent_id in (
        "agent_viventium_online_tool_use_95aeb3",
        "agent_8Y1d7JNhpubtvzYz3hvEv",
    ):
        prompt = activation_by_agent_id[agent_id]["prompt"].lower()

        assert "primary decision rule" in prompt
        assert 'return "should_activate": false when' in prompt
        assert "activate (true) when all of these are true" in prompt
        assert "chat" in prompt
        assert "direct_ok" in prompt
        assert "respond only with yes" in prompt
        assert "capability question" in prompt


def test_productivity_activation_prompts_name_their_owned_scopes() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    ms365_prompt = activation_by_agent_id["agent_viventium_online_tool_use_95aeb3"]["prompt"]
    google_prompt = activation_by_agent_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["prompt"]

    assert "PRIMARY DECISION RULE:" in ms365_prompt
    assert "SCOPE:" in ms365_prompt
    assert "Microsoft 365 / Outlook / OneDrive" in ms365_prompt

    assert "PRIMARY DECISION RULE:" in google_prompt
    assert "SCOPE:" in google_prompt
    assert "Google Workspace" in google_prompt


def test_productivity_activation_configs_define_provider_fallback_chain() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    for agent_id in (
        "agent_viventium_online_tool_use_95aeb3",
        "agent_8Y1d7JNhpubtvzYz3hvEv",
    ):
        activation = activation_by_agent_id[agent_id]
        fallbacks = activation["fallbacks"]
        assert isinstance(fallbacks, list)
        assert len(fallbacks) >= 2
        assert all(isinstance(entry.get("provider"), str) and entry["provider"] for entry in fallbacks)
        assert all(isinstance(entry.get("model"), str) and entry["model"] for entry in fallbacks)


def test_productivity_activation_prompts_keep_parallel_provider_rule() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    ms365_prompt = activation_by_agent_id["agent_viventium_online_tool_use_95aeb3"]["prompt"]
    google_prompt = activation_by_agent_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["prompt"]

    assert "Another cortex may activate in parallel for the Google portion" in ms365_prompt
    assert "Another cortex may activate in parallel for the Microsoft portion" in google_prompt
    assert "check both Outlook and Gmail and summarize anything urgent" in ms365_prompt
    assert "check both Outlook and Gmail and summarize anything urgent" in google_prompt


def test_background_agent_execution_models_match_launch_bundle_mix() -> None:
    agents_by_id = _load_background_agents_by_id()

    expected = {
        "agent_viventium_background_analysis_95aeb3": ("anthropic", "claude-sonnet-4-6"),
        "agent_viventium_confirmation_bias_95aeb3": ("anthropic", "claude-sonnet-4-6"),
        "agent_viventium_red_team_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_deep_research_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_online_tool_use_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_parietal_cortex_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_pattern_recognition_95aeb3": ("anthropic", "claude-sonnet-4-6"),
        "agent_viventium_emotional_resonance_95aeb3": ("anthropic", "claude-sonnet-4-6"),
        "agent_viventium_strategic_planning_95aeb3": ("anthropic", "claude-opus-4-7"),
        "agent_viventium_support_95aeb3": ("anthropic", "claude-sonnet-4-6"),
        "agent_8Y1d7JNhpubtvzYz3hvEv": ("openAI", "gpt-5.4"),
    }

    for agent_id, (provider, model) in expected.items():
        agent = agents_by_id[agent_id]
        assert agent["provider"] == provider
        assert agent["model"] == model
        assert agent["model_parameters"]["model"] == model


def test_deep_research_ships_with_web_search_and_openai_reasoning_effort() -> None:
    agents_by_id = _load_background_agents_by_id()
    deep_research = agents_by_id["agent_viventium_deep_research_95aeb3"]

    assert "web_search" in deep_research["tools"]
    assert deep_research["model_parameters"]["reasoning_effort"] == "xhigh"
    assert "thinkingBudget" not in deep_research["model_parameters"]


def test_background_agent_execution_models_stay_within_launch_ready_families() -> None:
    agents_by_id = _load_background_agents_by_id()

    allowed = {
        ("anthropic", "claude-sonnet-4-6"),
        ("anthropic", "claude-opus-4-7"),
        ("openAI", "gpt-5.4"),
    }

    for agent in agents_by_id.values():
        provider_model = (agent["provider"], agent["model"])
        assert provider_model in allowed


def test_background_agents_do_not_drift_back_to_deprecated_runtime_models() -> None:
    bundle = yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    serialized = yaml.safe_dump(bundle, sort_keys=True)
    sync_source = SYNC_AGENTS_SCRIPT.read_text(encoding="utf-8")
    compiler_source = CONFIG_COMPILER.read_text(encoding="utf-8")
    assert "gpt-4o" not in serialized
    assert "gpt-4o-mini" not in serialized
    assert "llama-3.3-70b-versatile" not in serialized
    assert "private-owner@example.com" not in sync_source
    assert "llama-3.3-70b-versatile" not in compiler_source
    assert "llama-3.1-8b-instant" not in compiler_source


def test_productivity_and_help_instructions_do_not_contradict_parallel_tooling() -> None:
    agents_by_id = _load_background_agents_by_id()

    ms365_instructions = agents_by_id["agent_viventium_online_tool_use_95aeb3"]["instructions"]
    google_instructions = agents_by_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["instructions"]
    support_agent = agents_by_id["agent_viventium_support_95aeb3"]
    support_instructions = support_agent["instructions"]

    assert "handled by the main agent directly" not in ms365_instructions
    assert "another cortex may activate in parallel for the google portion" in ms365_instructions.lower()
    assert "another cortex may activate in parallel for the microsoft portion" in google_instructions.lower()
    assert "you have no tools" not in support_instructions.lower()
    assert "if a search tool is available" in support_instructions.lower()
    assert "verify viventium usage/help information" in support_instructions.lower()
    assert support_agent["tools"] == ["web_search"]


def test_runtime_activation_plumbing_stays_config_driven_and_avoids_illegal_title_hardcoding() -> None:
    background_cortex_source = BACKGROUND_CORTEX_SERVICE.read_text(encoding="utf-8")
    brewing_hold_source = BREWING_HOLD_SERVICE.read_text(encoding="utf-8")
    productivity_context_source = PRODUCTIVITY_SPECIALIST_CONTEXT.read_text(encoding="utf-8")
    voice_phase_a_policy_source = VOICE_PHASE_A_POLICY.read_text(encoding="utf-8")

    assert "activation?.intent_scope" in background_cortex_source
    assert "resolveProductivitySpecialistScope" in background_cortex_source
    assert "titleAndScope.includes" not in background_cortex_source
    assert "productivity tool agent" not in background_cortex_source
    assert "PRODUCTIVITY_ACTIVATION_SCOPES" not in background_cortex_source
    assert "ActivationScopeKey:" in background_cortex_source
    assert "resolveDeterministicLiveEmailActivation" not in background_cortex_source
    assert "reduceMessagesForProductivitySpecialist" not in background_cortex_source
    assert "resolveProductivitySpecialistScope" in brewing_hold_source
    assert "hasExplicitProductivityRequest" not in brewing_hold_source
    assert "['online_tool_use', 'google']" not in brewing_hold_source
    assert "VIVENTIUM_TOOL_CORTEX_HOLD_AGENT_IDS" not in brewing_hold_source
    assert "cortex?.activationScope" not in brewing_hold_source
    assert "cortex?.activation_scope" not in brewing_hold_source
    assert "cortex?.intent_scope" not in brewing_hold_source
    assert "isToolHoldCandidate(cortex)" in voice_phase_a_policy_source
    assert "pseudoActivations" not in voice_phase_a_policy_source
    assert "name: 'Google'" not in voice_phase_a_policy_source
    assert "name: 'MS365'" not in voice_phase_a_policy_source
    assert "instructions.includes('do not reference memory systems or assumed prior context')" not in (
        productivity_context_source
    )
    assert "hasExplicitProductivityRequest" not in productivity_context_source
    assert "reduceMessagesForProductivitySpecialist" not in productivity_context_source
    assert "agent?.intent_scope" not in productivity_context_source
    assert "extractLegacyProductivityScopeHeader" in productivity_context_source
    assert "scopeHeaderPattern" in productivity_context_source
    assert "normalized === 'gmail'" not in productivity_context_source
    assert "normalized === 'google'" not in productivity_context_source
    assert "normalized === 'outlook'" not in productivity_context_source
    assert "normalized === 'microsoft365'" not in productivity_context_source
    assert "startsWith('productivity_')" in productivity_context_source
    assert "agentForRun.intent_scope = activationScope" not in background_cortex_source


def test_background_follow_up_fallbacks_stay_on_launch_ready_model_families() -> None:
    follow_up_source = BACKGROUND_CORTEX_FOLLOW_UP_SERVICE.read_text(encoding="utf-8")

    assert "DEFAULT_MODELS" in follow_up_source
    assert "normalizeRuntimeProvider" in follow_up_source
    assert "gpt-4o" not in follow_up_source
    assert "gpt-4o-mini" not in follow_up_source
    assert "claude-3" not in follow_up_source
