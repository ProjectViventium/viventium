from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_BACKEND = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend"
if str(WORKBENCH_BACKEND) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_BACKEND))

from prompt_workbench import drafts, import_mapper, prompt_service, promptfoo_adapter, scheduled_prompts, sync_engine  # noqa: E402
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
    assert "includeSchedule: !isUserLevelSchedule || scheduleTouched" in schedule_source
    assert "includeMemoryWriteMode: !isUserLevelSchedule" in schedule_source
    assert "setScheduleTouched(true)" in schedule_source
    assert "schedule-execution-card" in schedule_source
    assert "GlassHive host" in schedule_source
    assert "Viventium agent" in schedule_source
    assert "This user-level schedule does not use Workbench variable rendering" in schedule_source
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


def test_nightly_prompt_template_prefers_configured_default_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setenv("VIVENTIUM_DEFAULT_TIMEZONE", "America/Toronto")

    template = scheduled_prompts.nightly_prompt_template()

    assert template["schedule"] == {
        "type": "daily",
        "time": "03:00",
        "timezone": "America/Toronto",
    }


def test_nightly_prompt_template_requests_private_risk_radar_sidecar() -> None:
    prompt_text = scheduled_prompts.nightly_prompt_template()["promptText"]

    assert "{{local.viventium.my_folder}}" in prompt_text
    assert "periphery/risk_radar/YYYY/MM" in prompt_text
    assert "paired .md and .json" in prompt_text
    assert "If there is no strong evidence" in prompt_text
    assert "Do not add a saved-memory key" in prompt_text
    for field in scheduled_prompts.PERIPHERY_REQUIRED_FIELDS:
        assert field in prompt_text


def test_nightly_seed_reconciles_existing_builtin_schedule_timezone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_DEFAULT_TIMEZONE", "America/Toronto")
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
    )

    expected_schedule = {"type": "daily", "time": "03:00", "timezone": "America/Toronto"}
    assert reseeded["id"] == existing["id"]
    assert reseeded["schedule"] == expected_schedule
    stored = scheduled_prompts.storage().get_scheduled_prompt_definition(existing["id"])
    task = scheduled_prompts.storage().get_task("startup-admin", stored["task_id"])
    assert stored["schedule"] == expected_schedule
    assert task["schedule"] == expected_schedule


def test_nightly_seed_reconciles_existing_builtin_prompt_into_scheduler_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    existing = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "promptText": "legacy scratchpad-only nightly prompt\n",
            "active": False,
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    reseeded = scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    stored = scheduled_prompts.storage().get_scheduled_prompt_definition(existing["id"])
    task = scheduled_prompts.storage().get_task("startup-admin", stored["task_id"])
    assert reseeded["id"] == existing["id"]
    assert "periphery/risk_radar/YYYY/MM" in stored["prompt_text"]
    assert "periphery/risk_radar/YYYY/MM" in task["prompt"]


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
    assert runs and Path(runs[0]["private_detail_path"]).exists()
    assert "mongodb://" not in Path(runs[0]["private_detail_path"]).read_text(encoding="utf-8")


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


def test_scheduled_prompt_periphery_artifact_metadata_review(
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
    (artifact_dir / "20260625T030000Z.risk_radar.md").write_text(
        "Private synthetic insight body that must never appear in metadata.",
        encoding="utf-8",
    )
    (artifact_dir / "20260625T030000Z.risk_radar.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
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
    assert payload["invalidArtifacts"] == []
    assert "periphery/<moduleId>/YYYY/MM" in payload["contract"]
    encoded = json.dumps(payload)
    assert "Private synthetic insight body" not in encoded
    assert "Private observation text" not in encoded
    assert "private-conversation-id" not in encoded
    assert str(tmp_path) not in encoded


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


def test_workbench_startup_seeds_active_glasshive_nightly_from_runtime_env(
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
    prompt_bank.write_text(json.dumps({"families": []}), encoding="utf-8")
    runner = eval_root / "run-exact-model-evals.cjs"
    runner.write_text("// synthetic runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[list[str]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(max_cases=2, live=True, prompt_id="main.voice_style")

    assert result["returnCode"] == 0
    assert captured
    assert f"--prompt-bank={prompt_bank}" in captured[0]
    assert "--prompt-bank" not in captured[0]
    assert "--prompt-id=main.voice_style" in captured[0]


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
