from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from scripts.viventium.prompt_registry import load_and_resolve_prompt_refs


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
AGENT_CLIENT_CONTROLLER = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "controllers"
    / "agents"
    / "client.js"
)
RUNTIME_CARD_GUARD_PROMPT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "prompts"
    / "main"
    / "background_cortex_runtime_card_guard.md"
)
SYNC_AGENTS_SCRIPT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "scripts"
    / "viventium-sync-agents.js"
)
CONNECTED_ACCOUNTS_HANDOFF_PROVISIONER = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "scripts"
    / "viventium-provision-connected-accounts-agent.js"
)
CONFIG_COMPILER = REPO_ROOT / "scripts" / "viventium" / "config_compiler.py"
LIBRECHAT_YAML = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "librechat.yaml"
)


def _load_activation_by_agent_id() -> dict[str, dict]:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
    cortices = bundle["mainAgent"]["background_cortices"]
    return {entry["agent_id"]: entry["activation"] for entry in cortices}


def _load_background_agents_by_id() -> dict[str, dict]:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
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
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
    owner = bundle["meta"]["user"]

    assert owner["email"] == "user@example.com"
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


def test_broker_first_local_baseline_disables_retired_main_background_cortices() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()
    agents_by_id = _load_background_agents_by_id()

    retired_main_background_cortices = {
        "agent_viventium_deep_research_95aeb3": "web_search",
        "agent_viventium_online_tool_use_95aeb3": "sys__server__sys_mcp_ms-365",
        "agent_8Y1d7JNhpubtvzYz3hvEv": "sys__server__sys_mcp_google_workspace",
    }

    for agent_id, required_tool in retired_main_background_cortices.items():
        assert activation_by_agent_id[agent_id]["enabled"] is False
        assert required_tool in set(agents_by_id[agent_id]["tools"])

    assert (
        activation_by_agent_id["agent_viventium_confirmation_bias_95aeb3"]["enabled"] is True
    )


def test_confirmation_bias_is_compact_no_tool_review() -> None:
    agents_by_id = _load_background_agents_by_id()
    confirmation_bias = agents_by_id["agent_viventium_confirmation_bias_95aeb3"]
    instructions = confirmation_bias["instructions"].lower()

    assert confirmation_bias["tools"] == []
    assert "no external tools" in instructions
    assert "do not assess inbox" in instructions
    assert "do not claim to access email, calendar, files, web search" in instructions
    assert "google/ms365 services" in instructions


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
        assert fallbacks[0] == {"provider": "xai", "model": "grok-4.20-non-reasoning"}
        assert len(fallbacks) >= 3
        assert all(isinstance(entry.get("provider"), str) and entry["provider"] for entry in fallbacks)
        assert all(isinstance(entry.get("model"), str) and entry["model"] for entry in fallbacks)


def test_productivity_execution_agents_ship_owned_mcp_tools() -> None:
    agents_by_id = _load_background_agents_by_id()

    ms365_tools = set(agents_by_id["agent_viventium_online_tool_use_95aeb3"]["tools"])
    google_tools = set(agents_by_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["tools"])

    assert {
        "sys__server__sys_mcp_ms-365",
        "list-mail-messages_mcp_ms-365",
        "get-mail-message_mcp_ms-365",
        "list-mail-folder-messages_mcp_ms-365",
        "list-calendar-events_mcp_ms-365",
        "get-calendar-event_mcp_ms-365",
        "list-folder-files_mcp_ms-365",
        "download-onedrive-file-content_mcp_ms-365",
        "get-excel-range_mcp_ms-365",
        "search-query_mcp_ms-365",
    } <= ms365_tools
    assert {
        "sys__server__sys_mcp_google_workspace",
        "search_gmail_messages_mcp_google_workspace",
        "get_gmail_message_content_mcp_google_workspace",
        "get_gmail_messages_content_batch_mcp_google_workspace",
        "get_gmail_thread_content_mcp_google_workspace",
        "list_calendars_mcp_google_workspace",
        "get_events_mcp_google_workspace",
        "search_drive_files_mcp_google_workspace",
        "get_drive_file_content_mcp_google_workspace",
        "search_docs_mcp_google_workspace",
        "get_doc_content_mcp_google_workspace",
        "read_sheet_values_mcp_google_workspace",
    } <= google_tools
    assert not any("_mcp_google_workspace" in tool for tool in ms365_tools)
    assert not any("_mcp_ms-365" in tool for tool in google_tools)
    assert "file_search" not in ms365_tools
    assert "file_search" not in google_tools


def test_main_agent_does_not_ship_provider_productivity_mcp_tools() -> None:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
    main_tools = set(bundle["mainAgent"]["tools"])

    assert not any("_mcp_google_workspace" in tool for tool in main_tools)
    assert not any("_mcp_ms-365" in tool for tool in main_tools)


