from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import importlib.util
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_BACKEND = REPO_ROOT / "viventium_v0_4" / "prompt-workbench" / "backend"
if str(WORKBENCH_BACKEND) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_BACKEND))

from prompt_workbench import cognitive_integrity, drafts, import_mapper, periphery_snapshots, prompt_service, promptfoo_adapter, scheduled_prompts, sync_engine  # noqa: E402
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


def test_cognitive_integrity_contract_distinguishes_worker_and_host_tools() -> None:
    payload = {
        "endpoints": {
            "agents": {
                "providerCapabilities": {
                    "glasshive-harness": {
                        "worker_native_tools": True,
                        "host_tools_transport": "broker_mcp",
                        "host_tools": ["file_search"],
                    }
                }
            }
        },
        "memory": {
            "tokenLimit": 8000,
            "keyLimits": {"world": 1200, "preferences": 600},
            "readProfile": {
                "tokenLimit": 8000,
                "keyLimits": {"world": 1200, "preferences": 600},
            },
        },
    }

    contract = cognitive_integrity._provider_and_memory_contract(payload)

    assert contract["providerCapabilityTransport"]["status"] == "ok"
    assert contract["memoryExposure"]["status"] == "ok"


def test_cognitive_integrity_imports_from_workbench_launch_path(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKBENCH_BACKEND)

    completed = subprocess.run(
        [sys.executable, "-c", "import prompt_workbench.cognitive_integrity"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_cognitive_integrity_contract_blocks_ambiguous_tools_and_hidden_memory() -> None:
    payload = {
        "endpoints": {
            "agents": {
                "providerCapabilities": {
                    "glasshive-harness": {"native_tools": True}
                }
            }
        },
        "memory": {
            "tokenLimit": 8000,
            "keyLimits": {"world": 1200},
            "readProfile": {"tokenLimit": 2200, "keyLimits": {"world": 320}},
        },
    }

    contract = cognitive_integrity._provider_and_memory_contract(payload)

    assert contract["providerCapabilityTransport"]["status"] == "blocked"
    assert "ambiguous_native_tools_field_present" in contract["providerCapabilityTransport"]["reasons"]
    assert contract["memoryExposure"]["status"] == "blocked"
    assert "read_total_below_storage_total" in contract["memoryExposure"]["reasons"]


def test_cognitive_integrity_contract_blocks_absent_memory_configuration() -> None:
    contract = cognitive_integrity._provider_and_memory_contract(
        {
            "endpoints": {
                "agents": {
                    "providerCapabilities": {
                        "glasshive-harness": {
                            "worker_native_tools": True,
                            "host_tools_transport": "broker_mcp",
                            "host_tools": ["file_search"],
                        }
                    }
                }
            }
        }
    )

    assert contract["memoryExposure"]["status"] == "blocked"
    assert "memory_config_missing" in contract["memoryExposure"]["reasons"]


def test_cognitive_integrity_blocks_failed_nightly_even_when_definition_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def list_scheduled_prompts(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "scheduledPrompts": [
                {
                    "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "lastStatus": "error",
                    "executor": "glasshive_host",
                    "executionProfile": "codex-cli",
                    "latestScheduledRun": {
                        "status": "failed",
                        "triggerKind": "scheduled",
                        "triggerSource": "scheduler_loop",
                        "startedAt": "2026-08-08T07:00:17Z",
                        "errorClass": "glasshive_evidence_check_failed",
                    },
                    "recentRuns": [
                        {"status": "failed", "errorClass": "glasshive_evidence_check_failed"}
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        cognitive_integrity.scheduled_prompts,
        "list_scheduled_prompts",
        list_scheduled_prompts,
    )

    result = cognitive_integrity._nightly_status("synthetic-user")

    assert result["status"] == "blocked"
    assert result["latestRunFailure"] is True
    assert result["lastErrorClass"] == "glasshive_evidence_check_failed"
    assert captured["read_only"] is True


def test_cognitive_integrity_does_not_let_manual_recovery_mask_failed_scheduled_nightly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def list_scheduled_prompts(**_: object) -> dict[str, object]:
        return {
            "scheduledPrompts": [
                {
                    "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "lastStatus": "completed",
                    "executor": "glasshive_host",
                    "executionProfile": "codex-cli",
                    "latestScheduledRun": {
                        "status": "failed",
                        "triggerKind": "scheduled",
                        "triggerSource": "scheduler_loop",
                        "startedAt": "2026-08-08T07:00:17Z",
                        "errorClass": "glasshive_evidence_check_failed",
                    },
                    "latestManualRun": {
                        "status": "completed",
                        "triggerKind": "manual",
                        "triggerSource": "workbench_manual",
                        "startedAt": "2026-08-08T15:46:44Z",
                    },
                    "recentRuns": [
                        {
                            "status": "completed",
                            "triggerKind": "manual",
                            "startedAt": "2026-08-08T15:46:44Z",
                        },
                        {
                            "status": "failed",
                            "triggerKind": "scheduled",
                            "startedAt": "2026-08-08T07:00:17Z",
                            "errorClass": "glasshive_evidence_check_failed",
                        },
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        cognitive_integrity.scheduled_prompts,
        "list_scheduled_prompts",
        list_scheduled_prompts,
    )

    result = cognitive_integrity._nightly_status("synthetic-user")

    assert result["status"] == "blocked"
    assert result["latestScheduledStatus"] == "failed"
    assert result["latestManualStatus"] == "completed"
    assert result["manualRecoveryAfterScheduledFailure"] is True
    assert result["lastErrorClass"] == "glasshive_evidence_check_failed"


def test_cognitive_integrity_blocks_when_manual_runs_evict_scheduled_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def list_scheduled_prompts(**_: object) -> dict[str, object]:
        return {
            "scheduledPrompts": [
                {
                    "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "lastStatus": "completed",
                    "recentRuns": [
                        {
                            "status": "completed",
                            "triggerKind": "manual",
                            "startedAt": f"2026-08-08T1{minute}:00:00Z",
                        }
                        for minute in range(5)
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        cognitive_integrity.scheduled_prompts,
        "list_scheduled_prompts",
        list_scheduled_prompts,
    )

    result = cognitive_integrity._nightly_status(
        "synthetic-user",
        now=datetime(2026, 8, 8, 16, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "blocked"
    assert result["latestScheduledStatus"] is None
    assert "scheduled_run_not_observed" in result["reasons"]


def test_cognitive_integrity_blocks_stale_scheduled_nightly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def list_scheduled_prompts(**_: object) -> dict[str, object]:
        return {
            "scheduledPrompts": [
                {
                    "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "lastStatus": "completed",
                    "latestScheduledRun": {
                        "status": "completed",
                        "triggerKind": "scheduled",
                        "startedAt": "2026-08-05T07:00:00Z",
                    },
                    "recentRuns": [],
                }
            ]
        }

    monkeypatch.setattr(
        cognitive_integrity.scheduled_prompts,
        "list_scheduled_prompts",
        list_scheduled_prompts,
    )

    result = cognitive_integrity._nightly_status(
        "synthetic-user",
        now=datetime(2026, 8, 8, 16, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "blocked"
    assert "scheduled_run_stale" in result["reasons"]
    assert result["latestScheduledAt"] == "2026-08-05T07:00:00Z"


def test_cognitive_integrity_rejects_a_projected_nightly_without_scheduler_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cognitive_integrity.scheduled_prompts,
        "list_scheduled_prompts",
        lambda **_: {
            "scheduledPrompts": [
                {
                    "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "latestScheduledRun": {
                        "status": "completed",
                        "triggerKind": "unknown",
                        "triggerSource": "scheduler_loop",
                        "startedAt": "2026-08-08T07:00:00Z",
                    },
                    "recentRuns": [],
                }
            ]
        },
    )

    result = cognitive_integrity._nightly_status(
        "synthetic-user",
        now=datetime(2026, 8, 8, 8, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "blocked"
    assert "scheduled_run_provenance_invalid" in result["reasons"]


def test_scheduling_db_path_honors_selected_app_support_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("SCHEDULING_DB_PATH", raising=False)
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path))

    assert scheduled_prompts._scheduling_db_path() == str(
        tmp_path / "state" / "runtime" / "isolated" / "scheduling" / "schedules.db"
    )


def test_scheduling_db_path_honors_runtime_state_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("SCHEDULING_DB_PATH", raising=False)
    monkeypatch.setenv("VIVENTIUM_STATE_ROOT", str(tmp_path))
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path / "ignored"))

    assert scheduled_prompts._scheduling_db_path() == str(
        tmp_path / "scheduling" / "schedules.db"
    )


def test_cognitive_integrity_blocks_codex_symlink_that_hides_enabled_companion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    bundle_cli = tmp_path / "bundle" / "codex"
    bundle_cli.parent.mkdir()
    bundle_cli.write_text("#!/bin/sh\necho 'code_mode_host stable true'\n", encoding="utf-8")
    bundle_cli.chmod(0o755)
    companion = bundle_cli.parent / "codex-code-mode-host"
    companion.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    companion.chmod(0o755)
    invocation = tmp_path / "bin" / "codex"
    invocation.parent.mkdir()
    invocation.symlink_to(bundle_cli)
    (runtime_dir / "runtime.env").write_text(f"WPR_CODEX_BIN={invocation}\n", encoding="utf-8")
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    result = cognitive_integrity._runtime_codex_worker_status()

    assert result["status"] == "blocked"
    assert result["binaryInvocation"] == "symlink"
    assert result["companionReady"] is False
    assert result["reasons"] == ["enabled_code_mode_host_companion_missing_at_invocation_path"]

    (runtime_dir / "runtime.env").write_text(f"WPR_CODEX_BIN={bundle_cli}\n", encoding="utf-8")
    assert cognitive_integrity._runtime_codex_worker_status()["status"] == "ok"


def test_cognitive_integrity_rejects_successful_but_unparseable_codex_feature_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    binary = tmp_path / "codex"
    binary.write_text("#!/bin/sh\necho 'not structured feature output'\n", encoding="utf-8")
    binary.chmod(0o755)
    (runtime_dir / "runtime.env").write_text(f"WPR_CODEX_BIN={binary}\n", encoding="utf-8")
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    result = cognitive_integrity._runtime_codex_worker_status()

    assert result == {"status": "blocked", "reasons": ["codex_feature_probe_unparseable"]}


def test_cognitive_integrity_requires_configured_non_admin_qa_account(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    assert cognitive_integrity._qa_test_account_status()["reasons"] == [
        "qa_test_account_not_configured"
    ]

    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_QA_EMAIL=qa-person@example.com\n"
        "VIVENTIUM_LOCAL_MONGO_PORT=27117\n"
        "VIVENTIUM_LOCAL_MONGO_DB=LibreChatViventium\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"count":1,"role":"USER","userId":"synthetic-user-id"}\n',
            stderr="",
        )

    monkeypatch.setattr(cognitive_integrity.subprocess, "run", fake_run)

    result = cognitive_integrity._qa_test_account_status()

    assert result["status"] == "ok"
    assert result["accountCount"] == 1
    assert "qa-person@example.com" not in " ".join(captured["command"])
    assert "qa-person@example.com" in str(captured["input"])


def test_cognitive_integrity_blocks_a_degraded_per_turn_memory_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    import json

    app_support = tmp_path / "app-support"
    health_dir = app_support / "state" / "memory-continuity-health"
    health_dir.mkdir(parents=True)
    user_hash = hashlib.sha256(b"synthetic-user-id").hexdigest()[:24]
    (health_dir / f"{user_hash}.read.json").write_text(
        json.dumps({"status": "ok", "path": "read", "updatedAt": "2026-08-08T10:00:00Z"}),
        encoding="utf-8",
    )
    (health_dir / f"{user_hash}.writer.json").write_text(
        json.dumps(
            {
                "status": "degraded",
                "path": "writer",
                "reason": "provider_auth",
                "updatedAt": "2026-08-08T10:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    result = cognitive_integrity._memory_continuity_runtime_status(
        user_hash,
        now=datetime.fromisoformat("2026-08-08T10:02:00+00:00"),
    )

    assert result["savedMemoryRead"]["status"] == "ok"
    assert result["savedMemoryRead"]["scope"] == "configured_qa_test_account"
    assert result["immediateMemoryWriter"]["status"] == "blocked"
    assert result["immediateMemoryWriter"]["reason"] == "provider_auth"
    assert result["immediateMemoryWriter"]["scope"] == "configured_qa_test_account"


def test_cognitive_integrity_blocks_missing_and_stale_memory_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    health_dir = app_support / "state" / "memory-continuity-health"
    health_dir.mkdir(parents=True)
    user_hash = "synthetic-user-hash"
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    missing = cognitive_integrity._memory_continuity_runtime_status(
        user_hash,
        now=datetime(2026, 8, 8, 16, 0, tzinfo=timezone.utc),
    )
    assert missing["savedMemoryRead"]["status"] == "blocked"
    assert missing["savedMemoryRead"]["reason"] == "no_runtime_receipt"
    assert missing["immediateMemoryWriter"]["status"] == "blocked"

    stale_payload = {
        "status": "ok",
        "updatedAt": "2026-08-06T10:00:00Z",
        "provider": "openai",
        "model": "synthetic-model",
        "effort": "medium",
    }
    for path_key in ("read", "writer"):
        (health_dir / f"{user_hash}.{path_key}.json").write_text(
            json.dumps({**stale_payload, "path": path_key}),
            encoding="utf-8",
        )

    stale = cognitive_integrity._memory_continuity_runtime_status(
        user_hash,
        now=datetime(2026, 8, 8, 16, 0, tzinfo=timezone.utc),
    )
    assert stale["savedMemoryRead"]["status"] == "blocked"
    assert stale["savedMemoryRead"]["reason"] == "runtime_receipt_stale"
    assert stale["immediateMemoryWriter"]["status"] == "blocked"
    assert stale["immediateMemoryWriter"]["effort"] == "medium"


def test_cognitive_integrity_blocks_unobserved_memory_paths_in_joined_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cognitive_integrity, "_safe_runtime_drift", lambda _path: {"status": "ok"})
    monkeypatch.setattr(cognitive_integrity, "_safe_prompt_drift", lambda: {"status": "ok"})
    monkeypatch.setattr(
        cognitive_integrity,
        "load_source_of_truth_librechat_yaml",
        lambda: {
            "endpoints": {
                "agents": {
                    "providerCapabilities": {
                        "glasshive-harness": {
                            "worker_native_tools": True,
                            "host_tools_transport": "broker_mcp",
                            "host_tools": ["file_search"],
                        }
                    }
                }
            },
            "memory": {
                "tokenLimit": 1,
                "keyLimits": {"core": 1},
                "readProfile": {"tokenLimit": 1, "keyLimits": {"core": 1}},
            },
        },
    )
    monkeypatch.setattr(cognitive_integrity, "_live_contract", cognitive_integrity.load_source_of_truth_librechat_yaml)
    monkeypatch.setattr(cognitive_integrity, "_runtime_codex_worker_status", lambda: {"status": "ok"})
    monkeypatch.setattr(cognitive_integrity, "_nightly_status", lambda _user: {"status": "ok"})
    monkeypatch.setattr(cognitive_integrity, "_health_context_status", lambda _user: {"status": "ok"})
    monkeypatch.setattr(
        cognitive_integrity,
        "_consciousness_continuity_status",
        lambda _user: {"status": "ok"},
    )
    monkeypatch.setattr(
        cognitive_integrity,
        "_qa_test_account_status",
        lambda: {"status": "ok", "accountHash": "synthetic-hash"},
    )
    monkeypatch.setattr(
        cognitive_integrity,
        "_memory_continuity_runtime_status",
        lambda _hash: {
            "savedMemoryRead": {"status": "not_observed"},
            "immediateMemoryWriter": {"status": "not_observed"},
        },
    )
    monkeypatch.setattr(cognitive_integrity, "_memory_hardening_status", lambda: {"status": "ok"})
    monkeypatch.setattr(cognitive_integrity, "_conversation_recall_runtime_status", lambda: {"status": "ok"})

    result = cognitive_integrity.cognitive_integrity_report(user_id="synthetic-user")

    assert result["status"] == "blocked"
    assert "qaAccountSavedMemoryReadRuntime" in result["blockingChecks"]
    assert "qaAccountImmediateMemoryWriterRuntime" in result["blockingChecks"]


def test_cognitive_integrity_recall_health_requires_a_structured_up_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "RAG_API_URL=http://127.0.0.1:9999\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"[]"

    monkeypatch.setattr(cognitive_integrity.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = cognitive_integrity._conversation_recall_runtime_status()

    assert result == {
        "status": "blocked",
        "reason": "recall_health_invalid_payload",
        "httpStatus": 200,
    }


def test_cognitive_integrity_recall_health_accepts_only_explicit_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "RAG_API_URL=http://127.0.0.1:9999\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cognitive_integrity, "APP_SUPPORT_VIVENTIUM_DIR", app_support)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"status":"UP"}'

    monkeypatch.setattr(cognitive_integrity.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    result = cognitive_integrity._conversation_recall_runtime_status()

    assert result["status"] == "ok"
    assert result["declaredStatus"] == "UP"


def test_sync_status_lists_each_canonical_background_agent_prompt_unit() -> None:
    source = prompt_service.source_agents_bundle()

    rows = sync_engine._agent_rows(source=source, live=source, ledger={"records": {}})

    background_rows = [row for row in rows if row["sourcePromptId"] != "main.conscious_agent"]
    assert len(background_rows) == len(source["backgroundAgents"]) == 12
    assert {row["sourcePromptId"] for row in background_rows} == {
        "cortex.background_analysis.execution",
        "cortex.confirmation_bias.execution",
        "cortex.deep_memory.execution",
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


@pytest.mark.parametrize(
    "headers",
    [
        {"x-viventium-workbench-token": "synthetic-current-launch-token"},
        {"x-viventium-workbench-token": "synthetic-rotated-launch-token"},
        {"authorization": "Bearer synthetic-current-launch-token"},
        {"authorization": "Bearer synthetic-rotated-launch-token"},
    ],
)
def test_workbench_rejects_current_and_rotated_legacy_bearers_without_loopback_fallback(
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv(
        "VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", "synthetic-current-launch-token"
    )
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "synthetic-admin")
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)
    monkeypatch.setattr(auth, "_librechat_admin_auth", lambda _request: None)
    client = TestClient(app)

    assert client.get("/api/auth/status").json()["method"] == "local_loopback_admin"
    assert client.get("/api/variables", headers=headers).status_code == 401
    assert client.get("/api/auth/status", headers=headers).json()["authenticated"] is False


@pytest.mark.parametrize(
    "path",
    (
        "/api/prompts",
        "/api/prompts/synthetic-prompt",
        "/api/prompts/synthetic-prompt/workbench-context",
        "/api/prompts/synthetic-prompt/revisions/synthetic-revision",
        "/api/sync/status",
        "/api/drafts",
        "/api/drafts/synthetic-draft",
        "/api/evals",
        "/api/evals/runs",
        "/api/evals/runs/synthetic-run",
        "/api/evals/promptfoo/synthetic-prompt",
        "/api/frames",
    ),
)
def test_workbench_private_read_routes_reject_revoked_bearer_credentials(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "synthetic-admin")
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)
    monkeypatch.setattr(auth, "_librechat_admin_auth", lambda _request: None)

    response = TestClient(app).get(
        path,
        headers={"x-viventium-workbench-token": "synthetic-revoked-bearer"},
    )

    assert response.status_code == 401


def test_workbench_rejects_leaked_bearer_from_non_loopback_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", "synthetic-leaked-token")
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: False)
    monkeypatch.setattr(auth, "_librechat_admin_auth", lambda _request: None)

    response = TestClient(app).get(
        "/api/variables", headers={"x-viventium-workbench-token": "synthetic-leaked-token"}
    )

    assert response.status_code == 401


def test_workbench_rejects_remote_clients_even_with_a_verified_admin_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: False)
    monkeypatch.setattr(
        auth,
        "_librechat_admin_auth",
        lambda _request: auth.AuthContext(
            authenticated=True,
            admin=True,
            method="librechat_admin",
            user_id="synthetic-admin",
        ),
    )
    client = TestClient(app, cookies={"viventium_session": "synthetic-admin-session"})

    assert client.get("/api/auth/status").json()["authenticated"] is False
    assert client.get("/api/variables").status_code == 401


def test_workbench_redirects_legacy_page_credentials_without_referrer_or_history_leak() -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    secret = "synthetic-legacy-url-token"
    client = TestClient(app)
    response = client.get(
        f"/?workbench_token={secret}&tab=evals",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?tab=evals"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in response.headers["cache-control"]
    assert secret not in response.text
    assert secret not in json.dumps(dict(response.headers))


def test_workbench_rejects_api_url_credentials_and_sets_no_referrer_policy() -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from prompt_workbench.app import app

    secret = "synthetic-legacy-url-token"
    client = TestClient(app)
    response = client.get(f"/api/health?workbench_token={secret}")
    clean_response = client.get("/api/health")

    assert response.status_code == 400
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in response.headers["cache-control"]
    assert secret not in response.text
    assert clean_response.headers["referrer-policy"] == "no-referrer"


def test_workbench_frontend_and_browser_qa_never_store_or_transmit_launch_bearers() -> None:
    api_source = (WORKBENCH_SRC / "api.ts").read_text(encoding="utf-8")
    qa_source = (
        REPO_ROOT / "qa" / "prompt-workbench" / "scripts" / "live-evals-browser-qa.cjs"
    ).read_text(encoding="utf-8")

    assert 'removeLocalStorage("viventium.promptWorkbench.launchToken")' in api_source
    assert (
        'window.sessionStorage.removeItem("viventium.promptWorkbench.launchToken")'
        in api_source
    )
    assert "writeLocalStorage" not in api_source
    assert "readLocalStorage" not in api_source
    assert "sessionStorage.setItem" not in api_source
    assert "x-viventium-workbench-token" not in api_source
    assert "state.authUrl" not in qa_source
    assert 'localStorage.getItem("viventium.promptWorkbench.launchToken")' not in qa_source
    assert 'await page.goto(state.url,' in qa_source


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

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)
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

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)

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


def test_workbench_accepts_only_the_existing_admin_cookie_without_a_launch_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", "synthetic-private-launch-token")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_LOOPBACK_ADMIN_AUTH", "false")
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)

    captured_headers: dict[str, str] = {}

    class FakeAdminVerifyResponse:
        status = 200

        def read(self) -> bytes:
            return json.dumps(
                {"user": {"id": "cookie-admin-1", "email": "admin@example.test"}}
            ).encode("utf-8")

        def __enter__(self) -> "FakeAdminVerifyResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def verify_admin_cookie(request: object, *_args: object, **_kwargs: object) -> FakeAdminVerifyResponse:
        captured_headers.update(
            {str(key).lower(): str(value) for key, value in request.header_items()}
        )
        return FakeAdminVerifyResponse()

    monkeypatch.setattr(auth.urllib.request, "urlopen", verify_admin_cookie)
    client = TestClient(app, cookies={"viventium_session": "synthetic-admin-session"})

    status = client.get("/api/auth/status")

    assert status.status_code == 200
    assert status.json()["admin"] is True
    assert status.json()["method"] == "librechat_admin"
    assert status.json()["userId"] == "cookie-admin-1"
    assert "viventium_session=synthetic-admin-session" in captured_headers["cookie"]
    assert "authorization" not in captured_headers
    assert "x-viventium-workbench-token" not in captured_headers


@pytest.mark.parametrize(
    "cookies",
    (
        {"unrelated_localhost_app": "synthetic-preference"},
        {"refreshToken": "synthetic-expired-local-session"},
        {"viventium_session": "synthetic-expired-admin-session"},
    ),
)
def test_direct_loopback_admin_survives_ambient_or_expired_browser_cookies(
    cookies: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("httpx")
    pytest.importorskip("fastapi.testclient")
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID", "synthetic-owner-admin")
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_LOOPBACK_ADMIN_AUTH", "true")
    from fastapi.testclient import TestClient
    from prompt_workbench import auth
    from prompt_workbench.app import app

    monkeypatch.setattr(auth, "_is_loopback_request", lambda _request: True)
    monkeypatch.setattr(auth, "_librechat_admin_auth", lambda _request: None)

    client = TestClient(app, cookies=cookies)
    status = client.get("/api/auth/status")

    assert status.json()["authenticated"] is True
    assert status.json()["method"] == "local_loopback_admin"
    assert status.json()["userId"] == "synthetic-owner-admin"
    assert client.get("/api/prompts").status_code == 200


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
    assert "GlassHive worker" in schedule_source
    assert "Viventium Main (Agent Builder)" in schedule_source
    assert "Inherits the persisted Main Agent route and fallback at run time" in schedule_source
    assert "This user-level schedule does not use Workbench variable" in schedule_source
    assert "User-level scheduler policy" in schedule_source
    assert "confirmUserLevelDelivery" in api_source
    assert "Manual Viventium Main run started" in schedule_source
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


def test_prompt_trace_status_layout_keeps_healthy_copy_in_the_message_column() -> None:
    frame_source = (WORKBENCH_SRC / "components" / "FramePanel.tsx").read_text(encoding="utf-8")
    css_source = (WORKBENCH_SRC / "styles.css").read_text(encoding="utf-8")

    assert "trace-source-status${showWarning ? ' has-warning' : ''}" in frame_source
    assert "grid-template-columns: minmax(0, 1fr) auto;" in css_source
    assert ".trace-source-status.has-warning" in css_source
    assert "grid-template-columns: min-content minmax(0, 1fr) auto;" in css_source


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


def test_scheduled_prompt_update_persists_registered_source_prompt_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from prompt_workbench.app import ScheduledPromptPatchRequest

    assert ScheduledPromptPatchRequest(
        sourcePromptId="scheduler.consciousness_continuity_opportunity"
    ).model_dump()["sourcePromptId"] == "scheduler.consciousness_continuity_opportunity"

    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv(
        "VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive")
    )
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    created = scheduled_prompts.create_scheduled_prompt(
        {
            "title": "Continuity",
            "promptText": "Orient, appraise, choose, act, observe, and reappraise.",
            "executor": "viventium_agent",
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    updated = scheduled_prompts.update_scheduled_prompt(
        created["id"],
        {"sourcePromptId": "scheduler.consciousness_continuity_opportunity"},
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    stored = scheduled_prompts.storage().get_scheduled_prompt_definition(created["id"])
    task = scheduled_prompts.storage().get_task("startup-admin", stored["task_id"])
    assert updated["sourcePromptId"] == "scheduler.consciousness_continuity_opportunity"
    assert stored["source_prompt_id"] == "scheduler.consciousness_continuity_opportunity"
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["source_prompt_id"]
        == "scheduler.consciousness_continuity_opportunity"
    )
    assert (
        task["metadata"]["prompt_context"]["effective_prompt_id"]
        == "scheduler.consciousness_continuity_opportunity"
    )


def test_custom_memory_off_glasshive_schedule_uses_isolated_parallel_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_GLASSHIVE_ISOLATED_PARALLEL_POLICY", "true")
    monkeypatch.setenv("VIVENTIUM_PARALLEL_WORK_EXECUTION_MODE", "docker")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    created = scheduled_prompts.create_scheduled_prompt(
        {
            "title": "Isolated synthetic task",
            "promptText": "Return a bounded synthetic result.",
            "executor": "glasshive_host",
            "memoryWriteMode": "off",
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(created["id"])
    task = store.get_task("startup-admin", definition["task_id"])
    execution = definition["metadata"]["execution"]
    workbench = task["metadata"]["workbench_scheduled_prompt"]
    assert execution["execution_mode"] == "docker"
    assert execution["workspace_root"] == ""
    assert workbench["execution_mode"] == "docker"
    assert workbench["workspace_root"] == ""
    assert workbench["my_folder"] == ""
    assert definition["my_folder"]
    assert created["workspaceRoot"] == ""
    assert created["myFolder"] == ""


def test_governed_glasshive_schedule_keeps_configured_host_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_GLASSHIVE_ISOLATED_PARALLEL_POLICY", "true")
    monkeypatch.setenv("VIVENTIUM_PARALLEL_WORK_EXECUTION_MODE", "docker")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    created = scheduled_prompts.create_scheduled_prompt(
        {
            "title": "Governed memory task",
            "promptText": "Prepare a governed memory proposal.",
            "executor": "glasshive_host",
            "memoryWriteMode": "propose",
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    definition = scheduled_prompts.storage().get_scheduled_prompt_definition(created["id"])
    assert definition["metadata"]["execution"]["execution_mode"] == "host"
    assert definition["metadata"]["execution"]["workspace_root"]


def test_nightly_seed_migrates_existing_memory_off_builtin_to_isolated_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("VIVENTIUM_GLASSHIVE_ISOLATED_PARALLEL_POLICY", "true")
    monkeypatch.setenv("VIVENTIUM_PARALLEL_WORK_EXECUTION_MODE", "docker")
    monkeypatch.setenv("WPR_DEFAULT_EXECUTION_MODE", "host")
    monkeypatch.setenv("WPR_HOST_WORKSPACE_ROOT", str(tmp_path / "host-workspace"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-test-scheduled")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda script: None)

    template = scheduled_prompts.nightly_prompt_template()
    created = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": scheduled_prompts.NIGHTLY_TEMPLATE_ID,
            "active": True,
            "memoryWriteMode": "off",
        },
        user_id="startup-admin",
        email="startup-admin@example.test",
    )
    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(created["id"])
    version_before = store.latest_scheduled_prompt_version(created["id"])
    stale_metadata = dict(definition["metadata"])
    stale_execution = dict(stale_metadata["execution"])
    stale_execution.update(
        {
            "execution_mode": "host",
            "workspace_root": str(tmp_path / "host-workspace"),
        }
    )
    stale_metadata["execution"] = stale_execution
    store.update_scheduled_prompt_definition(created["id"], {"metadata": stale_metadata})

    task = store.get_task("startup-admin", definition["task_id"])
    task_metadata = dict(task["metadata"])
    task_metadata["execution"] = dict(stale_execution)
    task_workbench = dict(task_metadata["workbench_scheduled_prompt"])
    task_workbench.update(
        {
            "execution_mode": "host",
            "workspace_root": str(tmp_path / "host-workspace"),
        }
    )
    task_metadata["workbench_scheduled_prompt"] = task_workbench
    store.update_task(
        "startup-admin",
        definition["task_id"],
        {
            "metadata": task_metadata,
            "last_run_at": "2026-08-20T07:00:00Z",
            "last_status": "error",
            "last_error": "provider_quota_exhausted",
            "last_generated_text": "preserved prior result",
        },
    )

    scheduled_prompts.seed_nightly_prompt(
        user_id="startup-admin",
        email="startup-admin@example.test",
    )

    stored = store.get_scheduled_prompt_definition(created["id"])
    task = store.get_task("startup-admin", definition["task_id"])
    version_after = store.latest_scheduled_prompt_version(created["id"])
    assert stored["metadata"]["execution"]["execution_mode"] == "docker"
    assert stored["metadata"]["execution"]["workspace_root"] == ""
    assert task["metadata"]["execution"]["execution_mode"] == "docker"
    assert task["metadata"]["execution"]["workspace_root"] == ""
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_mode"] == "docker"
    assert task["metadata"]["workbench_scheduled_prompt"]["workspace_root"] == ""
    assert task["metadata"]["workbench_scheduled_prompt"]["my_folder"] == stored["my_folder"]
    assert stored["active"] == 1
    assert task["active"] == 1
    assert task["last_run_at"] == "2026-08-20T07:00:00Z"
    assert task["last_status"] == "error"
    assert task["last_error"] == "provider_quota_exhausted"
    assert task["last_generated_text"] == "preserved prior result"
    assert version_after["id"] == version_before["id"]


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
        "WPR_CLAUDE_CODE_EFFORT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert scheduled_prompts._default_automation_model("codex-cli") == ""
    assert scheduled_prompts._default_automation_reasoning_effort() == ""

    monkeypatch.setenv("WPR_MODEL_CLAUDE_CODE", "claude-configured-test")
    monkeypatch.setenv("WPR_CLAUDE_CODE_EFFORT", "max")
    assert scheduled_prompts._default_automation_model("claude-code") == "claude-configured-test"
    assert scheduled_prompts._default_automation_model("unknown-profile") == ""

    monkeypatch.setenv("GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE", "claude-code")
    assert (
        scheduled_prompts._default_glasshive_fallback_worker_profile("codex-cli")
        == "claude-code"
    )
    assert scheduled_prompts._default_glasshive_fallback_worker_route("codex-cli") == {
        "fallback_worker_profile": "claude-code",
        "fallback_worker_model": "claude-configured-test",
        "fallback_reasoning_effort": "max",
    }
    assert scheduled_prompts._default_glasshive_fallback_worker_profile("claude-code") == ""


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
    monkeypatch.setenv("GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE", "claude-code")
    monkeypatch.setenv("WPR_MODEL_CLAUDE_CODE", "claude-fallback-test")
    monkeypatch.setenv("WPR_CLAUDE_CODE_EFFORT", "max")
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
    assert created.json()["fallbackWorkerProfile"] == "claude-code"
    assert created.json()["fallbackWorkerModel"] == "claude-fallback-test"
    assert created.json()["fallbackReasoningEffort"] == "max"

    patched = client.patch(f"/api/scheduled-prompts/{prompt_id}", json={"active": True})
    assert patched.status_code == 200
    assert patched.json()["active"] is True

    invalid_mode = client.patch(f"/api/scheduled-prompts/{prompt_id}", json={"memoryWriteMode": "direct_mongo"})
    assert invalid_mode.status_code == 400

    manual = client.post(f"/api/scheduled-prompts/{prompt_id}/manual-runs")
    assert manual.status_code == 200
    assert manual.json()["run"]["status"] == "queued"
    assert manual.json()["run"]["triggerKind"] == "manual"
    assert manual.json()["run"]["triggerSource"] == "workbench_manual"
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
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_worker_profile"]
        == "claude-code"
    )
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_worker_model"]
        == "claude-fallback-test"
    )
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_reasoning_effort"]
        == "max"
    )
    assert runs and Path(runs[0]["private_detail_path"]).exists()
    assert runs[0]["trigger_kind"] == "manual"
    assert runs[0]["trigger_source"] == "workbench_manual"
    assert runs[0]["occurrence_key"] == runs[0]["run_id"]
    assert runs[0]["lease_until"] is not None
    due_at = datetime.fromisoformat(runs[0]["due_at"].replace("Z", "+00:00"))
    started_at = datetime.fromisoformat(runs[0]["started_at"].replace("Z", "+00:00"))
    assert due_at <= started_at
    assert (started_at - due_at).total_seconds() < 1
    assert runs[0]["execution_snapshot"]["dispatch_idempotency_key"] == runs[0]["run_id"]
    blocked = store.claim_scheduled_prompt_occurrence(
        task_id=task["id"],
        user_id=task["user_id"],
        executor=task["executor"],
        due_at=task["next_run_at"],
        lease_owner="scheduler-test",
        now=runs[0]["started_at"],
        lease_seconds=60,
    )
    assert blocked["claimed"] is False
    assert blocked["reason"] == "task_has_active_occurrence"
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


def test_public_scheduled_run_exposes_backward_compatible_audit_outcomes() -> None:
    public = scheduled_prompts._public_run(
        {
            "run_id": "run-audit-1",
            "status": "completed",
            "executor": "viventium_agent",
            "disposition": "silent",
            "started_at": "2026-08-10T13:00:00Z",
            "completed_at": "2026-08-10T13:00:01.250Z",
            "execution_snapshot_json": json.dumps(
                {
                    "model": "gpt-5.6-sol",
                    "reasoning_effort": "xhigh",
                    "usage": {"input_tokens": 120, "output_tokens": 30, "cost_usd": 0.012},
                    "degraded_dependencies": ["calendar unavailable"],
                    "private_prompt": "must not surface",
                }
            ),
            "channel_outcomes_json": json.dumps(
                {
                    "workbench": {"outcome": "audit_only", "reason": "audit_sink"},
                    "telegram": {
                        "outcome": "suppressed",
                        "reason": "no_useful_output",
                        "generated_text": "must not surface",
                    },
                }
            ),
        }
    )

    assert public["disposition"] == "silent"
    assert public["effectiveModel"] == "gpt-5.6-sol"
    assert public["effectiveReasoningEffort"] == "xhigh"
    assert public["latencyMs"] == 1250
    assert public["usage"] == {"inputTokens": 120, "outputTokens": 30, "costUsd": 0.012}
    assert public["degradedDependencies"] == ["calendar unavailable"]
    assert public["channelOutcomes"] == {
        "workbench": {"outcome": "audit_only", "reason": "audit_sink"},
        "telegram": {"outcome": "suppressed", "reason": "no_useful_output"},
    }
    assert "private_prompt" not in json.dumps(public)
    assert "generated_text" not in json.dumps(public)


def test_schedules_panel_supports_windowed_intervals_and_audit_context() -> None:
    source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "ScheduledPromptsPanel.tsx"
    ).read_text(encoding="utf-8")

    assert '<option value="interval">Interval</option>' in source
    assert 'active_window' in source
    assert 'start_local' in source
    assert 'end_local' in source
    assert 'cadence: "restart_daily"' in source
    assert 'Projected runs/day' in source
    assert 'Dedicated conversation per run' in source
    assert 'Dedicated durable conversation' in source
    assert 'Destination channels' in source
    assert 'deliveryLibreChat' in source
    assert 'deliveryTelegram' in source
    assert 'LibreChat chat' in source
    assert 'Telegram' in source
    assert 'Source prompt' in source
    assert 'Standing Main capability' in source
    assert 'Run envelope' in source
    assert 'Canonical output' in source
    assert 'Effective prompt' in source
    assert 'Effective scheduled model' in source
    assert 'Effective scheduled effort' in source
    assert 'run.disposition' in source
    assert 'run.effectiveModel' in source
    assert 'run.channelOutcomes' in source
    assert 'Latency:' in source
    assert 'Tokens / cost: not recorded' in source
    assert 'Degraded dependencies:' in source
    assert 'silent, delivered, partial, superseded, or failed' in source
    assert 'Workbench is an audit sink, not user delivery' in source
    assert 'aria-describedby' in source
    assert 'role="switch"' in source
    assert 'aria-checked={item.active}' in source
    assert 'aria-label={`${item.active ? "Disable" : "Enable"} ${item.title}`}' in source
    assert 'className="schedule-row-select"' in source


def test_schedules_panel_opens_related_prompts_in_the_normal_editor() -> None:
    schedule_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "ScheduledPromptsPanel.tsx"
    ).read_text(encoding="utf-8")
    dock_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "WorkbenchDock.tsx"
    ).read_text(encoding="utf-8")

    assert "onOpenPrompt?: (id: string) => void" in schedule_source
    assert "onOpenPrompt?.(selected.sourcePromptId!)" in schedule_source
    assert "onOpenPrompt?.(selected.effectivePromptId!)" in schedule_source
    assert "onOpenPrompt?.(selected.runEnvelopePromptId!)" in schedule_source
    assert "onOpenPrompt?.(selected.canonicalOutputPromptId!)" in schedule_source
    assert "onOpenPrompt?.(selected.standingCapabilityPromptId!)" in schedule_source
    assert 'href={`/api/prompts/' not in schedule_source
    assert "onOpenPrompt={onOpenPrompt}" in dock_source


def test_dock_hides_flexlayout_measurement_text_from_the_accessibility_tree() -> None:
    source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "WorkbenchDock.tsx"
    ).read_text(encoding="utf-8")

    assert "useLayoutEffect" in source
    assert "dockHostRef" in source
    assert "querySelectorAll<HTMLElement>('.flexlayout__layout_metrics')" in source
    assert "setAttribute('aria-hidden', 'true')" in source
    assert 'ref={dockHostRef}' in source


def test_scheduler_prompt_contracts_are_visible_as_workbench_related_sources() -> None:
    envelope = prompt_service.related_config_for_prompt("scheduler.run_envelope")
    opportunity = prompt_service.related_config_for_prompt(
        "scheduler.consciousness_continuity_opportunity"
    )
    canonical_output = prompt_service.related_config_for_prompt("scheduler.canonical_output")

    assert envelope[0]["selector"] == "SCHEDULER_RUN_ENVELOPE_TEMPLATE"
    assert opportunity[0]["selector"] == (
        "CONSCIOUSNESS_CONTINUITY_OPPORTUNITY_PROMPT_ID"
    )
    assert canonical_output[0]["selector"] == "buildScheduledCanonicalOutputInstructions"
    assert all(
        row["status"] == "source"
        for row in [*envelope, *opportunity, *canonical_output]
    )


def test_legacy_nightly_runs_without_trigger_provenance_remain_unknown() -> None:
    schedule = {"type": "daily", "time": "03:00", "timezone": "America/Toronto"}

    scheduled = scheduled_prompts._public_run(
        {"run_id": "run-scheduled", "due_at": "2026-08-08T07:00:00Z"},
        schedule=schedule,
        timezone_name="America/Toronto",
    )
    manual = scheduled_prompts._public_run(
        {"run_id": "run-manual", "due_at": "2026-08-08T15:46:42Z"},
        schedule=schedule,
        timezone_name="America/Toronto",
    )

    assert scheduled["triggerKind"] == "unknown"
    assert manual["triggerKind"] == "unknown"


def test_caller_label_cannot_impersonate_scheduler_or_manual_provenance() -> None:
    assert scheduled_prompts._public_run(
        {
            "run_id": "caller-labelled",
            "trigger_kind": "scheduled",
            "trigger_source": "unverified_caller",
        }
    )["triggerKind"] == "unknown"
    assert scheduled_prompts._public_run(
        {
            "run_id": "scheduler-loop",
            "trigger_kind": "scheduled",
            "trigger_source": "scheduler_loop",
        }
    )["triggerKind"] == "scheduled"


def test_scheduler_provenance_requires_due_time_to_match_declared_schedule() -> None:
    schedule = {"type": "daily", "time": "03:00", "timezone": "America/Toronto"}
    matching = scheduled_prompts._public_run(
        {
            "run_id": "scheduler-on-cadence",
            "due_at": "2026-08-08T07:00:00Z",
            "trigger_kind": "scheduled",
            "trigger_source": "scheduler_loop",
        },
        schedule=schedule,
        timezone_name="America/Toronto",
    )
    forged = scheduled_prompts._public_run(
        {
            "run_id": "scheduler-off-cadence",
            "due_at": "2026-08-08T15:46:42Z",
            "trigger_kind": "scheduled",
            "trigger_source": "scheduler_loop",
        },
        schedule=schedule,
        timezone_name="America/Toronto",
    )

    assert matching["triggerKind"] == "scheduled"
    assert forged["triggerKind"] == "unknown"


def test_public_definition_projects_latest_scheduled_outside_recent_manual_window() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_task(self, *_args):
            return None

        def latest_scheduled_prompt_version(self, *_args):
            return None

        def list_scheduled_prompt_runs(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("trigger_kind") == "scheduled":
                return [
                    {
                        "run_id": "scheduled-run",
                        "status": "completed",
                        "trigger_kind": "scheduled",
                        "trigger_source": "scheduler_loop",
                        "due_at": "2026-08-08T03:00:00Z",
                        "started_at": "2026-08-08T07:00:00Z",
                    }
                ]
            if kwargs.get("trigger_kind") == "manual":
                return [
                    {
                        "run_id": "manual-run",
                        "status": "completed",
                        "trigger_kind": "manual",
                        "trigger_source": "workbench_manual",
                        "started_at": "2026-08-08T12:00:00Z",
                    }
                ]
            return [
                {
                    "run_id": f"manual-{index}",
                    "status": "completed",
                    "trigger_kind": "manual",
                    "trigger_source": "workbench_manual",
                    "started_at": f"2026-08-08T1{index}:00:00Z",
                }
                for index in range(5)
            ]

    store = FakeStore()
    public = scheduled_prompts._public_definition(
        {
            "id": "definition-1",
            "task_id": None,
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "timezone": "UTC",
            "active": True,
        },
        store=store,
    )

    assert len(public["recentRuns"]) == 5
    assert public["latestScheduledRun"]["runId"] == "scheduled-run"
    assert public["latestScheduledRun"]["triggerKind"] == "scheduled"
    assert public["latestManualRun"]["runId"] == "manual-run"
    assert any(
        call.get("trigger_kind") == "scheduled"
        and call.get("trigger_source") == "scheduler_loop"
        for call in store.calls
    )


def _create_orphaned_nightly_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    template_id: str | None = None,
) -> tuple[object, dict[str, object], dict[str, object]]:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "synthetic-nightly-model")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(scheduled_prompts, "_query_mongo_json", lambda _script: None)

    selected_template_id = template_id or scheduled_prompts.NIGHTLY_TEMPLATE_ID
    is_health_context = selected_template_id == scheduled_prompts.HEALTH_CONTEXT_TEMPLATE_ID
    template = (
        scheduled_prompts.health_context_prompt_template()
        if is_health_context
        else scheduled_prompts.nightly_prompt_template()
    )
    schedule_time = "06:15" if is_health_context else "03:00"
    created = scheduled_prompts.create_scheduled_prompt(
        {
            **template,
            "templateId": selected_template_id,
            "schedule": {"type": "daily", "time": schedule_time, "timezone": "UTC"},
            "active": True,
        },
        user_id="synthetic-nightly-owner",
        email="nightly@example.test",
    )
    store = scheduled_prompts.storage()
    definition = store.get_scheduled_prompt_definition(str(created["id"]))
    assert definition is not None
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=2)
    due = now.replace(
        hour=6 if is_health_context else 3,
        minute=15 if is_health_context else 0,
        second=0,
        microsecond=0,
    )
    started_iso = started.isoformat().replace("+00:00", "Z")
    due_iso = due.isoformat().replace("+00:00", "Z")
    lease_until = (now + timedelta(hours=22)).isoformat().replace("+00:00", "Z")
    store.update_task(
        "synthetic-nightly-owner",
        str(definition["task_id"]),
        {
            "last_run_at": started_iso,
            "last_status": "running",
            "last_error": None,
            "last_delivery_outcome": "queued",
            "updated_at": started_iso,
        },
    )
    run = store.create_scheduled_prompt_run(
        {
            "run_id": "sp_run_orphaned_synthetic",
            "task_id": definition["task_id"],
            "definition_id": definition["id"],
            "user_id": "synthetic-nightly-owner",
            "due_at": due_iso,
            "started_at": started_iso,
            "status": "running",
            "executor": "glasshive_host",
            "glasshive_project_id": "prj_synthetic_nightly",
            "glasshive_worker_id": "wrk_synthetic_nightly",
            "glasshive_run_id": "run_synthetic_nightly",
            "trigger_kind": "scheduled",
            "trigger_source": "scheduler_loop",
            "occurrence_key": "schedule:synthetic-nightly",
            "lease_owner": "scheduler:999999999:synthetic-owner",
            "lease_until": lease_until,
            "disposition": "running",
            "created_at": started_iso,
            "updated_at": started_iso,
        }
    )
    return store, definition, run


def test_workbench_terminal_reconciliation_loads_canonical_runtime_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WPR_API_TOKEN", raising=False)
    monkeypatch.delenv("GLASSHIVE_API_TOKEN", raising=False)
    monkeypatch.delenv("GLASSHIVE_RUNTIME_URL", raising=False)
    monkeypatch.delenv("WPR_API_URL", raising=False)
    loaded: list[bool] = []

    def load_runtime() -> None:
        loaded.append(True)
        os.environ["WPR_API_TOKEN"] = "synthetic-runtime-token"
        os.environ["GLASSHIVE_RUNTIME_URL"] = "http://127.0.0.1:9876"

    observed: dict[str, object] = {}

    def get_run(url: str, headers: dict[str, str], timeout: int) -> dict[str, object]:
        observed.update({"url": url, "headers": headers, "timeout": timeout})
        return {"run_id": "run-safe", "state": "failed"}

    monkeypatch.setattr(scheduled_prompts, "load_viventium_runtime_env", load_runtime)
    monkeypatch.setattr(scheduled_prompts, "_get_json", get_run)

    assert scheduled_prompts._glasshive_run_snapshot({"glasshive_run_id": "run-safe"}) == {
        "run_id": "run-safe",
        "state": "failed",
    }
    assert loaded == [True]
    assert observed["url"] == "http://127.0.0.1:9876/v1/runs/run-safe"
    assert observed["headers"]["Authorization"] == "Bearer synthetic-runtime-token"
    assert observed["timeout"] == 2


def test_workbench_stalled_nightly_reconciles_confirmed_worker_failure_and_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(tmp_path, monkeypatch)
    provider_reads: list[str] = []

    def terminal_snapshot(run: dict[str, object]) -> dict[str, object]:
        provider_reads.append(str(run["glasshive_run_id"]))
        return {
            "run_id": "run_synthetic_nightly",
            "worker_id": "wrk_synthetic_nightly",
            "project_id": "prj_synthetic_nightly",
            "state": "failed",
            "failure_class": "provider_response_failed",
            "ended_at": original_run["started_at"],
            "instruction": "DO-NOT-EXPOSE-synthetic-provider-body",
        }

    monkeypatch.setattr(scheduled_prompts, "_glasshive_run_snapshot", terminal_snapshot)

    result = scheduled_prompts.list_scheduled_prompts(user_id="synthetic-nightly-owner")

    [public] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    assert public["lastStatus"] == "error"
    assert public["latestScheduledRun"]["status"] == "failed"
    assert public["latestScheduledRun"]["errorClass"] == "provider_response_failed"
    assert public["latestScheduledRun"]["completedAt"] == original_run["started_at"]
    assert "DO-NOT-EXPOSE-synthetic-provider-body" not in json.dumps(public)
    assert provider_reads == ["run_synthetic_nightly"]

    [persisted] = store.list_scheduled_prompt_runs(definition_id=str(definition["id"]))
    assert persisted["run_id"] == original_run["run_id"]
    assert persisted["status"] == "failed"
    assert persisted["disposition"] == "failed"
    assert persisted["lease_until"] is None
    assert persisted["lease_owner"] is None
    parent = store.get_task("synthetic-nightly-owner", str(definition["task_id"]))
    assert parent["last_status"] == "error"
    assert parent["last_delivery_outcome"] == "failed"


def test_workbench_read_only_nightly_reports_confirmed_failure_without_database_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(tmp_path, monkeypatch)
    monkeypatch.setattr(
        scheduled_prompts,
        "_glasshive_run_snapshot",
        lambda _run: {
            "run_id": "run_synthetic_nightly",
            "worker_id": "wrk_synthetic_nightly",
            "project_id": "prj_synthetic_nightly",
            "state": "failed",
            "failure_class": "provider_response_failed",
            "ended_at": original_run["started_at"],
        },
    )

    result = scheduled_prompts.list_scheduled_prompts(
        user_id="synthetic-nightly-owner",
        read_only=True,
    )

    [public] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    assert public["lastStatus"] == "error"
    assert public["latestScheduledRun"]["status"] == "failed"
    assert public["latestScheduledRun"]["errorClass"] == "provider_response_failed"
    [persisted] = store.list_scheduled_prompt_runs(definition_id=str(definition["id"]))
    assert persisted["status"] == "running"
    assert persisted["lease_until"] == original_run["lease_until"]
    parent = store.get_task("synthetic-nightly-owner", str(definition["task_id"]))
    assert parent["last_status"] == "running"


@pytest.mark.parametrize("read_only", [False, True], ids=["durable", "read-only"])
def test_workbench_stale_nightly_never_falsely_fails_a_newer_parent_occurrence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read_only: bool,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(tmp_path, monkeypatch)
    newer_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    store.update_task(
        "synthetic-nightly-owner",
        str(definition["task_id"]),
        {
            "last_run_at": newer_started_at,
            "last_status": "running",
            "updated_at": newer_started_at,
        },
    )
    monkeypatch.setattr(
        scheduled_prompts,
        "_glasshive_run_snapshot",
        lambda _run: {
            "run_id": "run_synthetic_nightly",
            "worker_id": "wrk_synthetic_nightly",
            "project_id": "prj_synthetic_nightly",
            "state": "failed",
            "failure_class": "provider_response_failed",
            "ended_at": original_run["started_at"],
        },
    )

    result = scheduled_prompts.list_scheduled_prompts(
        user_id="synthetic-nightly-owner",
        read_only=read_only,
    )

    [public] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    assert public["latestScheduledRun"]["status"] == "failed"
    assert public["lastStatus"] == "running"
    parent = store.get_task("synthetic-nightly-owner", str(definition["task_id"]))
    assert parent["last_status"] == "running"
    assert parent["last_run_at"] == newer_started_at


@pytest.mark.parametrize(
    "snapshot",
    [
        pytest.param(
            {
                "run_id": "run_synthetic_nightly",
                "worker_id": "wrk_synthetic_nightly",
                "project_id": "prj_synthetic_nightly",
                "state": "running",
            },
            id="genuinely-running-worker",
        ),
        pytest.param(
            {
                "run_id": "run_synthetic_nightly",
                "worker_id": "wrk_other_owner",
                "project_id": "prj_synthetic_nightly",
                "state": "failed",
                "failure_class": "provider_response_failed",
            },
            id="foreign-worker-is-never-trusted",
        ),
        pytest.param(None, id="provider-temporarily-unavailable"),
    ],
)
def test_workbench_never_falsely_fails_active_or_unverified_nightly_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, object] | None,
) -> None:
    store, definition, _original_run = _create_orphaned_nightly_run(tmp_path, monkeypatch)
    monkeypatch.setattr(scheduled_prompts, "_glasshive_run_snapshot", lambda _run: snapshot)

    result = scheduled_prompts.list_scheduled_prompts(user_id="synthetic-nightly-owner")

    [public] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    assert public["latestScheduledRun"]["status"] == "running"
    [persisted] = store.list_scheduled_prompt_runs(definition_id=str(definition["id"]))
    assert persisted["status"] == "running"
    parent = store.get_task("synthetic-nightly-owner", str(definition["task_id"]))
    assert parent["last_status"] == "running"


def test_workbench_completed_worker_without_verified_callback_stays_recoverably_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(tmp_path, monkeypatch)
    monkeypatch.setattr(
        scheduled_prompts,
        "_glasshive_run_snapshot",
        lambda _run: {
            "run_id": "run_synthetic_nightly",
            "worker_id": "wrk_synthetic_nightly",
            "project_id": "prj_synthetic_nightly",
            "state": "completed",
            "ended_at": original_run["started_at"],
        },
    )

    result = scheduled_prompts.list_scheduled_prompts(user_id="synthetic-nightly-owner")

    [public] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    assert public["latestScheduledRun"]["status"] == "failed"
    assert public["latestScheduledRun"]["errorClass"] == "stale_run_reconciled"
    [persisted] = store.list_scheduled_prompt_runs(definition_id=str(definition["id"]))
    assert persisted["run_id"] == original_run["run_id"]
    assert persisted["status"] == "failed"
    assert persisted["error_class"] == "stale_run_reconciled"
    assert persisted["callback_payload_json"] is None


@pytest.mark.parametrize(
    ("worker_state", "provider_failure", "expected_failure"),
    [
        pytest.param(
            "failed",
            "provider_quota_exhausted",
            "provider_quota_exhausted",
            id="provider-quota",
        ),
        pytest.param(
            "completed",
            None,
            "stale_run_reconciled",
            id="missing-signed-callback",
        ),
        pytest.param(
            "failed",
            "worker_launch_failed",
            "worker_launch_failed",
            id="failed-worker-launch",
        ),
    ],
)
def test_health_context_correlation_failure_never_hides_successful_whoop_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_state: str,
    provider_failure: str | None,
    expected_failure: str,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(
        tmp_path,
        monkeypatch,
        template_id=scheduled_prompts.HEALTH_CONTEXT_TEMPLATE_ID,
    )
    monkeypatch.setattr(
        scheduled_prompts,
        "_glasshive_run_snapshot",
        lambda _run: {
            "run_id": "run_synthetic_nightly",
            "worker_id": "wrk_synthetic_nightly",
            "project_id": "prj_synthetic_nightly",
            "state": worker_state,
            "failure_class": provider_failure,
            "ended_at": original_run["started_at"],
        },
    )
    monkeypatch.setattr(
        scheduled_prompts.periphery_snapshots,
        "preview_snapshot",
        lambda _user_id, *, include_health: {
            "healthEvidence": {
                "status": "complete",
                "provider": "whoop",
                "acquisitionSchedule": "06:00",
            },
            "includeHealth": include_health,
        },
    )

    result = scheduled_prompts.list_scheduled_prompts(user_id="synthetic-nightly-owner")
    [correlation] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    acquisition = scheduled_prompts.periphery_snapshot_status(
        str(definition["id"]),
        user_id="synthetic-nightly-owner",
    )["snapshot"]

    assert correlation["templateId"] == scheduled_prompts.HEALTH_CONTEXT_TEMPLATE_ID
    assert correlation["schedule"]["time"] == "06:15"
    assert correlation["memoryWriteMode"] == "off"
    assert correlation["latestScheduledRun"]["status"] == "failed"
    assert correlation["latestScheduledRun"]["errorClass"] == expected_failure
    assert acquisition["includeHealth"] is True
    assert acquisition["healthEvidence"] == {
        "status": "complete",
        "provider": "whoop",
        "acquisitionSchedule": "06:00",
    }
    parent = store.get_task("synthetic-nightly-owner", str(definition["task_id"]))
    assert parent["last_status"] == "error"


def test_health_context_failed_launch_without_worker_preserves_acquisition_and_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, definition, original_run = _create_orphaned_nightly_run(
        tmp_path,
        monkeypatch,
        template_id=scheduled_prompts.HEALTH_CONTEXT_TEMPLATE_ID,
    )
    claimed = store.update_scheduled_prompt_run_if_current(
        str(original_run["run_id"]),
        {
            "status": "failed",
            "disposition": "failed",
            "error_class": "completion_error",
            "glasshive_run_id": None,
            "glasshive_worker_id": None,
            "glasshive_project_id": None,
            "completed_at": original_run["started_at"],
        },
        expected_status="running",
        expected_error_class=None,
    )
    assert claimed["updated"] is True
    store.update_task(
        "synthetic-nightly-owner",
        str(definition["task_id"]),
        {
            "last_status": "error",
            "last_delivery_outcome": "failed",
            "last_delivery_reason": "completion_error",
        },
    )

    def never_lookup_provider(_run: dict[str, object]) -> None:
        raise AssertionError("A failed launch has no authenticated GlassHive run to reconcile.")

    monkeypatch.setattr(scheduled_prompts, "_glasshive_run_snapshot", never_lookup_provider)
    monkeypatch.setattr(
        scheduled_prompts.periphery_snapshots,
        "preview_snapshot",
        lambda _user_id, *, include_health: {
            "healthEvidence": {"status": "complete", "provider": "whoop"},
            "includeHealth": include_health,
        },
    )

    result = scheduled_prompts.list_scheduled_prompts(
        user_id="synthetic-nightly-owner",
        read_only=True,
    )
    [correlation] = [
        row
        for row in result["scheduledPrompts"]
        if row.get("id") == definition["id"]
    ]
    acquisition = scheduled_prompts.periphery_snapshot_status(
        str(definition["id"]),
        user_id="synthetic-nightly-owner",
    )["snapshot"]

    assert correlation["schedule"]["time"] == "06:15"
    assert correlation["lastStatus"] == "error"
    assert correlation["latestScheduledRun"]["status"] == "failed"
    assert correlation["latestScheduledRun"]["errorClass"] == "completion_error"
    assert acquisition["healthEvidence"]["status"] == "complete"


def test_workbench_external_manual_run_lease_never_hides_failure_for_a_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renewals: list[dict[str, object]] = []

    class LeaseStore:
        @staticmethod
        def get_scheduled_prompt_run(_run_id: str) -> dict[str, object]:
            return {
                "status": "waiting_external",
                "lease_owner": "workbench:run-synthetic",
            }

        @staticmethod
        def renew_scheduled_prompt_run_lease(_run_id: str, **kwargs: object) -> bool:
            renewals.append(kwargs)
            return True

    monkeypatch.setattr(scheduled_prompts, "DEFAULT_OCCURRENCE_LEASE_SECONDS", 900)
    monkeypatch.setattr(scheduled_prompts, "scheduled_prompt_stale_seconds", lambda: 86_400)

    scheduled_prompts._extend_async_manual_run_lease(LeaseStore(), "run-synthetic")

    [renewal] = renewals
    assert renewal["lease_seconds"] == 900


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
            "channel": ["librechat", "telegram"],
            "conversationPolicy": "same",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["executor"] == "viventium_agent"
    assert body["executionProfile"] == "Viventium Main (Agent Builder)"
    assert body["executionMode"] == "inherits Agent Builder route and fallback at run time"
    assert body["executionModel"] is None
    assert body["reasoningEffort"] is None
    assert body["channel"] == ["librechat", "telegram"]
    assert body["conversationPolicy"] == "same"
    task = scheduled_prompts.storage().get_task(body["userId"], body["taskId"])
    assert task["executor"] == "viventium_agent"
    assert task["channel"] == ["librechat", "telegram"]
    assert task["conversation_policy"] == "same"

    calls = []

    def fake_dispatch(task_for_dispatch):
        calls.append(dict(task_for_dispatch))
        preclaimed = scheduled_prompts.storage().get_scheduled_prompt_run(
            task_for_dispatch["_scheduled_prompt_run_id"]
        )
        assert preclaimed["lease_until"] is not None
        assert preclaimed["lease_owner"].startswith("workbench:")
        return {
            "conversation_id": "conversation-1",
            "delivery": {
                "outcome": "sent",
                "reason": "manual_run",
                "generated_text": "private",
                "channels": {
                    "librechat": {"outcome": "sent", "reason": "canonical"},
                    "telegram": {"outcome": "failed", "reason": "channel_dispatch_failed"},
                },
            },
            "channel_errors": {
                "telegram": {
                    "outcome": "failed",
                    "reason": "channel_dispatch_failed",
                    "error_class": "TimeoutError",
                }
            },
            "execution": {
                "provider": "openai",
                "model": "gpt-test-scheduled",
                "reasoning_effort": "xhigh",
            },
        }

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_dispatch)
    manual = client.post(f"/api/scheduled-prompts/{body['id']}/manual-runs")
    assert manual.status_code == 200
    assert manual.json()["run"]["executor"] == "viventium_agent"
    assert manual.json()["run"]["status"] == "completed"
    assert manual.json()["run"]["triggerKind"] == "manual"
    assert manual.json()["run"]["resultSummary"] == "sent: manual_run"
    assert manual.json()["run"]["disposition"] == "partial"
    assert manual.json()["run"]["effectiveModel"] == "gpt-test-scheduled"
    assert manual.json()["run"]["effectiveReasoningEffort"] == "xhigh"
    assert manual.json()["run"]["interactionRef"] == "conversation:conversation-1"
    assert calls[0]["_scheduled_prompt_run_id"] == manual.json()["run"]["runId"]
    assert calls[0]["_scheduled_prompt_occurrence_key"] == manual.json()["run"]["runId"]
    assert calls[0]["_scheduled_prompt_trigger_kind"] == "manual"
    assert calls[0]["_scheduled_prompt_trigger_source"] == "workbench_manual"
    assert manual.json()["run"]["channelOutcomes"] == {
        "librechat": {"outcome": "sent", "reason": "canonical"},
        "telegram": {"outcome": "failed", "reason": "channel_dispatch_failed"},
    }
    completed = scheduled_prompts.storage().get_scheduled_prompt_run(manual.json()["run"]["runId"])
    assert completed["lease_owner"] is None
    assert completed["lease_until"] is None
    persisted_task = scheduled_prompts.storage().get_task(body["userId"], body["taskId"])
    assert persisted_task["last_conversation_id"] == "conversation-1"
    assert persisted_task["conversation_id"] == "conversation-1"
    duplicate = client.post(f"/api/scheduled-prompts/{body['id']}/manual-runs")
    assert duplicate.status_code == 200
    assert duplicate.json()["coalesced"] is True
    assert duplicate.json()["run"]["executor"] == "viventium_agent"
    assert [call["id"] for call in calls] == [body["taskId"]]


def test_workbench_viventium_manual_run_failure_records_failed_disposition(
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
            "title": "Failing Viventium route prompt",
            "promptText": "Exercise the terminal audit path",
            "schedule": {"type": "daily", "time": "03:00", "timezone": "UTC"},
            "active": False,
            "memoryWriteMode": "off",
            "executor": "viventium_agent",
            "channel": ["librechat", "telegram"],
            "conversationPolicy": "same",
        },
    )
    assert created.status_code == 200
    definition = scheduled_prompts.storage().get_scheduled_prompt_definition(created.json()["id"])
    task = scheduled_prompts.storage().get_task(definition["user_id"], definition["task_id"])

    def failing_dispatch(_task):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", failing_dispatch)
    with pytest.raises(TimeoutError, match="synthetic timeout"):
        scheduled_prompts._manual_run_workbench_viventium_agent(
            scheduled_prompts.storage(), definition, task
        )

    [run] = scheduled_prompts.storage().list_scheduled_prompt_runs(
        definition_id=created.json()["id"], limit=1
    )
    assert run["status"] == "failed"
    assert run["disposition"] == "failed"


def test_user_level_viventium_manual_run_failure_records_failed_disposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    store = scheduled_prompts.storage()
    now = "2026-08-20T12:00:00Z"
    store.create_task(
        {
            "id": "task-user-manual-failure",
            "user_id": "user-a",
            "agent_id": "agent-main",
            "prompt": "Synthetic scheduled Main failure",
            "schedule": {"type": "daily", "time": "12:00", "timezone": "UTC"},
            "channel": "librechat",
            "executor": "viventium_agent",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:agent-main",
            "created_source": "user",
            "created_at": now,
            "updated_at": now,
            "updated_by": "agent:agent-main",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-08-21T12:00:00Z",
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

    monkeypatch.setattr(
        scheduled_prompts,
        "dispatch_task",
        lambda _task: (_ for _ in ()).throw(TimeoutError("synthetic timeout")),
    )

    with pytest.raises(TimeoutError, match="synthetic timeout"):
        scheduled_prompts.manual_run(
            "user_schedule:task-user-manual-failure",
            user_id="user-a",
            confirm_user_level_delivery=True,
        )

    [run] = store.list_scheduled_prompt_runs(
        task_id="task-user-manual-failure",
        trigger_kind="manual",
        trigger_source="workbench_manual",
        limit=1,
    )
    assert run["status"] == "failed"
    assert run["disposition"] == "failed"
    assert run["error_class"] == "TimeoutError"


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


def test_periphery_collection_hardens_worker_created_artifact_permissions(tmp_path: Path) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True)
    sidecar = artifact_dir / "20260810T160238Z.health_context.json"
    markdown = sidecar.with_suffix(".md")
    markdown.write_text("Synthetic private health context", encoding="utf-8")
    sidecar.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "health_context",
                "generatedAt": "2026-08-10T16:02:38Z",
                "scheduledRunRef": {"runId": "synthetic"},
                "sourceRefs": [],
                "confidence": "medium",
                "severity": "low",
                "timeSensitivity": "same_day",
                "ttl": "P1D",
                "staleAfter": "2099-08-11T16:02:38Z",
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
    for directory in (root, root / "health_context", root / "health_context" / "2026", artifact_dir):
        directory.chmod(0o755)
    sidecar.chmod(0o644)
    markdown.chmod(0o644)

    _, artifacts, invalid, _ = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert len(artifacts) == 1
    assert invalid == []
    assert sidecar.stat().st_mode & 0o777 == 0o600
    assert markdown.stat().st_mode & 0o777 == 0o600
    assert all(
        directory.stat().st_mode & 0o777 == 0o700
        for directory in (root, root / "health_context", root / "health_context" / "2026", artifact_dir)
    )


def test_periphery_collection_rejects_symlinked_worker_artifacts(tmp_path: Path) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True)
    external_sidecar = tmp_path / "external-health-context.json"
    external_sidecar.write_text("{}", encoding="utf-8")
    external_sidecar.chmod(0o644)
    sidecar = artifact_dir / "20260810T160238Z.health_context.json"
    sidecar.symlink_to(external_sidecar)

    _, artifacts, invalid, _ = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert artifacts == []
    assert len(invalid) == 1
    assert invalid[0]["reason"] == "unsafe_symlink"
    assert external_sidecar.stat().st_mode & 0o777 == 0o644


def test_periphery_read_reuses_ingestion_guard_for_symlinked_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    my_folder = Path(scheduled_prompts._glasshive_my_folder("user-a"))
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sidecar = artifact_dir / "20260810T160238Z.health_context.json"
    sidecar.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "health_context",
                "generatedAt": "2026-08-10T16:02:38Z",
                "scheduledRunRef": {"runId": "synthetic"},
                "sourceRefs": [],
                "confidence": "medium",
                "severity": "low",
                "timeSensitivity": "same_day",
                "ttl": "P1D",
                "staleAfter": "2099-08-11T16:02:38Z",
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
    external_markdown = tmp_path / "outside-private-content.md"
    external_markdown.write_text("must stay outside Periphery", encoding="utf-8")
    sidecar.with_suffix(".md").symlink_to(external_markdown)
    artifact_id = scheduled_prompts._periphery_artifact_id(sidecar, root)

    with pytest.raises(ValueError, match="unsafe_symlink"):
        scheduled_prompts.read_user_periphery_artifact(
            user_id="user-a",
            artifact_id=artifact_id,
        )


def test_periphery_collection_rejects_hard_linked_artifacts(tmp_path: Path) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True)
    external_sidecar = tmp_path / "external-health-context.json"
    external_sidecar.write_text("{}", encoding="utf-8")
    external_sidecar.chmod(0o644)
    sidecar = artifact_dir / "20260810T160238Z.health_context.json"
    os.link(external_sidecar, sidecar)

    _, artifacts, invalid, _ = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert artifacts == []
    assert len(invalid) == 1
    assert invalid[0]["reason"] == "unsafe_hard_link"
    assert external_sidecar.stat().st_mode & 0o777 == 0o644


