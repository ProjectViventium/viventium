from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "viventium" / "default_nightly_routines.py"
HOST_CLI_AUTH_PATH = REPO_ROOT / "scripts" / "viventium" / "host_cli_auth.py"


def load_module():
    spec = importlib.util.spec_from_file_location("default_nightly_routines", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_defaults_enable_glasshive_workbench_memory_without_private_user(monkeypatch) -> None:
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
    assert updated["integrations"]["glasshive"]["enabled"] is True
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