def test_connected_accounts_handoff_provisioner_is_supported_confirmed_write_and_surgical() -> None:
    source = CONNECTED_ACCOUNTS_HANDOFF_PROVISIONER.read_text(encoding="utf-8")

    assert "VIVENTIUM_ENABLE_RETIRED_CONNECTED_ACCOUNTS_HANDOFF" not in source
    assert "Historical provisioner" not in source
    assert "agent_viventium_connected_accounts_95aeb3" in source
    assert "Main_To_ConnectedAccounts" in source
    assert "const READ_TOOLS" in source
    assert "const WRITE_TOOLS" in source
    assert "const CONNECTED_ACCOUNT_TOOLS" in source
    assert "getAgent" in source
    assert "UPDATED', AGENT_ID" in source
    assert "ACL_GRANTED" in source
    assert "const existingEdges" in source
    assert "existingEdges.filter" in source
    assert "existingEdge?.promptKey !== edge.promptKey" in source
    assert "updateAgent({ id: MAIN_ID }, { edges: mergedEdges })" in source
    assert "const FALLBACK_LLM_PROVIDER = 'openAI'" in source
    assert "const FALLBACK_LLM_MODEL = 'gpt-5.4'" in source
    assert "fallback_llm_provider: FALLBACK_LLM_PROVIDER" in source
    assert "fallback_llm_model: FALLBACK_LLM_MODEL" in source
    assert "fallback_llm_model_parameters: FALLBACK_LLM_MODEL_PARAMETERS" in source
    assert "Do not dump raw API fields, account email addresses, aliases" in source
    assert "Do not expose account email addresses, aliases, OAuth details" in source
    assert "Default to read-only inspection" in source
    assert "act only when the user explicitly asked for that external action" in source
    assert "Do not say this path is read-only if the relevant write tool is present" in source
    assert "Ask for confirmation before any external write" in source

    expected_read_tools = {
        "sys__server__sys_mcp_google_workspace",
        "search_gmail_messages_mcp_google_workspace",
        "get_gmail_message_content_mcp_google_workspace",
        "get_gmail_messages_content_batch_mcp_google_workspace",
        "get_gmail_thread_content_mcp_google_workspace",
        "list_calendars_mcp_google_workspace",
        "get_events_mcp_google_workspace",
        "search_drive_files_mcp_google_workspace",
        "get_drive_file_content_mcp_google_workspace",
        "search_docs_mcp_google_workspace",
        "get_doc_content_mcp_google_workspace",
        "read_sheet_values_mcp_google_workspace",
        "sys__server__sys_mcp_ms-365",
        "list-mail-messages_mcp_ms-365",
        "get-mail-message_mcp_ms-365",
        "list-mail-folder-messages_mcp_ms-365",
        "list-calendar-events_mcp_ms-365",
        "get-calendar-event_mcp_ms-365",
        "list-folder-files_mcp_ms-365",
        "download-onedrive-file-content_mcp_ms-365",
        "get-excel-range_mcp_ms-365",
        "search-query_mcp_ms-365",
    }
    expected_write_tools = {
        "send_gmail_message_mcp_google_workspace",
        "draft_gmail_message_mcp_google_workspace",
        "create_event_mcp_google_workspace",
        "modify_event_mcp_google_workspace",
        "create-draft-email_mcp_ms-365",
        "send-mail_mcp_ms-365",
        "create-specific-calendar-event_mcp_ms-365",
        "update-specific-calendar-event_mcp_ms-365",
        "create-calendar-event_mcp_ms-365",
        "update-calendar-event_mcp_ms-365",
    }
    forbidden_connected_accounts_tools = {
        "create_drive_file_mcp_google_workspace",
        "upload-file-content_mcp_ms-365",
        "delete-onedrive-file_mcp_ms-365",
        "delete_event_mcp_google_workspace",
        "move-mail-message_mcp_ms-365",
        "delete-mail-message_mcp_ms-365",
        "delete-calendar-event_mcp_ms-365",
        "delete-specific-calendar-event_mcp_ms-365",
    }

    for tool in expected_read_tools:
        assert tool in source
    for tool in expected_write_tools:
        assert tool in source
    for tool in forbidden_connected_accounts_tools:
        assert tool not in source


