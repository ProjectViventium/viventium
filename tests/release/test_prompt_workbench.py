from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import importlib.util
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_BACKEND = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend"
if str(WORKBENCH_BACKEND) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_BACKEND))

from prompt_workbench import drafts, import_mapper, periphery_snapshots, prompt_service, promptfoo_adapter, scheduled_prompts, sync_engine  # noqa: E402
from prompt_workbench import evals  # noqa: E402
from prompt_workbench.paths import resolve_repo_path  # noqa: E402
from prompt_workbench.runtime_env import load_viventium_runtime_env  # noqa: E402


PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
WORKBENCH_DIST = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "dist"
WORKBENCH_ROOT = REPO_ROOT / "viventium_v0_4" / "prompt-workbench"
WORKBENCH_SRC = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "src"
PROMPT_WORKBENCH_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "viventium_prompt_workbench_cli",
    REPO_ROOT / "scripts" / "viventium" / "prompt_workbench.py",
)
assert PROMPT_WORKBENCH_SCRIPT_SPEC and PROMPT_WORKBENCH_SCRIPT_SPEC.loader
prompt_workbench_cli = importlib.util.module_from_spec(PROMPT_WORKBENCH_SCRIPT_SPEC)
PROMPT_WORKBENCH_SCRIPT_SPEC.loader.exec_module(prompt_workbench_cli)


def synthetic_home_path(*parts: str) -> str:
    return "/" + "/".join(("Users", "example-user", *parts))


def synthetic_private_ip() -> str:
    return ".".join(("192", "168", "1", "10"))


@pytest.fixture(autouse=True)
def restore_environment_after_workbench_test() -> None:
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)


def write_prompt(root: Path, rel: str, prompt_id: str, body: str, **metadata: object) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": prompt_id,
        "owner_layer": "test",
        "target": "test",
        "version": 1,
        "status": "active",
        "safety_class": "public_product",
        "required_context": [],
        "output_contract": "test",
        **metadata,
    }
    path.write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False).strip() + "\n---\n" + body.rstrip() + "\n",
        encoding="utf-8",
    )
    return path


def test_workbench_render_matches_existing_prompt_registry() -> None:
    registry = load_prompt_registry(PROMPT_ROOT)
    expected = render_prompt("main.conscious_agent", registry)

    actual = prompt_service.render_prompt_payload("main.conscious_agent")["rendered"]

    assert actual == expected
    assert "# Identity" in actual


def test_sync_status_lists_each_canonical_background_agent_prompt_unit() -> None:
    source = prompt_service.source_agents_bundle()

    rows = sync_engine._agent_rows(source=source, live=source, ledger={"records": {}})

    background_rows = [row for row in rows if row["sourcePromptId"] != "main.conscious_agent"]
    assert len(background_rows) == len(source["backgroundAgents"]) == 11
    assert {row["sourcePromptId"] for row in background_rows} == {
        "cortex.background_analysis.execution",
        "cortex.confirmation_bias.execution",
        "cortex.red_team.execution",
        "cortex.deep_research.execution",
        "cortex.online_tool_use.execution",
        "cortex.parietal_cortex.execution",
        "cortex.pattern_recognition.execution",
        "cortex.emotional_resonance.execution",
        "cortex.strategic_planning.execution",
        "cortex.support.execution",
        "cortex.google.execution",
    }
    assert all(row["state"] == "synced" for row in rows)


def test_drift_board_never_substitutes_an_unrelated_agent_row() -> None:
    source = (WORKBENCH_SRC / "components" / "DriftBoard.tsx").read_text(encoding="utf-8")

    assert "?? rows[0]" not in source
    assert "No managed live row for this prompt" in source


def test_workbench_loads_canonical_runtime_env_without_overwriting_existing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            [
                "SCHEDULING_MCP_URL=http://localhost:7110/mcp",
                "VIVENTIUM_SCHEDULING_MCP_PORT=7110",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SCHEDULING_MCP_URL", raising=False)
    monkeypatch.delenv("VIVENTIUM_SCHEDULING_MCP_PORT", raising=False)

    load_viventium_runtime_env(runtime_env)

    assert os.environ["SCHEDULING_MCP_URL"] == "http://localhost:7110/mcp"
    assert os.environ["VIVENTIUM_SCHEDULING_MCP_PORT"] == "7110"

    monkeypatch.setenv("SCHEDULING_MCP_URL", "http://example.invalid/mcp")
    load_viventium_runtime_env(runtime_env)
    assert os.environ["SCHEDULING_MCP_URL"] == "http://example.invalid/mcp"


def test_workbench_previews_memory_hardening_runtime_templates() -> None:
    prompt = prompt_service.get_prompt("memory.transcript_summarizer")
    context = prompt_service.workbench_context("memory.hardener_consolidation")

    assert prompt["metadata"]["target"] == "memory_hardening.meeting_transcript_summarizer.prompt"
    assert "{{transcript_envelope_json}}" in prompt["rendered"]
    assert "transcript_envelope_json" in prompt["variables"]
    assert context["linkedEvals"]["caseCount"] >= 2
    assert any(family["id"] == "memory_hardening_consolidation" for family in context["linkedEvals"]["families"])


def test_scheduling_workbench_context_links_prompts_config_evals_and_history() -> None:
    context = prompt_service.workbench_context("mcp.scheduling_cortex.server")
    related_config = context["relatedConfig"]
    encoded = json.dumps(related_config)

    assert context["linkedEvals"]["caseCount"] >= 2
    assert any(family["id"] == "scheduling_self_continuity" for family in context["linkedEvals"]["families"])
    assert {row["id"] for row in related_config} == {
        "scheduling-direct-action-owner",
        "scheduling-main-agent-tools",
        "scheduling-mcp-server",
    }
    assert all(row["gitHistory"] for row in related_config)
    assert all("patch" not in history for row in related_config for history in row["gitHistory"])
    assert "schedule_create_mcp_scheduling-cortex" in encoded
    assert "mcpServers.scheduling-cortex" in encoded
    assert "/Users" not in encoded
    assert str(Path.home()) not in encoded
    assert prompt_service.workbench_context("main.identity")["relatedConfig"] == []


def test_workbench_static_index_is_fresh_and_assets_are_immutable() -> None:
    if not (WORKBENCH_DIST / "index.html").exists():
        pytest.skip("Prompt Workbench dist bundle is not built in this checkout")
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    index_response = client.get("/", headers={"If-Modified-Since": "Sat, 16 May 2026 00:00:00 GMT"})

    assert index_response.status_code == 200
    assert "no-store" in index_response.headers["cache-control"]

    match = re.search(r'(?:src|href)="(/assets/[^"]+)"', index_response.text)
    assert match, "dist index should reference at least one built asset"
    asset_response = client.get(match.group(1))

    assert asset_response.status_code == 200
    assert "immutable" in asset_response.headers["cache-control"]


def test_workbench_build_version_exposes_public_safe_bundle_hash() -> None:
    if not (WORKBENCH_DIST / "index.html").exists():
        pytest.skip("Prompt Workbench dist bundle is not built in this checkout")
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    payload = TestClient(app).get("/api/build-version").json()

    assert payload["available"] is True
    assert re.fullmatch(r"[0-9a-f]{16}", payload["indexHash"])
    assert payload["entryAssets"]
    encoded = json.dumps(payload)
    assert str(REPO_ROOT) not in encoded


def test_workbench_cors_is_limited_to_served_loopback_origins() -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:8781",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:9999",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:8781"
    assert "access-control-allow-origin" not in blocked.headers


def test_workbench_rejects_non_loopback_host_header() -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)

    assert client.get("/api/health", headers={"host": "127.0.0.1:8783"}).status_code == 200
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_scheduled_prompt_admin_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", raising=False)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)

    assert client.get("/api/scheduled-prompts").status_code == 401
    assert client.get("/api/variables").status_code == 401
    assert client.post("/api/prompts/render", json={"promptId": "main.conscious_agent", "variables": {}}).status_code == 401
    assert client.post("/api/sync/push-live-dry-run", json={"env": "local"}).status_code == 401

    from prompt_workbench import auth

    monkeypatch.setattr(auth, "_librechat_admin_auth", lambda request: auth.AuthContext(True, False, method="librechat"))
    assert client.get("/api/scheduled-prompts", headers={"authorization": "Bearer non-admin"}).status_code == 403


def test_scheduled_prompt_admin_verify_carries_user_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", raising=False)
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    class FakeAdminVerifyResponse:
        status = 200

        def read(self) -> bytes:
            return json.dumps({"user": {"id": "admin-user-1", "email": "admin@example.test"}}).encode("utf-8")

        def __enter__(self) -> "FakeAdminVerifyResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(auth.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeAdminVerifyResponse())

    status = TestClient(app).get("/api/auth/status", headers={"authorization": "Bearer admin"})

    assert status.status_code == 200
    assert status.json()["admin"] is True
    assert status.json()["userId"] == "admin-user-1"
    assert status.json()["email"] == "admin@example.test"


def test_direct_loopback_workbench_resolves_single_local_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", raising=False)
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda request: True)
    monkeypatch.setattr(
        auth,
        "_query_local_admin_users",
        lambda: [{"_id": "admin-user-1", "email": "admin@example.test", "role": "ADMIN"}],
    )

    client = TestClient(app)
    status = client.get("/api/auth/status")

    assert status.status_code == 200
    assert status.json()["admin"] is True
    assert status.json()["method"] == "local_loopback_admin"
    assert status.json()["userId"] == "admin-user-1"
    assert client.get("/api/scheduled-prompts").status_code == 200


def test_direct_loopback_workbench_resolves_admin_with_unique_schedule_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", raising=False)
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    now = "2026-05-22T10:00:00Z"
    scheduled_prompts.storage().create_task(
        {
            "id": "task-owned-by-admin-b",
            "user_id": "admin-b",
            "agent_id": "agent-1",
            "prompt": "Owned scheduled prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "telegram",
            "executor": "viventium_agent",
            "conversation_policy": "same",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:agent-1",
            "created_source": "user",
            "created_at": now,
            "updated_at": now,
            "updated_by": "agent:agent-1",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-23T03:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": None,
        }
    )
    monkeypatch.setattr(auth, "_is_loopback_request", lambda request: True)
    monkeypatch.setattr(
        auth,
        "_query_local_admin_users",
        lambda: [
            {"_id": "admin-a", "email": "admin-a@example.test", "role": "ADMIN"},
            {"_id": "admin-b", "email": "admin-b@example.test", "role": "ADMIN"},
        ],
    )

    status = TestClient(app).get("/api/auth/status")

    assert status.status_code == 200
    assert status.json()["method"] == "local_loopback_admin"
    assert status.json()["userId"] == "admin-b"


def test_scheduled_prompt_variables_render_wrapped_and_governed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    rendered = scheduled_prompts.render_variables(
        "{{user}}\n{{local.viventium.database}}\n{{memory_agent.system_prompt}}\n{{viventium.background_agents.get_list(agent_name, system_prompt)}}",
        user_id="test-admin",
    )

    assert "<user>" in rendered["rendered"]
    assert "<local.viventium.database>" in rendered["rendered"]
    assert "<memory_agent.system_prompt>" in rendered["rendered"]
    assert "<viventium.background_agents.get_list>" in rendered["rendered"]
    assert "server-side snapshots only" in rendered["rendered"]
    assert "mongodb://127.0.0.1" not in rendered["rendered"]
    assert rendered["variableSnapshotHash"]
    assert "resolutionStatus" in rendered["rendered"]
    assert "directly in the database" not in scheduled_prompts.NIGHTLY_PROMPT_TEMPLATE
    frontend_panel = (
        REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "src" / "components" / "ScheduledPromptsPanel.tsx"
    ).read_text(encoding="utf-8")
    assert "directly in the database" not in frontend_panel
    assert "const defaultPrompt =" not in frontend_panel
    assert "getNightlyScheduledPromptTemplate" in frontend_panel