def test_periphery_index_write_does_not_follow_preplanted_temp_symlink(tmp_path: Path) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    root.mkdir(parents=True)
    external_file = tmp_path / "outside-index-target.json"
    external_file.write_text("outside stays unchanged", encoding="utf-8")
    external_mode = external_file.stat().st_mode & 0o777
    (root / "._index.json.tmp").symlink_to(external_file)

    scheduled_prompts._collect_periphery(str(my_folder), user_id="user-a")

    assert external_file.read_text(encoding="utf-8") == "outside stays unchanged"
    assert external_file.stat().st_mode & 0o777 == external_mode
    assert not (root / "_index.json").is_symlink()
    assert (root / "_index.json").stat().st_mode & 0o777 == 0o600
    assert root.stat().st_mode & 0o777 == 0o700


def test_periphery_collection_rejects_a_symlinked_root_without_writing_through_it(
    tmp_path: Path,
) -> None:
    my_folder = tmp_path / "my-folder"
    my_folder.mkdir()
    external_root = tmp_path / "outside-periphery"
    external_root.mkdir()
    root = my_folder / "periphery"
    root.symlink_to(external_root, target_is_directory=True)

    _, artifacts, invalid, index = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert artifacts == []
    assert invalid[0]["reason"] == "unsafe_symlink"
    assert index["status"] == "blocked"
    assert index["blockedReasons"] == ["unsafe_symlink"]
    assert not (external_root / "_index.json").exists()


