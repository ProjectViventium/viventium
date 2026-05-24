from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def minimal_config() -> dict:
    return {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret"},
            "personalization": {"default_conversation_recall": False},
            "memory_hardening": {
                "enabled": False,
                "transcripts": {"source_dir": ""},
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }


def write_config(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_transcripts_source_cli_sets_config_backs_up_and_compiles(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    config_path = app_support / "config.yaml"
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    write_config(config_path, minimal_config())

    result = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "--runtime-dir",
            str(runtime_dir),
            "transcripts",
            "source",
            "set",
            str(transcript_dir),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["source_dir"] == str(transcript_dir.resolve())
    assert Path(payload["backup_path"]).exists()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["runtime"]["memory_hardening"]["transcripts"]["source_dir"] == str(
        transcript_dir.resolve()
    )
    runtime_env = (runtime_dir / "runtime.env").read_text(encoding="utf-8")
    assert f"VIVENTIUM_MEMORY_TRANSCRIPTS_DIR={transcript_dir.resolve()}" in runtime_env


def test_transcripts_source_cli_clear_and_status(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    runtime_dir = app_support / "runtime"
    config_path = app_support / "config.yaml"
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    config = minimal_config()
    config["runtime"]["memory_hardening"]["transcripts"]["source_dir"] = str(transcript_dir)
    write_config(config_path, config)

    clear = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "--runtime-dir",
            str(runtime_dir),
            "transcripts",
            "source",
            "clear",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert clear.returncode == 0, clear.stderr
    assert json.loads(clear.stdout)["changed"] is True

    status = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "--runtime-dir",
            str(runtime_dir),
            "transcripts",
            "source",
            "status",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["status"] == "not_configured"
    assert payload["source_dir"] == ""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["runtime"]["memory_hardening"]["transcripts"]["source_dir"] == ""


def test_transcripts_source_help_is_side_effect_free(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    config_path = app_support / "config.yaml"
    write_config(config_path, minimal_config())
    before = config_path.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "transcripts",
            "--help",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "transcripts source set" in result.stdout
    assert config_path.read_text(encoding="utf-8") == before
    assert not (app_support / "runtime" / "runtime.env").exists()


def test_transcripts_source_status_works_while_lock_exists(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    config_path = app_support / "config.yaml"
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    config = minimal_config()
    config["runtime"]["memory_hardening"]["transcripts"]["source_dir"] = str(transcript_dir)
    write_config(config_path, config)
    lock_dir = app_support / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    (lock_dir / "command").write_text("upgrade\n", encoding="utf-8")

    result = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "transcripts",
            "source",
            "status",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["source_dir"] == str(transcript_dir.resolve())


def test_transcripts_source_set_respects_active_mutation_lock(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    config_path = app_support / "config.yaml"
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    write_config(config_path, minimal_config())
    lock_dir = app_support / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    (lock_dir / "command").write_text("upgrade\n", encoding="utf-8")

    result = subprocess.run(
        [
            str(ROOT / "bin/viventium"),
            "--app-support-dir",
            str(app_support),
            "--config-file",
            str(config_path),
            "transcripts",
            "source",
            "set",
            str(transcript_dir),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Another Viventium CLI operation is already running (upgrade" in result.stderr
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["runtime"]["memory_hardening"]["transcripts"]["source_dir"] == ""


def test_config_settings_rejects_non_directory_without_backup(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    backup_dir = tmp_path / "backups"
    write_config(config_path, minimal_config())
    not_a_dir = tmp_path / "not-a-dir.txt"
    not_a_dir.write_text("not a folder\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/viventium/config_settings.py"),
            "--config-file",
            str(config_path),
            "--backup-dir",
            str(backup_dir),
            "transcripts-source-set",
            str(not_a_dir),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must be a folder" in result.stderr
    assert not backup_dir.exists()