def test_background_agents_function_resolves_names_and_system_prompts_from_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    (prompts_root / "registry.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (prompts_root / "agent-one.md").write_text(
        "\n".join(
            [
                "---",
                "id: qa.agent_one",
                "owner_layer: qa",
                "target: qa",
                "version: 1",
                "status: active",
                "safety_class: public_product",
                "output_contract: text",
                "---",
                "Resolved prompt for {{current_user}}.",
            ]
        ),
        encoding="utf-8",
    )
    agents_yaml = tmp_path / "agents.yaml"
    agents_yaml.write_text(
        yaml.safe_dump(
            {
                "backgroundAgents": [
                    {"name": "QA Agent One", "instructions": {"promptRef": "qa.agent_one", "promptVars": {"current_user": "Synthetic User"}}},
                    {"id": "qa-agent-two", "instructions": "Inline background prompt"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(scheduled_prompts, "AGENTS_SOURCE_PATH", agents_yaml)
    monkeypatch.setattr(scheduled_prompts, "PROMPTS_ROOT", prompts_root)

    rendered = scheduled_prompts.render_variables(
        "{{viventium.background_agents.get_list(agent_name, system_prompt)}}",
        user_id="test-admin",
    )
    item = rendered["variableSnapshot"]["items"][0]

    assert item["placeholder"] == "viventium.background_agents.get_list(agent_name, system_prompt)"
    assert item["wrapper"] == "viventium.background_agents.get_list"
    assert item["value"] == [
        {"agent_name": "QA Agent One", "system_prompt": "Resolved prompt for Synthetic User."},
        {"agent_name": "qa-agent-two", "system_prompt": "Inline background prompt"},
    ]
    assert "<viventium.background_agents.get_list>" in rendered["rendered"]
    assert "Resolved prompt for Synthetic User." in rendered["rendered"]


def test_scheduled_prompt_memories_resolve_librechat_user_id_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_query(script: str):
        calls.append(script)
        if "db.users.findOne" in script:
            return {"_id": "507f1f77bcf86cd799439011", "email": "qa@example.test", "role": "ADMIN"}
        if "db.memoryentries.find" in script:
            assert "userId:objectId" in script
            assert "userId:userId" in script
            return [{"key": "core", "value": "saved memory value", "updatedAt": "2026-05-22T10:00:00Z"}]
        return None

    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", fake_query)

    rendered = scheduled_prompts.render_variables("{{user.memories}}", user_id="507f1f77bcf86cd799439011")

    assert "<user.memories>" in rendered["rendered"]
    assert "saved memory value" in rendered["rendered"]
    assert any("db.memoryentries.find" in script for script in calls)


def test_scheduled_prompt_memories_distinguish_empty_from_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def empty_query(script: str):
        if "db.users.findOne" in script:
            return {"_id": "507f1f77bcf86cd799439011", "email": "qa@example.test", "role": "ADMIN"}
        if "db.memoryentries.find" in script:
            return []
        return None

    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", empty_query)
    empty_rendered = scheduled_prompts.render_variables("{{user.memories}}", user_id="507f1f77bcf86cd799439011")
    assert "<user.memories>\n[]\n</user.memories>" in empty_rendered["rendered"]
    assert "mongo_unavailable" not in empty_rendered["rendered"]

    def unavailable_query(script: str):
        if "db.users.findOne" in script:
            return {"_id": "507f1f77bcf86cd799439011", "email": "qa@example.test", "role": "ADMIN"}
        if "db.memoryentries.find" in script:
            return None
        return None

    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", unavailable_query)
    unavailable_rendered = scheduled_prompts.render_variables("{{user.memories}}", user_id="507f1f77bcf86cd799439011")
    assert "mongo_unavailable" in unavailable_rendered["rendered"]
    assert "Memory lookup unavailable" in unavailable_rendered["rendered"]

    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    user_unavailable = scheduled_prompts.render_variables("{{user.memories}}", user_id="507f1f77bcf86cd799439011")
    assert "mongo_unavailable" in user_unavailable["rendered"]
    assert "User memory lookup unavailable" in user_unavailable["rendered"]


def test_periphery_snapshot_keeps_private_full_evidence_but_quarantines_reviewed_qa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(periphery_snapshots, "workbench_private_root", lambda: tmp_path / "private")
    my_folder = tmp_path / "my-folder"
    my_folder.mkdir()
    (my_folder / "working-note.md").write_text("A real private scratch note.", encoding="utf-8")
    (my_folder / "old-qa-note.md").write_text("Synthetic QA residue.", encoding="utf-8")
    (my_folder / "memory-proposals-202607110700.json").write_text('{"actions": []}', encoding="utf-8")

    def fake_query(script: str):
        assert "periphery_snapshot_v1" in script
        return {
            "user": {"id": "user-private-id", "email": "person@example.test", "name": "Person"},
            "counts": {"conversations": 2, "messages": 3, "memories": 1},
            "memories": [
                {"id": "memory-private-id", "key": "core", "value": "Private durable context", "updatedAt": "2026-07-10T10:00:00Z"}
            ],
            "conversations": [
                {
                    "id": "conversation-real-id",
                    "title": "Current planning",
                    "tags": [],
                    "updatedAt": "2026-07-10T11:00:00Z",
                    "messages": [
                        {"id": "message-real-1", "role": "user", "text": "Private current goal", "createdAt": "2026-07-10T10:59:00Z"},
                        {"id": "message-real-2", "role": "assistant", "text": "Private response", "createdAt": "2026-07-10T11:00:00Z"},
                    ],
                },
                {
                    "id": "conversation-qa-id",
                    "title": "Must not reach the model snapshot",
                    "tags": ["qa"],
                    "updatedAt": "2026-07-10T12:00:00Z",
                    "messages": [
                        {"id": "message-qa-1", "role": "user", "text": "Adversarial QA phrase", "createdAt": "2026-07-10T12:00:00Z"}
                    ],
                },
            ],
        }

    labels = {
        "schemaVersion": 1,
        "messages": {"message-real-2": {"label": "qa", "include": False, "reason": "reviewed message fixture"}},
        "scratchpads": {"old-qa-note.md": {"label": "qa", "include": False, "reason": "reviewed fixture residue"}},
    }
    periphery_snapshots.write_labels("user-a", labels)
    result = periphery_snapshots.create_snapshot(
        user_id="user-a",
        email="person@example.test",
        my_folder=str(my_folder),
        query_mongo_json=fake_query,
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )

    full_payload = json.loads(Path(result["fullSnapshotPath"]).read_text(encoding="utf-8"))
    model_payload = json.loads(result["modelSnapshotJson"])
    manifest = result["manifest"]
    assert len(full_payload["conversations"]) == 2
    assert len(model_payload["conversations"]) == 1
    assert len(model_payload["conversations"][0]["messages"]) == 1
    assert len(model_payload["scratchpads"]) == 1
    assert "Adversarial QA phrase" not in result["modelSnapshotJson"]
    assert "Synthetic QA residue" not in result["modelSnapshotJson"]
    assert manifest["status"] == "complete"
    assert manifest["counts"]["conversationsExcluded"] == 1
    assert manifest["counts"]["scratchpadsExcluded"] == 1
    assert manifest["sourceRefCount"] >= 4
    assert "person@example.test" not in json.dumps(manifest)
    assert "conversation-real-id" not in result["modelSnapshotJson"]
    assert str(tmp_path) not in json.dumps(manifest)
    assert Path(result["fullSnapshotPath"]).stat().st_mode & 0o777 == 0o600


def test_periphery_snapshot_reports_mongo_unavailable_without_inventing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(periphery_snapshots, "workbench_private_root", lambda: tmp_path / "private")
    result = periphery_snapshots.create_snapshot(
        user_id="user-a",
        email=None,
        my_folder=str(tmp_path / "missing-folder"),
        query_mongo_json=lambda _script: None,
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )

    model_payload = json.loads(result["modelSnapshotJson"])
    assert result["manifest"]["status"] == "degraded"
    assert result["manifest"]["missingPrerequisites"] == ["mongo"]
    assert model_payload["conversations"] == []
    assert model_payload["memories"] == []
    assert model_payload["status"] == "degraded"


def test_periphery_snapshot_preview_is_metadata_only_and_does_not_query_mongo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(periphery_snapshots, "workbench_private_root", lambda: tmp_path / "private")
    calls = []
    preview = periphery_snapshots.preview_snapshot("user-a", query_mongo_json=lambda script: calls.append(script))

    assert preview["status"] == "not_created"
    assert calls == []


def test_periphery_snapshot_retention_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(periphery_snapshots, "workbench_private_root", lambda: tmp_path / "private")
    payload = {"user": {"id": "u"}, "counts": {}, "memories": [], "conversations": []}
    started = datetime(2026, 7, 1, 7, 0, tzinfo=timezone.utc)
    for offset in range(periphery_snapshots.SNAPSHOT_RETENTION_COUNT + 2):
        periphery_snapshots.create_snapshot(
            user_id="user-a",
            email=None,
            my_folder=None,
            query_mongo_json=lambda _script: payload,
            now=started + timedelta(days=offset),
        )

    snapshot_root = next((tmp_path / "private" / "periphery-snapshots").iterdir())
    assert len(list(snapshot_root.glob("*.manifest.json"))) == periphery_snapshots.SNAPSHOT_RETENTION_COUNT
    assert len(list(snapshot_root.glob("*.model.json"))) == periphery_snapshots.SNAPSHOT_RETENTION_COUNT
    assert len(list(snapshot_root.glob("*.full.json"))) == periphery_snapshots.SNAPSHOT_RETENTION_COUNT


def test_periphery_snapshot_large_corpus_stays_within_worker_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(periphery_snapshots, "workbench_private_root", lambda: tmp_path / "private")
    conversations = []
    for conversation_index in range(130):
        conversations.append(
            {
                "id": f"conversation-{conversation_index}",
                "title": "Synthetic bounded corpus",
                "tags": [],
                "updatedAt": "2026-07-10T10:00:00Z",
                "messages": [
                    {
                        "id": f"message-{conversation_index}-{message_index}",
                        "role": "user" if message_index % 2 == 0 else "assistant",
                        "text": "x" * 500,
                        "createdAt": "2026-07-10T10:00:00Z",
                    }
                    for message_index in range(100)
                ],
            }
        )
    result = periphery_snapshots.create_snapshot(
        user_id="user-a",
        email=None,
        my_folder=None,
        query_mongo_json=lambda _script: {
            "user": {"id": "u"},
            "counts": {"conversations": 1206, "messages": 12919, "memories": 0},
            "memories": [],
            "conversations": conversations,
        },
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )

    model = json.loads(result["modelSnapshotJson"])
    included_messages = sum(len(row["messages"]) for row in model["conversations"])
    assert len(model["conversations"]) <= periphery_snapshots.MAX_CONVERSATIONS
    assert included_messages <= periphery_snapshots.MAX_MESSAGES
    assert all(len(row["messages"]) <= periphery_snapshots.MAX_MESSAGES_PER_CONVERSATION for row in model["conversations"])
    assert len(result["modelSnapshotJson"]) < 3_000_000
    assert result["manifest"]["counts"]["conversationsAvailable"] == 1206


def test_periphery_snapshot_queries_newest_messages_then_restores_chronology() -> None:
    script = periphery_snapshots._mongo_snapshot_script("user-a", None)

    assert ".sort({createdAt:-1,_id:-1}).limit(" in script
    assert "grouped[key].sort((left, right)" in script
    assert ".sort({createdAt:1,_id:1}).limit(" not in script


def test_variable_render_endpoint_uses_authenticated_admin_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "auth-user")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL", "auth@example.test")
    calls: list[tuple[str, str | None]] = []

    def fake_render_variables(prompt_text: str, *, user_id: str, email: str | None = None):
        calls.append((user_id, email))
        return {"rendered": prompt_text, "variableSnapshot": {"items": []}, "variableSnapshotHash": "hash"}

    monkeypatch.setattr(scheduled_prompts, "render_variables", fake_render_variables)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    response = TestClient(app).post(
        "/api/variables/render",
        json={"promptText": "{{user.memories}}", "userId": "foreign-user", "email": "foreign@example.test"},
    )

    assert response.status_code == 200
    assert calls == [("auth-user", "")]


def test_scheduled_prompt_object_has_drafts_preview_and_execution_config_ui() -> None:
    draft_source = (WORKBENCH_SRC / "components" / "DraftPanel.tsx").read_text(encoding="utf-8")
    schedule_source = (WORKBENCH_SRC / "components" / "ScheduledPromptsPanel.tsx").read_text(encoding="utf-8")
    dock_source = (WORKBENCH_SRC / "components" / "WorkbenchDock.tsx").read_text(encoding="utf-8")
    api_source = (WORKBENCH_SRC / "api.ts").read_text(encoding="utf-8")

    assert "selectedScheduledPrompt" in draft_source
    assert "Scheduled prompt draft view" in draft_source
    assert "<RenderedPrompt markdown={scheduledPreviewQuery.data?.rendered" in draft_source
    assert "renderVariables(selectedScheduledPrompt?.promptText" in draft_source
    assert "sourceKind !== 'user_schedule'" in draft_source
    assert "Workbench variable rendering is not applied" in draft_source
    assert "selectedScheduledPrompt={selectedScheduledPrompt}" in dock_source
    assert "includeSchedule: !draft.id || scheduleTouched" in schedule_source
    assert "includeMemoryWriteMode: !isUserLevelSchedule" in schedule_source
    assert "setScheduleTouched(true)" in schedule_source
    assert "schedule-execution-card" in schedule_source
    assert "GlassHive host" in schedule_source
    assert "Viventium agent" in schedule_source
    assert "This user-level schedule does not use Workbench variable" in schedule_source
    assert "User-level scheduler policy" in schedule_source
    assert "confirmUserLevelDelivery" in api_source
    assert "Manual Viventium schedule run started" in schedule_source
    assert "Run Viventium" in schedule_source
    assert "workspaceRoot" in schedule_source
    assert "executionProfile" in schedule_source
    assert "getScheduledPromptMemoryProposals" in schedule_source
    assert "getScheduledPromptPeripheryArtifacts" in api_source
    assert "getScheduledPromptPeripheryArtifacts" in schedule_source
    assert "Periphery Artifacts" in schedule_source
    assert "Content counts for" in schedule_source
    assert "invalidArtifacts" in schedule_source
    assert "Apply governed" in schedule_source
    assert "same_worker" in schedule_source
    assert "new_worker_each_run" in schedule_source


def test_topbar_sync_actions_signal_pending_and_done_states() -> None:
    app_source = (WORKBENCH_SRC / "App.tsx").read_text(encoding="utf-8")
    css_source = (WORKBENCH_SRC / "styles.css").read_text(encoding="utf-8")

    assert "liveWorkCount" in app_source
    assert "sourceWorkCount" in app_source
    assert "sync-action-${pullLiveState}" in app_source
    assert "sync-action-${pushLiveState}" in app_source
    assert "liveWorkCount > 0 || sourceWorkCount > 0" in app_source
    assert "need pull or merge before Push dry-run" in app_source
    assert ".toolbar-button.sync-action-done" in css_source
    assert ".toolbar-button.sync-action-needs-action" in css_source


def test_scheduled_prompt_template_endpoint_and_user_scoping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "user-a")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    template = client.get("/api/scheduled-prompts/templates/nightly-subconscious")
    assert template.status_code == 200
    assert template.json()["id"] == scheduled_prompts.NIGHTLY_TEMPLATE_ID
    assert "directly in the database" not in template.json()["promptText"]

    own = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Owned prompt",
            "promptText": "Use {{local.viventium.database}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
        },
    )
    assert own.status_code == 200
    other = scheduled_prompts.create_scheduled_prompt(
        {
            "title": "Other user prompt",
            "promptText": "Use {{local.viventium.database}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
        },
        user_id="user-b",
    )

    listed = client.get("/api/scheduled-prompts")
    titles = {item["title"] for item in listed.json()["scheduledPrompts"]}
    assert titles == {"Owned prompt"}
    assert client.patch(f"/api/scheduled-prompts/{other['id']}", json={"active": True}).status_code == 403


def test_nightly_prompt_template_uses_current_system_timezone_over_compiled_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_DEFAULT_TIMEZONE", "America/Toronto")
    monkeypatch.setattr(scheduled_prompts, "_system_timezone_name", lambda: "Europe/Paris")

    template = scheduled_prompts.nightly_prompt_template()

    assert template["schedule"] == {
        "type": "daily",
        "time": "03:00",
        "timezone": "Europe/Paris",
    }
    assert template["memoryWriteMode"] == "off"


def test_nightly_prompt_template_uses_current_system_timezone_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.delenv("VIVENTIUM_DEFAULT_TIMEZONE", raising=False)
    monkeypatch.setattr(scheduled_prompts, "_system_timezone_name", lambda: "Europe/Paris")

    template = scheduled_prompts.nightly_prompt_template()

    assert template["schedule"]["timezone"] == "Europe/Paris"


def test_nightly_prompt_template_requests_private_risk_radar_sidecar() -> None:
    prompt_text = scheduled_prompts.nightly_prompt_template()["promptText"]

    assert "{{local.viventium.my_folder}}" in prompt_text
    assert "{{viventium.periphery.snapshot}}" in prompt_text
    assert "scheduled-prompt/periphery-snapshot.json" in prompt_text
    assert "periphery/risk_radar/YYYY/MM" in prompt_text
    assert "paired .md and .json" in prompt_text
    assert "If there is no strong evidence" in prompt_text
    assert "Do not add a saved-memory key" in prompt_text
    assert "{{user.memories}}" not in prompt_text
    assert "{{memory_agent.system_prompt}}" not in prompt_text
    assert "{{viventium.background_agents.get_list(agent_name, system_prompt)}}" not in prompt_text
    assert len(prompt_text) < 4_000
    for field in scheduled_prompts.PERIPHERY_REQUIRED_FIELDS:
        assert field in prompt_text


def test_nightly_dispatch_render_keeps_private_evidence_out_of_the_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_snapshot = json.dumps(
        {
            "snapshotRef": "snapshot:20260711T070000Z-abc123abc123",
            "conversations": [{"messages": [{"text": "Private evidence body"}]}],
        }
    )
    monkeypatch.setattr(
        periphery_snapshots,
        "create_snapshot",
        lambda **_kwargs: {
            "manifest": {
                "snapshotRef": "snapshot:20260711T070000Z-abc123abc123",
                "status": "complete",
                "generatedAt": "2026-07-11T07:00:00Z",
                "counts": {"conversationsIncluded": 1},
                "sourceRefCount": 2,
            },
            "modelSnapshotJson": model_snapshot,
        },
    )

    rendered = scheduled_prompts.render_variables(
        scheduled_prompts.NIGHTLY_PROMPT_TEMPLATE,
        user_id="user-a",
        snapshot_mode="create",
    )

    assert "Private evidence body" not in rendered["rendered"]
    assert rendered["privatePeripherySnapshotJson"] == model_snapshot
    assert rendered["peripherySnapshotManifest"]["status"] == "complete"
    assert len(rendered["rendered"]) < 8_000


def test_nightly_seed_preserves_existing_builtin_schedule_timezone_and_disabled_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_DEFAULT_TIMEZONE", "America/Toronto")
    monkeypatch.setattr(
        scheduled_prompts, "_system_timezone_name", lambda: "America/Toronto"
    )
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "schedule": {"type": "daily", "time": "03:00", "timezone": "America/Los_Angeles"},
            "active": False,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
        active=True,
    )

    expected_schedule = {"type": "daily", "time": "03:00", "timezone": "America/Los_Angeles"}
    assert reseeded["id"] == existing["id"]
    assert reseeded["schedule"] == expected_schedule
    assert reseeded["active"] is False
    stored = scheduled_prompts.storage().get_scheduled_prompt_definition(existing["id"])
    task = scheduled_prompts.storage().get_task("startup-admin", stored["task_id"])
    assert stored["schedule"] == expected_schedule
    assert task["schedule"] == expected_schedule
    assert stored["timezone"] == "America/Los_Angeles"
    assert stored["metadata"]["schedule_timezone_mode"] == "fixed"
    assert stored["active"] == 0
    assert task["active"] == 0