def test_connected_accounts_handoff_is_source_owned_with_confirmed_email_calendar_writes() -> None:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )

    connected_agent_id = "agent_viventium_connected_accounts_95aeb3"
    edges = bundle["mainAgent"].get("edges", [])
    edge = next(
        (
            candidate
            for candidate in edges
            if candidate.get("promptKey") == "Main_To_ConnectedAccounts"
        ),
        None,
    )
    assert edge is not None
    assert edge["edgeType"] == "handoff"
    assert edge["to"] == connected_agent_id
    assert "Default to read-only inspection" in edge["prompt"]
    assert "explicit user confirmation" in edge["prompt"]
    assert "Do not claim this path is read-only" in edge["prompt"]

    handoff_agents = {entry["id"]: entry for entry in bundle.get("handoffAgents", [])}
    assert connected_agent_id in handoff_agents
    connected = handoff_agents[connected_agent_id]

    assert connected["name"] == "Connected Accounts"
    assert connected["provider"] == "anthropic"
    assert connected["model"] == "claude-opus-4-8"
    assert connected["fallback_llm_provider"] == "openAI"
    assert connected["fallback_llm_model"] == "gpt-5.4"
    assert "Default to read-only inspection" in connected["instructions"]
    assert "act only when the user explicitly asked for that external action" in connected[
        "instructions"
    ]
    assert "Do not say this path is read-only if the relevant write tool is present" in connected[
        "instructions"
    ]

    tools = set(connected["tools"])
    assert {
        "sys__server__sys_mcp_google_workspace",
        "search_gmail_messages_mcp_google_workspace",
        "get_gmail_messages_content_batch_mcp_google_workspace",
        "sys__server__sys_mcp_ms-365",
        "list-mail-messages_mcp_ms-365",
        "list-calendar-events_mcp_ms-365",
    } <= tools
    assert {
        "send_gmail_message_mcp_google_workspace",
        "draft_gmail_message_mcp_google_workspace",
        "create_event_mcp_google_workspace",
        "modify_event_mcp_google_workspace",
        "create-draft-email_mcp_ms-365",
        "send-mail_mcp_ms-365",
        "create-specific-calendar-event_mcp_ms-365",
        "update-specific-calendar-event_mcp_ms-365",
        "create-calendar-event_mcp_ms-365",
        "update-calendar-event_mcp_ms-365",
    } <= tools
    assert not {
        "upload-file-content_mcp_ms-365",
        "delete-onedrive-file_mcp_ms-365",
        "create_drive_file_mcp_google_workspace",
        "delete_event_mcp_google_workspace",
        "move-mail-message_mcp_ms-365",
        "delete-mail-message_mcp_ms-365",
        "delete-calendar-event_mcp_ms-365",
        "delete-specific-calendar-event_mcp_ms-365",
    } & tools


def test_agent_sync_preserves_handoff_targets_and_canonical_acl_grants() -> None:
    source = SYNC_AGENTS_SCRIPT.read_text(encoding="utf-8")

    assert "handoffAgents" in source
    assert "collectEdgeTargetAgentIds" in source
    assert "Handoff agent missing" in source
    assert "ResourceType.REMOTE_AGENT" in source
    assert "AccessRoleIds.AGENT_OWNER" in source
    assert "AccessRoleIds.REMOTE_AGENT_OWNER" in source
    assert "grantPermission({" in source
    assert "principalModel: PrincipalModel.USER" not in source


def test_main_agent_does_not_defer_productivity_checks_to_background_cortices() -> None:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
    instructions = bundle["mainAgent"]["instructions"].lower()

    assert "do not promise that a background cortex will check gmail" in instructions
    assert "do not promise that a background cortex will check outlook" in instructions
    assert "do not defer the check to background cortices" in instructions
    assert "use the connected accounts handoff for immediate checks" in instructions
    assert "first get explicit user confirmation" in instructions
    assert "including the connected accounts handoff when it has the required write tool" in instructions
    assert "write-capable connected-account path" in instructions
    assert "glasshive host-signed broker path" in instructions
    assert "if no write-capable path is available" in instructions
    assert "creating/updating calendar events" in instructions
    assert "deleting/moving/archive/mark-read mail" in instructions
    assert "sharing/permission changes" in instructions
    assert "use a brokered worker when the request needs delegated/long-running glasshive work" in instructions
    assert "memory is background" in instructions
    assert "verified current-run google connector/tool evidence" in instructions
    assert "verified current-run microsoft connector/tool evidence" in instructions


def test_runtime_card_guard_fallback_matches_productivity_live_data_rule() -> None:
    agent_client_source = AGENT_CLIENT_CONTROLLER.read_text(encoding="utf-8").lower()

    assert "background_cortex_runtime_card_guard_fallback" in agent_client_source
    assert "do not tell the user that background cortices will check gmail" in agent_client_source
    assert "outlook, ms365, google workspace, the web, or any live connector" in agent_client_source
    assert "verified current-run tool evidence, a brokered worker" in agent_client_source


