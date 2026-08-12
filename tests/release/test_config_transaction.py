from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSACTION_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "config_transaction.py"
CLI = REPO_ROOT / "bin" / "viventium"


def run_transaction(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TRANSACTION_SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def replace_secret_references_with_synthetic_values(node: object) -> None:
    if isinstance(node, dict):
        if "secret_ref" in node:
            node.pop("secret_ref")
            node["secret_value"] = "synthetic-non-secret"
        for value in node.values():
            replace_secret_references_with_synthetic_values(value)
    elif isinstance(node, list):
        for value in node:
            replace_secret_references_with_synthetic_values(value)


def test_prepare_merges_input_over_existing_without_dropping_unknown_fields(tmp_path: Path) -> None:
    existing = tmp_path / "existing.yaml"
    incoming = tmp_path / "incoming.yaml"
    candidate = tmp_path / "candidate.yaml"
    existing.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "profile": "isolated",
                    "auth": {"allow_registration": False},
                    "future_runtime_field": {"preserve_me": True},
                },
                "integrations": {"telegram": {"enabled": True}},
                "future_top_level": {"owner_choice": "keep"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    incoming.write_text(
        yaml.safe_dump(
            {
                "runtime": {"profile": "compat"},
                "integrations": {"telegram": {"enabled": False}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_transaction(
        "prepare",
        "--existing",
        str(existing),
        "--input",
        str(incoming),
        "--output",
        str(candidate),
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    assert payload["runtime"]["profile"] == "compat"
    assert payload["runtime"]["auth"]["allow_registration"] is False
    assert payload["runtime"]["future_runtime_field"] == {"preserve_me": True}
    assert payload["integrations"]["telegram"]["enabled"] is False
    assert payload["future_top_level"] == {"owner_choice": "keep"}


def test_apply_creates_private_backup_and_atomic_candidate_copy(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    candidate = tmp_path / "candidate.yaml"
    backup_dir = tmp_path / "backups"
    config.write_text("runtime:\n  profile: isolated\n", encoding="utf-8")
    config.chmod(0o600)
    candidate.write_text("runtime:\n  profile: compat\n", encoding="utf-8")

    result = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(backup_dir),
    )

    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    backup = Path(status["backup_path"])
    assert status["had_existing"] is True
    assert yaml.safe_load(config.read_text(encoding="utf-8"))["runtime"]["profile"] == "compat"
    assert backup.read_text(encoding="utf-8") == "runtime:\n  profile: isolated\n"
    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup_dir.stat().st_mode & 0o777 == 0o700
    assert config.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".config.yaml.*.tmp"))


def test_rollback_restores_prior_config_atomically(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    candidate = tmp_path / "candidate.yaml"
    backup_dir = tmp_path / "backups"
    config.write_text("owner: preserved\n", encoding="utf-8")
    candidate.write_text("owner: changed\n", encoding="utf-8")

    applied = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(backup_dir),
    )
    assert applied.returncode == 0, applied.stderr
    status = json.loads(applied.stdout)

    rolled_back = run_transaction(
        "rollback",
        "--config",
        str(config),
        "--backup",
        status["backup_path"],
        "--had-existing",
        "true",
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert config.read_text(encoding="utf-8") == "owner: preserved\n"
    assert config.stat().st_mode & 0o777 == 0o600


def test_cli_headless_paths_use_candidate_instead_of_direct_canonical_output() -> None:
    source = CLI.read_text(encoding="utf-8")

    assert "prepare_config_candidate" in source
    assert "apply_config_candidate" in source
    assert "rollback_config_candidate" in source
    assert 'WIZARD_ARGS=(--output "$CONFIG_CANDIDATE_FILE")' in source
    assert 'scripts/viventium/config_transaction.py' in source


def test_headless_configure_preserves_existing_fields_and_compiles_candidate(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_support = home / "Library" / "Application Support" / "Viventium"
    config = app_support / "config.yaml"
    runtime = app_support / "runtime"
    app_support.mkdir(parents=True)

    existing = yaml.safe_load((REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8"))
    replace_secret_references_with_synthetic_values(existing)
    existing["runtime"]["memory_hardening"]["enabled"] = False
    existing["runtime"]["future_runtime_field"] = {"preserve_me": True}
    existing["future_top_level"] = {"owner_choice": "keep"}
    config.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")

    incoming = tmp_path / "incoming.yaml"
    incoming.write_text("runtime:\n  log_level: debug\n", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        "VIVENTIUM_CONFIG_FILE": str(config),
        "VIVENTIUM_RUNTIME_DIR": str(runtime),
        "VIVENTIUM_PYTHON_BIN": sys.executable,
    }

    result = subprocess.run(
        [str(CLI), "configure", "--headless", "--config-input", str(incoming)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    updated = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert updated["runtime"]["log_level"] == "debug"
    assert updated["runtime"]["future_runtime_field"] == {"preserve_me": True}
    assert updated["future_top_level"] == {"owner_choice": "keep"}
    assert (runtime / "runtime.env").is_file()
    backups = list((app_support / "state" / "config-backups").glob("config-*.yaml"))
    assert len(backups) == 1
    assert yaml.safe_load(backups[0].read_text(encoding="utf-8"))["runtime"]["log_level"] == "info"
    assert not list((app_support / "state" / "config-candidates").glob("attempt.*"))


def test_headless_configure_validation_failure_leaves_canonical_config_unchanged(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_support = home / "Library" / "Application Support" / "Viventium"
    config = app_support / "config.yaml"
    runtime = app_support / "runtime"
    app_support.mkdir(parents=True)

    existing = yaml.safe_load((REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8"))
    replace_secret_references_with_synthetic_values(existing)
    existing["runtime"]["memory_hardening"]["enabled"] = False
    existing["future_top_level"] = {"owner_choice": "keep"}
    config.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")
    before = config.read_bytes()

    incoming = tmp_path / "invalid.yaml"
    incoming.write_text(
        "integrations:\n"
        "  telegram_codex:\n"
        "    enabled: false\n"
        "    secret_value: synthetic-dormant-token\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        "VIVENTIUM_CONFIG_FILE": str(config),
        "VIVENTIUM_RUNTIME_DIR": str(runtime),
        "VIVENTIUM_PYTHON_BIN": sys.executable,
    }

    result = subprocess.run(
        [str(CLI), "configure", "--headless", "--config-input", str(incoming)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "Config candidate was not created" in result.stderr
    assert config.read_bytes() == before
    assert not any(runtime.iterdir())
    assert not (app_support / "state" / "config-backups").exists()
    assert not list((app_support / "state" / "config-candidates").glob("attempt.*"))