def test_periphery_discovery_does_not_enumerate_a_symlinked_module_directory(
    tmp_path: Path,
) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    root.mkdir(parents=True)
    external_module = tmp_path / "outside-module"
    external_artifact_dir = external_module / "2026" / "08"
    external_artifact_dir.mkdir(parents=True)
    external_sidecar = external_artifact_dir / "private-name.health_context.json"
    external_sidecar.write_text("{}", encoding="utf-8")
    external_mode = external_sidecar.stat().st_mode & 0o777
    (root / "health_context").symlink_to(external_module, target_is_directory=True)

    _, artifacts, invalid, index = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert artifacts == []
    assert len(invalid) == 1
    assert invalid[0]["reason"] == "unsafe_symlink"
    assert "private-name" not in json.dumps(invalid)
    assert index["status"] == "blocked"
    assert external_sidecar.stat().st_mode & 0o777 == external_mode


def test_glasshive_folder_precreates_owner_only_periphery_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))

    my_folder = Path(scheduled_prompts._glasshive_my_folder("user-a"))

    assert (my_folder / "periphery").is_dir()
    assert all(
        directory.stat().st_mode & 0o777 == 0o700
        for directory in (my_folder.parent, my_folder, my_folder / "periphery")
    )


def test_glasshive_folder_enforces_permissions_only_at_the_private_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    my_folder = Path(scheduled_prompts._glasshive_my_folder("user-a"))

    def deny_private_permission_change(descriptor: int, mode: int) -> None:
        raise PermissionError("synthetic unsupported private permissions")

    monkeypatch.setattr(scheduled_prompts.os, "fchmod", deny_private_permission_change)

    assert Path(scheduled_prompts._glasshive_my_folder("user-a")) == my_folder
    with pytest.raises(RuntimeError, match="private_continuity_permissions_unavailable"):
        scheduled_prompts._glasshive_my_folder("user-a", require_private=True)


