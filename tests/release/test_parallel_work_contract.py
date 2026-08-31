from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
AGENT_SOURCE = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.viventium-agents.yaml"
)
LIBRECHAT_SOURCE = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.librechat.yaml"
)

KEY_PRINCIPLES = ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md"
PARALLEL_REQUIREMENTS = (
    ROOT / "docs" / "requirements_and_learnings" / "55_Parallel_Work_Orchestration.md"
)
VOICE_REQUIREMENTS = ROOT / "docs" / "requirements_and_learnings" / "06_Voice_Calls.md"
PARALLEL_CASES = ROOT / "qa" / "parallel-orchestrator" / "cases.md"
VOICE_CASES = ROOT / "qa" / "modern-playground-voice" / "cases.md"
FILE_CASES = ROOT / "qa" / "telegram-document-attachments" / "cases.md"


def _bundle() -> dict:
    return yaml.safe_load(AGENT_SOURCE.read_text(encoding="utf-8"))


def test_main_exposes_one_atomic_delegation_and_one_canonical_control_plane() -> None:
    main = _bundle()["mainAgent"]
    glasshive_tools = {
        tool
        for tool in main["tools"]
        if "glasshive-workers-projects" in tool or tool.startswith("active_work_")
    }

    assert glasshive_tools == {
        "worker_delegate_once_mcp_glasshive-workers-projects",
        "active_work_list",
        "active_work_action",
    }
    assert main["tool_options"] == {
        "worker_delegate_once_mcp_glasshive-workers-projects": {"defer_loading": False}
    }


def test_background_direct_action_ownership_matches_main_parallel_work_tools() -> None:
    source = _bundle()
    servers = source["config"]["viventium"]["background_cortices"]["activation_policy"][
        "direct_action_mcp_servers"
    ]
    glasshive = next(server for server in servers if server["server"] == "glasshive-workers-projects")

    app_source = yaml.safe_load(LIBRECHAT_SOURCE.read_text(encoding="utf-8"))
    app_servers = app_source["viventium"]["background_cortices"]["activation_policy"][
        "direct_action_mcp_servers"
    ]
    app_glasshive = next(
        server for server in app_servers if server["server"] == "glasshive-workers-projects"
    )

    assert glasshive["tool_names"] == [
        "worker_delegate_once_mcp_glasshive-workers-projects",
        "active_work_list",
        "active_work_action",
    ]
    assert app_glasshive["tool_names"] == glasshive["tool_names"]


def test_main_declares_parallel_capability_while_defaulting_to_focused() -> None:
    orchestration = _bundle()["mainAgent"]["glasshive_options"]["orchestration"]

    assert orchestration == {
        "parallel_available": True,
        "default_mode": "focused",
        "worker_profile": "codex-cli",
        "fallback_worker_profile": "claude-code",
    }


def test_glasshive_launch_headers_do_not_forward_surface_recipient_identity() -> None:
    source = yaml.safe_load(LIBRECHAT_SOURCE.read_text(encoding="utf-8"))
    headers = source["mcpServers"]["glasshive-workers-projects"]["headers"]

    assert {
        "X-Viventium-Telegram-Chat-Id",
        "X-Viventium-Telegram-User-Id",
        "X-Viventium-Telegram-Message-Id",
        "X-Viventium-Voice-Call-Session-Id",
        "X-Viventium-Voice-Request-Id",
    }.isdisjoint(headers)


def test_full_worker_capability_parity_is_cross_feature_and_release_blocking() -> None:
    principles = KEY_PRINCIPLES.read_text(encoding="utf-8")
    parallel_requirements = PARALLEL_REQUIREMENTS.read_text(encoding="utf-8")
    voice_requirements = VOICE_REQUIREMENTS.read_text(encoding="utf-8")
    parallel_cases = PARALLEL_CASES.read_text(encoding="utf-8")
    voice_cases = VOICE_CASES.read_text(encoding="utf-8")
    file_cases = FILE_CASES.read_text(encoding="utf-8")
    principles_compact = " ".join(principles.split())
    parallel_requirements_compact = " ".join(parallel_requirements.split())

    assert "full mission-relevant input, reasoning, action, and output path" in principles_compact
    assert "Every new capability requires an explicit Worker Bee" in principles_compact
    assert "### 9. Full capability and reliability parity" in parallel_requirements
    assert (
        "Every new Viventium capability is automatically in scope"
        in parallel_requirements_compact
    )
    assert "### Queen Bee And Worker Bee Voice Parity" in voice_requirements

    assert "`PWK-UC-019`" in parallel_cases
    assert "`MPV-061`" in parallel_cases
    assert "`TGDOC-010`" in parallel_cases
    assert "### MPV-061 Full Queen Bee And Worker Bee Voice Parity" in voice_cases
    assert "## `TGDOC-010` - Worker Bee File Input And Output Parity" in file_cases
    voice_status = voice_cases.split("`MPV-061`", 1)[1].splitlines()[0]
    assert "FAIL 2026-08-25" in voice_status
    assert "cannot dilute that observed failure" in voice_status
    assert "NOT RUN" in file_cases.split("`TGDOC-010`", 1)[1].splitlines()[0]