def test_nightly_seed_migrates_legacy_untagged_default_after_travel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    current_timezone = ["America/Toronto"]
    monkeypatch.setattr(
        scheduled_prompts, "_system_timezone_name", lambda: current_timezone[0]
    )

    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **scheduled_prompts.nightly_prompt_template(),
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    stored = store.get_scheduled_prompt_definition(existing["id"])
    legacy_metadata = dict(stored.get("metadata") or {})
    legacy_metadata.pop("schedule_timezone_mode", None)
    store.update_scheduled_prompt_definition(existing["id"], {"metadata": legacy_metadata})

    current_timezone[0] = "Europe/Amsterdam"
    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    expected = {"type": "daily", "time": "03:00", "timezone": "Europe/Amsterdam"}
    stored = store.get_scheduled_prompt_definition(existing["id"])
    task = store.get_task("startup-admin", stored["task_id"])
    assert reseeded["schedule"] == expected
    assert stored["schedule"] == expected
    assert task["schedule"] == expected
    assert stored["metadata"]["schedule_timezone_mode"] == "local"


def test_nightly_seed_refreshes_managed_local_timezone_without_resetting_user_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    current_timezone = ["America/Toronto"]
    monkeypatch.setattr(
        scheduled_prompts, "_system_timezone_name", lambda: current_timezone[0]
    )
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "title": "My nightly review",
            "promptText": "Keep this user-authored nightly prompt",
            "active": False,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    current_timezone[0] = "Europe/Amsterdam"

    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
        active=True,
    )

    stored = scheduled_prompts.storage().get_scheduled_prompt_definition(existing["id"])
    task = scheduled_prompts.storage().get_task("startup-admin", stored["task_id"])
    expected = {"type": "daily", "time": "03:00", "timezone": "Europe/Amsterdam"}
    assert reseeded["schedule"] == expected
    assert stored["schedule"] == expected
    assert task["schedule"] == expected
    assert stored["metadata"]["schedule_timezone_mode"] == "local"
    assert stored["title"] == "My nightly review"
    assert stored["prompt_text"] == "Keep this user-authored nightly prompt\n"
    assert stored["active"] == 0
    assert task["active"] == 0


def test_nightly_prompt_update_preserves_local_mode_until_schedule_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_DEFAULT_TIMEZONE", "America/Toronto")
    monkeypatch.setattr(
        scheduled_prompts, "_system_timezone_name", lambda: "America/Toronto"
    )
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    created = scheduled_prompts.create_scheduled_prompt(
        {
            **scheduled_prompts.nightly_prompt_template(),
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    updated = scheduled_prompts.update_scheduled_prompt(
        created["id"],
        {"title": "Updated without touching schedule"},
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    stored = store.get_scheduled_prompt_definition(created["id"])
    assert updated["schedule"] == {
        "type": "daily",
        "time": "03:00",
        "timezone": "America/Toronto",
    }
    assert stored["metadata"]["schedule_timezone_mode"] == "local"

    scheduled_prompts.update_scheduled_prompt(
        created["id"],
        {"schedule": dict(updated["schedule"])},
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    stored = store.get_scheduled_prompt_definition(created["id"])
    assert stored["metadata"]["schedule_timezone_mode"] == "fixed"


def test_nightly_seed_preserves_user_prompt_and_repairs_only_scheduler_task_plumbing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    custom_prompt = "Keep this user-authored nightly prompt\n"
    custom_schedule = {"type": "daily", "time": "04:30", "timezone": "Europe/Paris"}
    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "title": "My nightly review",
            "promptText": custom_prompt,
            "schedule": custom_schedule,
            "active": False,
            "memoryWriteMode": "propose",
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    stored_before = store.get_scheduled_prompt_definition(existing["id"])
    version_before = store.latest_scheduled_prompt_version(existing["id"])
    store.update_task(
        "startup-admin",
        stored_before["task_id"],
        {
            "executor": "viventium_agent",
            "prompt": "stale task mirror",
            "schedule": {"type": "daily", "time": "01:00", "timezone": "UTC"},
            "active": 1,
            "last_run_at": "2026-07-10T08:00:00Z",
            "last_status": "completed",
            "last_generated_text": "preserved run summary",
        },
    )

    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
        active=True,
    )

    stored = store.get_scheduled_prompt_definition(existing["id"])
    task = store.get_task("startup-admin", stored["task_id"])
    version_after = store.latest_scheduled_prompt_version(existing["id"])
    assert reseeded["id"] == existing["id"]
    assert stored["title"] == "My nightly review"
    assert stored["prompt_text"] == custom_prompt
    assert stored["schedule"] == custom_schedule
    assert stored["timezone"] == "Europe/Paris"
    assert stored["active"] == 0
    assert stored["memory_write_mode"] == "propose"
    assert task["executor"] == "glasshive_host"
    assert task["prompt"] == custom_prompt
    assert task["schedule"] == custom_schedule
    assert task["active"] == 0
    assert task["last_run_at"] == "2026-07-10T08:00:00Z"
    assert task["last_status"] == "completed"
    assert task["last_generated_text"] == "preserved run summary"
    assert version_after["id"] == version_before["id"]


def test_nightly_seed_backfills_legacy_execution_metadata_without_resetting_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setenv("GLASSHIVE_DEFAULT_WORKER_PROFILE", "claude-code")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "active": True,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(existing["id"])
    definition_metadata = dict(definition["metadata"])
    definition_execution = dict(definition_metadata["execution"])
    definition_execution["execution_model"] = "gpt-stale"
    definition_execution["reasoning_effort"] = "high"
    definition_execution["execution_profile"] = "codex-cli"
    definition_metadata["execution"] = definition_execution
    store.update_scheduled_prompt_definition(
        existing["id"],
        {"metadata": definition_metadata, "memory_write_mode": "propose"},
    )

    task = store.get_task("startup-admin", definition["task_id"])
    task_metadata = dict(task["metadata"])
    task_workbench = dict(task_metadata["workbench_scheduled_prompt"])
    task_workbench["execution_model"] = "gpt-stale"
    task_workbench["reasoning_effort"] = "high"
    task_workbench["memory_write_mode"] = "propose"
    task_metadata["workbench_scheduled_prompt"] = task_workbench
    task_metadata.pop("misfire_policy")
    store.update_task("startup-admin", definition["task_id"], {"metadata": task_metadata})

    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    stored = store.get_scheduled_prompt_definition(existing["id"])
    task = store.get_task("startup-admin", definition["task_id"])
    assert reseeded["executionModel"] == "gpt-test-scheduled"
    assert reseeded["reasoningEffort"] == "xhigh"
    assert stored["metadata"]["execution"]["execution_profile"] == "codex-cli"
    assert stored["metadata"]["execution"]["execution_model"] == "gpt-test-scheduled"
    assert stored["metadata"]["execution"]["reasoning_effort"] == "xhigh"
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_profile"] == "codex-cli"
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_model"] == "gpt-test-scheduled"
    assert task["metadata"]["workbench_scheduled_prompt"]["reasoning_effort"] == "xhigh"
    assert stored["metadata"]["execution"]["ignore_user_config"] is True
    assert task["metadata"]["workbench_scheduled_prompt"]["ignore_user_config"] is True
    assert stored["memory_write_mode"] == "propose"
    assert task["metadata"]["workbench_scheduled_prompt"]["memory_write_mode"] == "propose"
    assert task["metadata"]["misfire_policy"] == scheduled_prompts.NIGHTLY_MISFIRE_POLICY


@pytest.mark.parametrize(
    ("missing_field", "env_name", "error_fragment"),
    [
        ("execution_model", "WPR_MODEL_HOST_CODEX_CLI", "WPR_MODEL_HOST_CODEX_CLI or execution_model"),
        (
            "reasoning_effort",
            "WPR_CODEX_CLI_REASONING_EFFORT",
            "WPR_CODEX_CLI_REASONING_EFFORT or reasoning_effort",
        ),
    ],
)
def test_nightly_seed_fails_cleanly_when_legacy_execution_tuple_and_env_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
    env_name: str,
    error_fragment: str,
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **scheduled_prompts.nightly_prompt_template(),
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "active": False,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(existing["id"])
    definition_metadata = dict(definition["metadata"])
    definition_execution = dict(definition_metadata["execution"])
    definition_execution.pop(missing_field)
    definition_metadata["execution"] = definition_execution
    store.update_scheduled_prompt_definition(existing["id"], {"metadata": definition_metadata})

    task = store.get_task("startup-admin", definition["task_id"])
    task_metadata = dict(task["metadata"])
    task_execution = dict(task_metadata["execution"])
    task_execution.pop(missing_field)
    task_metadata["execution"] = task_execution
    task_workbench = dict(task_metadata["workbench_scheduled_prompt"])
    task_workbench.pop(missing_field)
    task_metadata["workbench_scheduled_prompt"] = task_workbench
    store.update_task("startup-admin", definition["task_id"], {"metadata": task_metadata})
    monkeypatch.delenv(env_name, raising=False)
    if env_name == "WPR_MODEL_HOST_CODEX_CLI":
        monkeypatch.delenv("WPR_MODEL_CODEX_CLI", raising=False)

    with pytest.raises(RuntimeError, match=error_fragment):
        scheduled_prompts.seed_nightly_prompt(
            user_id="startup-admin",
            email="startup-admin@example.test",
        )


def test_scheduled_automation_tuple_is_config_driven_and_profile_aware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "WPR_MODEL_HOST_CODEX_CLI",
        "WPR_MODEL_CODEX_CLI",
        "WPR_MODEL_CLAUDE_CODE",
        "WPR_CODEX_CLI_REASONING_EFFORT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert scheduled_prompts._default_automation_model("codex-cli") == ""
    assert scheduled_prompts._default_automation_reasoning_effort() == ""

    monkeypatch.setenv("WPR_MODEL_CLAUDE_CODE", "claude-configured-test")
    assert scheduled_prompts._default_automation_model("claude-code") == "claude-configured-test"
    assert scheduled_prompts._default_automation_model("unknown-profile") == ""


def test_scheduled_prompt_crud_manual_run_and_private_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    my_folder_root = tmp_path / "glasshive"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(my_folder_root))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("SCHEDULER_GLASSHIVE_DISABLE_DISPATCH", "1")
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-5.6-sol")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "QA scheduled prompt",
            "promptText": "Write to {{local.viventium.my_folder}} using {{local.viventium.database}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
            "executor": "glasshive_host",
            "glasshiveWorkerStrategy": "new_worker_each_run",
        },
    )
    assert created.status_code == 200
    prompt_id = created.json()["id"]
    assert created.json()["active"] is False
    assert created.json()["executionModel"] == "gpt-5.6-sol"
    assert created.json()["reasoningEffort"] == "xhigh"

    patched = client.patch(f"/api/scheduled-prompts/{prompt_id}", json={"active": True})
    assert patched.status_code == 200
    assert patched.json()["active"] is True

    invalid_mode = client.patch(f"/api/scheduled-prompts/{prompt_id}", json={"memoryWriteMode": "direct_mongo"})
    assert invalid_mode.status_code == 400

    manual = client.post(f"/api/scheduled-prompts/{prompt_id}/manual-runs")
    assert manual.status_code == 200
    assert manual.json()["run"]["status"] == "queued"
    assert manual.json()["run"]["privateDetailPointer"].startswith("private://scheduled-prompt-run/")
    assert str(tmp_path) not in json.dumps(manual.json())
    duplicate = client.post(f"/api/scheduled-prompts/{prompt_id}/manual-runs")
    assert duplicate.status_code == 200
    assert duplicate.json()["coalesced"] is True
    assert duplicate.json()["run"]["status"] == "queued"

    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(prompt_id)
    task = store.get_task(definition["user_id"], definition["task_id"])
    runs = store.list_scheduled_prompt_runs(definition_id=prompt_id)

    assert task["executor"] == "glasshive_host"
    assert task["channel"] == "workbench"
    assert task["metadata"]["workbench_scheduled_prompt"]["glasshive_worker_strategy"] == "new_worker_each_run"
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_model"] == "gpt-5.6-sol"
    assert task["metadata"]["workbench_scheduled_prompt"]["reasoning_effort"] == "xhigh"
    assert runs and Path(runs[0]["private_detail_path"]).exists()
    assert "mongodb://" not in Path(runs[0]["private_detail_path"]).read_text(encoding="utf-8")


def test_public_scheduled_run_exposes_requested_and_effective_effort_only() -> None:
    public = scheduled_prompts._public_run(
        {
            "run_id": "run-1",
            "status": "failed",
            "executor": "glasshive_host",
            "callback_payload_json": json.dumps(
                {
                    "effort_projection": {
                        "requested": "xhigh",
                        "effective": "medium",
                        "fallback_reason": "xhigh_route_not_proven",
                    },
                    "private": "must not surface",
                }
            ),
        }
    )

    assert public["requestedReasoningEffort"] == "xhigh"
    assert public["effectiveReasoningEffort"] == "medium"
    assert public["reasoningFallbackReason"] == "xhigh_route_not_proven"
    assert "private" not in public


def test_workbench_scheduled_prompt_can_use_viventium_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Viventium route prompt",
            "promptText": "Review {{user}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
            "executor": "viventium_agent",
            "channel": "librechat",
            "conversationPolicy": "same",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["executor"] == "viventium_agent"
    assert body["channel"] == "librechat"
    assert body["conversationPolicy"] == "same"
    task = scheduled_prompts.storage().get_task(body["userId"], body["taskId"])
    assert task["executor"] == "viventium_agent"
    assert task["channel"] == "librechat"
    assert task["conversation_policy"] == "same"

    calls = []

    def fake_dispatch(task_for_dispatch):
        calls.append(task_for_dispatch["id"])
        return {"delivery": {"outcome": "sent", "reason": "manual_run", "generated_text": "private"}}

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_dispatch)
    manual = client.post(f"/api/scheduled-prompts/{body['id']}/manual-runs")
    assert manual.status_code == 200
    assert manual.json()["run"]["executor"] == "viventium_agent"
    assert manual.json()["run"]["status"] == "completed"
    assert manual.json()["run"]["resultSummary"] == "sent: manual_run"
    duplicate = client.post(f"/api/scheduled-prompts/{body['id']}/manual-runs")
    assert duplicate.status_code == 200
    assert duplicate.json()["coalesced"] is True
    assert duplicate.json()["run"]["executor"] == "viventium_agent"
    assert calls == [body["taskId"]]


