from __future__ import annotations

from pathlib import Path

import yaml

from scripts.viventium.prompt_registry import load_and_resolve_prompt_refs


ROOT = Path(__file__).resolve().parents[2]
SOURCE_OF_TRUTH = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.viventium-agents.yaml"
)
VOICE_CALL_PROMPT = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "prompts"
    / "surface"
    / "voice_call.md"
)
AGENT_CALLBACKS = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "controllers"
    / "agents"
    / "callbacks.js"
)

MAIN_ID = "agent_viventium_main_95aeb3"
DEEP_MEMORY_ID = "agent_viventium_deep_memory_95aeb3"
REALITY_CHECK_ID = "agent_viventium_reality_check_95aeb3"
RED_TEAM_ID = "agent_viventium_red_team_95aeb3"
CONNECTED_ACCOUNTS_ID = "agent_viventium_connected_accounts_95aeb3"

ANTI_SYCOPHANCY_EDGE_CONTRACT = {
    (MAIN_ID, REALITY_CHECK_ID, "handoff"),
    (REALITY_CHECK_ID, MAIN_ID, "handoff"),
    (MAIN_ID, RED_TEAM_ID, "handoff"),
    (RED_TEAM_ID, MAIN_ID, "handoff"),
}


def _load_raw() -> dict:
    return yaml.safe_load(SOURCE_OF_TRUTH.read_text(encoding="utf-8"))


def _load_resolved() -> dict:
    return load_and_resolve_prompt_refs(_load_raw())


def _by_id(rows: list[dict], agent_id: str) -> dict:
    matches = [row for row in rows if row.get("id") == agent_id]
    assert len(matches) == 1, f"Expected exactly one source-owned agent {agent_id}"
    return matches[0]


def test_anti_012_librechat_callback_callsites_stay_inside_fork_replay_markers() -> None:
    source = AGENT_CALLBACKS.read_text(encoding="utf-8")
    needles = (
        "markMainProviderAttemptStart(req, metadata);",
        "markMainProviderFirstOutput(req, metadata, { kind: 'provider_token' });",
        "markMainProviderFirstOutput(req, metadata, { kind: 'visible_text_delta' });",
    )

    for needle in needles:
        start = 0
        found = 0
        while (index := source.find(needle, start)) >= 0:
            found += 1
            preceding = source[:index]
            assert preceding.rfind("VIVENTIUM START") > preceding.rfind("VIVENTIUM END"), (
                f"ANTI-012 callback callsite escaped fork replay markers: {needle}"
            )
            start = index + len(needle)
        assert found > 0, f"Missing ANTI-012 callback callsite: {needle}"


def test_deep_memory_is_one_always_on_background_cortex_with_recall_access() -> None:
    bundle = _load_resolved()
    main = bundle["mainAgent"]
    agent = _by_id(bundle["backgroundAgents"], DEEP_MEMORY_ID)
    cortex_matches = [
        row for row in main["background_cortices"] if row.get("agent_id") == DEEP_MEMORY_ID
    ]

    assert len(cortex_matches) == 1
    activation = cortex_matches[0]["activation"]
    assert activation == {"enabled": True, "mode": "always"}
    assert "file_search" in agent["tools"]
    assert agent["conversation_recall_agent_only"] is False
    assert agent["provider"] == "openAI"
    assert agent["model"] == "gpt-5.6-terra"
    assert agent["model_parameters"]["resendFiles"] is True
    assert agent["fallback_llm_provider"] == "glasshive-harness"
    assert agent["fallback_llm_model"] == "codex-cli:gpt-5.6-sol"
    assert agent["fallback_llm_model_parameters"] == {
        "model": "codex-cli:gpt-5.6-sol",
        "reasoning_effort": "medium",
    }
    assert agent["hide_sequential_outputs"] is False
    assert isinstance(agent["instructions"], str) and agent["instructions"].strip()
    instructions = agent["instructions"].lower()
    assert "do not announce, narrate, or promise a search" in instructions
    assert "missing evidence is not a contradiction" in instructions
    assert "prior assistant statements" in instructions
    assert "leads only, not memory evidence" in instructions
    assert "do not answer the user's question" in instructions
    assert "never report a non-finding" in instructions


