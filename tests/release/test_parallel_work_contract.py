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

    assert glasshive["tool_names"] == [
        "worker_delegate_once_mcp_glasshive-workers-projects",
        "active_work_list",
        "active_work_action",
    ]


def test_main_declares_parallel_capability_while_defaulting_to_focused() -> None:
    orchestration = _bundle()["mainAgent"]["glasshive_options"]["orchestration"]

    assert orchestration == {
        "parallel_available": True,
        "default_mode": "focused",
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
