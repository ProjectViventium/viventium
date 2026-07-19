from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler",
    ROOT / "scripts/viventium/config_compiler.py",
)
assert SPEC and SPEC.loader
config_compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config_compiler)


def minimal_config() -> dict:
    return {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "synthetic-call-session"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "synthetic-groq",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "synthetic-openai",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }


def test_feelings_case_catalog_preserves_truth_invariant_stable_ids() -> None:
    cases = (ROOT / "qa/emotional-cortex/cases.md").read_text(encoding="utf-8")

    assert "`EMO-009` | Truth/safety invariant" in cases
    assert "Feelings modulate expression, not facts" in cases
    assert "`EMO-UC-013` | Ask a factual or safety-sensitive question under high affect" in cases
    assert "`EMO-037` | Configurable conscious-only scope" in cases
    assert "`EMO-UC-027` | Use keyboard/reduced motion on mobile" in cases


def test_feelings_defaults_match_owner_approved_contract() -> None:
    settings = config_compiler.resolve_feelings_settings({})

    assert settings["available"] is True
    assert settings["default_enabled"] is False
    assert settings["agent_scope"] == "all_agents"
    assert settings["reaction"]["activation_mode"] == "always"
    assert settings["reaction"]["provider"] == "openai"
    assert settings["reaction"]["model"] == "gpt-5.6-terra"
    assert settings["reaction"]["use_responses_api"] is True
    assert settings["reaction"]["reasoning_effort"] == "none"
    assert settings["reaction"]["service_tier"] == "priority"
    assert settings["reaction"]["timeout_ms"] == 15000
    assert settings["reaction"]["fallback_provider"] == "anthropic"
    assert settings["reaction"]["fallback_model"] == "claude-opus-4-8"
    assert list(settings["bands"]) == [
        "energy",
        "mood",
        "drive",
        "curiosity",
        "vigilance",
        "care",
        "connection",
        "openness",
        "play",
    ]


def test_feelings_compiler_doc_defers_band_truth_to_the_canonical_feature_doc() -> None:
    compiler_doc = (
        ROOT / "docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md"
    ).read_text(encoding="utf-8")

    assert "all nine default Nature/half-life/enabled values" in compiler_doc
    assert "54_Emotional_Cortex_And_Feeling_State.md" in compiler_doc
    assert "all seven default Nature/half-life/enabled values" not in compiler_doc


def test_feelings_compile_to_explicit_env_contract() -> None:
    config = minimal_config()
    config["runtime"]["feelings"] = {
        "agent_scope": "conscious_agent",
        "reaction": {
            "activation_mode": "classified",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "low",
            "service_tier": "default",
            "fallback_provider": "xai",
            "fallback_model": "grok-4.20-non-reasoning",
        },
    }

    env = config_compiler.render_runtime_env(
        config,
        config_compiler.build_agent_assignments(config),
    )

    assert env["VIVENTIUM_FEELINGS_AVAILABLE"] == "true"
    assert env["VIVENTIUM_FEELINGS_DEFAULT_ENABLED"] == "false"
    assert env["VIVENTIUM_FEELINGS_AGENT_SCOPE"] == "conscious_agent"
    assert env["VIVENTIUM_FEELINGS_REACTION_ACTIVATION_MODE"] == "classified"
    assert env["VIVENTIUM_FEELINGS_REACTION_MODEL"] == "gpt-5.6-sol"
    assert env["VIVENTIUM_FEELINGS_REACTION_REASONING_EFFORT"] == "low"
    assert env["VIVENTIUM_FEELINGS_REACTION_SERVICE_TIER"] == "default"
    assert env["VIVENTIUM_FEELINGS_REACTION_FALLBACK_PROVIDER"] == "xai"
    assert env["VIVENTIUM_FEELINGS_REACTION_FALLBACK_MODEL"] == "grok-4.20-non-reasoning"
    bands = json.loads(env["VIVENTIUM_FEELINGS_BANDS_JSON"])
    assert bands["care"]["baseline"] == 74


@pytest.mark.parametrize("scope", ["primary", "workers", "everyone"])
def test_feelings_rejects_unknown_agent_scope(scope: str) -> None:
    with pytest.raises(SystemExit, match="runtime.feelings.agent_scope"):
        config_compiler.resolve_feelings_settings(
            {"runtime": {"feelings": {"agent_scope": scope}}}
        )


