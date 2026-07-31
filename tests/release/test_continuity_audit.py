from __future__ import annotations

import importlib.util
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "scripts" / "viventium" / "continuity_audit.py"
SNAPSHOT_WRAPPER = REPO_ROOT / "viventium_v0_4" / "viventium-local-state-snapshot.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "restore.sh"


def write_test_recoverable_bundle(snapshot_dir: Path, *, include_telegram: bool = False) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / ".viventium-recoverable").write_text("v1\n", encoding="utf-8")
    config = snapshot_dir / "config" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("version: 1\ninstall:\n  mode: native\n", encoding="utf-8")
    mongo = snapshot_dir / "mongo" / "viventium.archive.gz"
    mongo.parent.mkdir(parents=True, exist_ok=True)
    mongo.write_bytes(gzip.compress(b"synthetic-mongodump-archive"))
    schedules = snapshot_dir / "schedules" / "schedules.db"
    schedules.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(schedules)
    connection.execute("CREATE TABLE scheduled_tasks (id TEXT PRIMARY KEY, active INTEGER NOT NULL)")
    connection.commit()
    connection.close()

    def artifact(relative: str, domain: str, role: str, media_type: str, method: str) -> dict:
        path = snapshot_dir / relative
        row = {
            "path": relative,
            "domain": domain,
            "role": role,
            "mediaType": media_type,
            "captureMethod": method,
            "schemaVersion": 1,
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if media_type == "application/gzip":
            row["uncompressedSize"] = len(gzip.decompress(path.read_bytes()))
        return row

    artifacts = [
        artifact("config/config.yaml", "config", "canonical_config", "application/yaml", "file_copy"),
        artifact("mongo/viventium.archive.gz", "mongo", "mongo_archive", "application/gzip", "mongodump_archive"),
        artifact("schedules/schedules.db", "schedules", "schedules_database", "application/vnd.sqlite3", "sqlite_backup"),
    ]
    channel_paths: list[str] = []
    if include_telegram:
        channel_paths = ["telegram/user_configs/copied.json"]
        artifacts.append(
            artifact(
                channel_paths[0],
                "channels",
                "telegram_user_config",
                "application/json",
                "file_copy",
            )
        )
    manifest = {
        "schemaVersion": 1,
        "bundleKind": "complete",
        "domains": [
            {"name": "config", "status": "captured", "policy": "restore", "artifacts": ["config/config.yaml"]},
            {"name": "mongo", "status": "captured", "policy": "restore", "artifacts": ["mongo/viventium.archive.gz"]},
            {"name": "files", "status": "empty", "policy": "restore", "artifacts": []},
            {"name": "schedules", "status": "captured", "policy": "restore", "artifacts": ["schedules/schedules.db"]},
            {"name": "recall", "status": "rebuild_required", "policy": "rebuild_derived", "artifacts": []},
            {"name": "auth", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
            {
                "name": "channels",
                "status": "captured" if channel_paths else "empty",
                "policy": "restore",
                "artifacts": channel_paths,
            },
        ],
        "artifacts": artifacts,
    }
    (snapshot_dir / "recoverable-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def load_continuity_audit_module():
    spec = importlib.util.spec_from_file_location("viventium_continuity_audit", AUDIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bash_public_safe_path_label(path: str, home: str) -> str:
    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts' / 'viventium' / 'common.sh'}' && "
                f"public_safe_path_label '{path}'"
            ),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "HOME": home},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_capture_manifest_uses_public_safe_path_labels(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()

    app_support_dir = tmp_path / "Library" / "Application Support" / "Viventium"
    runtime_dir = app_support_dir / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=true\n"
        "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER=ollama\n"
        "VIVENTIUM_RAG_EMBEDDINGS_MODEL=qwen3-embedding:0.6b\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text(
        "OWNER_LOCAL_SENTINEL=must-not-emit-local\n",
        encoding="utf-8",
    )
    service_env = runtime_dir / "service-env"
    service_env.mkdir()
    (service_env / "librechat.env").write_text(
        "MONGO_URI=mongodb://synthetic-user:synthetic-password@127.0.0.1:1/NoDatabase\n",
        encoding="utf-8",
    )
    (service_env / "librechat.owner.env").write_text(
        "OWNER_SERVICE_SENTINEL=must-not-emit-owner\n",
        encoding="utf-8",
    )

    manifest = continuity_audit.capture_manifest(
        type(
            "Args",
            (),
            {
                "repo_root": str(REPO_ROOT),
                "app_support_dir": str(app_support_dir),
                "config_file": None,
                "runtime_dir": str(runtime_dir),
                "label": "test",
            },
        )()
    )

    for value in manifest["paths"].values():
        if isinstance(value, str):
            assert not value.startswith(str(Path.home()))
            assert not value.startswith("/")
    serialized = json.dumps(manifest, sort_keys=True)
    for forbidden in (
        "synthetic-user",
        "synthetic-password",
        "must-not-emit-local",
        "must-not-emit-owner",
        "librechat.owner.env",
    ):
        assert forbidden not in serialized


def test_python_and_bash_path_sanitizers_match(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    home = str(Path.home())
    samples = [
        home,
        f"{home}/Library/Application Support/Viventium",
        str(tmp_path / "snapshot"),
    ]

    for sample in samples:
        assert continuity_audit.sanitize_path_label(Path(sample)) == bash_public_safe_path_label(
            sample,
            home,
        )


def test_resolve_mongo_uri_derives_local_runtime_uri(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()

    uri = continuity_audit.resolve_mongo_uri(
        {
            "MONGO_URI": "",
            "VIVENTIUM_LOCAL_MONGO_PORT": "27117",
            "VIVENTIUM_LOCAL_MONGO_DB": "LibreChatViventium",
        },
        tmp_path / "runtime",
    )

    assert uri == "mongodb://127.0.0.1:27117/LibreChatViventium"


def test_resolve_mongo_uri_prefers_generated_service_env(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()

    runtime_dir = tmp_path / "runtime"
    service_env = runtime_dir / "service-env" / "librechat.env"
    service_env.parent.mkdir(parents=True)
    service_env.write_text("MONGO_URI=mongodb://127.0.0.1:27118/ServiceEnvDb\n", encoding="utf-8")

    uri = continuity_audit.resolve_mongo_uri(
        {
            "MONGO_URI": "",
            "VIVENTIUM_LOCAL_MONGO_PORT": "27117",
            "VIVENTIUM_LOCAL_MONGO_DB": "LibreChatViventium",
        },
        runtime_dir,
    )

    assert uri == "mongodb://127.0.0.1:27118/ServiceEnvDb"


def test_compare_manifests_flags_older_surfaces(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    snapshot_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-10T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": None},
                },
            }
        ),
        encoding="utf-8",
    )
    live_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": "2026-04-09T00:00:00+00:00"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
            },
        )()
    )

    assert result["status"] == "error"
    assert result["olderSurfaces"] == ["messages"]


