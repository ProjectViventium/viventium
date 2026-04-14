from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "scripts" / "viventium" / "continuity_audit.py"
SNAPSHOT_WRAPPER = REPO_ROOT / "viventium_v0_4" / "viventium-local-state-snapshot.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "restore.sh"


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
    assert not str(Path.home()) in json.dumps(result)


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
    assert "metadata-only continuity snapshot" in result.stderr


def test_restore_can_mark_recall_stale_without_snapshot_manifest(tmp_path: Path) -> None:
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

    assert result.returncode == 0
    marker = (
        config_home
        / "state"
        / "runtime"
        / "isolated"
        / "continuity"
        / "recall-rebuild-required.json"
    )
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["reason"] == "restore-follow-through"
    assert payload["snapshotLabel"] == "<local>/snapshot"
    assert "snapshotDir" not in payload
    assert "age comparison is unavailable" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_refuses_older_snapshot_without_override(tmp_path: Path) -> None:
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
    assert "Refusing to apply an older continuity snapshot" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_fails_when_telegram_safety_backup_cannot_be_written(tmp_path: Path) -> None:
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

    assert result.returncode == 1
    assert "Failed to back up current Telegram user configs" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr
    assert (telegram_target / "live.json").exists()