def test_periphery_index_reports_partial_privacy_rejection_as_degraded() -> None:
    index = scheduled_prompts._periphery_index_payload(
        [{"moduleId": "health_context", "qualityStatus": "passed"}],
        [
            {"reason": "unsafe_hard_link"},
            {"reason": "invalid_json"},
        ],
    )

    assert index["status"] == "degraded"
    assert index["blockedArtifactCount"] == 1
    assert index["blockedReasons"] == ["unsafe_hard_link"]


def test_periphery_collection_hardens_artifacts_beyond_index_limit(tmp_path: Path) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True)
    sidecars: list[Path] = []
    for index in range(scheduled_prompts.PERIPHERY_ARTIFACT_LIMIT + 3):
        sidecar = artifact_dir / f"20260810T16{index:04d}Z.health_context.json"
        sidecar.write_text("{}", encoding="utf-8")
        sidecar.chmod(0o644)
        sidecars.append(sidecar)

    scheduled_prompts._collect_periphery(str(my_folder), user_id="user-a")

    assert all(sidecar.stat().st_mode & 0o777 == 0o600 for sidecar in sidecars)


def test_periphery_collection_fails_closed_when_private_permissions_cannot_be_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    my_folder = tmp_path / "my-folder"
    root = my_folder / "periphery"
    artifact_dir = root / "health_context" / "2026" / "08"
    artifact_dir.mkdir(parents=True)
    sidecar = artifact_dir / "20260810T160238Z.health_context.json"
    sidecar.write_text("{}", encoding="utf-8")
    sidecar.chmod(0o644)
    original_fchmod = os.fchmod
    failed_once = False

    def fail_for_first_private_file(descriptor: int, mode: int) -> None:
        nonlocal failed_once
        if mode == 0o600 and not failed_once:
            failed_once = True
            raise PermissionError("synthetic private-permission failure")
        original_fchmod(descriptor, mode)

    monkeypatch.setattr(scheduled_prompts.os, "fchmod", fail_for_first_private_file)

    _, artifacts, invalid, index = scheduled_prompts._collect_periphery(
        str(my_folder),
        user_id="user-a",
    )

    assert artifacts == []
    assert len(invalid) == 1
    assert invalid[0]["reason"] == "private_permissions_unavailable"
    assert index["status"] == "blocked"
    assert index["blockedReasons"] == ["private_permissions_unavailable"]
    assert sidecar.stat().st_mode & 0o777 == 0o644
    assert root.stat().st_mode & 0o777 == 0o700


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
            "channel": ["librechat", "telegram"],
            "conversationPolicy": "same",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed user schedule"
    assert patched.json()["active"] is True
    task = scheduled_prompts.storage().get_task("user-a", "task-user-level")
    assert task["active"] == 1
    assert task["schedule"]["time"] == "06:15"
    assert task["channel"] == ["librechat", "telegram"]
    assert task["conversation_policy"] == "same"
    assert task["metadata"]["workbench_title"] == "Renamed user schedule"

    dispatched_tasks = []

    def fake_user_schedule_dispatch(task_for_dispatch):
        dispatched_tasks.append(dict(task_for_dispatch))
        return {
            "delivery": {
                "outcome": "sent",
                "reason": "manual_run",
                "generated_text": "private result",
            }
        }

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_user_schedule_dispatch)
    manual_without_confirmation = client.post(f"/api/scheduled-prompts/{user_schedule['id']}/manual-runs")
    assert manual_without_confirmation.status_code == 400
    assert "explicit delivery confirmation" in manual_without_confirmation.json()["detail"]

    manual = client.post(
        f"/api/scheduled-prompts/{user_schedule['id']}/manual-runs",
        json={"confirmUserLevelDelivery": True},
    )
    assert manual.status_code == 200
    assert manual.json()["run"]["status"] == "completed"
    assert manual.json()["run"]["triggerKind"] == "manual"
    assert manual.json()["run"]["triggerSource"] == "workbench_manual"
    assert manual.json()["run"]["disposition"] == "delivered"
    assert manual.json()["run"]["resultSummary"] == "sent: manual_run"
    assert dispatched_tasks[0]["_scheduled_prompt_run_id"] == manual.json()["run"]["runId"]
    assert dispatched_tasks[0]["_scheduled_prompt_occurrence_key"] == manual.json()["run"]["runId"]
    assert dispatched_tasks[0]["_scheduled_prompt_trigger_kind"] == "manual"
    assert dispatched_tasks[0]["_scheduled_prompt_trigger_source"] == "workbench_manual"
    [persisted_manual_run] = scheduled_prompts.storage().list_scheduled_prompt_runs(
        task_id="task-user-level",
        trigger_kind="manual",
        trigger_source="workbench_manual",
        limit=1,
    )
    assert persisted_manual_run["status"] == "completed"
    assert persisted_manual_run["disposition"] == "delivered"
    runs = client.get(f"/api/scheduled-prompts/{user_schedule['id']}/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["status"] == "completed"
    assert runs.json()["runs"][0]["triggerKind"] == "manual"

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
    failed_task = scheduled_prompts.storage().get_task("user-a", "task-user-level")
    failed_run = scheduled_prompts._public_task_run(failed_task)
    assert failed_run["status"] == "failed"
    assert "/Users/" not in failed_run["errorClass"]
    assert "mongodb://" not in failed_run["errorClass"]
    assert synthetic_private_ip() not in failed_run["errorClass"]

    deleted = client.delete(f"/api/scheduled-prompts/{user_schedule['id']}")
    assert deleted.status_code == 200
    assert scheduled_prompts.storage().get_task("user-a", "task-user-level") is None


def test_user_level_run_now_ignores_stale_task_running_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT", str(tmp_path / "glasshive"))
    now = "2020-01-01T00:00:00Z"
    store = scheduled_prompts.storage()
    store.create_task(
        {
            "id": "task-stale-running",
            "user_id": "user-a",
            "agent_id": "agent-1",
            "prompt": "Synthetic continuity check",
            "schedule": {"type": "daily", "time": "06:15", "timezone": "UTC"},
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
            "last_run_at": now,
            "next_run_at": "2026-08-21T10:15:00Z",
            "last_status": "running",
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": None,
        }
    )
    dispatched = []

    def fake_dispatch(task):
        dispatched.append(task)
        return {
            "delivery": {
                "outcome": "suppressed",
                "reason": "nta",
                "generated_text": None,
            }
        }

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_dispatch)

    result = scheduled_prompts._manual_run_locked(
        "user_schedule:task-stale-running",
        user_id="user-a",
        confirm_user_level_delivery=True,
    )

    assert result.get("coalesced") is not True
    assert len(dispatched) == 1
    assert result["run"]["status"] == "completed"


