from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULING_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "MCPs" / "scheduling-cortex"
if str(SCHEDULING_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_ROOT))


def test_glasshive_callback_url_uses_scheduling_mcp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduling_cortex import dispatch

    monkeypatch.delenv("SCHEDULING_GLASSHIVE_CALLBACK_URL", raising=False)
    monkeypatch.delenv("VIVENTIUM_SCHEDULING_MCP_PORT", raising=False)
    monkeypatch.delenv("SCHEDULING_MCP_PORT", raising=False)
    monkeypatch.delenv("SCHEDULER_PORT", raising=False)
    monkeypatch.setenv("SCHEDULING_MCP_URL", "http://localhost:7110/mcp")

    assert (
        dispatch._glasshive_callback_url()
        == "http://localhost:7110/internal/scheduled-prompts/glasshive-callback"
    )


def test_glasshive_callback_url_uses_configured_scheduling_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduling_cortex import dispatch

    monkeypatch.delenv("SCHEDULING_GLASSHIVE_CALLBACK_URL", raising=False)
    monkeypatch.delenv("SCHEDULING_MCP_URL", raising=False)
    monkeypatch.setenv("VIVENTIUM_SCHEDULING_MCP_PORT", "7110")

    assert (
        dispatch._glasshive_callback_url()
        == "http://127.0.0.1:7110/internal/scheduled-prompts/glasshive-callback"
    )


def test_glasshive_executor_branches_before_librechat_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduling_cortex import dispatch
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-1",
            "user_id": "user-1",
            "task_id": "task-1",
            "title": "QA",
            "source_prompt_id": None,
            "template_id": None,
            "prompt_text": "<local.viventium.database>{}</local.viventium.database>",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 1,
            "memory_write_mode": "propose",
            "workspace_alias": "workbench-scheduled-def-1",
            "my_folder": str(tmp_path / "my_folder"),
            "metadata": {},
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
        }
    )

    def fail_generation(*_: object, **__: object) -> dict[str, object]:
        raise AssertionError("LibreChat scheduler generation must not run for glasshive_host executor")

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        calls.append((url, payload))
        if url.endswith("/v1/projects"):
            return {"project_id": "proj_1"}
        if url.endswith("/workers/find-or-resume"):
            assert payload["profile"] == "codex-cli"
            assert payload["execution_mode"] == "host"
            bundle = payload["bootstrap_bundle"]
            assert isinstance(bundle, dict)
            assert bundle["callbacks"]["events_webhook_url"]
            assert "rendered-prompt.md" in json.dumps(bundle)
            assert "utf8_static_server.py" in json.dumps(bundle)
            assert "memory-proposals-yyyymmddHHmm.json" in json.dumps(bundle)
            return {"worker_id": "wrk_1"}
        if url.endswith("/assign"):
            assert "FINAL REPORT" in str(payload["instruction"])
            return {"run_id": "run_1"}
        raise AssertionError(url)

    monkeypatch.setattr(dispatch, "_run_scheduler_generation", fail_generation)
    monkeypatch.setattr(dispatch, "_post_json", fake_post_json)

    result = dispatch.dispatch_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "agent-1",
            "prompt": "<local.viventium.database>{}</local.viventium.database>",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "next_run_at": "2026-05-22T10:00:00Z",
            "metadata": {
                "workbench_scheduled_prompt": {
                    "definition_id": "def-1",
                    "version_id": "ver-1",
                    "title": "QA",
                    "rendered_hash": "abc",
                    "variable_snapshot_hash": "def",
                    "variable_snapshot_json": "{}",
                    "memory_write_mode": "propose",
                    "workspace_alias": "workbench-scheduled-def-1",
                    "workspace_root": str(tmp_path),
                    "my_folder": str(tmp_path / "my_folder"),
                }
            },
        }
    )

    assert result["delivery"]["outcome"] == "queued"
    assert [url.rsplit("/", 1)[-1] for url, _ in calls] == ["projects", "find-or-resume", "assign"]


