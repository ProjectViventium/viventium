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
