from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "viventium" / "default_nightly_routines.py"
HOST_CLI_AUTH_PATH = REPO_ROOT / "scripts" / "viventium" / "host_cli_auth.py"


def load_module():
    spec = importlib.util.spec_from_file_location("default_nightly_routines", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_defaults_fill_missing_nightly_fields_without_overriding_glasshive_disable(
    monkeypatch,
) -> None:
    module = load_module()
    monkeypatch.setattr(module, "detect_worker_profile", lambda: "")

    config = {
        "version": 1,
        "runtime": {"personalization": {"default_conversation_recall": False}},
        "integrations": {"glasshive": {"enabled": False}},
    }

    updated, changed = module.ensure_default_nightly_routines(config)

    assert changed is True
    runtime = updated["runtime"]
    assert runtime["nightly_routines"]["defaults_version"] == 1
    assert runtime["prompt_workbench"]["enabled"] is True
    assert runtime["prompt_workbench"]["seed_nightly"] == {
        "enabled": True,
        "active": True,
        "executor": "glasshive_host",
    }
    assert runtime["memory_hardening"]["enabled"] is True
    assert runtime["memory_hardening"]["operator_user_email"] == ""
    assert "owner-specific-name" not in str(updated).lower()
    assert updated["integrations"]["glasshive"]["enabled"] is False
    assert updated["integrations"]["glasshive"]["host_worker"]["enabled"] is True


def test_auto_worker_profile_uses_logged_in_claude_when_codex_is_not_ready(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "detect_worker_profile", lambda: "claude-code")

    config = {
        "version": 1,
        "runtime": {"nightly_routines": {"defaults_version": 1, "auto_worker_profile": True}},
        "integrations": {"glasshive": {"enabled": True, "host_worker": {"enabled": True}}},
    }

    updated, changed = module.ensure_default_nightly_routines(config)

    assert changed is True
    assert updated["integrations"]["glasshive"]["host_worker"]["default_worker_profile"] == "claude-code"
    assert "provider" not in updated["runtime"].get("memory_hardening", {})


def test_auto_worker_profile_preserves_explicit_user_worker_choice(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "detect_worker_profile", lambda: "codex-cli")

    config = {
        "version": 1,
        "runtime": {
            "nightly_routines": {"defaults_version": 1, "auto_worker_profile": True},
            "memory_hardening": {"provider": "anthropic"},
        },
        "integrations": {
            "glasshive": {
                "enabled": True,
                "host_worker": {"enabled": True, "default_worker_profile": "claude-code"},
            }
        },
    }

    updated, changed = module.ensure_default_nightly_routines(config)

    assert changed is False
    assert updated["integrations"]["glasshive"]["host_worker"]["default_worker_profile"] == "claude-code"
    assert updated["runtime"]["memory_hardening"]["provider"] == "anthropic"


def test_defaults_marker_respects_later_user_disable(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "detect_worker_profile", lambda: "")

    config = {
        "version": 1,
        "runtime": {
            "nightly_routines": {"defaults_version": 1, "auto_worker_profile": False},
            "prompt_workbench": {"enabled": False},
            "memory_hardening": {"enabled": False},
        },
        "integrations": {"glasshive": {"enabled": False}},
    }

    updated, changed = module.ensure_default_nightly_routines(config)

    assert changed is False
    assert updated["runtime"]["prompt_workbench"]["enabled"] is False
    assert updated["runtime"]["memory_hardening"]["enabled"] is False
    assert updated["integrations"]["glasshive"]["enabled"] is False


def test_first_seen_defaults_preserve_every_explicit_leaf_and_unknown_config(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "detect_worker_profile", lambda: "codex-cli")

    config = {
        "version": 1,
        "runtime": {
            "nightly_routines": {
                "enabled": False,
                "auto_worker_profile": False,
                "owner_note": "",
            },
            "prompt_workbench": {
                "enabled": False,
                "seed_nightly": {
                    "enabled": False,
                    "active": False,
                    "executor": "",
                    "owner_extension": {"mode": "manual"},
                },
            },
            "memory_hardening": {
                "enabled": False,
                "schedule": "",
                "operator_user_email": "",
                "dry_run_first": False,
            },
            "owner_runtime_extension": {"enabled": False, "value": ""},
        },
        "integrations": {
            "glasshive": {
                "enabled": False,
                "host_worker": {
                    "enabled": False,
                    "workspace_root": "",
                    "default_execution_mode": "",
                    "default_worker_profile": "",
                    "owner_extension": False,
                },
            },
            "owner_integration_extension": {"enabled": False, "value": ""},
        },
        "owner_top_level_extension": {"enabled": False, "value": ""},
    }

    updated, changed = module.ensure_default_nightly_routines(config)

    assert changed is True
    assert updated["runtime"]["nightly_routines"] == {
        "enabled": False,
        "auto_worker_profile": False,
        "owner_note": "",
        "defaults_version": 1,
    }
    assert updated["runtime"]["prompt_workbench"] == {
        "enabled": False,
        "seed_nightly": {
            "enabled": False,
            "active": False,
            "executor": "",
            "owner_extension": {"mode": "manual"},
        },
    }
    assert updated["runtime"]["memory_hardening"] == {
        "enabled": False,
        "schedule": "",
        "operator_user_email": "",
        "dry_run_first": False,
    }
    assert updated["integrations"]["glasshive"] == {
        "enabled": False,
        "host_worker": {
            "enabled": False,
            "workspace_root": "",
            "default_execution_mode": "",
            "default_worker_profile": "",
            "owner_extension": False,
        },
    }
    assert updated["runtime"]["owner_runtime_extension"] == {
        "enabled": False,
        "value": "",
    }
    assert updated["integrations"]["owner_integration_extension"] == {
        "enabled": False,
        "value": "",
    }
    assert updated["owner_top_level_extension"] == {
        "enabled": False,
        "value": "",
    }


def test_cli_write_preserves_first_seen_personalization_and_noop_is_byte_exact(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "# owner comment must survive a no-op\n"
        "version: 1\n"
        "runtime:\n"
        "  nightly_routines:\n"
        "    enabled: false\n"
        "    auto_worker_profile: false\n"
        "  prompt_workbench:\n"
        "    enabled: false\n"
        "    seed_nightly:\n"
        "      enabled: false\n"
        "      active: false\n"
        "      executor: ''\n"
        "  memory_hardening:\n"
        "    enabled: false\n"
        "    schedule: ''\n"
        "integrations:\n"
        "  glasshive:\n"
        "    enabled: false\n"
        "    host_worker:\n"
        "      enabled: false\n"
        "      default_worker_profile: ''\n"
        "owner_extension:\n"
        "  enabled: false\n"
        "  value: ''\n",
        encoding="utf-8",
    )
    config_path.chmod(0o640)

    first = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--config",
            str(config_path),
            "--write",
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": ""},
    )

    assert first.returncode == 0, first.stderr
    migrated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert migrated["runtime"]["nightly_routines"]["enabled"] is False
    assert migrated["runtime"]["nightly_routines"]["auto_worker_profile"] is False
    assert migrated["runtime"]["prompt_workbench"]["enabled"] is False
    assert migrated["runtime"]["prompt_workbench"]["seed_nightly"] == {
        "enabled": False,
        "active": False,
        "executor": "",
    }
    assert migrated["runtime"]["memory_hardening"] == {
        "enabled": False,
        "schedule": "",
        "operator_user_email": "",
        "dry_run_first": True,
    }
    assert migrated["integrations"]["glasshive"] == {
        "enabled": False,
        "host_worker": {
            "enabled": False,
            "default_worker_profile": "",
            "workspace_root": "~/viventium",
            "default_execution_mode": "host",
        },
    }
    assert migrated["owner_extension"] == {"enabled": False, "value": ""}
    assert migrated["runtime"]["nightly_routines"]["defaults_version"] == 1
    assert config_path.stat().st_mode & 0o777 == 0o640

    after_migration = config_path.read_bytes()
    fixed_mtime_ns = 1_700_000_000_000_000_000
    os.utime(config_path, ns=(fixed_mtime_ns, fixed_mtime_ns))
    second = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--config",
            str(config_path),
            "--write",
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": ""},
    )

    assert second.returncode == 0, second.stderr
    assert config_path.read_bytes() == after_migration
    assert config_path.stat().st_mtime_ns == fixed_mtime_ns
    assert config_path.stat().st_mode & 0o777 == 0o640


def test_claude_auth_detection_fails_closed_on_malformed_status(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("host_cli_auth", HOST_CLI_AUTH_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Completed:
        returncode = 0
        stdout = "Not logged in"

    monkeypatch.setattr(module, "host_cli_command", lambda command: "/usr/local/bin/claude" if command == "claude" else "")
    monkeypatch.setattr(module, "run_status", lambda *_args, **_kwargs: Completed())

    assert module.host_cli_auth_ready("claude") is False