def test_glasshive_dispatch_replaces_stale_cached_project_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling_cortex import dispatch
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))

    stale_project_id = "prj_stale"
    replacement_project_id = "prj_replacement"
    task_metadata = {
        "workbench_scheduled_prompt": {
            "definition_id": "def-1",
            "version_id": "ver-1",
            "title": "QA",
            "rendered_hash": "abc",
            "variable_snapshot_hash": "def",
            "variable_snapshot_json": "{}",
            "memory_write_mode": "off",
            "workspace_alias": "workbench-scheduled-def-1",
            "workspace_root": str(tmp_path),
            "my_folder": str(tmp_path / "my_folder"),
            "glasshive_project_id": stale_project_id,
        }
    }
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-1",
            "user_id": "user-1",
            "task_id": "task-1",
            "title": "QA",
            "source_prompt_id": None,
            "template_id": None,
            "prompt_text": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 1,
            "memory_write_mode": "off",
            "workspace_alias": "workbench-scheduled-def-1",
            "my_folder": str(tmp_path / "my_folder"),
            "metadata": {"glasshive_project_id": stale_project_id},
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
        }
    )
    storage.create_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-27T10:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": task_metadata,
        }
    )

    get_calls: list[str] = []
    post_calls: list[str] = []

    def fake_get_json(url: str, headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        get_calls.append(url)
        if url.endswith(f"/v1/projects/{stale_project_id}"):
            raise dispatch.HttpJsonError(
                "GET /v1/projects/prj_stale failed: HTTP 404: Not Found",
                status=404,
                method="GET",
                path="/v1/projects/prj_stale",
            )
        return {"project_id": replacement_project_id}

    def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        post_calls.append(url)
        if url.endswith("/v1/projects"):
            return {"project_id": replacement_project_id}
        if url.endswith(f"/v1/projects/{replacement_project_id}/workers/find-or-resume"):
            return {"worker_id": "wrk_1"}
        if url.endswith("/assign"):
            return {"run_id": "run_1"}
        raise AssertionError(url)

    monkeypatch.setattr(dispatch, "_get_json", fake_get_json)
    monkeypatch.setattr(dispatch, "_post_json", fake_post_json)

    result = dispatch.dispatch_task(storage.get_task("user-1", "task-1"))

    assert result["delivery"]["outcome"] == "queued"
    assert any(url.endswith(f"/v1/projects/{stale_project_id}") for url in get_calls)
    assert any(url.endswith(f"/v1/projects/{replacement_project_id}/workers/find-or-resume") for url in post_calls)
    updated_definition = storage.get_scheduled_prompt_definition("def-1")
    assert updated_definition["metadata"]["glasshive_project_id"] == replacement_project_id
    updated_task = storage.get_task("user-1", "task-1")
    assert (
        updated_task["metadata"]["workbench_scheduled_prompt"]["glasshive_project_id"]
        == replacement_project_id
    )


def test_glasshive_dispatch_repairs_task_cache_from_valid_definition_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling_cortex import dispatch
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))

    stale_project_id = "prj_task_stale"
    valid_project_id = "prj_definition_valid"
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-1",
            "user_id": "user-1",
            "task_id": "task-1",
            "title": "QA",
            "source_prompt_id": None,
            "template_id": None,
            "prompt_text": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 1,
            "memory_write_mode": "off",
            "workspace_alias": "workbench-scheduled-def-1",
            "my_folder": str(tmp_path / "my_folder"),
            "metadata": {"glasshive_project_id": valid_project_id},
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
        }
    )
    storage.create_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-27T10:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": {
                "workbench_scheduled_prompt": {
                    "definition_id": "def-1",
                    "version_id": "ver-1",
                    "title": "QA",
                    "rendered_hash": "abc",
                    "variable_snapshot_hash": "def",
                    "variable_snapshot_json": "{}",
                    "memory_write_mode": "off",
                    "workspace_alias": "workbench-scheduled-def-1",
                    "workspace_root": str(tmp_path),
                    "my_folder": str(tmp_path / "my_folder"),
                    "glasshive_project_id": stale_project_id,
                }
            },
        }
    )

    post_calls: list[str] = []

    def fake_get_json(url: str, headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        if url.endswith(f"/v1/projects/{stale_project_id}"):
            raise dispatch.HttpJsonError(
                "GET /v1/projects/prj_task_stale failed: HTTP 404: Not Found",
                status=404,
                method="GET",
                path="/v1/projects/prj_task_stale",
            )
        if url.endswith(f"/v1/projects/{valid_project_id}"):
            return {"project_id": valid_project_id}
        raise AssertionError(url)

    def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        post_calls.append(url)
        if url.endswith(f"/v1/projects/{valid_project_id}/workers/find-or-resume"):
            return {"worker_id": "wrk_1"}
        if url.endswith("/assign"):
            return {"run_id": "run_1"}
        raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(dispatch, "_get_json", fake_get_json)
    monkeypatch.setattr(dispatch, "_post_json", fake_post_json)

    result = dispatch.dispatch_task(storage.get_task("user-1", "task-1"))

    assert result["delivery"]["outcome"] == "queued"
    assert not any(url.endswith("/v1/projects") for url in post_calls)
    assert any(url.endswith(f"/v1/projects/{valid_project_id}/workers/find-or-resume") for url in post_calls)
    updated_task = storage.get_task("user-1", "task-1")
    assert (
        updated_task["metadata"]["workbench_scheduled_prompt"]["glasshive_project_id"]
        == valid_project_id
    )


def test_glasshive_dispatch_does_not_replace_project_on_non_404_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling_cortex import dispatch
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))

    project_id = "prj_validation_error"
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-1",
            "user_id": "user-1",
            "task_id": "task-1",
            "title": "QA",
            "source_prompt_id": None,
            "template_id": None,
            "prompt_text": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 1,
            "memory_write_mode": "off",
            "workspace_alias": "workbench-scheduled-def-1",
            "my_folder": str(tmp_path / "my_folder"),
            "metadata": {"glasshive_project_id": project_id},
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
        }
    )
    storage.create_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-27T10:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": {
                "workbench_scheduled_prompt": {
                    "definition_id": "def-1",
                    "version_id": "ver-1",
                    "title": "QA",
                    "rendered_hash": "abc",
                    "variable_snapshot_hash": "def",
                    "variable_snapshot_json": "{}",
                    "memory_write_mode": "off",
                    "workspace_alias": "workbench-scheduled-def-1",
                    "workspace_root": str(tmp_path),
                    "my_folder": str(tmp_path / "my_folder"),
                    "glasshive_project_id": project_id,
                }
            },
        }
    )

    post_calls: list[str] = []

    def fake_get_json(url: str, headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        raise dispatch.HttpJsonError(
            "GET /v1/projects/prj_validation_error failed: HTTP 500: Server Error",
            status=500,
            method="GET",
            path="/v1/projects/prj_validation_error",
        )

    def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_s: int) -> dict[str, object]:
        post_calls.append(url)
        raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(dispatch, "_get_json", fake_get_json)
    monkeypatch.setattr(dispatch, "_post_json", fake_post_json)

    with pytest.raises(dispatch.HttpJsonError):
        dispatch.dispatch_task(storage.get_task("user-1", "task-1"))

    assert post_calls == []