def test_runtime_card_guard_source_prompt_matches_inline_fallback() -> None:
    prompt_source = RUNTIME_CARD_GUARD_PROMPT.read_text(encoding="utf-8")
    _, _, prompt_body = prompt_source.partition("---\n")
    _, _, prompt_body = prompt_body.partition("---\n")

    agent_client_source = AGENT_CLIENT_CONTROLLER.read_text(encoding="utf-8")
    match = re.search(
        r"const BACKGROUND_CORTEX_RUNTIME_CARD_GUARD_FALLBACK = \[(.*?)\]\.join\('\\n'\);",
        agent_client_source,
        re.DOTALL,
    )
    assert match is not None

    fallback_lines: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fallback_lines.append(ast.literal_eval(stripped.rstrip(",")))

    normalize = lambda text: "\n".join(line.rstrip() for line in text.strip().splitlines())
    assert normalize(prompt_body) == normalize("\n".join(fallback_lines))


def test_productivity_direct_action_surfaces_are_same_scope_forward_contracts() -> None:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
    policy = bundle["config"]["viventium"]["background_cortices"]["activation_policy"]
    surfaces = policy["direct_action_mcp_servers"]
    intent_scopes = {
        cortex["activation"]["intent_scope"]
        for cortex in bundle["mainAgent"]["background_cortices"]
        if cortex.get("activation", {}).get("intent_scope", "").startswith("productivity_")
    }

    productivity_surfaces = [
        surface
        for surface in surfaces
        if str(surface.get("scope_key", "")).startswith("productivity_")
    ]
    assert productivity_surfaces
    for surface in productivity_surfaces:
        assert surface["scope_key"] in intent_scopes
        assert surface["same_scope_background_allowed"] is True
        assert "when this mcp is connected to the main agent" in surface["owns"].lower()
        assert "available to the main agent" not in surface["owns"].lower()


def test_productivity_activation_prompts_keep_parallel_provider_rule() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    ms365_prompt = activation_by_agent_id["agent_viventium_online_tool_use_95aeb3"]["prompt"]
    google_prompt = activation_by_agent_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["prompt"]

    assert "Another cortex may activate in parallel for the Google portion" in ms365_prompt
    assert "Another cortex may activate in parallel for the Microsoft portion" in google_prompt
    assert "check both Outlook and Gmail and summarize anything urgent" in ms365_prompt
    assert "check both Outlook and Gmail and summarize anything urgent" in google_prompt


def test_productivity_activation_prompts_cover_generic_plural_inbox_sweeps() -> None:
    activation_by_agent_id = _load_activation_by_agent_id()

    ms365_prompt = activation_by_agent_id["agent_viventium_online_tool_use_95aeb3"]["prompt"]
    google_prompt = activation_by_agent_id["agent_8Y1d7JNhpubtvzYz3hvEv"]["prompt"]

    for prompt, provider in (
        (ms365_prompt, "Microsoft"),
        (google_prompt, "Google"),
    ):
        assert "check my inboxes" in prompt
        assert "check my email accounts" in prompt
        assert "check all my inboxes for anything urgent" in prompt
        assert "with no provider restriction" in prompt
        assert f"true for the {provider}" in prompt

    assert "check my Gmail inbox; ignore Outlook" in ms365_prompt
    assert "check my Outlook inbox; ignore Gmail" in google_prompt


def test_background_agent_execution_models_match_launch_bundle_mix() -> None:
    agents_by_id = _load_background_agents_by_id()

    expected = {
        "agent_viventium_background_analysis_95aeb3": ("anthropic", "claude-sonnet-4-5"),
        "agent_viventium_confirmation_bias_95aeb3": ("anthropic", "claude-sonnet-4-5"),
        "agent_viventium_red_team_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_deep_research_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_online_tool_use_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_parietal_cortex_95aeb3": ("openAI", "gpt-5.4"),
        "agent_viventium_pattern_recognition_95aeb3": ("anthropic", "claude-sonnet-4-5"),
        "agent_viventium_emotional_resonance_95aeb3": ("anthropic", "claude-sonnet-4-5"),
        "agent_viventium_strategic_planning_95aeb3": ("anthropic", "claude-opus-4-8"),
        "agent_viventium_support_95aeb3": ("anthropic", "claude-sonnet-4-5"),
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
        ("anthropic", "claude-sonnet-4-5"),
        ("anthropic", "claude-opus-4-8"),
        ("openAI", "gpt-5.4"),
    }

    for agent in agents_by_id.values():
        provider_model = (agent["provider"], agent["model"])
        assert provider_model in allowed


def test_background_agents_do_not_drift_back_to_deprecated_runtime_models() -> None:
    bundle = load_and_resolve_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )
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