def test_manual_run_coalescing_names_the_actual_scheduled_owner() -> None:
    response = scheduled_prompts._coalesced_manual_run_response(
        {
            "run_id": "scheduled-run",
            "status": "running",
            "trigger_kind": "scheduled",
        }
    )

    assert response["dispatch"]["delivery"]["reason"] == (
        "scheduled_occurrence_already_inflight"
    )


def test_user_level_manual_run_preserves_declared_executor_and_one_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    store = scheduled_prompts.storage()
    now = "2026-08-20T12:00:00Z"
    store.create_task(
        {
            "id": "task-user-worker",
            "user_id": "user-a",
            "agent_id": "agent-main",
            "prompt": "Synthetic isolated work",
            "schedule": {"type": "daily", "time": "12:00", "timezone": "UTC"},
            "channel": "workbench",
            "executor": "glasshive_host",
            "conversation_policy": "new",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:agent-main",
            "created_source": "user",
            "created_at": now,
            "updated_at": now,
            "updated_by": "agent:agent-main",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-08-21T12:00:00Z",
            "last_status": None,
            "last_error": None,
            "last_delivery_outcome": None,
            "last_delivery_reason": None,
            "last_delivery_at": None,
            "last_generated_text": None,
            "last_delivery": None,
            "metadata": {"workbench_scheduled_prompt": {"executor": "glasshive_host"}},
        }
    )
    dispatched = []

    def fake_dispatch(task_for_dispatch):
        dispatched.append(dict(task_for_dispatch))
        preclaimed = store.get_scheduled_prompt_run(task_for_dispatch["_scheduled_prompt_run_id"])
        assert preclaimed["lease_until"] is not None
        assert preclaimed["lease_owner"].startswith("workbench:")
        return {
            "delivery": {"outcome": "queued", "reason": "worker_queued"},
            "execution": {"executor": "glasshive_host"},
        }

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_dispatch)

    result = scheduled_prompts.manual_run(
        "user_schedule:task-user-worker",
        user_id="user-a",
        confirm_user_level_delivery=True,
    )

    assert result["run"]["executor"] == "glasshive_host"
    assert result["run"]["status"] == "queued"
    assert result["run"]["triggerKind"] == "manual"
    assert dispatched[0]["executor"] == "glasshive_host"
    assert dispatched[0]["_scheduled_prompt_run_id"] == result["run"]["runId"]
    assert dispatched[0]["_scheduled_prompt_occurrence_key"] == result["run"]["runId"]
    runs = store.list_scheduled_prompt_runs(task_id="task-user-worker")
    assert len(runs) == 1
    assert runs[0]["executor"] == "glasshive_host"


def test_user_level_manual_run_renews_lease_during_long_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULING_DB_PATH", str(tmp_path / "schedules.db"))
    monkeypatch.setattr(scheduled_prompts, "DEFAULT_OCCURRENCE_LEASE_SECONDS", 1)
    store = scheduled_prompts.storage()
    now = "2026-08-20T12:00:00Z"
    store.create_task(
        {
            "id": "task-long-manual",
            "user_id": "user-a",
            "agent_id": "agent-main",
            "prompt": "Synthetic long Main run",
            "schedule": {"type": "daily", "time": "12:00", "timezone": "UTC"},
            "channel": "telegram",
            "executor": "viventium_agent",
            "conversation_policy": "same",
            "conversation_id": None,
            "last_conversation_id": None,
            "active": 1,
            "created_by": "agent:agent-main",
            "created_source": "user",
            "created_at": now,
            "updated_at": now,
            "updated_by": "agent:agent-main",
            "updated_source": "user",
            "last_run_at": None,
            "next_run_at": "2026-08-21T12:00:00Z",
            "last_status": None,
            "last_error": None,
            "metadata": {},
        }
    )
    overlapping_claims: list[dict[str, Any]] = []

    def fake_dispatch(_task_for_dispatch: dict[str, Any]) -> dict[str, Any]:
        time.sleep(1.3)
        claim_now = scheduled_prompts._utc_now()
        overlapping_claims.append(
            store.claim_scheduled_prompt_occurrence(
                task_id="task-long-manual",
                user_id="user-a",
                executor="viventium_agent",
                due_at=claim_now,
                lease_owner="scheduler:test",
                now=claim_now,
                lease_seconds=1,
            )
        )
        return {"delivery": {"outcome": "sent", "reason": "manual_run"}}

    monkeypatch.setattr(scheduled_prompts, "dispatch_task", fake_dispatch)

    result = scheduled_prompts.manual_run(
        "user_schedule:task-long-manual",
        user_id="user-a",
        confirm_user_level_delivery=True,
    )

    assert result["run"]["status"] == "completed"
    assert overlapping_claims[0]["claimed"] is False
    assert overlapping_claims[0]["reason"] == "task_has_active_occurrence"


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
    monkeypatch.setenv("GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE", "codex-cli")
    monkeypatch.setenv("WPR_MODEL_CLAUDE_CODE", "claude-primary-test")
    monkeypatch.setenv("WPR_CLAUDE_CODE_EFFORT", "max")
    monkeypatch.setenv("WPR_MODEL_HOST_CODEX_CLI", "gpt-fallback-test")
    monkeypatch.setenv("WPR_CODEX_CLI_REASONING_EFFORT", "xhigh")
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
    assert task["metadata"]["workbench_scheduled_prompt"]["execution_model"] == "claude-primary-test"
    assert task["metadata"]["workbench_scheduled_prompt"]["reasoning_effort"] == "max"
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_worker_profile"]
        == "codex-cli"
    )
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_worker_model"]
        == "gpt-fallback-test"
    )
    assert (
        task["metadata"]["workbench_scheduled_prompt"]["fallback_reasoning_effort"]
        == "xhigh"
    )
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