def test_glasshive_dispatch_refuses_stale_prompt_when_definition_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling_cortex import dispatch

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    monkeypatch.setenv("SCHEDULER_GLASSHIVE_DISABLE_DISPATCH", "1")

    with pytest.raises(RuntimeError, match="definition def-missing unavailable; refusing stale dispatch"):
        dispatch.dispatch_task(
            {
                "id": "task-1",
                "user_id": "user-1",
                "agent_id": "agent-1",
                "prompt": "Study <user.memories>\n[]\n</user.memories>",
                "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
                "channel": "workbench",
                "executor": "glasshive_host",
                "conversation_policy": "new",
                "next_run_at": "2026-05-22T10:00:00Z",
                "metadata": {
                    "workbench_scheduled_prompt": {
                        "definition_id": "def-missing",
                        "version_id": "ver-stale",
                        "title": "QA",
                        "rendered_hash": "stale-rendered",
                        "variable_snapshot_hash": "stale-snapshot",
                        "variable_snapshot_json": "{}",
                        "memory_write_mode": "propose",
                    }
                },
            }
        )


def test_glasshive_dispatch_refreshes_workbench_variables_at_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling_cortex import dispatch
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_root = tmp_path / "private"
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(db_path))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(private_root))
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", "test-secret")
    monkeypatch.setenv("SCHEDULER_GLASSHIVE_DISABLE_DISPATCH", "1")

    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-1",
            "user_id": "user-1",
            "task_id": "task-1",
            "title": "QA",
            "source_prompt_id": None,
            "template_id": "workbench_nightly_subconscious_thought_formation_v1",
            "prompt_text": "Study {{user.memories}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 1,
            "memory_write_mode": "propose",
            "workspace_alias": "workbench-scheduled-def-1",
            "my_folder": str(tmp_path / "my_folder"),
            "metadata": {},
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
        }
    )
    storage.create_scheduled_prompt_version(
        {
            "id": "ver-1",
            "definition_id": "def-1",
            "version_number": 1,
            "prompt_text": "Study {{user.memories}}",
            "rendered_text": "Study <user.memories>\n[]\n</user.memories>",
            "rendered_hash": "stale-rendered",
            "variable_snapshot_json": "{}",
            "variable_snapshot_hash": "stale-snapshot",
            "created_at": "2026-05-22T10:00:00Z",
        }
    )
    storage.create_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "prompt-workbench",
            "prompt": "Study <user.memories>\n[]\n</user.memories>",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-22T10:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": {
                "workbench_scheduled_prompt": {
                    "definition_id": "def-1",
                    "version_id": "ver-1",
                    "title": "QA",
                    "rendered_hash": "stale-rendered",
                    "variable_snapshot_hash": "stale-snapshot",
                    "variable_snapshot_json": "{}",
                    "memory_write_mode": "propose",
                    "workspace_alias": "workbench-scheduled-def-1",
                    "workspace_root": str(tmp_path),
                    "my_folder": str(tmp_path / "my_folder"),
                }
            },
        }
    )

    rendered = "Study <user.memories>\n[{\"key\":\"core\",\"value\":\"fresh\"}]\n</user.memories>"

    class FakeWorkbenchScheduledPrompts:
        @staticmethod
        def render_variables(prompt_text: str, *, user_id: str, email: str | None = None) -> dict[str, object]:
            assert prompt_text == "Study {{user.memories}}"
            assert user_id == "user-1"
            return {
                "rendered": rendered,
                "renderedHash": dispatch._sha256_prefix(rendered),
                "variableSnapshotJson": "{\"items\":[{\"placeholder\":\"user.memories\"}]}",
                "variableSnapshotHash": "fresh-snapshot",
            }

    monkeypatch.setattr(
        dispatch,
        "_import_workbench_scheduled_prompts",
        lambda: FakeWorkbenchScheduledPrompts,
    )

    result = dispatch.dispatch_task(storage.get_task("user-1", "task-1"))

    assert result["delivery"]["outcome"] == "queued"
    updated_task = storage.get_task("user-1", "task-1")
    assert updated_task["prompt"] == "Study {{user.memories}}"
    metadata = updated_task["metadata"]["workbench_scheduled_prompt"]
    assert metadata["rendered_hash"] == dispatch._sha256_prefix(rendered)
    assert metadata["variable_snapshot_hash"] == "fresh-snapshot"
    assert "variable_snapshot_json" not in metadata
    assert metadata["variable_snapshot_pointer"].endswith("fresh-snapshot")
    latest = storage.latest_scheduled_prompt_version("def-1")
    assert latest["version_number"] == 2
    assert latest["rendered_text"] == f'<private-rendered-prompt hash="{dispatch._sha256_prefix(rendered)}" />'
    assert "user.memories" not in latest["variable_snapshot_json"]
    run = storage.list_scheduled_prompt_runs(definition_id="def-1")[0]
    assert run["rendered_hash"] == dispatch._sha256_prefix(rendered)
    assert run["variable_snapshot_hash"] == "fresh-snapshot"
    private_detail = json.loads(Path(run["private_detail_path"]).read_text(encoding="utf-8"))
    assert private_detail["rendered_prompt"] == rendered
    assert "user.memories" in private_detail["variable_snapshot_json"]