def test_reality_check_is_one_full_life_glasshive_handoff_with_evidence_tools() -> None:
    bundle = _load_resolved()
    reality = _by_id(bundle["handoffAgents"], REALITY_CHECK_ID)

    assert reality["provider"] == "glasshive-harness"
    assert reality["glasshive_options"] == {
        "workspace": {"mode": "life"},
        "access": "full",
        "fallback_model": "claude-code:opus",
        "fallback_reasoning_effort": "high",
    }
    assert reality.get("fallback_llm_model") in (None, "")
    assert reality.get("fallback_llm_provider") in (None, "")
    assert {"file_search", "web_search"} <= set(reality["tools"])
    assert reality["model_parameters"]["resendFiles"] is True
    assert reality["hide_sequential_outputs"] is False
    assert isinstance(reality["instructions"], str) and reality["instructions"].strip()
    instructions = reality["instructions"].lower()
    assert "normal clickable markdown links" in instructions
    assert "provider-internal citation" in instructions
    assert "opaque source ids" in instructions
    assert "usable source links" in instructions


def test_existing_red_team_identity_is_shared_by_background_and_foreground_paths() -> None:
    bundle = _load_resolved()
    main = bundle["mainAgent"]
    red_team = _by_id(bundle["backgroundAgents"], RED_TEAM_ID)

    assert sum(
        row.get("agent_id") == RED_TEAM_ID for row in main["background_cortices"]
    ) == 1
    assert sum(
        edge.get("from") == MAIN_ID
        and edge.get("to") == RED_TEAM_ID
        and edge.get("edgeType") == "handoff"
        for edge in main["edges"]
    ) == 1
    assert not [
        agent
        for agent in bundle.get("handoffAgents", [])
        if agent.get("name") == red_team["name"] or agent.get("id") == RED_TEAM_ID
    ]
    assert red_team["model_parameters"]["resendFiles"] is True


def test_anti_sycophancy_graph_has_exactly_four_bounded_visible_handoff_edges() -> None:
    bundle = _load_resolved()
    main = bundle["mainAgent"]
    anti_edges = [
        edge
        for edge in main["edges"]
        if (edge.get("from"), edge.get("to"), edge.get("edgeType"))
        in ANTI_SYCOPHANCY_EDGE_CONTRACT
    ]

    assert len(anti_edges) == 4
    assert {
        (edge["from"], edge["to"], edge["edgeType"]) for edge in anti_edges
    } == ANTI_SYCOPHANCY_EDGE_CONTRACT
    assert all("prompt" not in edge and "promptKey" not in edge for edge in anti_edges)
    assert all(str(edge.get("description") or "").strip() for edge in anti_edges)
    assert main["recursion_limit"] == 40
    assert main["hide_sequential_outputs"] is False


def test_every_main_handoff_uses_shared_history_without_manual_transfer_payload() -> None:
    bundle = _load_resolved()
    main = bundle["mainAgent"]
    outgoing = [
        edge
        for edge in main["edges"]
        if edge.get("from") == MAIN_ID and edge.get("edgeType") == "handoff"
    ]

    assert {edge.get("to") for edge in outgoing} == {
        REALITY_CHECK_ID,
        RED_TEAM_ID,
        CONNECTED_ACCOUNTS_ID,
    }
    assert all("prompt" not in edge and "promptKey" not in edge for edge in outgoing)

    connected_accounts = _by_id(bundle["handoffAgents"], CONNECTED_ACCOUNTS_ID)
    instructions = connected_accounts["instructions"].lower()
    assert "when the main agent hands a request to you" in instructions
    assert "satisfy it directly with your connected tools" in instructions