def test_scheduled_prompt_memory_proposal_review_and_governed_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "proposal-user")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Proposal prompt",
            "promptText": "Write proposal",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
    ).json()
    my_folder = Path(created["myFolder"])
    proposal_file = my_folder / "memory-proposals-202605220300.json"
    proposal_file.write_text(
        json.dumps({"actions": [{"action": "set", "key": "context", "value": "Synthetic context", "reason": "QA"}]}),
        encoding="utf-8",
    )

    proposals = client.get(f"/api/scheduled-prompts/{created['id']}/memory-proposals")
    assert proposals.status_code == 200
    [proposal] = proposals.json()["proposals"]
    assert proposal["actionCount"] == 1
    assert proposal["actions"][0]["key"] == "context"
    assert proposal["actions"][0]["valueHash"]

    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        assert "viventium-memory-proposal-apply.js" in cmd[1]
        assert "--apply" in cmd
        assert "--user-id" in cmd
        assert cmd[cmd.index("--user-id") + 1] == "proposal-user"

        class Completed:
            returncode = 0
            stdout = json.dumps({"ok": True, "mode": "apply", "reason": "ok", "actionCount": 1, "appliedCount": 1})
            stderr = ""

        return Completed()

    monkeypatch.setattr(scheduled_prompts.subprocess, "run", fake_run)
    applied = client.post(
        f"/api/scheduled-prompts/{created['id']}/memory-proposals/{proposal['proposalId']}/apply",
        json={"apply": True},
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True


@pytest.mark.parametrize("legacy_schema_version", ["1.0", "risk_radar.v1"])
def test_scheduled_prompt_periphery_artifact_metadata_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_schema_version: str,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "periphery-user")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Periphery prompt",
            "promptText": "Write private periphery notes",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
    ).json()
    artifact_dir = Path(created["myFolder"]) / "periphery" / "risk_radar" / "2026" / "06"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "20260625T030000Z.risk_radar.md").write_text(
        "Private synthetic insight body that must never appear in metadata.",
        encoding="utf-8",
    )
    (artifact_dir / "20260625T030000Z.risk_radar.json").write_text(
        json.dumps(
            {
                "schemaVersion": legacy_schema_version,
                "moduleId": "risk_radar",
                "generatedAt": "2026-06-25T07:00:00Z",
                "scheduledRunRef": {"runId": "sp_run_private_1", "definitionId": created["id"]},
                "sourceRefs": [{"kind": "conversation", "id": "private-conversation-id"}],
                "confidence": "medium",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P7D",
                "staleAfter": "2026-07-02T07:00:00Z",
                "observations": [{"summary": "Private observation text should not leak."}],
                "risks": [],
                "blindSpots": [{"summary": "Private blind spot text should not leak."}],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": ["on_demand"],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/scheduled-prompts/{created['id']}/periphery-artifacts")

    assert response.status_code == 200
    payload = response.json()
    [artifact] = payload["artifacts"]
    assert artifact["moduleId"] == "risk_radar"
    assert artifact["generatedAt"] == "2026-06-25T07:00:00Z"
    assert artifact["markdownExists"] is True
    assert artifact["contentCounts"]["observations"] == 1
    assert artifact["contentCounts"]["blindSpots"] == 1
    assert artifact["sourceRefCount"] == 1
    assert artifact["scheduledRunRefHash"]
    assert artifact["qualityStatus"] == "legacy"
    assert payload["invalidArtifacts"] == []
    assert payload["index"]["artifactCount"] == 1
    assert "periphery/<moduleId>/YYYY/MM" in payload["contract"]
    encoded = json.dumps(payload)
    assert "Private synthetic insight body" not in encoded
    assert "Private observation text" not in encoded
    assert "private-conversation-id" not in encoded
    assert str(tmp_path) not in encoded


def test_scheduled_prompt_periphery_v2_resolves_snapshot_evidence_and_builds_private_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "periphery-user")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda _script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Periphery v2 prompt",
            "promptText": "Write private periphery notes",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
    ).json()
    snapshot = periphery_snapshots.create_snapshot(
        user_id="periphery-user",
        email=None,
        my_folder=created["myFolder"],
        query_mongo_json=lambda _script: {
            "user": {"id": "private-user"},
            "counts": {"conversations": 0, "messages": 0, "memories": 1},
            "memories": [
                {"id": "private-memory", "key": "core", "value": "Private evidence body", "updatedAt": "2026-07-10T10:00:00Z"}
            ],
            "conversations": [],
        },
        schedule_store=scheduled_prompts.storage(),
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )
    model_snapshot = json.loads(snapshot["modelSnapshotJson"])
    source_ref = model_snapshot["memories"][0]["sourceRef"]
    artifact_dir = Path(created["myFolder"]) / "periphery" / "risk_radar" / "2026" / "07"
    artifact_dir.mkdir(parents=True)
    sidecar = artifact_dir / "20260711T071500Z.risk_radar.json"
    (artifact_dir / "20260711T071500Z.risk_radar.md").write_text("Private insight body", encoding="utf-8")
    sidecar.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "moduleId": "risk_radar",
                "generatedAt": "2026-07-11T07:15:00Z",
                "snapshotRef": snapshot["manifest"]["snapshotRef"],
                "scheduledRunRef": {"runId": "sp_run_private", "definitionId": created["id"]},
                "sourceRefs": [source_ref],
                "confidence": "medium",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P7D",
                "staleAfter": "2099-07-18T07:15:00Z",
                "observations": [{"kind": "observation", "summary": "Private observation", "sourceRefs": [source_ref]}],
                "risks": [],
                "blindSpots": [],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": ["on_demand"],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )

    payload = client.get(f"/api/scheduled-prompts/{created['id']}/periphery-artifacts").json()

    [artifact] = payload["artifacts"]
    assert artifact["qualityStatus"] == "passed"
    assert artifact["sourceRefsResolvedCount"] == 1
    assert artifact["sourceRefsUnresolvedCount"] == 0
    assert artifact["stale"] is False
    assert payload["index"]["artifactCount"] == 1
    assert payload["index"]["qualityCounts"] == {"passed": 1}
    index_path = Path(created["myFolder"]) / "periphery" / "_index.json"
    assert index_path.is_file()
    index_text = index_path.read_text(encoding="utf-8")
    assert "Private evidence body" not in index_text
    assert "Private insight body" not in index_text
    assert "Private observation" not in index_text
    detail = client.get(
        f"/api/scheduled-prompts/{created['id']}/periphery-artifacts/{artifact['artifactId']}"
    )
    assert detail.status_code == 200
    assert detail.json()["markdown"] == "Private insight body"
    assert detail.json()["sidecar"]["observations"][0]["summary"] == "Private observation"
    assert str(tmp_path) not in json.dumps(detail.json())


def test_scheduled_prompt_periphery_v2_flags_unresolved_and_invalid_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    snapshot = periphery_snapshots.create_snapshot(
        user_id="user-a",
        email=None,
        my_folder=None,
        query_mongo_json=lambda _script: {"user": {"id": "u"}, "counts": {}, "memories": [], "conversations": []},
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )
    root = tmp_path / "periphery"
    artifact_dir = root / "risk_radar" / "2026" / "07"
    artifact_dir.mkdir(parents=True)
    base = {
        "schemaVersion": 2,
        "moduleId": "risk_radar",
        "generatedAt": "2026-07-01T07:00:00Z",
        "snapshotRef": snapshot["manifest"]["snapshotRef"],
        "scheduledRunRef": {"runId": "sp_run_private"},
        "sourceRefs": ["conversation:000000000000000000000000"],
        "confidence": "medium",
        "severity": "low",
        "timeSensitivity": "low",
        "ttl": "P1D",
        "staleAfter": "2026-07-02T07:00:00Z",
        "observations": [
            {
                "kind": "observation",
                "summary": "Claim cites unresolved evidence",
                "sourceRefs": ["conversation:000000000000000000000000"],
            }
        ],
        "risks": [],
        "blindSpots": [],
        "opportunityCosts": [],
        "opportunities": [],
        "whatWouldMakeThisWrong": [],
        "whenToSurface": [],
        "proposedActions": [],
        "memoryProposalRefs": [],
    }
    unresolved_path = artifact_dir / "20260701T070000Z.risk_radar.json"
    unresolved_path.with_suffix(".md").write_text("Synthetic unresolved claim", encoding="utf-8")
    unresolved_path.write_text(json.dumps(base), encoding="utf-8")
    artifact, error = scheduled_prompts._load_periphery_artifact(
        unresolved_path,
        root,
        user_id="user-a",
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )
    assert error is None
    assert artifact["qualityStatus"] == "failed"
    assert artifact["sourceRefsUnresolvedCount"] == 1
    assert artifact["claimsGroundedCount"] == 0
    assert artifact["claimsUngroundedCount"] == 1
    assert artifact["qualityReasons"] == [
        "unresolved_evidence",
        "ungrounded_claims",
        "stale",
    ]
    assert artifact["stale"] is True

    invalid_path = artifact_dir / "20260701T080000Z.risk_radar.json"
    invalid_path.write_text(json.dumps({**base, "sourceRefs": "not-a-list"}), encoding="utf-8")
    artifact, error = scheduled_prompts._load_periphery_artifact(
        invalid_path,
        root,
        user_id="user-a",
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )
    assert artifact is None
    assert error["reason"] == "invalid_field_type"


def test_scheduled_prompt_periphery_marks_pruned_snapshot_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    snapshot = periphery_snapshots.create_snapshot(
        user_id="user-a",
        email=None,
        my_folder=None,
        query_mongo_json=lambda _script: {
            "user": {"id": "u"},
            "counts": {},
            "memories": [],
            "conversations": [],
        },
        now=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )
    root = tmp_path / "periphery"
    artifact_dir = root / "risk_radar" / "2026" / "07"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "20260711T071500Z.risk_radar.json"
    artifact_path.with_suffix(".md").write_text("No material result", encoding="utf-8")
    artifact_path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "moduleId": "risk_radar",
                "generatedAt": "2026-07-11T07:15:00Z",
                "snapshotRef": snapshot["manifest"]["snapshotRef"],
                "scheduledRunRef": {"runId": "sp_run_private"},
                "sourceRefs": [],
                "confidence": "low",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P1D",
                "staleAfter": "2026-07-12T07:15:00Z",
                "observations": [
                    {"kind": "no_result", "summary": "No material result", "sourceRefs": []}
                ],
                "risks": [],
                "blindSpots": [],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": [],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )

    before, error = scheduled_prompts._load_periphery_artifact(
        artifact_path,
        root,
        user_id="user-a",
        now=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
    )
    assert error is None
    assert before["qualityStatus"] == "passed"
    assert before["qualityReasons"] == []

    Path(snapshot["modelSnapshotPath"]).unlink()
    after, error = scheduled_prompts._load_periphery_artifact(
        artifact_path,
        root,
        user_id="user-a",
        now=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
    )
    assert error is None
    assert after["qualityStatus"] == "failed"
    assert after["qualityReasons"] == ["snapshot_unavailable"]


def test_user_periphery_read_cannot_cross_user_folders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    user_a_folder = Path(scheduled_prompts._glasshive_my_folder("user-a"))
    root = user_a_folder / "periphery"
    artifact_dir = root / "risk_radar" / "2026" / "07"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "20260711T071500Z.risk_radar.json"
    artifact_path.with_suffix(".md").write_text("Private user A insight", encoding="utf-8")
    artifact_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "risk_radar",
                "generatedAt": "2026-07-11T07:15:00Z",
                "scheduledRunRef": {"runId": "private"},
                "sourceRefs": [],
                "confidence": "low",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P1D",
                "staleAfter": "2099-07-12T07:15:00Z",
                "observations": [],
                "risks": [],
                "blindSpots": [],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": [],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )
    artifact_id = scheduled_prompts._periphery_artifact_id(artifact_path, root)

    own = scheduled_prompts.read_user_periphery_artifact(
        user_id="user-a",
        artifact_id=artifact_id,
    )
    assert own["markdown"] == "Private user A insight"
    with pytest.raises(KeyError):
        scheduled_prompts.read_user_periphery_artifact(
            user_id="user-b",
            artifact_id=artifact_id,
        )


def test_periphery_list_uses_generated_time_not_file_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    root = tmp_path / "my-folder" / "periphery"

    def write_artifact(timestamp: str, generated_at: str) -> Path:
        artifact_dir = root / "risk_radar" / "2026" / "07"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{timestamp}.risk_radar.json"
        path.with_suffix(".md").write_text("Synthetic insight", encoding="utf-8")
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "moduleId": "risk_radar",
                    "generatedAt": generated_at,
                    "scheduledRunRef": {"runId": "synthetic"},
                    "sourceRefs": [],
                    "confidence": "low",
                    "severity": "low",
                    "timeSensitivity": "low",
                    "ttl": "P1D",
                    "staleAfter": "2099-07-12T07:15:00Z",
                    "observations": [],
                    "risks": [],
                    "blindSpots": [],
                    "opportunityCosts": [],
                    "opportunities": [],
                    "whatWouldMakeThisWrong": [],
                    "whenToSurface": [],
                    "proposedActions": [],
                    "memoryProposalRefs": [],
                }
            ),
            encoding="utf-8",
        )
        return path

    older = write_artifact("20260709T070000Z", "2026-07-09T07:00:00Z")
    newer = write_artifact("20260710T070000Z", "2026-07-10T07:00:00Z")
    os.utime(older, (newer.stat().st_mtime + 60, newer.stat().st_mtime + 60))

    _, artifacts, _, _ = scheduled_prompts._collect_periphery(
        str(tmp_path / "my-folder"),
        user_id="user-a",
    )

    assert [item["generatedAt"] for item in artifacts] == [
        "2026-07-10T07:00:00Z",
        "2026-07-09T07:00:00Z",
    ]


def test_scheduled_prompt_periphery_artifacts_reject_invalid_and_foreign_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "periphery-user")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Periphery prompt",
            "promptText": "Write private periphery notes",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
    ).json()
    other = scheduled_prompts.create_scheduled_prompt(
        {
            "title": "Other periphery prompt",
            "promptText": "Write private periphery notes",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
        user_id="other-user",
    )
    artifact_dir = Path(created["myFolder"]) / "periphery" / "risk_radar" / "2026" / "06"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "invalid_json.risk_radar.json").write_text("{", encoding="utf-8")
    (artifact_dir / "mismatch.risk_radar.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "health_pressure",
                "generatedAt": "2026-06-25T07:00:00Z",
                "scheduledRunRef": {},
                "sourceRefs": [],
                "confidence": "low",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P7D",
                "staleAfter": "2026-07-02T07:00:00Z",
                "observations": [],
                "risks": [],
                "blindSpots": [],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": [],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )
    missing_required = {
        "schemaVersion": 1,
        "moduleId": "risk_radar",
        "generatedAt": "2026-06-25T07:00:00Z",
        "scheduledRunRef": {},
        "sourceRefs": [],
        "severity": "low",
        "timeSensitivity": "low",
        "ttl": "P7D",
        "staleAfter": "2026-07-02T07:00:00Z",
        "observations": [],
        "risks": [],
        "blindSpots": [],
        "opportunityCosts": [],
        "opportunities": [],
        "whatWouldMakeThisWrong": [],
        "whenToSurface": [],
        "proposedActions": [],
        "memoryProposalRefs": [],
    }
    (artifact_dir / "missing_required.risk_radar.json").write_text(
        json.dumps(missing_required),
        encoding="utf-8",
    )

    response = client.get(f"/api/scheduled-prompts/{created['id']}/periphery-artifacts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifacts"] == []
    assert {item["reason"] for item in payload["invalidArtifacts"]} == {
        "invalid_json",
        "missing_required_fields",
        "module_path_mismatch",
    }
    [missing] = [item for item in payload["invalidArtifacts"] if item["reason"] == "missing_required_fields"]
    assert missing["missingFields"] == ["confidence"]
    assert str(tmp_path) not in json.dumps(payload)
    assert client.get(f"/api/scheduled-prompts/{other['id']}/periphery-artifacts").status_code == 403


def test_scheduled_prompt_periphery_artifacts_report_missing_markdown_and_user_schedule_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "periphery-user")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Periphery prompt",
            "promptText": "Write private periphery notes",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "propose",
        },
    ).json()
    artifact_dir = Path(created["myFolder"]) / "periphery" / "risk_radar" / "2026" / "06"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "20260625T031500Z.risk_radar.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "risk_radar",
                "generatedAt": "2026-06-25T07:15:00Z",
                "scheduledRunRef": {},
                "sourceRefs": [],
                "confidence": "low",
                "severity": "low",
                "timeSensitivity": "low",
                "ttl": "P7D",
                "staleAfter": "2026-07-02T07:15:00Z",
                "observations": [],
                "risks": [],
                "blindSpots": [],
                "opportunityCosts": [],
                "opportunities": [],
                "whatWouldMakeThisWrong": [],
                "whenToSurface": [],
                "proposedActions": [],
                "memoryProposalRefs": [],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/scheduled-prompts/{created['id']}/periphery-artifacts")

    assert response.status_code == 200
    [artifact] = response.json()["artifacts"]
    assert artifact["markdownExists"] is False

    user_schedule = client.get("/api/scheduled-prompts/user_schedule:task-1/periphery-artifacts")
    assert user_schedule.status_code == 400
    assert "User-level schedules" in user_schedule.json()["detail"]