def test_glasshive_completion_callback_requires_signature_and_updates_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient

    from scheduling_cortex.server import build_server
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    secret = "test-secret"
    worker_id = "wrk_1"
    glasshive_run_id = "run_1"
    db_path = tmp_path / "schedules.db"
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", secret)

    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    storage.create_task(
        {
            "id": "task-1",
            "user_id": "user-1",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-23T10:00:00Z",
            "last_status": "error",
            "last_error": "previous stale failure",
            "last_delivery_outcome": "failed",
            "last_delivery_reason": "previous stale failure",
            "last_delivery_at": "2026-05-22T09:00:00Z",
            "last_generated_text": None,
            "last_delivery": {"outcome": "failed", "reason": "previous stale failure", "generated_text": None},
            "metadata": {},
        }
    )
    private_detail_path = tmp_path / "private" / "scheduled-run-1.json"
    private_detail_path.parent.mkdir(parents=True)
    private_detail_path.write_text(json.dumps({"memory_write_mode": "propose"}), encoding="utf-8")
    storage.create_scheduled_prompt_run(
        {
            "run_id": "scheduled-run-1",
            "task_id": "task-1",
            "definition_id": "def-1",
            "user_id": "user-1",
            "version_id": "ver-1",
            "due_at": "2026-05-22T10:00:00Z",
            "started_at": "2026-01-01T00:00:01Z",
            "completed_at": None,
            "status": "queued",
            "executor": "glasshive_host",
            "rendered_hash": "rendered",
            "variable_snapshot_hash": "snapshot",
            "glasshive_project_id": "proj_1",
            "glasshive_worker_id": worker_id,
            "glasshive_run_id": glasshive_run_id,
            "result_summary": None,
            "error_class": None,
            "private_detail_path": str(private_detail_path),
            "callback_payload_json": None,
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )

    mcp = build_server(storage)
    if not hasattr(mcp, "http_app"):
        pytest.skip("Cannot extract ASGI app from FastMCP server")
    client = TestClient(mcp.http_app(transport="streamable-http"))
    payload = {
        "event": "run.completed",
        "worker_id": worker_id,
        "run_id": glasshive_run_id,
        "message": "FINAL REPORT: complete at /Users/private/path with mongodb://127.0.0.1:27017/db",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    bad = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": "sha256=bad"},
    )
    assert bad.status_code == 401
    assert storage.get_scheduled_prompt_run("scheduled-run-1")["status"] == "queued"

    binding = f"{worker_id}:{glasshive_run_id}".encode("utf-8")
    derived_secret = hmac.new(secret.encode("utf-8"), binding, hashlib.sha256).hexdigest().encode("utf-8")
    signature = "sha256=" + hmac.new(derived_secret, raw, hashlib.sha256).hexdigest()
    ok = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": signature},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"

    updated = storage.get_scheduled_prompt_run("scheduled-run-1")
    assert updated["status"] == "completed"
    assert updated["result_summary"] == "GlassHive run completed. Private details are stored in the run detail file."
    callback_summary = json.loads(updated["callback_payload_json"])
    assert callback_summary["event"] == "run.completed"
    assert callback_summary["message_hash"]
    assert "FINAL REPORT" not in updated["callback_payload_json"]
    assert "mongodb://" not in updated["callback_payload_json"]
    assert "FINAL REPORT" in private_detail_path.read_text(encoding="utf-8")
    task = storage.get_task("user-1", "task-1")
    assert task["last_status"] == "success"
    assert task["last_error"] is None
    assert task["last_delivery_outcome"] == "sent"
    assert task["last_delivery"]["scheduled_prompt_run_id"] == "scheduled-run-1"


def test_glasshive_capacity_callback_keeps_run_queued_and_clears_stale_parent_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient

    from scheduling_cortex.server import build_server
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    secret = "test-secret"
    worker_id = "wrk_capacity"
    glasshive_run_id = "run_capacity"
    db_path = tmp_path / "schedules.db"
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", secret)

    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    storage.create_task(
        {
            "id": "task-capacity",
            "user_id": "user-capacity",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-05-23T10:00:00Z",
            "last_status": "error",
            "last_error": "previous stale failure",
            "last_delivery_outcome": "failed",
            "last_delivery_reason": "previous stale failure",
            "last_delivery_at": "2026-05-22T09:00:00Z",
            "last_generated_text": None,
            "last_delivery": {"outcome": "failed", "reason": "previous stale failure", "generated_text": None},
            "metadata": {},
        }
    )
    private_detail_path = tmp_path / "private" / "scheduled-run-capacity.json"
    private_detail_path.parent.mkdir(parents=True)
    private_detail_path.write_text(json.dumps({"memory_write_mode": "propose"}), encoding="utf-8")
    storage.create_scheduled_prompt_run(
        {
            "run_id": "scheduled-run-capacity",
            "task_id": "task-capacity",
            "definition_id": "def-capacity",
            "user_id": "user-capacity",
            "version_id": "ver-capacity",
            "due_at": "2026-05-22T10:00:00Z",
            "started_at": "2026-01-01T00:00:01Z",
            "completed_at": None,
            "status": "queued",
            "executor": "glasshive_host",
            "rendered_hash": "rendered",
            "variable_snapshot_hash": "snapshot",
            "glasshive_project_id": "proj_capacity",
            "glasshive_worker_id": worker_id,
            "glasshive_run_id": glasshive_run_id,
            "result_summary": None,
            "error_class": None,
            "private_detail_path": str(private_detail_path),
            "callback_payload_json": None,
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )

    mcp = build_server(storage)
    if not hasattr(mcp, "http_app"):
        pytest.skip("Cannot extract ASGI app from FastMCP server")
    client = TestClient(mcp.http_app(transport="streamable-http"))
    payload = {
        "event": "run.waiting_on_capacity",
        "worker_id": worker_id,
        "run_id": glasshive_run_id,
        "run_state": "queued",
        "message": "The codex-cli host worker is already busy with another active workspace.",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    binding = f"{worker_id}:{glasshive_run_id}".encode("utf-8")
    derived_secret = hmac.new(secret.encode("utf-8"), binding, hashlib.sha256).hexdigest().encode("utf-8")
    signature = "sha256=" + hmac.new(derived_secret, raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": signature},
    )

    assert response.status_code == 200
    updated = storage.get_scheduled_prompt_run("scheduled-run-capacity")
    assert updated["status"] == "queued"
    assert updated["completed_at"] is None
    assert updated["error_class"] is None
    assert updated["result_summary"] == "GlassHive run is waiting for host worker capacity and will retry."
    callback_summary = json.loads(updated["callback_payload_json"])
    assert callback_summary["event"] == "run.waiting_on_capacity"
    task = storage.get_task("user-capacity", "task-capacity")
    assert task["last_status"] == "running"
    assert task["last_error"] is None
    assert task["last_delivery_outcome"] == "queued"
    assert task["last_delivery"]["reason"] == "run.waiting_on_capacity"


def test_glasshive_queued_callback_does_not_downgrade_running_workbench_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient

    from scheduling_cortex.server import build_server
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    secret = "test-secret"
    worker_id = "wrk_ordering"
    glasshive_run_id = "run_ordering"
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", secret)
    storage = ScheduleStorage(StorageConfig(db_path=str(tmp_path / "schedules.db")))
    storage.create_task(
        {
            "id": "task-ordering",
            "user_id": "user-ordering",
            "agent_id": "prompt-workbench",
            "prompt": "Synthetic prompt",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-22T10:00:00Z",
            "updated_at": "2026-05-22T10:00:00Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": "2026-05-22T10:00:01Z",
            "next_run_at": "2026-05-23T10:00:00Z",
            "last_status": "running",
            "last_error": None,
            "last_delivery_outcome": "queued",
            "last_delivery_reason": "run.started",
            "last_delivery_at": "2026-05-22T10:00:01Z",
            "last_generated_text": None,
            "last_delivery": {"outcome": "queued", "reason": "run.started", "generated_text": None},
            "metadata": {},
        }
    )
    private_detail_path = tmp_path / "private" / "scheduled-run-ordering.json"
    private_detail_path.parent.mkdir(parents=True)
    private_detail_path.write_text("{}", encoding="utf-8")
    storage.create_scheduled_prompt_run(
        {
            "run_id": "scheduled-run-ordering",
            "task_id": "task-ordering",
            "definition_id": "def-ordering",
            "user_id": "user-ordering",
            "version_id": "ver-ordering",
            "due_at": "2026-05-22T10:00:00Z",
            "started_at": "2026-05-22T10:00:01Z",
            "completed_at": None,
            "status": "running",
            "executor": "glasshive_host",
            "rendered_hash": "rendered",
            "variable_snapshot_hash": "snapshot",
            "glasshive_project_id": "proj_ordering",
            "glasshive_worker_id": worker_id,
            "glasshive_run_id": glasshive_run_id,
            "result_summary": "GlassHive run started.",
            "error_class": None,
            "private_detail_path": str(private_detail_path),
            "callback_payload_json": None,
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )

    mcp = build_server(storage)
    if not hasattr(mcp, "http_app"):
        pytest.skip("Cannot extract ASGI app from FastMCP server")
    client = TestClient(mcp.http_app(transport="streamable-http"))
    payload = {"event": "run.queued", "worker_id": worker_id, "run_id": glasshive_run_id, "message": "Queued"}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    binding = f"{worker_id}:{glasshive_run_id}".encode("utf-8")
    derived_secret = hmac.new(secret.encode("utf-8"), binding, hashlib.sha256).hexdigest().encode("utf-8")
    signature = "sha256=" + hmac.new(derived_secret, raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": signature},
    )

    assert response.status_code == 200
    updated = storage.get_scheduled_prompt_run("scheduled-run-ordering")
    assert updated["status"] == "running"
    assert updated["completed_at"] is None
    assert storage.get_task("user-ordering", "task-ordering")["last_status"] == "running"


def test_apply_governed_callback_routes_memory_proposals_through_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient

    import scheduling_cortex.server as server_module
    from scheduling_cortex.server import build_server
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    secret = "test-secret"
    worker_id = "wrk_apply"
    glasshive_run_id = "run_apply"
    user_id = "user-apply"
    db_path = tmp_path / "schedules.db"
    my_folder = tmp_path / "my_folder"
    my_folder.mkdir()
    proposal = my_folder / "memory-proposals-202605220300.json"
    proposal.write_text(
        json.dumps({"actions": [{"action": "set", "key": "context", "value": "Synthetic context"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", secret)

    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    private_detail_path = tmp_path / "private" / "scheduled-run-apply.json"
    private_detail_path.parent.mkdir(parents=True)
    private_detail_path.write_text(
        json.dumps({"memory_write_mode": "apply_governed", "my_folder": str(my_folder), "user_id": user_id}),
        encoding="utf-8",
    )
    storage.create_scheduled_prompt_run(
        {
            "run_id": "scheduled-run-apply",
            "task_id": "task-apply",
            "definition_id": "def-apply",
            "user_id": user_id,
            "version_id": "ver-apply",
            "due_at": "2026-05-22T10:00:00Z",
            "started_at": "2026-01-01T00:00:01Z",
            "completed_at": None,
            "status": "queued",
            "executor": "glasshive_host",
            "rendered_hash": "rendered",
            "variable_snapshot_hash": "snapshot",
            "glasshive_project_id": "proj_apply",
            "glasshive_worker_id": worker_id,
            "glasshive_run_id": glasshive_run_id,
            "result_summary": None,
            "error_class": None,
            "private_detail_path": str(private_detail_path),
            "callback_payload_json": None,
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )

    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        assert cmd[:2] == ["node", cmd[1]]
        assert cmd[cmd.index("--proposal") + 1] == str(proposal)
        assert cmd[cmd.index("--user-id") + 1] == user_id
        assert "--apply" in cmd

        class Completed:
            returncode = 0
            stdout = json.dumps({"ok": True, "mode": "apply", "reason": "ok", "appliedCount": 1})
            stderr = ""

        return Completed()

    monkeypatch.setattr(server_module.subprocess, "run", fake_run)
    mcp = build_server(storage)
    if not hasattr(mcp, "http_app"):
        pytest.skip("Cannot extract ASGI app from FastMCP server")
    client = TestClient(mcp.http_app(transport="streamable-http"))
    payload = {"event": "run.completed", "worker_id": worker_id, "run_id": glasshive_run_id, "message": "FINAL REPORT: done"}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    binding = f"{worker_id}:{glasshive_run_id}".encode("utf-8")
    derived_secret = hmac.new(secret.encode("utf-8"), binding, hashlib.sha256).hexdigest().encode("utf-8")
    signature = "sha256=" + hmac.new(derived_secret, raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": signature},
    )
    assert response.status_code == 200
    updated = storage.get_scheduled_prompt_run("scheduled-run-apply")
    assert updated["status"] == "completed"
    assert updated["result_summary"] == "GlassHive run completed; governed memory proposal applied."
    private_detail = json.loads(private_detail_path.read_text(encoding="utf-8"))
    assert private_detail["memory_apply"]["ok"] is True


def test_storage_migrates_legacy_private_run_details_out_of_public_history(tmp_path: Path) -> None:
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "schedules.db"
    private_detail_path = tmp_path / "private" / "legacy-run.json"
    private_detail_path.parent.mkdir(parents=True)
    private_detail_path.write_text("{}", encoding="utf-8")
    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    storage.create_scheduled_prompt_run(
        {
            "run_id": "legacy-run",
            "task_id": "task-legacy",
            "definition_id": "def-legacy",
            "user_id": "user-legacy",
            "version_id": "ver-legacy",
            "due_at": "2026-05-22T10:00:00Z",
            "started_at": "2026-05-22T10:00:01Z",
            "completed_at": None,
            "status": "completed",
            "executor": "glasshive_host",
            "rendered_hash": "rendered",
            "variable_snapshot_hash": "snapshot",
            "glasshive_project_id": "proj_legacy",
            "glasshive_worker_id": "worker_legacy",
            "glasshive_run_id": "glasshive_legacy",
            "result_summary": (
                "FINAL REPORT at /Users/private/path with mongodb://127.0.0.1:27017/db "
                "and http://127.0.0.1:63362/private-proof.md"
            ),
            "error_class": None,
            "private_detail_path": str(private_detail_path),
            "callback_payload_json": json.dumps(
                {
                    "event": "run.completed",
                    "message": (
                        "FINAL REPORT with /Users/private/path, "
                        "mongodb://127.0.0.1:27017/db, and "
                        "http://localhost:63362/private-proof.md"
                    ),
                }
            ),
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )
    storage.create_scheduled_prompt_definition(
        {
            "id": "def-legacy",
            "user_id": "user-legacy",
            "task_id": "task-legacy",
            "title": "Legacy prompt",
            "source_prompt_id": None,
            "template_id": None,
            "prompt_text": "Study {{user.memories}}",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": 0,
            "memory_write_mode": "off",
            "workspace_alias": "legacy",
            "my_folder": None,
            "metadata": {"execution": {"executor": "glasshive_host"}},
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
        }
    )
    storage.create_scheduled_prompt_version(
        {
            "id": "ver-legacy-private",
            "definition_id": "def-legacy",
            "version_number": 1,
            "prompt_text": "Study {{user.memories}}",
            "rendered_text": "Rendered private memory value",
            "rendered_hash": "renderedhash",
            "variable_snapshot_json": json.dumps({"items": [{"value": "private memory"}]}),
            "variable_snapshot_hash": "snapshothash",
            "created_at": "2026-05-22T10:00:01Z",
        }
    )
    storage.create_task(
        {
            "id": "task-legacy",
            "user_id": "user-legacy",
            "agent_id": "prompt-workbench",
            "prompt": "Rendered private memory value",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 0,
            "created_by": "agent:prompt-workbench",
            "created_source": "user",
            "created_at": "2026-05-22T10:00:01Z",
            "updated_at": "2026-05-22T10:00:01Z",
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": None,
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": {
                "workbench_scheduled_prompt": {
                    "definition_id": "def-legacy",
                    "version_id": "ver-legacy-private",
                    "rendered_hash": "renderedhash",
                    "variable_snapshot_hash": "snapshothash",
                    "variable_snapshot_json": json.dumps({"items": [{"value": "private memory"}]}),
                }
            },
        }
    )

    migrated = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    run = migrated.get_scheduled_prompt_run("legacy-run")
    assert "mongodb://" not in run["result_summary"]
    assert "/Users/" not in run["result_summary"]
    assert "127.0.0.1:63362" not in run["result_summary"]
    callback = json.loads(run["callback_payload_json"])
    assert callback["migrated"] is True
    assert callback["message_hash"]
    assert "FINAL REPORT" not in run["callback_payload_json"]
    assert "mongodb://" not in run["callback_payload_json"]
    assert "localhost:63362" not in run["callback_payload_json"]
    private_detail = json.loads(private_detail_path.read_text(encoding="utf-8"))
    assert private_detail["legacy_callback_payloads"][0]["payload"].startswith("{")
    version = migrated.latest_scheduled_prompt_version("def-legacy")
    assert version["rendered_text"] == '<private-rendered-prompt hash="renderedhash" />'
    assert "private memory" not in version["variable_snapshot_json"]
    task = migrated.get_task("user-legacy", "task-legacy")
    assert task["prompt"] == "Study {{user.memories}}"
    task_wb = task["metadata"]["workbench_scheduled_prompt"]
    assert "variable_snapshot_json" not in task_wb
    assert task_wb["variable_snapshot_pointer"].endswith("snapshothash")


def test_glasshive_worker_lifecycle_callback_is_signed_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient

    from scheduling_cortex.server import build_server
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    secret = "test-secret"
    worker_id = "wrk_1"
    monkeypatch.setenv("SCHEDULING_GLASSHIVE_CALLBACK_SECRET", secret)
    storage = ScheduleStorage(StorageConfig(db_path=str(tmp_path / "schedules.db")))
    mcp = build_server(storage)
    if not hasattr(mcp, "http_app"):
        pytest.skip("Cannot extract ASGI app from FastMCP server")
    client = TestClient(mcp.http_app(transport="streamable-http"))

    payload = {"event": "worker.ready", "worker_id": worker_id, "message": "Worker ready"}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    binding = f"{worker_id}:".encode("utf-8")
    derived_secret = hmac.new(secret.encode("utf-8"), binding, hashlib.sha256).hexdigest().encode("utf-8")
    signature = "sha256=" + hmac.new(derived_secret, raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/internal/scheduled-prompts/glasshive-callback",
        content=raw,
        headers={"content-type": "application/json", "x-glasshive-signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ignored": "worker.ready"}