def write_verified_synthetic_exact_model_artifact(
    command: list[str],
    *,
    case_ids: list[str],
    provider: str = "synthetic-provider",
    model: str = "synthetic-model",
    agent_id: str = "synthetic-main-agent",
) -> None:
    output_directory = Path(
        next(value.removeprefix("--output-dir=") for value in command if value.startswith("--output-dir="))
    )
    agent_hash = evals._sha(agent_id)
    judge_hash = evals._sha("synthetic-judge-model")
    payload = {
        "summary": {"agentIdHash": agent_hash, "judgeModelHash": judge_hash, "resultCount": len(case_ids)},
        "args": {"agentIdHash": agent_hash, "judgeModelHash": judge_hash},
        "liveResults": [
            {
                "caseId": case_id,
                "status": "completed",
                "requestIdentityHash": evals._sha(f"synthetic-request:{case_id}"),
                "observedRequestIdentityHash": evals._sha(f"synthetic-request:{case_id}"),
                "semanticJudge": {
                    "status": "judged",
                    "pass": True,
                    "attemptCount": 1,
                    "rawHash": evals._sha(f"synthetic-judge-response:{case_id}"),
                },
                "promptFrameEvidenceForJudge": {
                    "prompt_frames": [
                        {
                            "source": "runtime_route_log",
                            "prompt_family": "main_runtime",
                            "requested_provider_hash": evals._sha(provider),
                            "requested_model_hash": evals._sha(model),
                            "requested_effort": "medium",
                            "provider_hash": evals._sha(provider),
                            "model_hash": evals._sha(model),
                            "effective_effort": "medium",
                            "fallback_used": False,
                            "fallback_reason": "none",
                            "agent_id_hash": agent_hash,
                            "request_identity_hash": evals._sha(
                                f"synthetic-request:{case_id}"
                            ),
                        }
                    ]
                },
            }
            for case_id in case_ids
        ],
    }
    (output_directory / "exact-model-eval.json").write_text(json.dumps(payload), encoding="utf-8")


def write_verified_synthetic_native_surface_artifact(
    command: list[str],
    *,
    case_ids: list[str],
    surface: str = "telegram",
    completion_surface: str | None = None,
    completion_expected: bool = True,
    provider: str = "synthetic-provider",
    model: str = "synthetic-model",
    agent_id: str = "synthetic-main-agent",
) -> None:
    output_directory = Path(
        next(value.removeprefix("--output-dir=") for value in command if value.startswith("--output-dir="))
    )
    agent_hash = evals._sha(agent_id)
    observed_completion_surface = completion_surface or {
        "scheduler": "workbench",
        "wing": "voice",
        "listen_only": "voice",
    }.get(surface, surface)
    cases = []
    for case_id in case_ids:
        request_hash = evals._sha(f"synthetic-request:{case_id}")
        completion_frames = (
            [
                {
                    "event": "viventium.prompt_frame",
                    "prompt_family": "main_run_create",
                    "surface": observed_completion_surface,
                    "provider": provider,
                    "model": model,
                    "requested_provider": provider,
                    "requested_model": model,
                    "requested_effort": "medium",
                    "effective_provider": provider,
                    "effective_model": model,
                    "effective_effort": "medium",
                    "fallback_used": False,
                    "fallback_reason": "none",
                    "agent_id_hash": agent_hash,
                    "request_identity_hash": request_hash,
                }
            ]
            if completion_expected
            else []
        )
        cases.append(
            {
                "caseId": case_id,
                "surface": surface,
                "requestedSurface": surface,
                "requestedCompletionSurface": observed_completion_surface,
                "observedCompletionSurface": (
                    observed_completion_surface if completion_expected else "none"
                ),
                "completionExpected": completion_expected,
                "completionSurfaceVerified": True,
                "completionFrameCount": len(completion_frames),
                "requestIdentityHash": request_hash,
                "actualCompletionAgentIdHash": (
                    agent_hash if completion_expected else "not_applicable"
                ),
                "completionProviderHashes": (
                    [evals._sha(provider)] if completion_expected else []
                ),
                "completionModelHashes": (
                    [evals._sha(model)] if completion_expected else []
                ),
                "requestedProviderHashes": (
                    [evals._sha(provider)] if completion_expected else []
                ),
                "requestedModelHashes": (
                    [evals._sha(model)] if completion_expected else []
                ),
                "requestedEfforts": ["medium"] if completion_expected else [],
                "effectiveEfforts": ["medium"] if completion_expected else [],
                "fallbackUsed": False,
                "fallbackReasons": ["none"] if completion_expected else [],
                "status": "completed",
                "semanticJudged": True,
                "semanticPass": True,
                "judge": {"verdict": "pass", "responseHash": evals._sha(f"judge:{case_id}")},
                "private": {"completionFrames": completion_frames},
            }
        )
    payload = {
        "args": {
            "agentIdHash": agent_hash,
            "surface": surface,
            "semanticRequired": True,
        },
        "selection": {
            "requestedSurface": surface,
            "selectedCaseIds": case_ids,
            "selectedCaseCount": len(case_ids),
        },
        "browserProbe": {"ok": True},
        "cleanup": {"ok": True, "status": "complete"},
        "cases": cases,
        "summary": {
            "status": "completed_with_semantic_native_surface_evidence",
            "browserOk": True,
            "cleanupOk": True,
            "selectedCoverageOk": True,
            "completionEvidenceOk": True,
            "semanticRequired": True,
            "selectedCaseCount": len(case_ids),
            "resultCount": len(case_ids),
            "completedCount": len(case_ids),
            "failedCount": 0,
            "semanticJudgedCount": len(case_ids),
            "semanticPassedCount": len(case_ids),
            "semanticFailedCount": 0,
            "routes": ["telegram_gateway"],
            "surfaces": [surface],
            "frameSurfaces": [observed_completion_surface] if completion_expected else [],
        },
    }
    (output_directory / "native-surface-playwright-qa.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_exact_model_execution_route_rejects_unrelated_request_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "exact"
    output_dir.mkdir()
    command = [f"--output-dir={output_dir}"]
    write_verified_synthetic_exact_model_artifact(command, case_ids=["case_one"])
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )

    def evaluate() -> dict[str, object]:
        return evals._exact_model_execution_route(
            output_dir,
            execution_target={"agentId": "synthetic-main-agent"},
            selected_case_ids=["case_one"],
            semantic_judge_required=True,
        )

    assert evaluate()["status"] == "verified"
    artifact_path = output_dir / "exact-model-eval.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    unrelated = dict(payload["liveResults"][0]["promptFrameEvidenceForJudge"]["prompt_frames"][0])
    unrelated["request_identity_hash"] = evals._sha("unrelated-request")
    payload["liveResults"][0]["promptFrameEvidenceForJudge"]["prompt_frames"] = [unrelated]
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    assert evaluate()["reason"] == "execution_request_identity_mismatch"


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
                            {"id": "case_one", "surface": "web"},
                            {"id": "case_two", "surface": "web"},
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
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append((cmd, int(kwargs["timeout"]), kwargs.get("env")))
        write_verified_synthetic_exact_model_artifact(cmd, case_ids=["case_two", "case_one"])
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


def test_non_web_eval_cases_use_the_trusted_native_surface_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exact_runner = tmp_path / "run-exact-model-evals.cjs"
    native_runner = tmp_path / "run-native-surface-playwright-qa.cjs"
    exact_runner.write_text("// exact\n", encoding="utf-8")
    native_runner.write_text("// native\n", encoding="utf-8")
    bank = {
        "families": [
            {
                "id": "telegram_smart_delivery",
                "cases": [
                    {
                        "id": "telegram_copy_ready_email_skips_optional_audio",
                        "surface": "telegram",
                    }
                ],
            }
        ]
    }
    selected = [
        {
            "family": bank["families"][0],
            "case": bank["families"][0]["cases"][0],
        }
    ]

    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", exact_runner)
    monkeypatch.setattr(evals, "NATIVE_SURFACE_EVAL_SCRIPT", native_runner)

    assert (
        evals._eval_runner(
            bank=bank,
            family="telegram_smart_delivery",
            prompt_id=None,
            selected=selected,
        )
        == native_runner
    )


@pytest.mark.parametrize("surface", ["telegram", "voice", "wing", "listen_only", "scheduler"])
def test_every_trusted_non_web_surface_uses_the_native_surface_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    exact_runner = tmp_path / "run-exact-model-evals.cjs"
    native_runner = tmp_path / "run-native-surface-playwright-qa.cjs"
    exact_runner.write_text("// exact\n", encoding="utf-8")
    native_runner.write_text("// native\n", encoding="utf-8")
    family = {"id": f"{surface}_family", "cases": [{"id": f"{surface}_case", "surface": surface}]}
    monkeypatch.setattr(evals, "EXACT_MODEL_EVAL_SCRIPT", exact_runner)
    monkeypatch.setattr(evals, "NATIVE_SURFACE_EVAL_SCRIPT", native_runner)

    assert (
        evals._eval_runner(
            bank={"families": [family]},
            family=family["id"],
            prompt_id=None,
            selected=[{"family": family, "case": family["cases"][0]}],
        )
        == native_runner
    )


@pytest.mark.parametrize(
    ("surface", "completion_surface", "completion_expected"),
    [
        ("voice", "voice", True),
        ("wing", "voice", True),
        ("scheduler", "workbench", True),
        ("listen_only", "voice", False),
    ],
)
def test_native_surface_route_verifies_trusted_completion_surface_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    completion_surface: str,
    completion_expected: bool,
) -> None:
    output_dir = tmp_path / surface
    output_dir.mkdir()
    command = [f"--output-dir={output_dir}"]
    write_verified_synthetic_native_surface_artifact(
        command,
        case_ids=[f"{surface}_case"],
        surface=surface,
        completion_surface=completion_surface,
        completion_expected=completion_expected,
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_agent_hash",
        lambda _target: evals._sha("synthetic-main-agent"),
    )

    result = evals._native_surface_execution_route(
        output_dir,
        execution_target=None,
        selected_case_ids=[f"{surface}_case"],
        requested_surface=surface,
        semantic_judge_required=True,
    )

    assert result["status"] == "verified"
    assert result["caseEvidence"][0]["surface"] == surface
    assert result["caseEvidence"][0]["completionSurface"] == completion_surface
    assert result["caseEvidence"][0]["completionExpected"] is completion_expected


def test_live_native_surface_eval_requires_request_bound_canonical_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bank = {
        "families": [
            {
                "id": "telegram_smart_delivery",
                "semanticJudge": True,
                "promptRefs": ["surface.telegram_text"],
                "cases": [
                    {"id": "telegram_case", "surface": "telegram", "rubric": ["use text"]}
                ],
            }
        ]
    }
    prompt_bank = tmp_path / "prompt-bank.json"
    prompt_bank.write_text(json.dumps(bank), encoding="utf-8")
    native_runner = tmp_path / "run-native-surface-playwright-qa.cjs"
    native_runner.write_text("// synthetic native runner\n", encoding="utf-8")
    private_root = tmp_path / "private"
    captured: list[list[str]] = []

    monkeypatch.setattr(drafts, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(drafts, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "PROMPT_BANK_PATH", prompt_bank)
    monkeypatch.setattr(evals, "NATIVE_SURFACE_EVAL_SCRIPT", native_runner)
    monkeypatch.setattr(evals, "workbench_private_root", lambda: private_root)
    monkeypatch.setattr(evals, "load_eval_bank", lambda: bank)
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_agent_hash",
        lambda _target: evals._sha("synthetic-main-agent"),
        raising=False,
    )

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        write_verified_synthetic_native_surface_artifact(cmd, case_ids=["telegram_case"])
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(evals.subprocess, "run", fake_run)

    result = evals.run_exact_model_eval(
        max_cases=1,
        live=True,
        family="telegram_smart_delivery",
        surface="telegram",
        case_ids=["telegram_case"],
    )

    assert result["returnCode"] == 0
    assert result["executionRoute"]["status"] == "verified"
    assert result["executionRoute"]["completedCaseCount"] == 1
    assert result["executionRoute"]["caseEvidence"] == [
        {
            "caseId": "telegram_case",
            "agentIdHash": evals._sha("synthetic-main-agent"),
                "requestIdentityHash": evals._sha("synthetic-request:telegram_case"),
                "surface": "telegram",
                "completionSurface": "telegram",
                "completionExpected": True,
                "semanticJudged": True,
            "semanticPassed": True,
        }
    ]
    assert captured and "--case-ids=telegram_case" in captured[0]


def test_native_surface_execution_route_rejects_unrelated_frames_and_false_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "native"
    output_dir.mkdir()
    command = [f"--output-dir={output_dir}"]
    write_verified_synthetic_native_surface_artifact(command, case_ids=["telegram_case"])
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )
    monkeypatch.setattr(
        evals,
        "_configured_execution_agent_hash",
        lambda _target: evals._sha("synthetic-main-agent"),
    )

    def evaluate() -> dict[str, object]:
        return evals._native_surface_execution_route(
            output_dir,
            execution_target=None,
            selected_case_ids=["telegram_case"],
            requested_surface="telegram",
            semantic_judge_required=True,
        )

    assert evaluate()["status"] == "verified"

    artifact_path = output_dir / "native-surface-playwright-qa.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    unrelated = dict(payload["cases"][0]["private"]["completionFrames"][0])
    unrelated["request_identity_hash"] = evals._sha("unrelated-request")
    payload["cases"][0]["private"]["completionFrames"].append(unrelated)
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")
    assert evaluate()["reason"] == "native_request_bound_frame_unverified"

    write_verified_synthetic_native_surface_artifact(command, case_ids=["telegram_case"])
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["cleanup"] = {"ok": False, "status": "failed"}
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")
    assert evaluate()["reason"] == "native_execution_summary_unverified"


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
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        write_verified_synthetic_exact_model_artifact(cmd, case_ids=["case_a"])
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
                                "agentId": "synthetic-red-team-agent",
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
    monkeypatch.setattr(
        prompt_service,
        "source_agents_bundle",
        lambda: {
            "mainAgent": {
                "background_cortices": [
                    {
                        "agent_id": "synthetic-red-team-agent",
                        "activation": {"provider": "synthetic-provider", "model": "synthetic-model"},
                    }
                ]
            }
        },
    )

    monkeypatch.setenv("VIVENTIUM_QA_USER_NAME", "Synthetic QA")
    monkeypatch.setenv("VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS", "6000")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append((cmd, kwargs.get("env")))
        output_directory = Path(
            next(value.removeprefix("--output-dir=") for value in cmd if value.startswith("--output-dir="))
        )
        payload = {
            "summary": {"resultCount": 1},
            "results": [
                {
                    "caseId": "red_team_explicit",
                    "targetKey": "red_team",
                    "repetition": 1,
                    "required": True,
                    "allowed": True,
                    "actual": True,
                    "pass": True,
                    "providerUsed": "synthetic-provider",
                    "modelUsed": "synthetic-model",
                    "effortUsed": "provider_default",
                    "requestedProvider": "synthetic-provider",
                    "requestedModel": "synthetic-model",
                    "requestedEffort": "provider_default",
                    "effectiveProvider": "synthetic-provider",
                    "effectiveModel": "synthetic-model",
                    "effectiveEffort": "provider_default",
                    "fallbackReason": "none",
                    "providerAttempts": [
                        {
                            "provider": "synthetic-provider",
                            "model": "synthetic-model",
                            "effort": "provider_default",
                            "source": "primary",
                            "status": "completed",
                            "fallbackReason": "none",
                        }
                    ],
                }
            ],
        }
        (output_directory / "activation-model-eval.json").write_text(json.dumps(payload), encoding="utf-8")
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
    monkeypatch.setattr(
        evals,
        "_configured_execution_route",
        lambda _target: {
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "effort": "medium",
            "fallbacks": [],
        },
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        write_verified_synthetic_exact_model_artifact(
            cmd,
            case_ids=["reads_uncertain_subtext_without_inventing"],
            agent_id="synthetic-eq-agent",
        )
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


def test_public_runner_summary_derives_quality_counts_from_canonical_lists() -> None:
    summary = evals._public_runner_summary(
        json.dumps(
            {
                "status": "partial_semantic_passed",
                "duplicateResponseQualityFailures": [],
                "unresolvedAsyncQualityFailures": [
                    {"privateReason": "synthetic-private-detail"}
                ],
            }
        )
    )

    assert summary == {
        "status": "partial_semantic_passed",
        "duplicateResponseQualityFailureCount": 0,
        "unresolvedAsyncQualityFailureCount": 1,
    }
    assert "synthetic-private-detail" not in json.dumps(summary)

    conflict = evals._public_runner_summary(
        json.dumps(
            {
                "status": "partial_semantic_passed",
                "duplicateResponseQualityFailureCount": 0,
                "duplicateResponseQualityFailures": [{"privateReason": "hidden"}],
            }
        )
    )
    assert conflict["status"] == "blocked"
    assert conflict["blockedReason"] == "runner_summary_quality_count_mismatch"
    assert "hidden" not in json.dumps(conflict)


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


def test_running_prompt_workbench_status_never_exposes_its_launch_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "synthetic-private-launch-token"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "read_state",
        lambda _app_support: {
            "pid": 4312,
            "port": 8781,
            "authUrl": f"http://127.0.0.1:8781?workbench_token={secret}",
            "managedByStack": True,
        },
    )
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: True)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda _pid, _root, _port: True,
    )
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)

    payload = prompt_workbench_cli.status_payload(REPO_ROOT, tmp_path)

    assert payload["url"] == "http://127.0.0.1:8781"
    assert "authUrl" not in payload
    assert secret not in json.dumps(payload)