def test_compare_manifests_warns_when_all_surfaces_unknown(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    payload = {
        "schemaVersion": 1,
        "surfaces": {
            "messages": {"latestTimestamp": None},
            "savedMemory": {"latestTimestamp": None},
            "schedules": {"latestTimestamp": None},
        },
    }
    snapshot_manifest.write_text(json.dumps(payload), encoding="utf-8")
    live_manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
            },
        )()
    )

    assert result["status"] == "warning"
    assert result["olderSurfaces"] == []
    assert any("age could not be proven" in warning for warning in result["warnings"])


def test_compare_manifests_tracks_newer_snapshot_without_error(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    snapshot_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": "2026-04-10T00:00:00+00:00"},
                },
            }
        ),
        encoding="utf-8",
    )
    live_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": "2026-04-10T00:00:00+00:00"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
            },
        )()
    )

    assert result["status"] == "ok"
    assert result["olderSurfaces"] == []
    assert result["surfaces"]["messages"]["relation"] == "newer"


def test_compare_manifests_warns_on_schema_version_mismatch(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    snapshot_manifest.write_text(
        json.dumps({"schemaVersion": 1, "surfaces": {}}),
        encoding="utf-8",
    )
    live_manifest.write_text(
        json.dumps({"schemaVersion": 2, "surfaces": {}}),
        encoding="utf-8",
    )

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
            },
        )()
    )

    assert result["status"] == "warning"
    assert any("different schema versions" in warning for warning in result["warnings"])


def test_compare_manifests_warns_on_recall_and_runtime_metadata_drift(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    snapshot_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runtime": {
                    "profile": "isolated",
                    "defaultConversationRecall": "true",
                    "embeddingsProvider": "ollama",
                    "embeddingsModel": "qwen3-embedding:0.6b",
                    "embeddingsProfile": "local",
                },
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "recall": {"rebuildRequired": False},
                },
            }
        ),
        encoding="utf-8",
    )
    live_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runtime": {
                    "profile": "isolated",
                    "defaultConversationRecall": "false",
                    "embeddingsProvider": "openai",
                    "embeddingsModel": "text-embedding-3-large",
                    "embeddingsProfile": "remote",
                },
                "surfaces": {
                    "messages": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "savedMemory": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "schedules": {"latestTimestamp": "2026-04-12T00:00:00+00:00"},
                    "recall": {"rebuildRequired": True},
                },
            }
        ),
        encoding="utf-8",
    )

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
            },
        )()
    )

    assert result["status"] == "warning"
    assert any("runtime/recall settings" in warning for warning in result["warnings"])
    assert {entry["field"] for entry in result["metadataDifferences"]} == {
        "runtime.defaultConversationRecall",
        "runtime.embeddingsProvider",
        "runtime.embeddingsModel",
        "runtime.embeddingsProfile",
        "surfaces.recall.rebuildRequired",
    }
    assert str(Path.home()) not in json.dumps(result)