def test_feelings_rejects_unknown_band_and_invalid_values() -> None:
    with pytest.raises(SystemExit, match="unknown band"):
        config_compiler.resolve_feelings_settings(
            {"runtime": {"feelings": {"bands": {"joy": {"baseline": 50}}}}}
        )
    with pytest.raises(SystemExit, match="baseline"):
        config_compiler.resolve_feelings_settings(
            {"runtime": {"feelings": {"bands": {"care": {"baseline": 101}}}}}
        )
    with pytest.raises(SystemExit, match="half_life_minutes"):
        config_compiler.resolve_feelings_settings(
            {"runtime": {"feelings": {"bands": {"play": {"half_life_minutes": 0}}}}}
        )


def test_feelings_rejects_invalid_reaction_modes_and_route_fields() -> None:
    invalid = [
        {"activation_mode": "sometimes"},
        {"reasoning_effort": "turbo"},
        {"service_tier": "ultra"},
        {"provider": "unknown"},
        {"fallback_provider": "unknown"},
    ]
    for reaction in invalid:
        with pytest.raises(SystemExit, match="runtime.feelings.reaction"):
            config_compiler.resolve_feelings_settings(
                {"runtime": {"feelings": {"reaction": reaction}}}
            )


def test_feelings_schema_and_examples_publish_the_contract() -> None:
    schema = (ROOT / "config.schema.yaml").read_text(encoding="utf-8")
    full = (ROOT / "config.full.example.yaml").read_text(encoding="utf-8")
    minimal = (ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8")

    for text in (schema, full, minimal):
        assert "feelings:" in text
    assert "all_agents" in schema
    assert "gpt-5.6-terra" in full
    assert "service_tier: priority" in full
    assert "fallback_provider: anthropic" in full
    assert "fallback_model: claude-opus-4-8" in minimal


def test_feelings_runtime_publishes_concurrency_privacy_and_telemetry_contract() -> None:
    librechat = ROOT / "viventium_v0_4/LibreChat"
    reaction = (
        librechat
        / "api/server/services/viventium/EmotionalReactionService.js"
    ).read_text(encoding="utf-8")
    persistence = (
        librechat / "packages/data-schemas/src/methods/feelingState.ts"
    ).read_text(encoding="utf-8")
    schema = (
        librechat / "packages/data-schemas/src/schema/feelingState.ts"
    ).read_text(encoding="utf-8")
    telemetry = (
        librechat / "api/server/services/viventium/feelingsTelemetry.js"
    ).read_text(encoding="utf-8")
    route = (
        librechat / "api/server/routes/viventium/feelings.js"
    ).read_text(encoding="utf-8")

    assert "reactionQueues" in reaction
    assert "feelingStimulusKey" in reaction
    assert "activation?.reason" not in reaction
    assert "fallback_llm_provider" in reaction
    assert "lastFallbackUsed" in reaction
    assert "commitFeelingReaction" in reaction
    assert "processedStimulusKeys: { $ne: stimulusKey }" in persistence
    assert "$set: { ...set, reactionHealth: health }" in persistence
    assert "processedStimulusKeys" in schema
    assert "p: index + 1" in telemetry and "n: partCount" in telemetry
    assert "requestHash(payload.requestId)" in telemetry
    assert "SAFE_FEELINGS_TELEMETRY_FIELDS" in telemetry
    assert "SAFE_FEELINGS_TELEMETRY_FIELDS.has(key)" in telemetry
    assert "requireFeelingsAvailable" in route
    assert "deleteFeelingState(userId, parsed.data.expectedVersion)" in route


def test_feelings_browser_harness_measures_the_visible_contract_not_page_layout() -> None:
    harness = (
        ROOT / "qa/emotional-cortex/scripts/feelings_runtime_browser_qa.cjs"
    ).read_text(encoding="utf-8")

    assert "VISIBLE_ASSISTANT_REPLY_TIMEOUT_MS" in harness
    assert "offsetFromTrackBottom" in harness
    assert "natureBeforePosition.ariaValue === natureAfterPosition.ariaValue" in harness
    assert "reducedStyles.laneIsReacting &&" not in harness
    assert "markerTransitionSeconds <= 0.01" in harness


def test_feelings_prompt_workbench_eval_bank_covers_embodiment_and_reactions() -> None:
    bank = json.loads(
        (ROOT / "qa/prompt-architecture/evals/prompt-bank.json").read_text(encoding="utf-8")
    )
    family = next(
        row for row in bank["families"] if row["id"] == "feelings_embodiment_and_reaction"
    )
    cases = {case["id"]: case for case in family["cases"]}

    assert len(cases) >= 19
    assert "feelings_direct_question_without_state_recap" in cases
    assert "feelings_low_energy_high_drive_are_distinct" in cases
    assert "feelings_curiosity_without_play_is_investigative" in cases
    assert "feelings_high_mood_low_energy_are_distinct" in cases
    assert "feelings_low_mood_high_energy_are_distinct" in cases
    assert "feelings_high_openness_low_connection_are_distinct" in cases
    assert "feelings_low_openness_high_connection_are_distinct" in cases
    assert "feelings_good_news_moves_mood_and_writes_natural_line" in cases
    assert "feelings_bad_news_moves_mood_and_writes_natural_line" in cases
    assert "feelings_fatigue_context_can_raise_openness" in cases
    assert "feelings_fatigue_boundary_can_lower_openness" in cases
    assert "feelings_high_openness_does_not_echo_private_canary" in cases
    assert "feelings_playful_exchange_reacts_current_only" in cases
    assert "feelings_mechanical_turn_allows_no_reaction" in cases
    assert all(case.get("fixture", {}).get("feelings") for case in cases.values())
    current_fixtures = [
        case["fixture"]["feelings"]["current"]
        for case in cases.values()
        if "current" in case["fixture"]["feelings"]
    ]
    assert current_fixtures
    assert all(
        list(current) == [
            "energy",
            "mood",
            "drive",
            "curiosity",
            "vigilance",
            "care",
            "connection",
            "openness",
            "play",
        ]
        for current in current_fixtures
    )
    assert family["evalIsolation"] == {
        "savedMemory": True,
        "conversationRecall": True,
        "backgroundCortices": True,
    }
    assert family["interCaseDelayMs"] >= 10000
    reaction_cases = [
        case for case in cases.values() if case["fixture"]["feelings"].get("observeReaction")
    ]
    assert len(reaction_cases) >= 4
    assert all(
        any("Nature" in rubric and "zero" in rubric for rubric in case["rubric"])
        for case in reaction_cases
    )
    assert all(
        case["fixture"]["feelings"].get("requiredCurrentDirections")
        or case["fixture"]["feelings"].get("requireNoCurrentChange") is True
        or case["fixture"]["feelings"].get("requireNoForbiddenInnerStateTokens") is True
        for case in reaction_cases
    )


def test_feelings_eval_runner_restores_state_and_cleans_synthetic_conversations() -> None:
    runner = (
        ROOT / "qa/prompt-architecture/evals/run-exact-model-evals.cjs"
    ).read_text(encoding="utf-8")

    assert "applyFeelingsFixtureWithRetry" in runner
    assert "restoreFeelingsFixtureWithRetry" in runner
    assert "finally" in runner
    assert "cleanupEvalConversations" in runner
    assert "cleanupConversationIds" in runner
    assert "captureRawFeelingsState" in runner
    assert "restoreRawFeelingsState" in runner
    assert 'status: "restored_exact"' in runner
    assert 'expiresIn: "2h"' in runner
    assert "viventiumEvalIsolation" in runner
    assert "suppressBackgroundCortices" in runner
    assert "runChatTurnWithRetry" in runner
    assert "isTransientChatTurnFailure" in runner
    assert "lastFallbackUsed" in runner
    assert "lastUsedProvider" in runner
    assert "lastPrimaryErrorClass" in runner
    assert "innerStateText" in runner
    assert "innerStateForbiddenTokenMatches" in runner
    assert "validateFeelingsReactionEvidence" in runner
    assert "feelingsDeterministicFailures" in runner
    assert "feelings_reaction_changed_nature" in runner
    assert "semanticJudgeExplicitlyDisabled" in runner
    assert 'testCase.familyId === "feelings_embodiment_and_reaction"' in runner
    assert "trailCursorTimestamp" in runner
    assert 'caseId: "feelings_fixture_restore"' in runner
    assert 'caseId: "qa_conversation_cleanup"' in runner