@pytest.mark.parametrize("json_output", [False, True])
def test_prompt_workbench_public_output_never_prints_legacy_auth_url(
    json_output: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "synthetic-private-launch-token"

    prompt_workbench_cli.print_payload(
        {
            "status": "running",
            "url": "http://127.0.0.1:8781",
            "authUrl": f"http://127.0.0.1:8781?workbench_token={secret}",
        },
        json_output=json_output,
    )

    output = capsys.readouterr().out
    assert "http://127.0.0.1:8781" in output
    assert "authUrl" not in output
    assert "workbench_token" not in output
    assert secret not in output


def test_prompt_workbench_open_uses_only_the_cookie_authenticated_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "synthetic-private-launch-token"
    opened: list[str] = []
    monkeypatch.setattr(
        prompt_workbench_cli,
        "start_server",
        lambda _args: {
            "status": "running",
            "url": "http://127.0.0.1:8781",
            "authUrl": f"http://127.0.0.1:8781?workbench_token={secret}",
        },
    )
    monkeypatch.setattr(prompt_workbench_cli, "open_browser", opened.append)

    result = prompt_workbench_cli.main(
        [
            "open",
            "--repo-root",
            str(REPO_ROOT),
            "--app-support-dir",
            str(tmp_path),
            "--json",
        ]
    )

    assert result == 0
    assert opened == ["http://127.0.0.1:8781"]
    output = capsys.readouterr().out
    assert "authUrl" not in output
    assert secret not in output


def test_prompt_workbench_start_never_creates_or_inherits_launch_bearer_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "synthetic-rotated-launch-token"
    app_support = tmp_path / "app-support"
    launched_environments: list[dict[str, str]] = []
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", secret)
    monkeypatch.setattr(prompt_workbench_cli, "choose_port", lambda *_args: 8781)
    monkeypatch.setattr(prompt_workbench_cli, "ensure_assets_built", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "resolve_launch_admin",
        lambda _env: {"userId": "synthetic-admin", "email": ""},
    )

    def launch_process(*_args: object, **kwargs: object) -> SimpleNamespace:
        launched_environments.append(dict(kwargs["env"]))
        return SimpleNamespace(pid=4312)

    monkeypatch.setattr(
        prompt_workbench_cli.subprocess,
        "Popen",
        launch_process,
    )
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 1.0)
    monkeypatch.setattr(prompt_workbench_cli, "wait_for_health", lambda *_args, **_kwargs: True)

    payload = prompt_workbench_cli.start_server(
        SimpleNamespace(
            repo_root=str(REPO_ROOT),
            app_support_dir=str(app_support),
            port=8781,
            no_build=True,
            timeout_seconds=1,
        )
    )

    assert payload["url"] == "http://127.0.0.1:8781"
    assert "authUrl" not in payload
    assert secret not in json.dumps(payload)
    assert prompt_workbench_cli.log_path(app_support).stat().st_mode & 0o777 == 0o600
    state = prompt_workbench_cli.read_state(app_support)
    assert "authUrl" not in state
    assert "workbench_token" not in json.dumps(state)
    assert secret not in json.dumps(state)
    assert "VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN" not in launched_environments[0]


def test_prompt_workbench_start_uses_the_selected_runtime_compiled_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_PROMPT_WORKBENCH_PORT=14781\n",
        encoding="utf-8",
    )
    preferred_ports: list[int] = []
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_PORT", raising=False)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)

    def choose_port(_app_support: Path, _root: Path, preferred: int) -> int:
        preferred_ports.append(preferred)
        return preferred

    monkeypatch.setattr(prompt_workbench_cli, "choose_port", choose_port)
    monkeypatch.setattr(prompt_workbench_cli, "ensure_assets_built", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "resolve_launch_admin",
        lambda _env: {"userId": "synthetic-admin", "email": ""},
    )
    monkeypatch.setattr(
        prompt_workbench_cli.subprocess,
        "Popen",
        lambda *_args, **_kwargs: SimpleNamespace(pid=4312),
    )
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_identity", lambda _root: "a" * 64)
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 1.0)
    monkeypatch.setattr(prompt_workbench_cli, "wait_for_health", lambda *_args, **_kwargs: True)

    payload = prompt_workbench_cli.start_server(
        SimpleNamespace(
            repo_root=str(REPO_ROOT),
            app_support_dir=str(app_support),
            port=None,
            no_build=True,
            timeout_seconds=1,
        )
    )

    assert preferred_ports == [14781]
    assert payload["port"] == 14781
    assert payload["url"] == "http://127.0.0.1:14781"


def test_prompt_workbench_private_state_strips_legacy_bearers_and_is_owner_only(
    tmp_path: Path,
) -> None:
    app_support = tmp_path / "app-support"
    private_directory = prompt_workbench_cli.state_dir(app_support)
    private_directory.mkdir(parents=True)
    os.chmod(private_directory, 0o755)
    private_state = prompt_workbench_cli.state_path(app_support)
    private_state.write_text("{}\n", encoding="utf-8")
    os.chmod(private_state, 0o644)

    prompt_workbench_cli.write_state(
        app_support,
        {"authUrl": "http://127.0.0.1:8781?workbench_token=synthetic-private-token"},
    )

    assert private_directory.stat().st_mode & 0o777 == 0o700
    assert private_state.stat().st_mode & 0o777 == 0o600
    assert "authUrl" not in prompt_workbench_cli.read_state(app_support)
    assert "synthetic-private-token" not in private_state.read_text(encoding="utf-8")


def test_prompt_workbench_start_hardens_existing_state_without_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    private_directory = prompt_workbench_cli.state_dir(app_support)
    private_directory.mkdir(parents=True)
    os.chmod(private_directory, 0o755)
    private_state = prompt_workbench_cli.state_path(app_support)
    private_state.write_text(
        json.dumps(
            {
                "pid": 4312,
                "port": 8781,
                "url": "http://127.0.0.1:8781",
                "authUrl": "http://127.0.0.1:8781?workbench_token=synthetic-private-token",
            }
        ),
        encoding="utf-8",
    )
    os.chmod(private_state, 0o644)
    private_log = prompt_workbench_cli.log_path(app_support)
    private_log.parent.mkdir(parents=True, exist_ok=True)
    private_log.write_text("Legacy synthetic private log\n", encoding="utf-8")
    os.chmod(private_log, 0o644)
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "status_payload",
        lambda _repo_root, _app_support: {
            "status": "running",
            "pid": 4312,
            "port": 8781,
            "url": "http://127.0.0.1:8781",
        },
    )
    monkeypatch.setattr(prompt_workbench_cli, "state_source_is_stale", lambda _state, _root: False)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda _pid: pytest.fail("An existing Workbench must not restart to harden its state"),
    )

    payload = prompt_workbench_cli.start_server(
        SimpleNamespace(
            repo_root=str(REPO_ROOT),
            app_support_dir=str(app_support),
            port=8781,
            no_build=True,
            timeout_seconds=1,
        )
    )

    assert payload["started"] is False
    assert payload["pid"] == 4312
    assert private_directory.stat().st_mode & 0o777 == 0o700
    assert private_state.stat().st_mode & 0o777 == 0o600
    assert private_log.stat().st_mode & 0o777 == 0o600
    assert "authUrl" not in prompt_workbench_cli.read_state(app_support)
    assert "synthetic-private-token" not in private_state.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("stack_requested", "initial_owner", "expected_owner"),
    [(True, False, True), (False, False, False), (False, True, True)],
)
def test_explicit_stack_start_adopts_only_its_owned_running_prompt_workbench(
    stack_requested: bool,
    initial_owner: bool,
    expected_owner: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    prompt_workbench_cli.write_state(
        app_support,
        {
            "pid": 4312,
            "port": 8781,
            "url": "http://127.0.0.1:8781",
            "authUrl": "http://127.0.0.1:8781?workbench_token=synthetic-private-token",
            "managedByStack": initial_owner,
        },
    )
    if stack_requested:
        monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", "1")
    else:
        monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: True)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda _pid, _root, _port: True,
    )
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "state_source_is_stale", lambda _state, _root: False)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda _pid: pytest.fail("Stack ownership adoption must not restart the Workbench"),
    )

    payload = prompt_workbench_cli.start_server(
        SimpleNamespace(
            repo_root=str(REPO_ROOT),
            app_support_dir=str(app_support),
            port=8781,
            no_build=True,
            timeout_seconds=1,
        )
    )

    assert payload["started"] is False
    assert payload["pid"] == 4312
    assert payload["managedByStack"] is expected_owner
    assert prompt_workbench_cli.read_state(app_support)["managedByStack"] is expected_owner


def test_prompt_workbench_concurrent_starts_share_one_private_lifecycle_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    first_launch_entered = threading.Event()
    release_first_launch = threading.Event()
    second_launch_entered = threading.Event()
    launched_pids: list[int] = []
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", "true")
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "ensure_assets_built", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "resolve_launch_admin",
        lambda _env: {"userId": "synthetic-admin", "email": ""},
    )
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 1.0)
    monkeypatch.setattr(prompt_workbench_cli, "state_source_is_stale", lambda _state, _root: False)
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda pid: pid in launched_pids)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, _root, _port=None: pid in launched_pids,
    )
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "wait_for_health", lambda *_args, **_kwargs: True)

    def launch_process(*_args: object, **_kwargs: object) -> SimpleNamespace:
        pid = 4312 + len(launched_pids)
        launched_pids.append(pid)
        if len(launched_pids) == 1:
            first_launch_entered.set()
            if not release_first_launch.wait(timeout=5):
                raise AssertionError("Timed out while holding the synthetic first launch")
        else:
            second_launch_entered.set()
        return SimpleNamespace(pid=pid)

    monkeypatch.setattr(prompt_workbench_cli.subprocess, "Popen", launch_process)
    args = SimpleNamespace(
        repo_root=str(REPO_ROOT),
        app_support_dir=str(app_support),
        port=8781,
        no_build=True,
        timeout_seconds=1,
    )

    def start() -> None:
        try:
            results.append(prompt_workbench_cli.start_server(args))
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=start)
    second = threading.Thread(target=start)
    first.start()
    try:
        assert first_launch_entered.wait(timeout=2)
        second.start()
        second_launch_entered.wait(timeout=0.25)
    finally:
        release_first_launch.set()
        first.join(timeout=5)
        if second.ident is not None:
            second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert launched_pids == [4312]
    assert sorted(result["started"] for result in results) == [False, True]
    assert {result["pid"] for result in results} == {4312}
    assert prompt_workbench_cli.read_state(app_support)["pid"] == 4312
    lock_file = prompt_workbench_cli.state_dir(app_support) / "lifecycle.lock"
    assert prompt_workbench_cli.state_dir(app_support).stat().st_mode & 0o777 == 0o700
    assert lock_file.stat().st_mode & 0o777 == 0o600


def test_prompt_workbench_start_rejects_another_process_preexisting_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    stopped: list[int] = []
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)
    monkeypatch.setattr(prompt_workbench_cli, "choose_port", lambda *_args: 8781)
    monkeypatch.setattr(prompt_workbench_cli, "ensure_assets_built", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "resolve_launch_admin",
        lambda _env: {"userId": "synthetic-admin", "email": ""},
    )
    monkeypatch.setattr(prompt_workbench_cli.subprocess, "Popen", lambda *_args, **_kwargs: SimpleNamespace(pid=4312))
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda pid: pid in {4312, 9912})
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, _root, _port=None: pid in {4312, 9912},
    )
    monkeypatch.setattr(prompt_workbench_cli, "process_descendant_pids", lambda _pid: [])
    monkeypatch.setattr(prompt_workbench_cli, "process_listens_on_port", lambda _pid, _port: False)
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 1.0)
    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", lambda pid: stopped.append(pid) or True)

    with pytest.raises(RuntimeError, match="did not become healthy|does not own"):
        prompt_workbench_cli.start_server(
            SimpleNamespace(
                repo_root=str(REPO_ROOT),
                app_support_dir=str(app_support),
                port=8781,
                no_build=True,
                timeout_seconds=0,
            )
        )

    assert prompt_workbench_cli.read_state(app_support) == {}
    assert 9912 not in stopped


def test_prompt_workbench_status_never_deletes_a_replacement_owner_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    stale = {"pid": 4312, "port": 8781, "url": "http://127.0.0.1:8781"}
    replacement = {"pid": 5312, "port": 8781, "url": "http://127.0.0.1:8781"}
    prompt_workbench_cli.write_state(app_support, stale)
    replaced = False

    def pid_running(pid: int) -> bool:
        nonlocal replaced
        if pid == 4312 and not replaced:
            replaced = True
            prompt_workbench_cli.write_state(app_support, replacement)
        return pid == 5312

    monkeypatch.setattr(prompt_workbench_cli, "pid_running", pid_running)

    payload = prompt_workbench_cli.status_payload(REPO_ROOT, app_support)

    assert payload["status"] == "stopped"
    assert prompt_workbench_cli.read_state(app_support) == replacement


def test_prompt_workbench_stop_never_deletes_a_replacement_owner_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    stale = {"pid": 4312, "port": 8781, "url": "http://127.0.0.1:8781"}
    replacement = {"pid": 5312, "port": 8781, "url": "http://127.0.0.1:8781"}
    prompt_workbench_cli.write_state(app_support, stale)
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *_args: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_owner_scope", lambda *_args: True)

    def stop_and_replace(pid: int) -> bool:
        assert pid == 4312
        prompt_workbench_cli.write_state(app_support, replacement)
        return True

    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", stop_and_replace)

    payload = prompt_workbench_cli.stop_server(
        SimpleNamespace(repo_root=str(REPO_ROOT), app_support_dir=str(app_support))
    )

    assert payload == {"status": "stopped", "stopped": True}
    assert prompt_workbench_cli.read_state(app_support) == replacement
    assert prompt_workbench_cli.user_stopped_marker_path(app_support).exists()


def test_prompt_workbench_stop_never_kills_the_same_checkout_from_another_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    prompt_workbench_cli.write_state(
        app_support,
        {"pid": 4312, "port": 8781, "url": "http://127.0.0.1:8781"},
    )
    stopped: list[int] = []
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *_args: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_owner_scope", lambda *_args: False)
    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", lambda pid: stopped.append(pid) or True)

    payload = prompt_workbench_cli.stop_server(
        SimpleNamespace(repo_root=str(REPO_ROOT), app_support_dir=str(app_support))
    )

    assert payload["status"] == "blocked"
    assert payload["stopped"] is False
    assert stopped == []


def test_prompt_workbench_stale_restart_never_kills_another_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    prompt_workbench_cli.write_state(
        app_support,
        {
            "pid": 4312,
            "port": 8781,
            "url": "http://127.0.0.1:8781",
            "sourceMtime": 1.0,
        },
    )
    stopped: list[int] = []
    monkeypatch.delenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", raising=False)
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *_args: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_owner_scope", lambda *_args: False)
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "state_source_is_stale", lambda *_args: True)
    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", lambda pid: stopped.append(pid) or True)

    with pytest.raises(RuntimeError, match="not owned by this runtime"):
        prompt_workbench_cli.start_server(
            SimpleNamespace(
                repo_root=str(REPO_ROOT),
                app_support_dir=str(app_support),
                port=8781,
                no_build=True,
                timeout_seconds=1,
            )
        )

    assert stopped == []


def configure_synthetic_orphaned_workbench(
    app_support: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    process_environment = {
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support.resolve()),
        "VIVENTIUM_DEV_ENV_SCOPE_ACTIVE": "false",
        "VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK": "true",
    }
    monkeypatch.setenv("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK", "true")
    monkeypatch.delenv("VIVENTIUM_DEV_ENV_SCOPE_ACTIVE", raising=False)
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda _port: False)
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda _port: [8216])
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda pid: pid in {8202, 8216})
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, root, port=None: pid in {8202, 8216}
        and root.resolve() == WORKBENCH_ROOT.resolve()
        and port == 8781,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_parent_pid",
        lambda pid: {8216: 8202, 8202: 1}.get(pid, 0),
        raising=False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_descendant_pids",
        lambda pid: [8216] if pid == 8202 else [],
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_listens_on_port",
        lambda pid, port: pid == 8216 and port == 8781,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_uid",
        lambda _pid: os.getuid(),
        raising=False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_environment_value",
        lambda _pid, key: process_environment.get(key),
        raising=False,
    )
    monkeypatch.setattr(prompt_workbench_cli, "http_healthy", lambda _port: True)
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 1.0)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: pytest.fail(f"Orphan recovery must not stop listener or wrapper {pid}"),
    )
    monkeypatch.setattr(
        prompt_workbench_cli.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("Orphan recovery must not launch another Workbench"),
    )
    return process_environment


def test_managed_prompt_workbench_recovers_only_its_same_scope_orphan_as_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    configure_synthetic_orphaned_workbench(app_support, monkeypatch)

    state = prompt_workbench_cli.recover_owned_workbench_state(
        REPO_ROOT,
        app_support,
        8781,
        managed_by_stack=True,
    )

    assert state["pid"] == 8202
    assert state["repoRoot"] == str(REPO_ROOT)
    assert state["managedByStack"] is True
    assert state["sourceIdentity"] is None
    assert prompt_workbench_cli.state_source_is_stale(state, WORKBENCH_ROOT) is True