def test_schedule_digest_protects_runtime_outcomes_and_user_changes(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    schedule_db = tmp_path / "schedules.db"
    connection = sqlite3.connect(schedule_db)
    connection.execute(
        """
        CREATE TABLE scheduled_tasks (
          id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          prompt TEXT NOT NULL,
          schedule_json TEXT NOT NULL,
          channel TEXT NOT NULL,
          executor TEXT NOT NULL,
          conversation_policy TEXT NOT NULL,
          conversation_id TEXT,
          active INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          created_source TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          updated_by TEXT NOT NULL,
          updated_source TEXT NOT NULL,
          last_run_at TEXT,
          next_run_at TEXT,
          last_status TEXT,
          last_error TEXT,
          last_delivery_outcome TEXT,
          last_delivery_reason TEXT,
          last_delivery_at TEXT,
          last_generated_text TEXT,
          last_delivery_json TEXT,
          metadata_json TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO scheduled_tasks (
          id, user_id, agent_id, prompt, schedule_json, channel, executor,
          conversation_policy, conversation_id, active, created_by, created_source,
          created_at, updated_at, updated_by, updated_source, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "schedule-1",
            "user-1",
            "agent-1",
            "synthetic reminder",
            '{"hour":9}',
            "telegram",
            "viventium_agent",
            "new",
            None,
            1,
            "user-1",
            "ui",
            "2026-07-01T00:00:00Z",
            "2026-07-01T00:00:00Z",
            "user-1",
            "ui",
            '{"timezone":"UTC"}',
        ),
    )
    connection.commit()
    connection.close()

    before, before_warnings = continuity_audit.read_schedule_summary(schedule_db)
    assert before_warnings == []
    assert before["configurationCount"] == 1
    assert len(before["configurationSha256"]) == 64

    connection = sqlite3.connect(schedule_db)
    connection.execute(
        """
        UPDATE scheduled_tasks
        SET updated_at = ?, last_run_at = ?, next_run_at = ?, last_status = ?,
            last_error = ?, last_delivery_outcome = ?, last_delivery_reason = ?,
            last_delivery_at = ?, last_generated_text = ?, last_delivery_json = ?
        WHERE id = ?
        """,
        (
            "2026-07-24T09:00:01Z",
            "2026-07-24T09:00:00Z",
            "2026-07-25T09:00:00Z",
            "success",
            None,
            "sent",
            "synthetic",
            "2026-07-24T09:00:01Z",
            "private generated output",
            '{"outcome":"sent"}',
            "schedule-1",
        ),
    )
    connection.commit()
    connection.close()

    after_runtime, after_runtime_warnings = continuity_audit.read_schedule_summary(schedule_db)
    assert after_runtime_warnings == []
    assert after_runtime["configurationSha256"] != before["configurationSha256"]

    connection = sqlite3.connect(schedule_db)
    connection.execute(
        "UPDATE scheduled_tasks SET prompt = ? WHERE id = ?",
        ("changed user reminder", "schedule-1"),
    )
    connection.commit()
    connection.close()

    after_user_change, _ = continuity_audit.read_schedule_summary(schedule_db)
    assert after_user_change["configurationSha256"] != after_runtime["configurationSha256"]


def test_strict_semantic_compare_rejects_protected_state_drift(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    base = {
        "schemaVersion": 2,
        "surfaces": {
            "messages": {"latestTimestamp": "2026-07-24T09:00:00Z"},
            "savedMemory": {"latestTimestamp": "2026-07-24T09:00:00Z"},
            "schedules": {"latestTimestamp": "2026-07-24T09:00:00Z"},
        },
        "semantic": {
            "config": {
                "available": True,
                "leafCount": 1,
                "leafDigests": ["0" * 64],
                "sha256": "0" * 64,
            },
            "mongo": {
                "available": True,
                "collections": {
                    "conversations": {"count": 2, "sha256": "a" * 64},
                    "messages": {"count": 4, "sha256": "b" * 64},
                },
            },
            "schedules": {
                "available": True,
                "configurationCount": 1,
                "configurationSha256": "c" * 64,
            },
        },
    }
    changed = json.loads(json.dumps(base))
    changed["semantic"]["mongo"]["collections"]["messages"]["count"] = 3
    snapshot_manifest.write_text(json.dumps(base), encoding="utf-8")
    live_manifest.write_text(json.dumps(changed), encoding="utf-8")

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
                "strict_semantic": True,
            },
        )()
    )

    assert result["status"] == "error"
    assert result["semanticDifferences"] == [
        {
            "field": "semantic.mongo.collections.messages.count",
            "snapshotValue": 4,
            "liveValue": 3,
        }
    ]
    assert any("protected continuity state changed" in error for error in result["errors"])


def test_emit_json_atomically_replaces_output_once(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    output = tmp_path / "continuity.json"
    output.write_text('{"stale":true}\n', encoding="utf-8")

    result = continuity_audit.emit_json({"status": "ok"}, str(output))

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "ok"}
    assert output.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob(".continuity.json.*.tmp")) == []


def test_emit_json_creates_private_output_directory_under_public_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    continuity_audit = load_continuity_audit_module()
    output = tmp_path / "state" / "continuity" / "audit.json"
    previous_umask = os.umask(0o022)
    try:
        result = continuity_audit.emit_json({"status": "ok"}, str(output))
    finally:
        os.umask(previous_umask)

    assert result == 0
    assert (tmp_path / "state").stat().st_mode & 0o777 == 0o700
    assert output.parent.stat().st_mode & 0o777 == 0o700
    assert output.stat().st_mode & 0o777 == 0o600


def test_strict_semantic_compare_allows_only_expired_ttl_documents_to_disappear(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    expired_digest = "1" * 64
    active_digest = "2" * 64
    durable_connection_digest = "3" * 64
    durable_mapping_digest = "4" * 64
    base = {
        "schemaVersion": 2,
        "capturedAt": "2026-07-24T09:00:00Z",
        "surfaces": {
            "messages": {"latestTimestamp": "2026-07-24T09:00:00Z"},
            "savedMemory": {"latestTimestamp": "2026-07-24T09:00:00Z"},
            "schedules": {"latestTimestamp": "2026-07-24T09:00:00Z"},
        },
        "semantic": {
            "config": {
                "available": True,
                "leafCount": 1,
                "leafDigests": ["0" * 64],
                "sha256": "0" * 64,
            },
            "mongo": {
                "available": True,
                "collections": {
                    "gatewaylinktokens": {
                        "count": 2,
                        "sha256": "a" * 64,
                        "ttl": {
                            "field": "expiresAt",
                            "expireAfterSeconds": 0,
                            "documents": [
                                {
                                    "sha256": expired_digest,
                                    "effectiveExpiryUnixMs": 1784883599000,
                                },
                                {
                                    "sha256": active_digest,
                                    "effectiveExpiryUnixMs": 1784887200000,
                                },
                            ],
                            "nonExpiring": {
                                "count": 0,
                                "sha256": hashlib.sha256().hexdigest(),
                            },
                        },
                    },
                    "channelconnections": {
                        "count": 1,
                        "sha256": durable_connection_digest,
                    },
                    "gatewayusermappings": {
                        "count": 1,
                        "sha256": durable_mapping_digest,
                    },
                },
            },
            "schedules": {
                "available": True,
                "configurationCount": 1,
                "configurationSha256": "5" * 64,
            },
        },
    }
    live = json.loads(json.dumps(base))
    live["capturedAt"] = "2026-07-24T09:05:00Z"
    live["semantic"]["mongo"]["collections"]["gatewaylinktokens"] = {
        "count": 1,
        "sha256": "b" * 64,
        "ttl": {
            "field": "expiresAt",
            "expireAfterSeconds": 0,
            "documents": [
                {
                    "sha256": active_digest,
                    "effectiveExpiryUnixMs": 1784887200000,
                }
            ],
            "nonExpiring": {
                "count": 0,
                "sha256": hashlib.sha256().hexdigest(),
            },
        },
    }
    snapshot_manifest.write_text(json.dumps(base), encoding="utf-8")
    live_manifest.write_text(json.dumps(live), encoding="utf-8")
    args = type(
        "Args",
        (),
        {
            "snapshot_manifest": str(snapshot_manifest),
            "live_manifest": str(live_manifest),
            "strict_semantic": True,
        },
    )()

    allowed = continuity_audit.compare_manifests(args)
    assert allowed["status"] == "ok"
    assert allowed["semanticDifferences"] == []

    live["semantic"]["mongo"]["collections"]["gatewaylinktokens"]["ttl"]["documents"] = []
    live["semantic"]["mongo"]["collections"]["gatewaylinktokens"]["count"] = 0
    live_manifest.write_text(json.dumps(live), encoding="utf-8")
    active_token_lost = continuity_audit.compare_manifests(args)
    assert active_token_lost["status"] == "error"
    assert active_token_lost["semanticDifferences"] == [
        {
            "field": (
                "semantic.mongo.collections.gatewaylinktokens."
                "unexpiredDocuments"
            ),
            "snapshotValue": 1,
            "liveValue": 0,
        }
    ]

    live = json.loads(json.dumps(base))
    live["capturedAt"] = "2026-07-24T09:05:00Z"
    live["semantic"]["mongo"]["collections"]["channelconnections"]["sha256"] = "6" * 64
    live_manifest.write_text(json.dumps(live), encoding="utf-8")
    durable_state_changed = continuity_audit.compare_manifests(args)
    assert durable_state_changed["status"] == "error"
    assert {
        "field": "semantic.mongo.collections.channelconnections.sha256",
        "snapshotValue": durable_connection_digest,
        "liveValue": "6" * 64,
    } in durable_state_changed["semanticDifferences"]

    malformed = json.loads(json.dumps(base))
    malformed["capturedAt"] = "2026-07-24T09:05:00Z"
    malformed["semantic"]["mongo"]["collections"]["gatewaylinktokens"]["ttl"][
        "documents"
    ][1]["sha256"] = "malformed"
    live_manifest.write_text(json.dumps(malformed), encoding="utf-8")
    malformed_ledger = continuity_audit.compare_manifests(args)
    assert malformed_ledger["status"] == "error"
    assert any(
        "mongo TTL lifecycle ledger (gatewaylinktokens)" in error
        for error in malformed_ledger["errors"]
    )

    missing_cutoff = json.loads(json.dumps(base))
    missing_cutoff.pop("capturedAt")
    live_manifest.write_text(json.dumps(missing_cutoff), encoding="utf-8")
    unavailable_cutoff = continuity_audit.compare_manifests(args)
    assert unavailable_cutoff["status"] == "error"
    assert any(
        "mongo TTL lifecycle ledger (gatewaylinktokens)" in error
        for error in unavailable_cutoff["errors"]
    )


def test_mongo_fingerprint_covers_user_agents_auth_and_channel_personalization() -> None:
    source = (
        REPO_ROOT / "scripts" / "viventium" / "continuity_mongo.cjs"
    ).read_text(encoding="utf-8")

    for collection in (
        "actions",
        "agentapikeys",
        "channelconnections",
        "channelpairingcodes",
        "channelthreads",
        "gatewaylinktokens",
        "gatewayusermappings",
        "mcpservers",
        "pluginauths",
        "telegramlinktokens",
    ):
        assert f"'{collection}'" in source
    assert "managedAgentIds(repoRoot, YAML)" in source
    assert "collections.useragents" in source
    assert "managed-agent-baseline-migration.json" in source
    assert "local.viventium-agents.yaml" in source
    assert "const fingerprintNames = [...present]" in source
    assert "!name.startsWith('system.')" in source
    assert "viventiumglasshivecallbackdeliveries" in source
    for lifecycle_collection in (
        "channeldeliveries",
        "channelingressquotas",
        "channelpairingattempts",
        "channelworkerleases",
        "viventiumgatewayingressevents",
        "viventiumtelegramingressevents",
        "viventiumvoiceingressevents",
    ):
        assert f"{lifecycle_collection}:" in source


def test_strict_compare_protects_unknown_future_mongo_collection_deletion(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    base = {
        "schemaVersion": 2,
        "surfaces": {
            "messages": {},
            "savedMemory": {},
            "schedules": {},
        },
        "semantic": {
            "config": {"available": True, "leafDigests": []},
            "mongo": {
                "available": True,
                "collections": {
                    "futurecustomstate": {
                        "count": 1,
                        "sha256": "a" * 64,
                    }
                },
            },
            "schedules": {
                "available": True,
                "configurationCount": 0,
                "configurationSha256": hashlib.sha256().hexdigest(),
            },
        },
    }
    live = json.loads(json.dumps(base))
    live["semantic"]["mongo"]["collections"] = {}
    snapshot_manifest.write_text(json.dumps(base), encoding="utf-8")
    live_manifest.write_text(json.dumps(live), encoding="utf-8")

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
                "strict_semantic": True,
            },
        )()
    )

    assert result["status"] == "error"
    assert {
        "field": "semantic.mongo.collections.futurecustomstate",
        "snapshotValue": {"count": 1, "sha256": "a" * 64},
        "liveValue": None,
    } in result["semanticDifferences"]


def test_strict_compare_protects_toolcalls_and_active_channel_delivery_ttl(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    active = "1" * 64
    expired = "2" * 64
    empty = hashlib.sha256().hexdigest()
    base = {
        "schemaVersion": 2,
        "capturedAt": "2026-07-24T10:00:00Z",
        "surfaces": {"messages": {}, "savedMemory": {}, "schedules": {}},
        "semantic": {
            "config": {"available": True, "leafDigests": []},
            "mongo": {
                "available": True,
                "collections": {
                    "toolcalls": {"count": 1, "sha256": "a" * 64},
                    "channeldeliveries": {
                        "count": 2,
                        "sha256": "b" * 64,
                        "ttl": {
                            "field": "expiresAt",
                            "expireAfterSeconds": 0,
                            "documents": [
                                {
                                    "sha256": expired,
                                    "effectiveExpiryUnixMs": 1784887199000,
                                },
                                {
                                    "sha256": active,
                                    "effectiveExpiryUnixMs": 1784890800000,
                                },
                            ],
                            "nonExpiring": {"count": 0, "sha256": empty},
                        },
                    },
                },
            },
            "schedules": {
                "available": True,
                "configurationCount": 0,
                "configurationSha256": empty,
            },
        },
    }
    live = json.loads(json.dumps(base))
    live["capturedAt"] = "2026-07-24T10:05:00Z"
    delivery = live["semantic"]["mongo"]["collections"]["channeldeliveries"]
    delivery["count"] = 1
    delivery["sha256"] = "c" * 64
    delivery["ttl"]["documents"] = [delivery["ttl"]["documents"][1]]
    snapshot_manifest.write_text(json.dumps(base), encoding="utf-8")
    live_manifest.write_text(json.dumps(live), encoding="utf-8")
    args = type(
        "Args",
        (),
        {
            "snapshot_manifest": str(snapshot_manifest),
            "live_manifest": str(live_manifest),
            "strict_semantic": True,
        },
    )()
    assert continuity_audit.compare_manifests(args)["status"] == "ok"

    live["semantic"]["mongo"]["collections"]["channeldeliveries"]["ttl"][
        "documents"
    ] = []
    live["semantic"]["mongo"]["collections"]["channeldeliveries"]["count"] = 0
    live["semantic"]["mongo"]["collections"].pop("toolcalls")
    live_manifest.write_text(json.dumps(live), encoding="utf-8")
    lost = continuity_audit.compare_manifests(args)
    assert lost["status"] == "error"
    assert any(
        difference["field"]
        == "semantic.mongo.collections.channeldeliveries.unexpiredDocuments"
        for difference in lost["semanticDifferences"]
    )
    assert any(
        difference["field"] == "semantic.mongo.collections.toolcalls"
        for difference in lost["semanticDifferences"]
    )


def test_schedule_fingerprint_protects_runtime_state_and_prompt_runs(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    database = tmp_path / "schedules.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE scheduled_tasks (
              id TEXT PRIMARY KEY,
              active INTEGER NOT NULL,
              last_conversation_id TEXT,
              next_run_at TEXT,
              last_status TEXT,
              last_delivery_outcome TEXT
            );
            CREATE TABLE scheduled_prompt_runs (
              id TEXT PRIMARY KEY,
              definition_id TEXT NOT NULL,
              status TEXT NOT NULL,
              delivered_at TEXT
            );
            INSERT INTO scheduled_tasks VALUES (
              'task-1', 1, 'conversation-1', '2026-07-25T10:00:00Z', 'ok', 'sent'
            );
            INSERT INTO scheduled_prompt_runs VALUES (
              'run-1', 'definition-1', 'delivered', '2026-07-24T10:00:00Z'
            );
            """
        )

    before, warnings = continuity_audit.read_schedule_summary(database)
    assert warnings == []
    assert before["configurationTables"] == {
        "scheduled_prompt_runs": 1,
        "scheduled_tasks": 1,
    }

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE scheduled_tasks
               SET last_conversation_id = NULL,
                   next_run_at = NULL,
                   last_status = 'pending',
                   last_delivery_outcome = NULL
             WHERE id = 'task-1'
            """
        )
        connection.execute("DELETE FROM scheduled_prompt_runs WHERE id = 'run-1'")

    after, warnings = continuity_audit.read_schedule_summary(database)
    assert warnings == []
    assert after["configurationCount"] == 1
    assert after["configurationSha256"] != before["configurationSha256"]


def test_strict_semantic_compare_fails_closed_when_fingerprints_are_unavailable(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    payload = {
        "schemaVersion": 2,
        "surfaces": {
            "messages": {"latestTimestamp": None},
            "savedMemory": {"latestTimestamp": None},
            "schedules": {"latestTimestamp": None},
        },
        "semantic": {
            "mongo": {"available": False, "collections": {}},
            "schedules": {"available": False},
        },
    }
    snapshot_manifest.write_text(json.dumps(payload), encoding="utf-8")
    live_manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
                "strict_semantic": True,
            },
        )()
    )

    assert result["status"] == "error"
    assert any("could not be proven" in error for error in result["errors"])


def test_config_semantic_fingerprint_allows_new_defaults_but_rejects_changed_personalization(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    before_config = tmp_path / "before.yaml"
    additive_config = tmp_path / "additive.yaml"
    changed_config = tmp_path / "changed.yaml"
    before_config.write_text(
        "version: 1\nllm:\n  primary:\n    model: synthetic-user-model\n",
        encoding="utf-8",
    )
    additive_config.write_text(
        "version: 1\nllm:\n  primary:\n    model: synthetic-user-model\n"
        "maintenance:\n  enabled: true\n",
        encoding="utf-8",
    )
    changed_config.write_text(
        "version: 1\nllm:\n  primary:\n    model: overwritten-model\n",
        encoding="utf-8",
    )
    before, before_warnings = continuity_audit.read_config_semantic_fingerprint(before_config)
    additive, additive_warnings = continuity_audit.read_config_semantic_fingerprint(additive_config)
    changed, changed_warnings = continuity_audit.read_config_semantic_fingerprint(changed_config)
    assert before_warnings == additive_warnings == changed_warnings == []
    assert set(before["leafDigests"]).issubset(additive["leafDigests"])
    assert not set(before["leafDigests"]).issubset(changed["leafDigests"])
    assert "synthetic-user-model" not in json.dumps(before)

    def manifest(config_semantic: dict) -> dict:
        return {
            "schemaVersion": 2,
            "surfaces": {
                "messages": {"latestTimestamp": None},
                "savedMemory": {"latestTimestamp": None},
                "schedules": {"latestTimestamp": None},
            },
            "semantic": {
                "config": config_semantic,
                "mongo": {"available": True, "collections": {}},
                "schedules": {
                    "available": True,
                    "configurationCount": 0,
                    "configurationSha256": "a" * 64,
                    "configurationTables": {},
                },
            },
        }

    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"
    snapshot_manifest.write_text(json.dumps(manifest(before)), encoding="utf-8")
    live_manifest.write_text(json.dumps(manifest(additive)), encoding="utf-8")
    additive_result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
                "strict_semantic": True,
            },
        )()
    )
    assert additive_result["status"] == "ok"

    live_manifest.write_text(json.dumps(manifest(changed)), encoding="utf-8")
    changed_result = continuity_audit.compare_manifests(
        type(
            "Args",
            (),
            {
                "snapshot_manifest": str(snapshot_manifest),
                "live_manifest": str(live_manifest),
                "strict_semantic": True,
            },
        )()
    )
    assert changed_result["status"] == "error"
    assert changed_result["semanticDifferences"][0]["field"] == (
        "semantic.config.protectedLeaves"
    )


def test_uploads_semantic_fingerprint_is_root_independent_and_private(tmp_path: Path) -> None:
    continuity_audit = load_continuity_audit_module()
    legacy = tmp_path / "legacy" / "uploads"
    canonical = tmp_path / "app-support" / "data" / "uploads"
    for root in (legacy, canonical):
        private = root / "synthetic-private-user" / "conversation"
        private.mkdir(parents=True)
        (private / "secret-name.txt").write_text(
            "synthetic private upload content\n",
            encoding="utf-8",
        )
        (root / "empty").mkdir()

    legacy_result, legacy_warnings = continuity_audit.read_uploads_semantic_fingerprint(legacy)
    canonical_result, canonical_warnings = continuity_audit.read_uploads_semantic_fingerprint(
        canonical
    )

    assert legacy_warnings == canonical_warnings == []
    assert legacy_result == canonical_result
    assert legacy_result["available"] is True
    assert legacy_result["fileCount"] == 1
    assert legacy_result["totalBytes"] == len(b"synthetic private upload content\n")
    rendered = json.dumps(legacy_result)
    assert "synthetic-private-user" not in rendered
    assert "secret-name.txt" not in rendered
    assert "synthetic private upload content" not in rendered


def test_uploads_semantic_fingerprint_rejects_unsafe_tree_without_leaking_path(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    private_name = "synthetic-private-link-name"
    (uploads / private_name).symlink_to(tmp_path / "outside")

    result, warnings = continuity_audit.read_uploads_semantic_fingerprint(uploads)

    assert result["available"] is False
    assert result["fileCount"] is None
    assert private_name not in json.dumps(result)
    assert private_name not in json.dumps(warnings)


def test_uploads_audit_uses_predecessor_until_migration_is_proven(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    legacy = repo / "viventium_v0_4" / "LibreChat" / "uploads"
    canonical = app_support / "data" / "uploads"
    legacy.mkdir(parents=True)
    (legacy / "legacy.txt").write_text("legacy\n", encoding="utf-8")
    canonical.mkdir(parents=True)
    runtime_env = {"VIVENTIUM_LIBRECHAT_UPLOADS_ROOT": str(canonical)}

    selected, warnings = continuity_audit.resolve_uploads_audit_root(
        repo_root=repo,
        app_support_dir=app_support,
        runtime_env=runtime_env,
    )
    assert selected == legacy
    assert warnings == []

    (canonical / "canonical.txt").write_text("canonical\n", encoding="utf-8")
    selected, warnings = continuity_audit.resolve_uploads_audit_root(
        repo_root=repo,
        app_support_dir=app_support,
        runtime_env=runtime_env,
    )
    assert selected is None
    assert warnings == [
        "Uploads semantic fingerprint failed: canonical and predecessor trees are both populated."
    ]


def test_strict_semantic_compare_gates_upload_content_and_unavailable_proof(
    tmp_path: Path,
) -> None:
    continuity_audit = load_continuity_audit_module()
    snapshot_manifest = tmp_path / "snapshot.json"
    live_manifest = tmp_path / "live.json"

    def manifest(uploads: dict) -> dict:
        return {
            "schemaVersion": 2,
            "surfaces": {
                "messages": {"latestTimestamp": None},
                "savedMemory": {"latestTimestamp": None},
                "schedules": {"latestTimestamp": None},
            },
            "semantic": {
                "config": {"available": True, "leafDigests": []},
                "mongo": {"available": True, "collections": {}},
                "schedules": {
                    "available": True,
                    "configurationCount": 0,
                    "configurationSha256": "a" * 64,
                    "configurationTables": {},
                },
                "uploads": uploads,
            },
        }

    protected = {
        "available": True,
        "fileCount": 1,
        "totalBytes": 9,
        "treeSha256": "b" * 64,
    }
    snapshot_manifest.write_text(json.dumps(manifest(protected)), encoding="utf-8")
    changed = dict(protected)
    changed["treeSha256"] = "c" * 64
    live_manifest.write_text(json.dumps(manifest(changed)), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "snapshot_manifest": str(snapshot_manifest),
            "live_manifest": str(live_manifest),
            "strict_semantic": True,
        },
    )()
    changed_result = continuity_audit.compare_manifests(args)
    assert changed_result["status"] == "error"
    assert changed_result["semanticDifferences"] == [
        {
            "field": "semantic.uploads.treeSha256",
            "snapshotValue": "b" * 64,
            "liveValue": "c" * 64,
        }
    ]

    live_manifest.write_text(
        json.dumps(
            manifest(
                {
                    "available": False,
                    "fileCount": None,
                    "totalBytes": None,
                    "treeSha256": None,
                }
            )
        ),
        encoding="utf-8",
    )
    unavailable_result = continuity_audit.compare_manifests(args)
    assert unavailable_result["status"] == "error"
    assert any("uploads" in error for error in unavailable_result["errors"])


def test_snapshot_wrapper_writes_manifest_without_private_helper(tmp_path: Path) -> None:
    home = tmp_path / "home"
    output_root = tmp_path / "snapshots"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(home / "Library" / "Application Support" / "Viventium")
    env.pop("VIVENTIUM_PRIVATE_REPO_DIR", None)

    result = subprocess.run(
        [str(SNAPSHOT_WRAPPER), "--output-root", str(output_root)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    latest_path = (output_root / "LATEST_PATH").read_text(encoding="utf-8").strip()
    manifest = Path(latest_path) / "continuity-manifest.json"
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["label"] == "snapshot"
    assert manifest.stat().st_mode & 0o777 == 0o600
    assert "metadata-only continuity audit" in result.stderr
    assert "No recoverable backup payload was created" in result.stderr


def test_snapshot_metadata_fallback_never_reuses_latest_snapshot(tmp_path: Path) -> None:
    home = tmp_path / "home"
    output_root = tmp_path / "snapshots"
    prior_snapshot = output_root / "20260717T120000Z"
    prior_snapshot.mkdir(parents=True)
    prior_manifest = prior_snapshot / "continuity-manifest.json"
    prior_manifest.write_text('{"sentinel": true}\n', encoding="utf-8")
    (output_root / "LATEST_PATH").write_text(f"{prior_snapshot}\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(home / "Library" / "Application Support" / "Viventium")
    env.pop("VIVENTIUM_PRIVATE_REPO_DIR", None)

    result = subprocess.run(
        [str(SNAPSHOT_WRAPPER), "--output-root", str(output_root)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    latest_path = Path((output_root / "LATEST_PATH").read_text(encoding="utf-8").strip())
    assert latest_path != prior_snapshot
    assert latest_path.parent == output_root
    assert (latest_path / ".viventium-metadata-only").read_text(encoding="utf-8") == "metadata-only\n"
    assert json.loads(prior_manifest.read_text(encoding="utf-8")) == {"sentinel": True}
    assert json.loads((latest_path / "continuity-manifest.json").read_text(encoding="utf-8"))["label"] == "snapshot"


def test_snapshot_manifest_failure_preserves_last_good_pointer(tmp_path: Path) -> None:
    home = tmp_path / "home"
    output_root = tmp_path / "snapshots"
    prior_snapshot = output_root / "20260717T120000Z"
    prior_snapshot.mkdir(parents=True)
    prior_manifest = prior_snapshot / "continuity-manifest.json"
    prior_manifest.write_text('{"sentinel": true}\n', encoding="utf-8")
    latest_pointer = output_root / "LATEST_PATH"
    latest_pointer.write_text(f"{prior_snapshot}\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
    fake_python.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(home / "Library" / "Application Support" / "Viventium")
    env["VIVENTIUM_PYTHON_BIN"] = str(fake_python)
    env.pop("VIVENTIUM_PRIVATE_REPO_DIR", None)

    result = subprocess.run(
        [str(SNAPSHOT_WRAPPER), "--output-root", str(output_root)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 42
    assert latest_pointer.read_text(encoding="utf-8").strip() == str(prior_snapshot)
    assert json.loads(prior_manifest.read_text(encoding="utf-8")) == {"sentinel": True}


def test_snapshot_private_helper_must_record_new_snapshot_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    output_root = tmp_path / "snapshots"
    prior_snapshot = output_root / "20260717T120000Z"
    prior_snapshot.mkdir(parents=True)
    prior_manifest = prior_snapshot / "continuity-manifest.json"
    prior_manifest.write_text('{"sentinel": true}\n', encoding="utf-8")
    (output_root / "LATEST_PATH").write_text(f"{prior_snapshot}\n", encoding="utf-8")

    private_repo = tmp_path / "private-repo"
    private_helper = private_repo / "viventium_v0_4" / "viventium-local-state-snapshot.sh"
    private_helper.parent.mkdir(parents=True)
    private_helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    private_helper.chmod(0o700)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(home / "Library" / "Application Support" / "Viventium")
    env["VIVENTIUM_PRIVATE_REPO_DIR"] = str(private_repo)

    result = subprocess.run(
        [str(SNAPSHOT_WRAPPER), "--output-root", str(output_root)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    latest_path = Path((output_root / "LATEST_PATH").read_text(encoding="utf-8").strip())
    assert latest_path != prior_snapshot
    assert (latest_path / ".viventium-metadata-only").exists()
    assert json.loads(prior_manifest.read_text(encoding="utf-8")) == {"sentinel": True}
    assert "did not record a new snapshot" in result.stderr
    assert "No recoverable backup payload was created" in result.stderr


def test_snapshot_private_helper_new_markerless_directory_is_not_published_as_backup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    output_root = tmp_path / "snapshots"
    private_repo = tmp_path / "private-repo"
    private_helper = private_repo / "viventium_v0_4" / "viventium-local-state-snapshot.sh"
    private_helper.parent.mkdir(parents=True)
    private_helper.write_text(
        '#!/bin/sh\nset -eu\nmkdir -p "$2/20990101T000000Z-empty"\n',
        encoding="utf-8",
    )
    private_helper.chmod(0o700)
    env = {
        **os.environ,
        "HOME": str(home),
        "VIVENTIUM_APP_SUPPORT_DIR": str(home / "Library" / "Application Support" / "Viventium"),
        "VIVENTIUM_PRIVATE_REPO_DIR": str(private_repo),
    }

    result = subprocess.run(
        [str(SNAPSHOT_WRAPPER), "--output-root", str(output_root)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    latest_path = Path((output_root / "LATEST_PATH").read_text(encoding="utf-8").strip())
    assert (latest_path / ".viventium-metadata-only").is_file()
    assert latest_path.name != "20990101T000000Z-empty"
    assert "did not create a structurally valid complete bundle" in result.stderr


def test_restore_refuses_metadata_only_latest_snapshot_before_live_audit(tmp_path: Path) -> None:
    config_home = tmp_path / "app-support"
    snapshot_dir = config_home / "snapshots" / "20260718T120000Z-metadata"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / ".viventium-metadata-only").write_text(
        "metadata-only\n",
        encoding="utf-8",
    )
    (config_home / "snapshots" / "LATEST_PATH").write_text(
        f"{snapshot_dir}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(RESTORE_SCRIPT), "--config-home", str(config_home)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "metadata-only continuity audit" in result.stderr
    assert "not a recoverable backup" in result.stderr
    assert "--snapshot-dir pointing to a complete bundle candidate" in result.stderr
    assert not (config_home / "state").exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_refuses_explicit_metadata_only_snapshot(tmp_path: Path) -> None:
    config_home = tmp_path / "app-support"
    snapshot_dir = tmp_path / "metadata-snapshot"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / ".viventium-metadata-only").write_text(
        "metadata-only\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--config-home",
            str(config_home),
            "--snapshot-dir",
            str(snapshot_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "metadata-only continuity audit" in result.stderr
    assert "not a recoverable backup" in result.stderr
    assert "--snapshot-dir pointing to a complete bundle candidate" in result.stderr
    assert not (config_home / "state").exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_refuses_markerless_snapshot_before_marking_recall_stale(tmp_path: Path) -> None:
    config_home = tmp_path / "app-support"
    runtime_dir = config_home / "runtime"
    snapshot_dir = tmp_path / "snapshot"
    runtime_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--config-home",
            str(config_home),
            "--snapshot-dir",
            str(snapshot_dir),
            "--mark-recall-stale",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    marker = (
        config_home
        / "state"
        / "runtime"
        / "isolated"
        / "continuity"
        / "recall-rebuild-required.json"
    )
    assert not marker.exists()
    assert "positive producer completeness marker is missing" in result.stderr
    assert "before creating or changing target state" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_does_not_trust_or_apply_unchecksummed_legacy_age_metadata(tmp_path: Path) -> None:
    config_home = tmp_path / "app-support"
    runtime_dir = config_home / "runtime"
    schedule_db = config_home / "state" / "runtime" / "isolated" / "scheduling" / "schedules.db"
    snapshot_dir = tmp_path / "snapshot"
    runtime_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        f"SCHEDULING_DB_PATH={schedule_db}\n",
        encoding="utf-8",
    )

    schedule_db.parent.mkdir(parents=True)
    connection = sqlite3.connect(schedule_db)
    connection.execute(
        "CREATE TABLE scheduled_tasks (active INTEGER NOT NULL, updated_at TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO scheduled_tasks (active, updated_at) VALUES (?, ?)",
        (1, "2026-04-12T00:00:00+00:00"),
    )
    connection.commit()
    connection.close()

    (snapshot_dir / "continuity-manifest.json").write_text(
        json.dumps(
            {
                "surfaces": {
                    "messages": {"latestTimestamp": None},
                    "savedMemory": {"latestTimestamp": None},
                    "schedules": {"latestTimestamp": "2026-04-11T00:00:00+00:00"},
                    "recall": {"rebuildRequired": False},
                },
            }
        ),
        encoding="utf-8",
    )
    write_test_recoverable_bundle(snapshot_dir)

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--config-home",
            str(config_home),
            "--snapshot-dir",
            str(snapshot_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4
    assert "explicit empty independent App Support target" in result.stderr
    assert "Target state was not changed" in result.stderr
    assert schedule_db.is_file()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_refuses_telegram_apply_before_touching_live_channel_state(tmp_path: Path) -> None:
    config_home = tmp_path / "app-support"
    runtime_dir = config_home / "runtime"
    snapshot_dir = tmp_path / "snapshot"
    telegram_target = tmp_path / "telegram-target"
    fake_bin = tmp_path / "bin"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n",
        encoding="utf-8",
    )
    (snapshot_dir / "telegram" / "user_configs").mkdir(parents=True)
    (snapshot_dir / "telegram" / "user_configs" / "copied.json").write_text("{}", encoding="utf-8")
    write_test_recoverable_bundle(snapshot_dir, include_telegram=True)
    telegram_target.mkdir(parents=True)
    (telegram_target / "live.json").write_text("{}", encoding="utf-8")
    fake_bin.mkdir(parents=True)
    cp_wrapper = fake_bin / "cp"
    cp_wrapper.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *restore-backups*) exit 1 ;;\n"
        "  *) exec /bin/cp \"$@\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    cp_wrapper.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR"] = str(telegram_target)

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--config-home",
            str(config_home),
            "--snapshot-dir",
            str(snapshot_dir),
            "--apply-telegram",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4
    assert "credentials require reauthentication" in result.stderr
    assert "Target state was not changed" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr
    assert (telegram_target / "live.json").exists()
    assert not (telegram_target / "copied.json").exists()