def test_scheduled_prompt_manual_run_uses_workbench_storage_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("SCHEDULING_DB_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("SCHEDULER_GLASSHIVE_DISABLE_DISPATCH", "1")
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    client = TestClient(app)
    created = client.post(
        "/api/scheduled-prompts",
        json={
            "title": "Default storage prompt",
            "promptText": "Write to {{local.viventium.my_folder}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
        },
    )
    assert created.status_code == 200
    prompt_id = created.json()["id"]

    manual = client.post(f"/api/scheduled-prompts/{prompt_id}/manual-runs")
    assert manual.status_code == 200
    assert manual.json()["run"]["status"] == "queued"
    assert os.environ["SCHEDULING_DB_PATH"].endswith(
        "Library/Application Support/Viventium/state/runtime/isolated/scheduling/schedules.db"
    )
    listed = client.get("/api/scheduled-prompts")
    [row] = [item for item in listed.json()["scheduledPrompts"] if item["id"] == prompt_id]
    assert [run["status"] for run in row["recentRuns"]] == ["queued"]


def test_user_level_scheduled_tasks_show_in_workbench_and_can_be_managed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "user-a")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    now = "2026-05-22T10:00:00Z"
    scheduled_prompts.storage().create_task(
        {
            "id": "task-user-level",
            "user_id": "user-a",
            "agent_id": "agent-1",
            "prompt": "Existing user-level scheduled prompt",
            "schedule": {"type": "cron", "cron": "17 4 * * 2", "timezone": "UTC", "custom": "preserve"},
            "channel": "telegram",
            "executor": "viventium_agent",
            "conversation_policy": "same",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:agent-1",
            "created_source": "user",
            "created_at": now,
            "updated_at": now,
            "updated_by": "agent:agent-1",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-23T03:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": None,
        }
    )

    client = TestClient(app)
    listed = client.get("/api/scheduled-prompts")
    assert listed.status_code == 200
    [user_schedule] = [
        item for item in listed.json()["scheduledPrompts"] if item["sourceKind"] == "user_schedule"
    ]
    assert user_schedule["id"] == "user_schedule:task-user-level"
    assert user_schedule["title"] == "Existing user-level scheduled prompt"
    assert user_schedule["executor"] == "viventium_agent"
    assert user_schedule["channel"] == "telegram"

    title_only = client.patch(
        f"/api/scheduled-prompts/{user_schedule['id']}",
        json={"title": "Renamed without schedule rewrite", "active": False},
    )
    assert title_only.status_code == 200
    task_after_title_only = scheduled_prompts.storage().get_task("user-a", "task-user-level")
    assert task_after_title_only["active"] == 0
    assert task_after_title_only["schedule"] == {"type": "cron", "cron": "17 4 * * 2", "timezone": "UTC", "custom": "preserve"}
    assert task_after_title_only["metadata"]["workbench_title"] == "Renamed without schedule rewrite"

    patched = client.patch(
        f"/api/scheduled-prompts/{user_schedule['id']}",
        json={
            "title": "Renamed user schedule",
            "active": True,
            "schedule": {"type": "daily", "time": "06:15", "timezone": "UTC"},
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed user schedule"
    assert patched.json()["active"] is True
    task = scheduled_prompts.storage().get_task("user-a", "task-user-level")
    assert task["active"] == 1
    assert task["schedule"]["time"] == "06:15"
    assert task["metadata"]["workbench_title"] == "Renamed user schedule"

    monkeypatch.setattr(
        scheduled_prompts,
        "dispatch_task",
        lambda task: {"delivery": {"outcome": "sent", "reason": "manual_run", "generated_text": "private result"}},
    )
    manual_without_confirmation = client.post(f"/api/scheduled-prompts/{user_schedule['id']}/manual-runs")
    assert manual_without_confirmation.status_code == 400
    assert "explicit delivery confirmation" in manual_without_confirmation.json()["detail"]

    manual = client.post(
        f"/api/scheduled-prompts/{user_schedule['id']}/manual-runs",
        json={"confirmUserLevelDelivery": True},
    )
    assert manual.status_code == 200
    assert manual.json()["run"]["status"] == "success"
    assert manual.json()["run"]["resultSummary"] == "sent: manual_run"
    runs = client.get(f"/api/scheduled-prompts/{user_schedule['id']}/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["status"] == "success"

    scheduled_prompts.storage().update_task(
        "user-a",
        "task-user-level",
        {
            "last_status": "failed",
            "last_error": (
                f"failure at {synthetic_home_path('private', 'path')} "
                f"with mongodb://127.0.0.1:27017/db and http://{synthetic_private_ip()}:8783/log"
            ),
            "updated_at": now,
        },
    )
    failed_runs = client.get(f"/api/scheduled-prompts/{user_schedule['id']}/runs")
    assert failed_runs.status_code == 200
    failed_run = failed_runs.json()["runs"][0]
    assert failed_run["status"] == "failed"
    assert "/Users/" not in failed_run["errorClass"]
    assert "mongodb://" not in failed_run["errorClass"]
    assert synthetic_private_ip() not in failed_run["errorClass"]

    deleted = client.delete(f"/api/scheduled-prompts/{user_schedule['id']}")
    assert deleted.status_code == 200
    assert scheduled_prompts.storage().get_task("user-a", "task-user-level") is None


def test_workbench_startup_seeds_builtin_nightly_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "startup-admin")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL", "startup-admin@example.test")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE", "false")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    with TestClient(app):
        pass

    rows = scheduled_prompts.storage().list_scheduled_prompt_definitions(user_id="startup-admin")
    seeded = [row for row in rows if row.get("template_id") == scheduled_prompts.NIGHTLY_TEMPLATE_ID]
    assert len(seeded) == 1
    assert not seeded[0]["active"]
    task = scheduled_prompts.storage().get_task("startup-admin", seeded[0]["task_id"])
    assert task["executor"] == "glasshive_host"
    assert task["channel"] == "workbench"
    assert task["metadata"]["misfire_policy"] == {"mode": "catch_up", "max_late_s": 12 * 60 * 60}


def test_workbench_startup_seeds_active_glasshive_nightly_from_runtime_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "startup-admin")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL", "startup-admin@example.test")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED", "true")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE", "true")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR", "glasshive_host")
    monkeypatch.setenv("GLASSHIVE_DEFAULT_WORKER_PROFILE", "claude-code")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    with TestClient(app):
        pass

    rows = scheduled_prompts.storage().list_scheduled_prompt_definitions(user_id="startup-admin")
    seeded = [row for row in rows if row.get("template_id") == scheduled_prompts.NIGHTLY_TEMPLATE_ID]
    assert len(seeded) == 1
    assert seeded[0]["active"]
    task = scheduled_prompts.storage().get_task("startup-admin", seeded[0]["task_id"])
    assert task["executor"] == "glasshive_host"
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_profile"] == "claude-code"
    assert task["metadata"]["misfire_policy"] == {"mode": "catch_up", "max_late_s": 12 * 60 * 60}