def test_foreground_consult_prompts_own_return_and_anti_loop_behavior() -> None:
    bundle = _load_resolved()
    main = bundle["mainAgent"]
    reality = _by_id(bundle["handoffAgents"], REALITY_CHECK_ID)
    red_team = _by_id(bundle["backgroundAgents"], RED_TEAM_ID)

    assert "do not send the same turn back to reality check" in main["instructions"].lower()
    assert "never hand off directly from main to red team" in main["instructions"].lower()
    assert "main's own web search is not a substitute" in main["instructions"].lower()
    assert "tool availability is not permission to consult again" in main[
        "instructions"
    ].lower()
    assert "already appears after the current user request" in main[
        "instructions"
    ].lower()
    assert "return control to the main agent exactly once" in reality["instructions"].lower()
    assert "return control to the main agent exactly once" in red_team["instructions"].lower()
    assert "never answer as the final speaker" in reality["instructions"].lower()
    assert "never answer as the final speaker" in red_team["instructions"].lower()

    outgoing = {
        edge["to"]: edge["description"].lower()
        for edge in main["edges"]
        if edge.get("from") == MAIN_ID
        and edge.get("to") in {REALITY_CHECK_ID, RED_TEAM_ID}
    }
    assert set(outgoing) == {REALITY_CHECK_ID, RED_TEAM_ID}
    assert all("at most once per user turn" in description for description in outgoing.values())


def test_deep_research_retains_web_search() -> None:
    bundle = _load_resolved()
    deep_research = _by_id(
        bundle["backgroundAgents"], "agent_viventium_deep_research_95aeb3"
    )

    assert "web_search" in deep_research["tools"]


def test_background_cortices_cannot_duplicate_main_direct_actions() -> None:
    bundle = _load_resolved()
    direct_surfaces = bundle["config"]["viventium"]["background_cortices"][
        "activation_policy"
    ]["direct_action_mcp_servers"]
    scoped_surfaces = [surface for surface in direct_surfaces if surface.get("scope_key")]

    assert scoped_surfaces, "Expected structured direct-action ownership declarations"
    assert all(
        surface.get("same_scope_background_allowed") is False
        for surface in scoped_surfaces
    ), "Background cortices must remain evidence-only for Main-owned action scopes"


def test_prompt_refs_resolve_and_voice_does_not_start_foreground_consults() -> None:
    bundle = _load_resolved()
    main_instructions = bundle["mainAgent"]["instructions"]
    voice_instructions = VOICE_CALL_PROMPT.read_text(encoding="utf-8").lower()

    assert isinstance(main_instructions, str) and main_instructions.strip()
    assert "do not start a foreground reality check or red team handoff during a live voice call" in (
        main_instructions.lower()
    )
    # Surface prompt stays generic: it may own the live-voice foreground-work boundary, while
    # consultant identities and graph mechanics remain in Main's graph-aware prompt.
    for forbidden in ("reality check", "red team", "handoff"):
        assert forbidden not in voice_instructions


def test_voice_prompt_keeps_unsolicited_research_out_of_the_immediate_answer() -> None:
    voice_instructions = VOICE_CALL_PROMPT.read_text(encoding="utf-8").lower()

    assert "unless the user explicitly asks for a lookup or tool action now" in voice_instructions
    assert "do not start foreground research or tool work" in voice_instructions
    assert "give the best bounded immediate answer" in voice_instructions
    assert "state what remains unverified" in voice_instructions
    assert "nonblocking background work" in voice_instructions
    assert "the current voice task may do it" in voice_instructions


def test_main_uses_relevant_life_context_before_asking_the_user() -> None:
    instructions = _load_resolved()["mainAgent"]["instructions"].lower()

    assert "authorized `/life`" in instructions
    assert "before saying it is unavailable or asking the user" in instructions
    assert "not web browsing" in instructions