@pytest.mark.parametrize(
    "mismatch",
    ("app_support", "checkout", "user", "development_scope"),
)
def test_managed_prompt_workbench_never_adopts_or_stops_a_foreign_orphan(
    mismatch: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support = tmp_path / "app-support"
    process_environment = configure_synthetic_orphaned_workbench(app_support, monkeypatch)
    if mismatch == "app_support":
        process_environment["VIVENTIUM_APP_SUPPORT_DIR"] = str(tmp_path / "other-app-support")
    elif mismatch == "checkout":
        monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *_args: False)
    elif mismatch == "user":
        monkeypatch.setattr(prompt_workbench_cli, "process_uid", lambda _pid: os.getuid() + 1)
    else:
        process_environment["VIVENTIUM_DEV_ENV_SCOPE_ACTIVE"] = "true"

    with pytest.raises(RuntimeError, match="owned by another runtime or listener"):
        prompt_workbench_cli.start_server(
            SimpleNamespace(
                repo_root=str(REPO_ROOT),
                app_support_dir=str(app_support),
                port=8781,
                no_build=True,
                timeout_seconds=1,
            )
        )

    assert prompt_workbench_cli.read_state(app_support) == {}


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


def test_prompt_workbench_process_owner_resolves_relative_app_dir_from_process_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "current"
    root = repo_root / "viventium_v0_4" / "prompt-workbench"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_command",
        lambda pid: (
            "uvicorn --app-dir viventium_v0_4/prompt-workbench/backend "
            "prompt_workbench.app:app --host 127.0.0.1 --port 8781"
        ),
    )
    monkeypatch.setattr(prompt_workbench_cli, "process_cwd", lambda pid: repo_root)

    assert prompt_workbench_cli.process_matches_workbench(4312, root) is True


def test_prompt_workbench_process_owner_rejects_relative_app_dir_from_another_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    other_repo = tmp_path / "other"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_command",
        lambda pid: (
            "uvicorn --app-dir viventium_v0_4/prompt-workbench/backend "
            "prompt_workbench.app:app --host 127.0.0.1 --port 8781"
        ),
    )
    monkeypatch.setattr(prompt_workbench_cli, "process_cwd", lambda pid: other_repo)

    assert prompt_workbench_cli.process_matches_workbench(4312, root) is False


def test_prompt_workbench_process_owner_does_not_trust_unrelated_command_substrings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    other_backend = tmp_path / "other" / "viventium_v0_4" / "prompt-workbench" / "backend"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_command",
        lambda pid: (
            f"uvicorn --app-dir {other_backend} prompt_workbench.app:app "
            f"--log-config {root}/synthetic-log.yaml"
        ),
    )

    assert prompt_workbench_cli.process_matches_workbench(4312, root) is False


def test_prompt_workbench_stop_pid_handles_signal_races_without_escaping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = iter([True, False])
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda _pid: next(running, False))
    monkeypatch.setattr(prompt_workbench_cli.os, "getpgid", lambda _pid: 4312)
    monkeypatch.setattr(
        prompt_workbench_cli.os,
        "killpg",
        lambda *_args: (_ for _ in ()).throw(ProcessLookupError()),
    )
    monkeypatch.setattr(
        prompt_workbench_cli.os,
        "kill",
        lambda *_args: (_ for _ in ()).throw(ProcessLookupError()),
    )

    assert prompt_workbench_cli.stop_pid(4312, timeout_seconds=0) is True


def test_prompt_workbench_source_freshness_uses_recorded_source_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 200.0)

    assert prompt_workbench_cli.state_source_is_stale({"sourceMtime": 199.0}, tmp_path) is True
    assert prompt_workbench_cli.state_source_is_stale({"sourceMtime": 200.0}, tmp_path) is False


def test_prompt_workbench_source_identity_detects_changed_bytes_with_unchanged_mtime(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prompt-workbench"
    source = root / "src" / "App.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("first\n", encoding="utf-8")
    fixed_time = 1_700_000_000_000_000_000
    os.utime(source, ns=(fixed_time, fixed_time))
    recorded = prompt_workbench_cli.workbench_source_identity(root)

    source.write_text("other\n", encoding="utf-8")
    os.utime(source, ns=(fixed_time, fixed_time))

    assert source.stat().st_mtime_ns == fixed_time
    assert prompt_workbench_cli.workbench_source_identity(root) != recorded
    assert prompt_workbench_cli.state_source_is_stale(
        {"sourceIdentity": recorded, "sourceMtime": source.stat().st_mtime},
        root,
    ) is True


def test_prompt_workbench_content_identity_is_bounded_to_runtime_build_inputs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prompt-workbench"
    inputs = {
        "src/App.tsx": "app",
        "public/viventium-logo.png": "logo",
        "index.html": "index",
        "package.json": "package",
        "package-lock.json": "lock",
        "tsconfig.json": "tsconfig",
        "vite.config.ts": "vite",
        "backend/prompt_workbench/app.py": "backend",
    }
    for relative, value in inputs.items():
        candidate = root / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(value, encoding="utf-8")
    excluded = [
        root / "dist" / "index.html",
        root / "node_modules" / "synthetic" / "index.js",
        root / "backend" / "tests" / "test_synthetic.py",
        root / "src" / "__pycache__" / "synthetic.pyc",
    ]
    for candidate in excluded:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("excluded", encoding="utf-8")

    frontend_before = prompt_workbench_cli.frontend_input_identity(root)
    runtime_before = prompt_workbench_cli.workbench_source_identity(root)
    for candidate in excluded:
        candidate.write_text("changed excluded", encoding="utf-8")
    assert prompt_workbench_cli.frontend_input_identity(root) == frontend_before
    assert prompt_workbench_cli.workbench_source_identity(root) == runtime_before

    (root / "package-lock.json").write_text("changed lock", encoding="utf-8")
    assert prompt_workbench_cli.frontend_input_identity(root) != frontend_before
    assert prompt_workbench_cli.workbench_source_identity(root) != runtime_before


def test_frontend_input_identity_matches_the_served_build_projection() -> None:
    app_module = importlib.import_module("prompt_workbench.app")

    assert prompt_workbench_cli.frontend_input_identity(
        WORKBENCH_ROOT
    ) == app_module._frontend_input_identity()


def test_prompt_workbench_build_receipt_binds_inputs_and_built_bytes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prompt-workbench"
    source = root / "src" / "App.tsx"
    asset = root / "dist" / "assets" / "index.js"
    source.parent.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    (root / "dist" / "index.html").write_text(
        '<script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    asset.write_text("built", encoding="utf-8")

    prompt_workbench_cli.write_build_receipt(root)
    assert prompt_workbench_cli.build_receipt_status(root)["receiptValid"] is True

    asset.write_text("stale", encoding="utf-8")
    status = prompt_workbench_cli.build_receipt_status(root)
    assert status["assetsCurrent"] is False
    assert status["receiptValid"] is False

    prompt_workbench_cli.write_build_receipt(root)
    source.write_text("changed", encoding="utf-8")
    status = prompt_workbench_cli.build_receipt_status(root)
    assert status["sourceCurrent"] is False
    assert status["receiptValid"] is False


def test_prompt_workbench_asset_builder_rebuilds_for_missing_or_stale_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "prompt-workbench"
    source = root / "src" / "App.tsx"
    asset = root / "dist" / "assets" / "index.js"
    source.parent.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    (root / "node_modules").mkdir()
    source.write_text("first", encoding="utf-8")
    (root / "dist" / "index.html").write_text(
        '<script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    asset.write_text("old", encoding="utf-8")
    builds: list[list[str]] = []

    def build(command: list[str], *_args: object, **_kwargs: object) -> None:
        builds.append(command)
        asset.write_text(f"built-{len(builds)}", encoding="utf-8")

    monkeypatch.setattr(prompt_workbench_cli, "run_logged", build)

    prompt_workbench_cli.ensure_assets_built(
        root,
        tmp_path / "workbench.log",
        skip_build=False,
    )
    assert builds == [["npm", "run", "build"]]
    assert prompt_workbench_cli.build_receipt_status(root)["receiptValid"] is True

    fixed_time = source.stat().st_mtime_ns
    source.write_text("other", encoding="utf-8")
    os.utime(source, ns=(fixed_time, fixed_time))
    prompt_workbench_cli.ensure_assets_built(
        root,
        tmp_path / "workbench.log",
        skip_build=False,
    )
    assert builds == [["npm", "run", "build"], ["npm", "run", "build"]]
    assert prompt_workbench_cli.build_receipt_status(root)["receiptValid"] is True


def test_prompt_workbench_no_build_rejects_an_unverified_receipt(tmp_path: Path) -> None:
    root = tmp_path / "prompt-workbench"
    (root / "dist").mkdir(parents=True)
    (root / "dist" / "index.html").write_text("stale", encoding="utf-8")

    with pytest.raises(RuntimeError, match="verified frontend build receipt"):
        prompt_workbench_cli.ensure_assets_built(
            root,
            tmp_path / "workbench.log",
            skip_build=True,
        )


def test_recovered_owned_process_is_stale_until_its_source_identity_is_proven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_identity", lambda _root: "a" * 64)

    assert prompt_workbench_cli.state_source_is_stale(
        {"sourceIdentity": None, "sourceMtime": 9999999999.0},
        tmp_path,
    ) is True
    assert prompt_workbench_cli.current_workbench_requires_restart(
        {"sourceIdentity": None},
        {"status": "running", "port": 8781},
        tmp_path,
        managed_by_stack=True,
        preferred_port=8781,
    ) is True


def test_prompt_workbench_legacy_state_fails_stale_when_source_changed_after_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_workbench_cli, "workbench_source_mtime", lambda _root: 200.0)
    started = datetime.fromtimestamp(150.0, tz=timezone.utc).isoformat()

    assert prompt_workbench_cli.state_source_is_stale({"startedAt": started}, tmp_path) is True
    assert prompt_workbench_cli.state_source_is_stale({}, tmp_path) is True


def test_managed_prompt_workbench_reclaims_only_a_recognized_stale_workbench_listener(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    app_support = tmp_path / "app-support"
    stopped: list[int] = []
    available_checks = iter([False, True])
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda port: [4312])
    monkeypatch.setattr(
        prompt_workbench_cli,
        "read_state",
        lambda candidate: {"pid": 4312, "port": 8781} if candidate == app_support else {},
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected_root, expected_port=None: expected_root == root and expected_port == 8781,
    )
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_owner_scope", lambda *_args: True)
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: stopped.append(pid) or True,
    )
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda port: next(available_checks))
    monkeypatch.setattr(prompt_workbench_cli.time, "sleep", lambda seconds: None)

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(8781, root, app_support)

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
        lambda pid, expected_root, expected_port=None: False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: stopped.append(pid) or True,
    )

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(
        8781,
        root,
        tmp_path / "app-support",
    )

    assert reclaimed is False
    assert stopped == []


def test_managed_prompt_workbench_refuses_to_reclaim_another_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    app_support = tmp_path / "app-support"
    prompt_workbench_cli.write_state(app_support, {"pid": 4312, "port": 8781})
    stopped: list[int] = []
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda _port: False)
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda _port: [4312])
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *_args: True)
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_owner_scope", lambda *_args: False)
    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", lambda pid: stopped.append(pid) or True)

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(
        8781,
        root,
        app_support,
    )

    assert reclaimed is False
    assert stopped == []


def test_dev_scoped_managed_prompt_workbench_never_reclaims_an_existing_listener(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    stopped: list[int] = []
    monkeypatch.setenv("VIVENTIUM_DEV_ENV_SCOPE_ACTIVE", "true")
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda port: [4312])
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected_root, expected_port=None: expected_root == root,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "stop_pid",
        lambda pid: stopped.append(pid) or True,
    )
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda port: False)

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(
        8781,
        root,
        tmp_path / "app-support",
    )

    assert reclaimed is False
    assert stopped == []


def test_managed_prompt_workbench_does_not_reclaim_without_current_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    stopped: list[int] = []
    monkeypatch.setattr(prompt_workbench_cli, "port_available", lambda port: False)
    monkeypatch.setattr(prompt_workbench_cli, "listener_pids", lambda port: [4312])
    monkeypatch.setattr(prompt_workbench_cli, "read_state", lambda app_support: {})
    monkeypatch.setattr(prompt_workbench_cli, "process_matches_workbench", lambda *args: True)
    monkeypatch.setattr(prompt_workbench_cli, "stop_pid", lambda pid: stopped.append(pid) or True)

    reclaimed = prompt_workbench_cli.reclaim_stale_managed_workbench_port(
        8781,
        root,
        tmp_path / "app-support",
    )

    assert reclaimed is False
    assert stopped == []


def test_prompt_workbench_process_owner_requires_expected_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    backend = root / "backend"
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_command",
        lambda pid: f"uvicorn --app-dir {backend} prompt_workbench.app:app --port 8781",
    )

    assert prompt_workbench_cli.process_matches_workbench(4312, root, 8781) is True
    assert prompt_workbench_cli.process_matches_workbench(4312, root, 10781) is False


def test_prompt_workbench_listener_ownership_checks_only_the_owner_process_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "current" / "viventium_v0_4" / "prompt-workbench"
    monkeypatch.setattr(prompt_workbench_cli, "pid_running", lambda pid: pid in {4312, 4313})
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected_root, expected_port=None: (
            pid in {4312, 4313} and expected_root == root and expected_port == 14781
        ),
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_descendant_pids",
        lambda owner_pid: [4313] if owner_pid == 4312 else [],
        raising=False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_listens_on_port",
        lambda pid, port: pid == 4313 and port == 14781,
        raising=False,
    )
    monkeypatch.setattr(
        prompt_workbench_cli,
        "listener_pids",
        lambda _port: pytest.fail("Listener ownership must not scan every machine socket."),
    )

    assert prompt_workbench_cli.process_owns_workbench_listener(4312, root, 14781) is True


def test_managed_prompt_workbench_restarts_its_current_process_when_compiled_port_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_workbench_cli, "state_source_is_stale", lambda state, root: False)
    current = {"status": "running", "pid": 4312, "port": 8781}

    assert prompt_workbench_cli.current_workbench_requires_restart(
        {},
        current,
        tmp_path,
        managed_by_stack=True,
        preferred_port=10781,
    ) is True
    assert prompt_workbench_cli.current_workbench_requires_restart(
        {},
        current,
        tmp_path,
        managed_by_stack=True,
        preferred_port=8781,
    ) is False


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
    monkeypatch.setattr(
        prompt_workbench_cli,
        "process_matches_workbench",
        lambda pid, expected, expected_port=None: False,
    )
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


def test_prompt_workbench_route_receipts_bind_effort_and_typed_fallback_lineage() -> None:
    telemetry_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "api"
        / "server"
        / "services"
        / "viventium"
        / "promptFrameTelemetry.js"
    ).read_text(encoding="utf-8")
    acceptance_source = (
        REPO_ROOT
        / "qa"
        / "prompt-workbench"
        / "scripts"
        / "run_pw_047_installed_full_bank.cjs"
    ).read_text(encoding="utf-8")
    panel_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "prompt-workbench"
        / "src"
        / "components"
        / "EvalPanel.tsx"
    ).read_text(encoding="utf-8")

    for field in (
        "requestedProvider",
        "requestedModel",
        "requestedEffort",
        "effectiveProvider",
        "effectiveModel",
        "effectiveEffort",
        "fallbackUsed",
        "fallbackAuthorized",
        "fallbackReason",
    ):
        assert field in acceptance_source
        assert field in panel_source
    for field in (
        "requested_provider",
        "requested_model",
        "requested_effort",
        "effective_provider",
        "effective_model",
        "effective_effort",
        "fallback_used",
        "fallback_reason",
    ):
        assert field in telemetry_source
    assert "PROMPT_FRAME_FALLBACK_REASONS" in telemetry_source
    assert "TYPED_FALLBACK_REASONS" in acceptance_source
    assert "eval_history_readback_mismatch" in acceptance_source


def test_pw047_inventory_enumerates_complete_route_lineage_without_provider_execution() -> None:
    bank = evals.load_eval_bank()
    families = bank["families"]
    case_count = sum(len(family["cases"]) for family in families)
    plan_count = sum(
        len({case.get("surface") or "web" for case in family["cases"]})
        for family in families
    )

    assert len(families) == 21
    assert case_count == 177
    assert plan_count == 29
    for family in families:
        runner = family.get("runner") or "main"
        route = evals._configured_family_execution_route(family["id"])
        assert route is not None
        assert route["kind"] == runner
        assert route["family"] == family["id"]
        variants = route["targets"] if runner == "background_activation" else [route]
        if runner == "background_activation":
            assert {variant["targetKey"] for variant in variants} == {
                target["key"] for target in family["activationTargets"]
            }
        for variant in variants:
            assert variant["provider"]
            assert variant["model"]
            assert variant["effort"]
            assert isinstance(variant["fallbacks"], list)
            triples = {
                (variant["provider"], variant["model"], variant["effort"]),
                *{
                    (fallback["provider"], fallback["model"], fallback["effort"])
                    for fallback in variant["fallbacks"]
                },
            }
            assert len(triples) == len(variant["fallbacks"]) + 1


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