def test_workbench_nightly_seed_logs_unresolved_admin_retry_window(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from prompt_workbench import app as app_module

    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_POLL_SECONDS", "0")
    monkeypatch.setattr(app_module, "_seed_builtin_scheduled_prompts", lambda: False)

    with caplog.at_level(logging.WARNING, logger="prompt_workbench.nightly_seed"):
        app_module._seed_when_first_admin_exists()

    assert "could not resolve a unique local admin" in caplog.text


def test_prompt_workbench_stop_sets_user_stopped_marker(tmp_path: Path) -> None:
    args = SimpleNamespace(repo_root=str(REPO_ROOT), app_support_dir=str(tmp_path))

    result = prompt_workbench_cli.stop_server(args)

    assert result["status"] == "stopped"
    marker = prompt_workbench_cli.user_stopped_marker_path(tmp_path)
    assert marker.exists()
    prompt_workbench_cli.clear_user_stopped_marker(tmp_path)
    assert not marker.exists()


def test_workbench_local_storage_access_goes_through_safe_wrapper() -> None:
    offenders: list[str] = []
    for path in WORKBENCH_SRC.rglob("*"):
        if path.name == "storage.ts" or path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\blocalStorage\b", text):
            offenders.append(str(path.relative_to(WORKBENCH_SRC)))

    assert offenders == []
    assert "viventium.promptWorkbench.syncSidebarOpen" in (WORKBENCH_SRC / "App.tsx").read_text(encoding="utf-8")


def test_prompt_rendered_tab_uses_safe_html_reader() -> None:
    editor_source = (WORKBENCH_SRC / "components" / "PromptEditor.tsx").read_text(encoding="utf-8")
    rendered_source = (WORKBENCH_SRC / "components" / "RenderedPrompt.tsx").read_text(encoding="utf-8")

    assert "<RenderedPrompt markdown={prompt.rendered}" in editor_source
    assert '<pre className="rendered-preview"' not in editor_source
    assert "dangerouslySetInnerHTML" not in rendered_source
    assert "kind: 'heading'" in rendered_source
    assert "kind: 'list'" in rendered_source
    assert "rendered-raw-text" in rendered_source
    assert "setMode('raw')" in rendered_source


def test_prompt_flow_map_uses_source_graph_eval_refs_and_double_click_navigation() -> None:
    flow_source = (WORKBENCH_SRC / "components" / "PromptFlow.tsx").read_text(encoding="utf-8")
    dock_source = (WORKBENCH_SRC / "components" / "WorkbenchDock.tsx").read_text(encoding="utf-8")
    app_source = (WORKBENCH_SRC / "App.tsx").read_text(encoding="utf-8")

    for label in [
        "Interaction Surfaces",
        "Conscious Agent",
        "Memory and Recall",
        "Background Cortex and Tools",
        "Delivery and Evaluation",
    ]:
        assert label in flow_source
    assert "onNodeDoubleClick" in flow_source
    assert "promptRefsForFamily" in flow_source
    assert "evalBank={tabState.evalBank}" in dock_source
    assert "onOpenPrompt={openPromptFromMap}" in app_source


def test_eval_panel_uses_declared_lineage_for_links_and_exposes_dependency_details() -> None:
    source = (WORKBENCH_SRC / "components" / "EvalPanel.tsx").read_text(encoding="utf-8")

    assert "selectedPromptId === 'main.conscious_agent'" not in source
    assert "['main.conscious_agent']" not in source
    assert "runHasPromptDependency" in source
    assert "Prompt and runtime context dependencies" in source
    assert "lineageManifest" in source
    assert "runnerSummary?.status" in source
    assert "semanticPassedCount" in source
    assert "semanticJudgeUnavailableCount" in source
    assert "judge unavailable" in source
    assert "semanticJudgeRequired" in source
    assert "Independent semantic rubric judging is required" in source
    assert "max={Math.max(1, visibleRows.length)}" in source
    assert "max={25}" not in source

    browser_harness = (
        REPO_ROOT / "qa/prompt-workbench/scripts/live-evals-browser-qa.cjs"
    ).read_text(encoding="utf-8")
    assert "FEELINGS_RUN_TIMEOUT_MS" in browser_harness
    assert "FEELINGS_MAX_CASES * 420_000" in browser_harness


def test_prompt_diff_wraps_both_panes_and_uses_working_tree_baseline() -> None:
    editor_source = (WORKBENCH_SRC / "components" / "PromptEditor.tsx").read_text(encoding="utf-8")
    diff_helper_source = (WORKBENCH_SRC / "promptDiff.ts").read_text(encoding="utf-8")
    api_source = (WORKBENCH_SRC / "api.ts").read_text(encoding="utf-8")
    types_source = (WORKBENCH_SRC / "types.ts").read_text(encoding="utf-8")
    css_source = (WORKBENCH_SRC / "styles.css").read_text(encoding="utf-8")
    app_source = (WORKBENCH_BACKEND / "prompt_workbench" / "app.py").read_text(encoding="utf-8")

    assert "diffWordWrap: 'on'" in editor_source
    assert "wordWrapOverride1: 'on'" in editor_source
    assert "wordWrapOverride2: 'on'" in editor_source
    assert "choosePromptDiffText" in editor_source
    assert "export function choosePromptDiffText" in diff_helper_source
    assert "workingTreeBaseText !== undefined" in diff_helper_source
    assert "workingTreeBaseText !== null" in diff_helper_source
    assert "prompt?.workingTreeBaseText && hasWorkingTreeSourceChange" not in editor_source
    assert "workingTreeBaseText" in diff_helper_source
    assert "Compare from" in editor_source
    assert "diffBaseOptions" in editor_source
    assert "getPromptRevision" in editor_source
    assert "selectedBaseText" in diff_helper_source
    assert "/api/prompts/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}" in api_source
    assert "interface PromptRevision" in types_source
    assert "@app.get(\"/api/prompts/{prompt_id}/revisions/{revision}\")" in app_source
    assert "workingTreeBaseText?: string | null" in types_source
    assert "workingTreeChanged?: boolean" in types_source
    assert ".diff-toolbar" in css_source
    assert ".diff-editor-shell" in css_source
    assert ".patch-preview pre" in css_source
    assert "white-space: pre-wrap" in css_source
    assert "overflow-wrap: anywhere" in css_source


def test_prompt_diff_text_helper_handles_working_tree_empty_baseline() -> None:
    if not (WORKBENCH_ROOT / "node_modules" / "typescript").exists():
        pytest.skip("Prompt Workbench TypeScript dependencies are not installed")
    helper_path = WORKBENCH_SRC / "promptDiff.ts"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const ts = require('typescript');
const source = fs.readFileSync(process.argv[1], 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
});
const module = { exports: {} };
vm.runInNewContext(compiled.outputText, { module, exports: module.exports, require });
const choosePromptDiffText = module.exports.choosePromptDiffText;
const cases = [
  {
    name: 'clean working-tree untracked baseline',
    input: { changed: false, currentPromptText: 'current', nextText: 'next', workingTreeChanged: true, workingTreeBaseText: '' },
    expected: { original: '', modified: 'current' },
  },
  {
    name: 'clean working-tree tracked baseline',
    input: { changed: false, currentPromptText: 'current', nextText: 'next', workingTreeChanged: true, workingTreeBaseText: 'head' },
    expected: { original: 'head', modified: 'current' },
  },
  {
    name: 'clean unchanged source',
    input: { changed: false, currentPromptText: 'current', nextText: 'next', workingTreeChanged: false, workingTreeBaseText: 'head' },
    expected: { original: 'current', modified: 'current' },
  },
  {
    name: 'dirty editor takes precedence',
    input: { changed: true, currentPromptText: 'current', nextText: 'editor', workingTreeChanged: true, workingTreeBaseText: 'head' },
    expected: { original: 'current', modified: 'editor' },
  },
  {
    name: 'selected history revision is explicit baseline',
    input: { changed: true, currentPromptText: 'current', nextText: 'editor', workingTreeChanged: true, workingTreeBaseText: 'head', selectedBaseText: 'old commit' },
    expected: { original: 'old commit', modified: 'editor' },
  },
  {
    name: 'selected current source overrides implicit working tree baseline',
    input: { changed: false, currentPromptText: 'current', nextText: 'next', workingTreeChanged: true, workingTreeBaseText: 'head', selectedBaseText: 'current' },
    expected: { original: 'current', modified: 'current' },
  },
  {
    name: 'null baseline falls back to current source',
    input: { changed: false, currentPromptText: 'current', nextText: 'next', workingTreeChanged: true, workingTreeBaseText: null },
    expected: { original: 'current', modified: 'current' },
  },
];
for (const testCase of cases) {
  const actual = choosePromptDiffText(testCase.input);
  if (JSON.stringify(actual) !== JSON.stringify(testCase.expected)) {
    throw new Error(`${testCase.name}: expected ${JSON.stringify(testCase.expected)} got ${JSON.stringify(actual)}`);
  }
}
"""
    subprocess.run(
        ["node", "-e", script, str(helper_path)],
        cwd=WORKBENCH_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_prompt_revision_text_comes_from_selected_git_revision(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "prompt.md"

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "qa@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "QA"], cwd=repo, check=True)
    target.write_text("first version\n", encoding="utf-8")
    subprocess.run(["git", "add", "prompt.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=repo, check=True, capture_output=True, text=True)
    first_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=repo, text=True).strip()
    target.write_text("second version\n", encoding="utf-8")
    subprocess.run(["git", "add", "prompt.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=repo, check=True, capture_output=True, text=True)

    assert prompt_service.normalize_prompt_revision(first_commit) == first_commit
    assert prompt_service.git_text_at_revision(target, first_commit, cwd=repo, git_path="prompt.md") == "first version\n"
    with pytest.raises(ValueError):
        prompt_service.normalize_prompt_revision(first_commit[:4])
    with pytest.raises(ValueError):
        prompt_service.normalize_prompt_revision("HEAD;rm -rf /")


@pytest.mark.parametrize("stage_change", [False, True])
def test_prompt_history_surfaces_uncommitted_working_tree_changes(tmp_path: Path, stage_change: bool) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "prompt.md"
    target.write_text("first applied line\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "prompt.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=QA", "-c", "user.email=qa@example.test", "commit", "-m", "initial prompt"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    target.write_text("first applied line\nsecond uncommitted line\n", encoding="utf-8")
    if stage_change:
        subprocess.run(["git", "add", "prompt.md"], cwd=repo, check=True, capture_output=True, text=True)

    rows = prompt_service.git_history(target, limit=1)
    head_text = prompt_service.git_text_at_head(target)

    assert rows[0]["commit"] == "working-tree"
    assert rows[0]["workingTree"] is True
    assert rows[0]["subject"] == "Uncommitted source changes"
    assert rows[0]["changeSummary"]["additions"] == 1
    assert "+second uncommitted line" in rows[0]["patch"]
    assert str(tmp_path) not in rows[0]["patch"]
    assert head_text == "first applied line\n"


def test_prompt_history_surfaces_untracked_prompt_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    readme = repo / "README.md"
    readme.write_text("initial repo\n", encoding="utf-8")
    target = repo / "new_prompt.md"

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=QA", "-c", "user.email=qa@example.test", "commit", "-m", "initial repo"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    target.write_text("---\nid: qa.new_prompt\n---\nnew body\n", encoding="utf-8")

    rows = prompt_service.git_history(target, limit=1)

    assert rows[0]["commit"] == "working-tree"
    assert rows[0]["workingTree"] is True
    assert rows[0]["changeSummary"]["additions"] == 4
    assert "new file mode" in rows[0]["patch"]
    assert "+new body" in rows[0]["patch"]
    assert str(tmp_path) not in rows[0]["patch"]
    assert prompt_service.git_text_at_head(target) is None


@pytest.mark.parametrize(
    ("source_hash", "live_hash", "ledger", "expected"),
    [
        ("a", "a", {"sourceHash": "a", "liveHash": "a"}, "synced"),
        ("a", "b", {"sourceHash": "a", "liveHash": "a"}, "live-ahead"),
        ("b", "a", {"sourceHash": "a", "liveHash": "a"}, "source-ahead"),
        ("b", "c", {"sourceHash": "a", "liveHash": "a"}, "conflict"),
        ("b", "c", None, "conflict"),
    ],
)
def test_sync_state_classifier(source_hash: str, live_hash: str, ledger: dict[str, str] | None, expected: str) -> None:
    assert (
        sync_engine.classify_sync_state(
            source_hash=source_hash,
            live_hash=live_hash,
            ledger_record=ledger,
        )
        == expected
    )


def test_clean_live_edit_maps_to_one_markdown_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    private_root = tmp_path / "private"
    write_prompt(prompt_root, "main.md", "main.test", "", includes=["section.test"])
    section_path = write_prompt(prompt_root, "section.md", "section.test", "# Section\nold behavior\n")
    monkeypatch.setattr(import_mapper, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)

    draft = import_mapper.create_import_live_draft(
        prompt_id="main.test",
        live_text="# Section\nnew behavior\n",
        private_root=private_root,
    )

    assert draft["status"] == "draft"
    assert draft["mappedPromptId"] == "section.test"
    assert "new behavior" in draft["patch"]
    assert draft["targetPath"].endswith("section.md")
    assert section_path.read_text(encoding="utf-8").count("old behavior") == 1


def test_ambiguous_live_edit_requires_manual_target() -> None:
    source = "# One\nold\n\n# Two\nold\n"
    live = "# One\nnew\n\n# Two\nnew\n"
    candidate = import_mapper.derive_single_section_replacement(
        source,
        live,
        [("one", "# One\nold"), ("two", "# Two\nold")],
    )

    assert candidate is None


def test_public_prompt_safety_blocks_private_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    private_text = target.read_text(encoding="utf-8") + "\nContact user@example.com\n"

    with pytest.raises(ValueError, match="Private pattern email_address"):
        drafts.create_file_draft(
            target_path=target,
            new_text=private_text,
            kind="source-edit",
            private_root=tmp_path / "private",
        )


def test_public_safety_scan_applies_to_eval_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)

    with pytest.raises(ValueError, match="Private pattern bearer_token"):
        fake_bearer_token = "Bearer " + "abcdefghijklmnop"
        drafts.create_file_draft(
            target_path=prompt_bank,
            new_text=json.dumps({"note": fake_bearer_token}),
            kind="eval-edit",
            private_root=tmp_path / "private",
        )


def test_eval_draft_target_is_limited_to_prompt_bank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    runner = eval_root / "run-exact-model-evals.cjs"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    runner.write_text("console.log('runner');\n", encoding="utf-8")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)

    with pytest.raises(ValueError, match="outside prompt/eval source roots"):
        drafts.create_file_draft(
            target_path=runner,
            new_text="console.log('changed');\n",
            kind="eval-edit",
            private_root=tmp_path / "private",
        )


def test_sync_status_rows_do_not_return_live_instruction_text() -> None:
    row = sync_engine._row_for_agent(
        agent_id="agent_test",
        label="Test",
        source_prompt_id="main.identity",
        source_instructions="source",
        live_instructions="live private prompt",
        live_version=1,
        records={},
    )

    assert "_liveInstructions" not in row
    assert row["liveTextAvailable"] is True
    assert sync_engine.LIVE_TEXT_CACHE["agent_test"] == "live private prompt"


def test_sync_status_does_not_return_local_absolute_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "source_agents_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(
        sync_engine,
        "load_latest_live_bundle",
        lambda: {"_artifactPath": str(tmp_path / "runs" / "viventium-agents.yaml"), "mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}},
    )
    monkeypatch.setattr(sync_engine, "_git_commit", lambda: "abc123")

    status = sync_engine.get_status(private_root=tmp_path / "private")
    encoded = json.dumps(status)

    assert "liveArtifactPath" not in status
    assert "ledgerPath" not in status
    assert str(tmp_path) not in encoded
    assert status["liveArtifactAvailable"] is True
    assert status["liveArtifactName"] == "viventium-agents.yaml"


def test_prompt_workbench_redacts_custom_private_roots_and_ledger_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "custom-private-root"
    private_artifact = private_root / "runs" / "result.json"
    command = ["node", "runner.js", f"--output={private_artifact}"]

    assert str(private_root) not in json.dumps(
        evals._safe_command(command, private_paths=(private_root,))
    )
    assert str(private_root) not in evals._sanitize_output(
        f"wrote {private_artifact}", private_paths=(private_root,)
    )
    assert str(private_root) not in json.dumps(
        sync_engine._safe_command(command, private_paths=(private_root,))
    )
    assert str(private_root) not in sync_engine._sanitize_output(
        f"wrote {private_artifact}", private_paths=(private_root,)
    )

    monkeypatch.setattr(sync_engine, "get_status", lambda private_root=None: {"agents": []})
    result = sync_engine.refresh_ledger_after_reconcile(private_root=private_root)

    assert result == {
        "status": "updated",
        "recordCount": 0,
        "ledgerAvailable": True,
        "ledgerName": "sync-ledger.json",
    }
    assert str(private_root) not in json.dumps(result)
    assert (private_root / "sync-ledger.json").is_file()


def test_pull_live_uses_pull_action(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0}

    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)

    sync_engine.pull_live(env="local")

    assert calls == [["pull", "--env=local"]]


def test_reviewed_push_uses_stored_dry_run_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0, "parsed": {"args": args}, "stdoutTail": "timestamp changes"}

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)
    monkeypatch.setattr(sync_engine, "refresh_ledger_after_reconcile", lambda private_root=None: {"status": "updated"})
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}})

    dry_run = sync_engine.push_live_dry_run(env="local")
    reviewed = sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert reviewed["returnCode"] == 0
    assert calls[0] == ["push", "--env=local", "--prompts-only", "--dry-run"]
    assert calls[1] == ["push", "--env=local", "--prompts-only", "--compare-reviewed"]

    with pytest.raises(ValueError, match="stored dry-run"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")


def test_reviewed_push_refuses_unresolved_live_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> dict[str, object]:
        calls.append(args)
        return {"returnCode": 0, "parsed": {"args": args}, "stdoutTail": "timestamp changes"}

    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "run_agent_sync", fake_run)
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": []})
    dry_run = sync_engine.push_live_dry_run(env="local")
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 0, "source-ahead": 0, "live-ahead": 1, "conflict": 0}})

    with pytest.raises(ValueError, match="Live drift still needs review"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_eval_preview_blocks_pending_prompt_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=False, prompt_id="main.voice_style")


def test_live_eval_blocks_any_pending_prompt_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "identity.md", "main.identity", "Applied identity")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied identity", "Draft identity"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=True, prompt_id="main.voice_style")


def test_live_eval_runner_uses_prompt_bank_equals_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps(
            {
                "families": [
                    {
                        "id": "voice_style",
                        "promptRefs": ["main.voice_style"],
                        "cases": [
                            {"id": "case_one", "surface": "voice"},
                            {"id": "case_two", "surface": "voice"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runner = eval_root / "run-exact-model-evals.cjs"
    runner.write_text("// synthetic runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[tuple[list[str], int, dict[str, str] | None]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(
        evals,
        "load_eval_bank",
        lambda: json.loads(prompt_bank.read_text(encoding="utf-8")),
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append((cmd, int(kwargs["timeout"]), kwargs.get("env")))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(
        max_cases=2,
        live=True,
        prompt_id="main.voice_style",
        case_ids=["case_two", "case_one"],
    )

    assert result["returnCode"] == 0
    assert captured
    assert f"--prompt-bank={prompt_bank}" in captured[0][0]
    assert "--prompt-bank" not in captured[0][0]
    assert "--prompt-id=main.voice_style" in captured[0][0]
    assert "--case-ids=case_two,case_one" in captured[0][0]
    assert "--local-jwt-fallback" in captured[0][0]
    assert captured[0][1] == 840
    assert captured[0][2] is not None
    assert captured[0][2]["VIVENTIUM_QA_ALLOW_LOCAL_JWT"] == "1"


def test_live_eval_timeout_scales_for_multi_case_exact_model_runs() -> None:
    assert evals._live_eval_timeout_seconds(1, evals.EXACT_MODEL_EVAL_SCRIPT) == 420
    assert evals._live_eval_timeout_seconds(10, evals.EXACT_MODEL_EVAL_SCRIPT) == 4200
    assert evals._live_eval_timeout_seconds(30, evals.EXACT_MODEL_EVAL_SCRIPT) == 12600
    assert evals._live_eval_timeout_seconds(100, evals.EXACT_MODEL_EVAL_SCRIPT) == 14400


def test_declared_semantic_eval_family_runs_its_rubric_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bank = {
        "families": [
            {
                "id": "semantic_family",
                "semanticJudge": True,
                "promptRefs": ["main.conscious_agent"],
                "cases": [
                    {
                        "id": "case_a",
                        "surface": "web",
                        "prompt": "Synthetic prompt",
                        "rubric": ["responds naturally"],
                    }
                ],
            }
        ]
    }
    prompt_bank = tmp_path / "prompt-bank.json"
    prompt_bank.write_text(json.dumps(bank), encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[list[str]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="semantic_family",
        prompt_id="main.conscious_agent",
    )

    assert result["returnCode"] == 0
    assert "--semantic-judge" in captured[0]
    assert result["semanticJudgeRequired"] is True


def test_live_eval_timeout_is_saved_as_an_inspectable_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    runner = eval_root / "run-exact-model-evals.cjs"
    runner.write_text("// synthetic runner\n", encoding="utf-8")
    private_root = tmp_path / "private"

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], output=b"partial progress")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(max_cases=2, live=True, prompt_id="main.voice_style")

    assert result["returnCode"] == 124
    assert result["timeoutSeconds"] == 840
    assert "timed out after 840 seconds" in result["stderrTail"]
    run_record = json.loads(
        (private_root / "eval-runs" / result["id"] / "workbench-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert run_record["returnCode"] == 124
    assert run_record["stdoutTail"] == "partial progress"


def test_live_activation_eval_uses_dedicated_runtime_classifier_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps(
            {
                "families": [
                    {
                        "id": "background_activation_routing",
                        "runner": "background_activation",
                        "promptRefs": ["cortex.red_team.activation"],
                        "activationTargets": [
                            {
                                "key": "red_team",
                                "promptRef": "cortex.red_team.activation",
                            }
                        ],
                        "cases": [
                            {
                                "id": "red_team_explicit",
                                "surface": "web",
                                "prompt": "Red-team this launch decision.",
                                "messages": [
                                    {"role": "user", "content": "Red-team this launch decision."}
                                ],
                                "required_activations": ["red_team"],
                                "allowed_activations": ["red_team"],
                                "rubric": ["Red Team activates and sibling cortices stay quiet."],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    exact_runner = eval_root / "run-exact-model-evals.cjs"
    exact_runner.write_text("// exact runner\n", encoding="utf-8")
    activation_runner = eval_root / "run-activation-model-evals.cjs"
    activation_runner.write_text("// activation runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[tuple[list[str], dict[str, str] | None]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", exact_runner)
    monkeypatch.setattr(evals, "ACTIVATION_MODEL_EVAL_SCRIPT", activation_runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(
        evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8"))
    )

    monkeypatch.setenv("VIVENTIUM_QA_USER_NAME", "Synthetic QA")
    monkeypatch.setenv("VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS", "6000")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append((cmd, kwargs.get("env")))
        return subprocess.CompletedProcess(cmd, 0, stdout="activation ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="background_activation_routing",
        prompt_id="cortex.red_team.activation",
    )

    assert result["returnCode"] == 0
    assert captured
    assert captured[0][0][1] == str(activation_runner)
    assert "--family=background_activation_routing" in captured[0][0]
    assert "--prompt-id=cortex.red_team.activation" in captured[0][0]
    assert "--qa-user-context" in captured[0][0]
    assert "--with-fallbacks" in captured[0][0]
    assert "--timeout-ms=6000" in captured[0][0]
    assert captured[0][1] is not None
    assert captured[0][1]["VIVENTIUM_QA_USER_NAME"] == "Synthetic QA"

    captured.clear()
    broad_result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="background_activation_routing",
        prompt_id="main.conscious_agent",
    )

    assert broad_result["returnCode"] == 0
    assert captured
    assert "--prompt-id=main.conscious_agent" not in captured[0][0]


def test_background_execution_eval_targets_the_specialist_agent_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    bank = {
        "families": [
            {
                "id": "emotional_resonance_execution",
                "runner": "background_execution",
                "executionTarget": {
                    "agentId": "synthetic-eq-agent",
                    "promptRef": "cortex.emotional_resonance.execution",
                },
                "promptRefs": ["cortex.emotional_resonance.execution"],
                "evalIsolation": {
                    "savedMemory": True,
                    "conversationRecall": True,
                    "feelings": True,
                    "backgroundCortices": True,
                },
                "cases": [
                    {
                        "id": "reads_uncertain_subtext_without_inventing",
                        "surface": "web",
                        "prompt": "I said yes, but kept rewriting the last sentence.",
                        "rubric": [
                            "surfaces plausible emotional subtext as uncertainty rather than fact",
                            "does not adopt a warm or gentle demeanor as the task",
                        ],
                    }
                ],
            }
        ]
    }
    prompt_bank.write_text(json.dumps(bank), encoding="utf-8")
    runner = eval_root / "run-exact-model-evals.cjs"
    runner.write_text("// synthetic exact runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[list[str]] = []
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="execution ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="emotional_resonance_execution",
        prompt_id="cortex.emotional_resonance.execution",
    )

    assert result["returnCode"] == 0
    assert "--agent-id=synthetic-eq-agent" in captured[0]
    assert "--semantic-judge" in captured[0]
    assert "--prompt-id=cortex.emotional_resonance.execution" in captured[0]
    assert result["executionTarget"] == {
        "mode": "direct_background_agent",
        "agentId": "synthetic-eq-agent",
        "promptRef": "cortex.emotional_resonance.execution",
    }
    assert result["lineageManifest"]["executionTarget"] == result["executionTarget"]

    captured.clear()
    inferred = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        prompt_id="cortex.emotional_resonance.execution",
    )
    assert inferred["executionTarget"] == result["executionTarget"]
    assert "--agent-id=synthetic-eq-agent" in captured[0]


def test_background_execution_eval_fails_closed_without_structured_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bank = {
        "families": [
            {
                "id": "broken_execution",
                "runner": "background_execution",
                "promptRefs": ["cortex.red_team.execution"],
                "cases": [{"id": "case", "surface": "web"}],
            }
        ]
    }
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")

    with pytest.raises(ValueError, match="structured executionTarget"):
        evals.run_exact_model_eval(
            max_cases=1,
            live=False,
            family="broken_execution",
            prompt_id="cortex.red_team.execution",
        )


def test_live_eval_records_public_runner_summary_and_actual_result_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bank = {
        "families": [
            {
                "id": "direct_specialist",
                "runner": "background_execution",
                "executionTarget": {
                    "agentId": "synthetic-specialist-agent",
                    "promptRef": "cortex.red_team.execution",
                },
                "promptRefs": ["cortex.red_team.execution"],
                "cases": [
                    {"id": "case_a", "surface": "web"},
                    {"id": "case_b", "surface": "web"},
                ],
            }
        ]
    }
    private_root = tmp_path / "private"
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    runner_stdout = json.dumps(
        {
            "status": "blocked",
            "blockedReason": "synthetic_dependency_unavailable",
            "resultCount": 0,
            "completedCount": 0,
            "failedCount": 0,
            "semanticJudgedCount": 0,
            "semanticPassedCount": 0,
            "semanticFailedCount": 0,
            "semanticJudgeUnavailableCount": 1,
            "duplicateResponseQualityFailureCount": 0,
            "unresolvedAsyncQualityFailureCount": 0,
            "publicReport": "/private/path/report.md",
            "privateJsonPathHash": "private-hash",
        }
    )
    monkeypatch.setattr(
        evals.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout=runner_stdout, stderr=""
        ),
    )

    result = evals.run_exact_model_eval(
        max_cases=2,
        live=True,
        family="direct_specialist",
        prompt_id="cortex.red_team.execution",
    )

    assert result["selectedCaseCount"] == 2
    assert result["resultCount"] == 0
    assert result["runnerSummary"] == {
        "status": "blocked",
        "blockedReason": "synthetic_dependency_unavailable",
        "resultCount": 0,
        "completedCount": 0,
        "failedCount": 0,
        "semanticJudgedCount": 0,
        "semanticPassedCount": 0,
        "semanticFailedCount": 0,
        "semanticJudgeUnavailableCount": 1,
        "duplicateResponseQualityFailureCount": 0,
        "unresolvedAsyncQualityFailureCount": 0,
    }
    assert "publicReport" not in result["runnerSummary"]
    assert "privateJsonPathHash" not in result["runnerSummary"]


def test_prompt_bank_registers_direct_specialist_execution_evals() -> None:
    bank = prompt_service.load_eval_bank()
    families = {row["id"]: row for row in bank["families"]}

    emotional = families["emotional_resonance_execution"]
    red_team = families["red_team_execution_independence"]
    assert emotional["runner"] == red_team["runner"] == "background_execution"
    assert emotional["executionTarget"]["promptRef"] == "cortex.emotional_resonance.execution"
    assert red_team["executionTarget"]["promptRef"] == "cortex.red_team.execution"
    assert emotional["evalIsolation"] == {
        "savedMemory": True,
        "conversationRecall": True,
        "feelings": True,
        "backgroundCortices": True,
    }
    assert red_team["evalIsolation"] == emotional["evalIsolation"]
    assert len(emotional["cases"]) >= 2
    assert len(red_team["cases"]) >= 2


def test_eval_preview_blocks_pending_eval_bank_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    drafts.create_file_draft(
        target_path=prompt_bank,
        new_text=json.dumps({"families": [{"id": "changed", "cases": []}]}) + "\n",
        kind="eval-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Eval preview blocked"):
        evals.run_exact_model_eval(max_cases=1, live=False, prompt_id="main.identity")


def test_active_draft_block_summary_is_public_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError) as raised:
        drafts.assert_no_active_blocking_drafts("Eval preview", prompt_id="main.voice_style")

    assert set(raised.value.blocking_drafts[0]) == {
        "id",
        "kind",
        "promptId",
        "targetPath",
        "status",
        "createdAt",
        "changeSummary",
    }
    encoded = json.dumps(raised.value.blocking_drafts)
    assert "newText" not in encoded
    assert "currentText" not in encoded
    assert "targetAbsolutePath" not in encoded
    assert "patch" not in encoded
    assert "idempotencyToken" not in encoded


def test_push_dry_run_blocks_pending_drafts_before_agent_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    calls: list[list[str]] = []
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0})

    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Push dry-run blocked"):
        sync_engine.push_live_dry_run(env="local")

    assert calls == []


def test_reviewed_push_blocks_pending_drafts_after_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    calls: list[list[str]] = []
    private_root = tmp_path / "private"
    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": []})
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0, "parsed": {"args": args}})

    dry_run = sync_engine.push_live_dry_run(env="local")
    drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Applied voice style", "Draft voice style"),
        kind="source-edit",
    )

    with pytest.raises(drafts.ActiveDraftBlockError, match="Reviewed push blocked"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_reviewed_push_refuses_source_changes_since_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = [
        {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": [{"agentId": "agent", "label": "Main", "sourceHash": "old"}]},
        {"counts": {"synced": 1, "source-ahead": 0, "live-ahead": 0, "conflict": 0}, "agents": [{"agentId": "agent", "label": "Main", "sourceHash": "new"}]},
    ]
    calls: list[list[str]] = []
    monkeypatch.setattr(sync_engine, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(sync_engine, "get_status", lambda: statuses.pop(0))
    monkeypatch.setattr(sync_engine, "run_agent_sync", lambda args: calls.append(args) or {"returnCode": 0, "parsed": {"args": args}})

    dry_run = sync_engine.push_live_dry_run(env="local")

    with pytest.raises(ValueError, match="Source changed since the stored dry-run"):
        sync_engine.push_live_reviewed(review_token=dry_run["reviewToken"], env="local")

    assert calls == [["push", "--env=local", "--prompts-only", "--dry-run"]]


def test_drafts_can_be_listed_and_discarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")

    draft = drafts.create_file_draft(
        target_path=target,
        new_text=target.read_text(encoding="utf-8").replace("Public text", "Public text updated"),
        kind="source-edit",
        private_root=tmp_path / "private",
    )
    listed = drafts.list_drafts(private_root=tmp_path / "private")
    discarded = drafts.discard_draft(draft["id"], private_root=tmp_path / "private")

    assert listed[0]["id"] == draft["id"]
    assert "currentText" not in listed[0]
    assert "newText" not in listed[0]
    assert listed[0]["changeSummary"]["additions"] == 1
    assert discarded["status"] == "discarded"


def test_duplicate_draft_saves_return_existing_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    new_text = target.read_text(encoding="utf-8").replace("Public text", "Public text updated")

    first = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=tmp_path / "private")
    second = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=tmp_path / "private")
    listed = drafts.list_drafts(private_root=tmp_path / "private")

    assert second["id"] == first["id"]
    assert second["duplicate"] is True
    assert len(listed) == 1


def test_apply_stale_draft_marks_already_applied_when_target_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    target = write_prompt(prompt_root, "safe.md", "safe.prompt", "Public text")
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", tmp_path / "evals" / "prompt-bank.json")
    private_root = tmp_path / "private"
    new_text = target.read_text(encoding="utf-8").replace("Public text", "Public text updated")
    draft = drafts.create_file_draft(target_path=target, new_text=new_text, kind="source-edit", private_root=private_root)
    target.write_text(new_text, encoding="utf-8")

    applied = drafts.apply_draft(draft["id"], draft["idempotencyToken"], private_root=private_root)

    assert applied["status"] == "applied"
    assert applied["alreadyApplied"] is True
    assert target.read_text(encoding="utf-8") == new_text


def test_repo_relative_prompt_paths_resolve_for_draft_api() -> None:
    rel_path = "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/identity.md"

    resolved = resolve_repo_path(rel_path)

    assert resolved == REPO_ROOT / rel_path
    assert resolved.exists()


def test_eval_preview_filters_family_and_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bank = {
        "families": [
            {
                "id": "family_a",
                "promptRefs": ["main.identity"],
                "cases": [{"id": "a_web", "surface": "web"}, {"id": "a_voice", "surface": "voice"}],
            },
            {
                "id": "family_b",
                "promptRefs": ["memory.transcript_summarizer"],
                "cases": [{"id": "b_web", "surface": "web"}],
            },
        ]
    }
    monkeypatch.setattr(evals, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)

    result = evals.run_exact_model_eval(max_cases=5, live=False, family="family_a", surface="voice", prompt_id="main.identity")

    assert result["mode"] == "synthetic-no-live-preview"
    assert result["resultCount"] == 1
    assert result["cases"] == [{"family": "family_a", "case": "a_voice", "surface": "voice"}]
    assert "outputDir" not in result
    assert result["privateOutputAvailable"] is True
    assert result["artifactName"] == result["id"]

    prompt_filtered = evals.run_exact_model_eval(
        max_cases=5,
        live=False,
        prompt_id="memory.transcript_summarizer",
    )

    assert prompt_filtered["cases"] == [{"family": "family_b", "case": "b_web", "surface": "web"}]
    assert prompt_filtered["promptHash"]

    explicit_cases = evals.run_exact_model_eval(
        max_cases=5,
        live=False,
        family="family_a",
        case_ids=["a_voice", "a_web", "a_voice"],
    )

    assert explicit_cases["cases"] == [
        {"family": "family_a", "case": "a_web", "surface": "web"},
        {"family": "family_a", "case": "a_voice", "surface": "voice"},
    ]
    assert explicit_cases["selectedCaseIds"] == ["a_web", "a_voice"]

    with pytest.raises(ValueError, match="do not match"):
        evals.run_exact_model_eval(
            max_cases=5,
            live=False,
            family="family_a",
            case_ids=["missing_case"],
        )

    with pytest.raises(ValueError, match="may contain only"):
        evals.run_exact_model_eval(
            max_cases=5,
            live=False,
            family="family_a",
            case_ids=["not a valid case id"],
        )


def test_eval_panel_exposes_explicit_case_selection_through_the_api_contract() -> None:
    panel_source = (WORKBENCH_SRC / "components" / "EvalPanel.tsx").read_text(
        encoding="utf-8"
    )
    api_source = (WORKBENCH_SRC / "api.ts").read_text(encoding="utf-8")
    app_source = (
        REPO_ROOT
        / "viventium_v0_4/prompt-workbench/backend/prompt_workbench/app.py"
    ).read_text(encoding="utf-8")

    assert 'aria-label={`Include ${row.caseId}`}' in panel_source
    assert "caseIds: selectedRunCaseIds" in panel_source
    assert "caseIds?: string[]" in api_source
    assert "caseIds: list[str]" in app_source


def test_feelings_eval_preview_records_complete_prompt_and_runtime_context_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    result = evals.run_exact_model_eval(
        max_cases=25,
        live=False,
        family="feelings_embodiment_and_reaction",
        prompt_id="main.conscious_agent",
    )

    lineage = result["lineageManifest"]
    prompt_ids = {row["id"] for row in lineage["promptDependencies"]}
    runtime_contexts = lineage["runtimeContextDependencies"]
    assert {
        "main.conscious_agent",
        "cortex.emotional_reaction.execution",
        "surface.voice.feeling_expression",
        "surface.telegram.audio_output",
        "surface.telegram.audio_provider.xai",
        "surface.telegram.audio_provider.plain_tts",
    }.issubset(prompt_ids)
    assert runtime_contexts == [
        {
            "id": "runtime.feelings.current_state",
            "kind": "runtime_context",
            "tag": "viventium_feeling_state",
            "lifecycle": "request_scoped",
            "owner": "feelings_runtime",
            "valuePolicy": "private_value_not_recorded",
            "roleContract": "eligible conscious/speaking synthesis context; not specialist-worker demeanor",
            "contractHash": runtime_contexts[0]["contractHash"],
        }
    ]
    assert lineage["promptCount"] == len(lineage["promptDependencies"])
    assert lineage["runtimeContextCount"] == 1
    assert lineage["manifestHash"]
    assert all("value" not in row for row in runtime_contexts)
    saved = json.loads(
        (private_root / "eval-runs" / result["id"] / "workbench-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["lineageManifest"]["manifestHash"] == lineage["manifestHash"]


def test_eval_run_history_is_linked_to_every_manifest_prompt_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    run_dir = private_root / "eval-runs" / "synthetic-run"
    run_dir.mkdir(parents=True)
    (run_dir / "workbench-run.json").write_text(
        json.dumps(
            {
                "id": "synthetic-run",
                "returnCode": 0,
                "stdoutTail": "",
                "stderrTail": "",
                "outputDir": str(run_dir),
                "createdAt": "2026-07-15T00:00:00Z",
                "live": True,
                "maxCases": 1,
                "promptId": "main.conscious_agent",
                "promptHash": "legacy-anchor-hash",
                "lineageManifest": {
                    "manifestHash": "manifest-hash",
                    "promptDependencies": [
                        {"id": "main.conscious_agent"},
                        {"id": "cortex.emotional_reaction.execution"},
                    ],
                    "runtimeContextDependencies": [],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)

    rows = evals.list_eval_runs_for_prompt("cortex.emotional_reaction.execution")

    assert [row["id"] for row in rows] == ["synthetic-run"]


def test_eval_run_history_does_not_implicitly_link_unowned_runs_to_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    run_dir = private_root / "eval-runs" / "specialist-only-run"
    run_dir.mkdir(parents=True)
    (run_dir / "workbench-run.json").write_text(
        json.dumps(
            {
                "id": "specialist-only-run",
                "returnCode": 0,
                "stdoutTail": "",
                "stderrTail": "",
                "outputDir": str(run_dir),
                "createdAt": "2026-07-15T00:00:00Z",
                "live": True,
                "maxCases": 1,
                "promptId": None,
                "lineageManifest": {
                    "manifestHash": "specialist-manifest-hash",
                    "promptDependencies": [
                        {"id": "cortex.red_team.execution"},
                    ],
                    "runtimeContextDependencies": [],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)

    main_rows = evals.list_eval_runs_for_prompt("main.conscious_agent")
    specialist_rows = evals.list_eval_runs_for_prompt("cortex.red_team.execution")

    assert main_rows == []
    assert [row["id"] for row in specialist_rows] == ["specialist-only-run"]


def test_eval_family_links_only_declared_prompt_dependencies() -> None:
    family = evals._public_family(
        {
            "id": "runtime_only",
            "promptRefs": ["memory.hardener_consolidation"],
            "cases": [{"id": "case", "surface": "memory_hardening"}],
        }
    )

    assert family["promptRefs"] == ["memory.hardener_consolidation"]
    assert family["cases"][0]["promptRefs"] == ["memory.hardener_consolidation"]


def test_eval_case_edit_creates_reviewed_eval_bank_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps({"families": [{"id": "family_a", "cases": [{"id": "case_a", "surface": "web", "prompt": "old", "rubric": ["old rubric"]}]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")

    draft = evals.create_eval_case_draft(
        family_id="family_a",
        case_id="case_a",
        updated_case={"prompt": "new", "rubric": ["new rubric"]},
    )

    assert draft["kind"] == "eval-edit"
    assert draft["status"] == "draft"
    assert "new rubric" in draft["patch"]
    assert prompt_bank.read_text(encoding="utf-8").count("old rubric") == 1


def test_eval_case_edit_rejects_semantic_noop_formatting_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        json.dumps({"families": [{"id": "family_a", "cases": [{"id": "case_a", "surface": "web", "prompt": "old", "rubric": ["old rubric"]}]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: tmp_path / "private")

    with pytest.raises(ValueError, match="No changes detected"):
        evals.create_eval_case_draft(
            family_id="family_a",
            case_id="case_a",
            updated_case={"prompt": "old", "rubric": ["old rubric"], "surface": "web"},
        )


def test_eval_case_create_appends_without_reformatting_unrelated_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(
        '{\n'
        '  "families": [\n'
        '    {\n'
        '      "id": "family_a",\n'
        '      "cases": [\n'
        '        {\n'
        '          "id": "case_a",\n'
        '          "surface": "web",\n'
        '          "prompt": "old",\n'
        '          "rubric": ["old rubric"]\n'
        '        }\n'
        '      ]\n'
        '    },\n'
        '    {\n'
        '      "id": "family_b",\n'
        '      "cases": [\n'
        '        {\n'
        '          "id": "case_b",\n'
        '          "surface": "wing",\n'
        '          "prompt": "ambient",\n'
        '          "exact_runner_excluded_rubric_indices": [1],\n'
        '          "rubric": ["stay quiet"]\n'
        '        }\n'
        '      ]\n'
        '    }\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )
    private_root = tmp_path / "private"
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: json.loads(prompt_bank.read_text(encoding="utf-8")))
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)

    draft = evals.create_eval_case_draft(
        family_id="family_a",
        case_id="new_case",
        updated_case={"surface": "voice", "prompt": "Say one useful thing.", "rubric": ["is concise"]},
        create=True,
    )
    raw_draft = json.loads((private_root / "drafts" / f"{draft['id']}.json").read_text(encoding="utf-8"))

    assert '"id": "new_case"' in draft["patch"]
    assert "exact_runner_excluded_rubric_indices" not in draft["patch"]
    assert json.loads(raw_draft["newText"])["families"][0]["cases"][1]["id"] == "new_case"


def test_workbench_context_links_prompt_history_evals_and_qa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "source_agents_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(sync_engine, "load_latest_live_bundle", lambda: {"mainAgent": {"id": "agent_test", "name": "Test", "instructions": "source"}})
    monkeypatch.setattr(sync_engine, "_git_commit", lambda: "abc123")

    context = prompt_service.workbench_context("main.identity")
    encoded = json.dumps(context)

    assert context["promptId"] == "main.identity"
    assert any(family["id"] == "main_identity_style" for family in context["linkedEvals"]["families"])
    assert any(row["id"] == "PW-004" for row in context["qaCoverage"])
    assert str(Path.home()) not in encoded


def test_runtime_prompt_bundle_status_is_prompt_specific_and_public_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.viventium.config_compiler as config_compiler_module

    monkeypatch.setattr(
        config_compiler_module,
        "check_prompt_bundle_drift",
        lambda: {
            "status": "blocked",
            "reason": "prompt_bundle_drift",
            "compare_reviewed": False,
            "live_path": "/private/local/runtime/prompt-bundle.json",
            "candidate_count": 3,
            "source": {"prompt_count": 66, "bundle_hash": "source"},
            "live": {"prompt_count": 63, "bundle_hash": "live"},
            "diff": {
                "added": ["memory.hardener_consolidation"],
                "removed": ["legacy.prompt"],
                "changed": ["main.identity"],
            },
            "drift_count": 3,
        },
    )

    affected = prompt_service.runtime_prompt_bundle_status("memory.hardener_consolidation")
    unaffected = prompt_service.runtime_prompt_bundle_status("memory.transcript_summarizer")
    encoded = json.dumps(affected)

    assert affected["promptState"] == "source-only"
    assert affected["promptAffected"] is True
    assert affected["driftCount"] == 3
    assert affected["sourcePromptCount"] == 66
    assert affected["livePromptCount"] == 63
    assert unaffected["promptState"] == "other-drift"
    assert unaffected["promptAffected"] is False
    assert "live_path" not in encoded
    assert "/private/local" not in encoded


def test_workbench_context_distinguishes_managed_agent_from_compiled_runtime_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sync_engine,
        "get_status",
        lambda: {
            "agents": [
                {
                    "agentId": "synthetic-main",
                    "label": "Viventium",
                    "sourcePromptId": "main.conscious_agent",
                    "sourceHash": "source",
                    "liveHash": "source",
                    "state": "synced",
                    "sourceChars": 10,
                    "liveChars": 10,
                    "liveTextAvailable": True,
                }
            ]
        },
    )
    monkeypatch.setattr(
        prompt_service,
        "runtime_prompt_bundle_status",
        lambda prompt_id: {
            "status": "ok",
            "reason": "matched",
            "promptState": "synced",
            "promptAffected": False,
            "liveBundleAvailable": True,
            "driftCount": 0,
        },
    )

    managed = prompt_service.workbench_context("main.identity")
    runtime = prompt_service.workbench_context("memory.hardener_consolidation")

    assert managed["delivery"]["kind"] == "managed_agent"
    assert managed["delivery"]["state"] == "synced"
    assert managed["runtimePromptBundle"] is None
    assert runtime["delivery"]["kind"] == "compiled_runtime"
    assert runtime["runtimePromptBundle"]["promptState"] == "synced"


def test_prompt_editor_labels_the_real_delivery_owner_instead_of_every_prompt_as_runtime_bundle() -> None:
    source = (WORKBENCH_SRC / "components" / "PromptEditor.tsx").read_text(encoding="utf-8")

    assert "deliveryLabel(context?.delivery, runtimeBundle)" in source
    assert "Managed agent:" in source
    assert "Compiled runtime:" in source


def test_workbench_context_surfaces_eval_edit_drafts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_root = tmp_path / "prompts"
    eval_root = tmp_path / "evals"
    eval_root.mkdir(parents=True)
    prompt_bank = eval_root / "prompt-bank.json"
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    write_prompt(prompt_root, "voice.md", "main.voice_style", "Applied voice style")
    private_root = tmp_path / "private"
    monkeypatch.setattr(prompt_service, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPTS_ROOT", prompt_root)
    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(sync_engine, "get_status", lambda: {"agents": []})
    monkeypatch.setattr(evals, "evals_for_prompt", lambda prompt_id: {"promptId": prompt_id, "familyCount": 0, "caseCount": 0, "families": []})
    monkeypatch.setattr(evals, "list_eval_runs_for_prompt", lambda prompt_id, limit=8: [])
    monkeypatch.setattr(prompt_service, "qa_coverage_for_prompt", lambda prompt_id: [])

    drafts.create_file_draft(
        target_path=prompt_bank,
        new_text=json.dumps({"families": [{"id": "changed", "cases": []}]}) + "\n",
        kind="eval-edit",
    )

    context = prompt_service.workbench_context("main.voice_style")

    assert any(draft["kind"] == "eval-edit" for draft in context["drafts"])


def test_promptfoo_adapter_round_trips_one_synthetic_case() -> None:
    bank = {
        "families": [
            {
                "id": "family",
                "cases": [
                    {
                        "id": "case",
                        "surface": "web",
                        "prompt": "Answer briefly.",
                        "rubric": ["answers briefly and avoids private content"],
                    }
                ],
            }
        ]
    }

    config = promptfoo_adapter.prompt_bank_to_promptfoo(bank, prompt_id="main.conscious_agent")

    assert config["providers"] == ["echo"]
    assert config["tests"][0]["metadata"]["prompt_id"] == "main.conscious_agent"
    assert config["tests"][0]["vars"]["case_id"] == "case"


def test_prompt_workbench_cli_status_is_public_safe(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"

    completed = subprocess.run(
        [
            str(REPO_ROOT / "bin" / "viventium"),
            "--app-support-dir",
            str(app_support),
            "prompt-workbench",
            "status",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)

    assert payload == {"pid": None, "port": None, "status": "stopped", "url": None}
    assert str(REPO_ROOT) not in completed.stdout


def test_prompt_workbench_cli_help_documents_scoped_stop() -> None:
    completed = subprocess.run(
        [str(REPO_ROOT / "bin" / "viventium"), "help", "prompt-workbench"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "prompt-workbench open" in completed.stdout
    assert "prompt-workbench stop" in completed.stdout
    assert "Stop does not stop" in completed.stdout
    assert "main Viventium runtime" in completed.stdout


def test_prompt_workbench_lifecycle_script_scopes_process_ownership() -> None:
    script = (REPO_ROOT / "scripts" / "viventium" / "prompt_workbench.py").read_text(encoding="utf-8")

    assert "state/prompt-workbench" not in script
    assert '"state" / "prompt-workbench"' in script
    assert "prompt_workbench.app:app" in script
    assert '"--no-access-log"' in script
    assert "Recorded PID did not belong to this Prompt Workbench." in script
    assert "Cleared stale workbench state; retry the action." in script
    assert "clear_state(app_support_dir)" in script
    assert '"__pycache__"' in script
    assert "viventium-librechat-start.sh" not in script
    assert "native_stack.sh" not in script


def test_managed_prompt_workbench_reclaims_only_a_recognized_stale_workbench_listener(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    stopped: list[int] = []
    available_checks = iter([False, True])
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda port: [4312])
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected_root: expected_root == root,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: stopped.append(pid) or True,
    )
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda port: next(available_checks))
    monkeypatch.setattr(prompt_workbench_cli.time, "sleep", lambda seconds: None)

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(8781, root)

    assert reclaimed is True
    assert stopped == [4312]


def test_managed_prompt_workbench_refuses_to_kill_a_workbench_from_another_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    stopped: list[int] = []
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda port: [4312])
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected_root: False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: stopped.append(pid) or True,
    )

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(8781, root)

    assert reclaimed is False
    assert stopped == []


def test_prompt_workbench_port_selection_does_not_reuse_another_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "read_state",
        lambda app_support: {"pid": 4312, "port": 8781},
    )
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda pid: True)
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda port: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda pid, expected: False)
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda port: port == 8782)

    selected = prompt_workbench_cli.choose_port(tmp_path / "app-support", root, 8781)

    assert selected == 8782


def test_schedules_panel_prefers_live_query_data_over_a_stale_dock_snapshot() -> None:
    source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "ScheduledPromptsPanel.tsx"
    ).read_text(encoding="utf-8")

    live_query = "schedulesQuery.data?.scheduledPrompts ??"
    dock_snapshot = "scheduledPrompts ??"
    assert 'queryKey: ["scheduledPrompts", "panel"]' in source
    assert source.index(live_query) < source.index(dock_snapshot)


def test_schedules_panel_only_sends_schedule_for_new_or_touched_drafts() -> None:
    source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "ScheduledPromptsPanel.tsx"
    ).read_text(encoding="utf-8")

    assert "includeSchedule: !draft.id || scheduleTouched" in source
    assert "includeSchedule: !isUserLevelSchedule || scheduleTouched" not in source


def test_prompt_workbench_dev_server_ports_are_consistent() -> None:
    lifecycle_script = (REPO_ROOT / "scripts" / "viventium" / "prompt_workbench.py").read_text(encoding="utf-8")
    package_json = json.loads((REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "package.json").read_text(encoding="utf-8"))
    vite_config = (REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "vite.config.ts").read_text(encoding="utf-8")
    app_source = (
        REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend" / "prompt_workbench" / "app.py"
    ).read_text(encoding="utf-8")

    assert "DEFAULT_PORT = 8781" in lifecycle_script
    assert "--port 8781" in package_json["scripts"]["serve"]
    assert "--port 8781" in package_json["scripts"]["dev:api"]
    assert "'/api': 'http://127.0.0.1:8781'" in vite_config
    assert "127.0.0.1:8765" not in app_source
