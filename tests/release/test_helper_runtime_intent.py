from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "helper_runtime_intent.py"
CLI = REPO_ROOT / "bin" / "viventium"


def load_module():
    spec = importlib.util.spec_from_file_location("helper_runtime_intent", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_intent_update_is_atomic_private_and_preserves_helper_binding(
    tmp_path: Path,
) -> None:
    module = load_module()
    config = tmp_path / "helper-config.json"
    config.write_text(
        json.dumps(
            {
                "repoRoot": "/synthetic/repo",
                "appSupportDir": "/synthetic/app-support",
                "showInStatusBar": False,
                "runtimeSupervision": {
                    "schemaVersion": 1,
                    "desiredState": "running",
                    "consecutiveLaunchAttempts": 7,
                    "nextLaunchAttemptAt": "2026-07-24T10:00:00Z",
                    "healthySince": None,
                },
            }
        ),
        encoding="utf-8",
    )

    assert module.update_runtime_intent(config, "stopped") is True
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["repoRoot"] == "/synthetic/repo"
    assert payload["showInStatusBar"] is False
    assert payload["runtimeSupervision"] == {
        "schemaVersion": 1,
        "desiredState": "stopped",
        "consecutiveLaunchAttempts": 0,
        "nextLaunchAttemptAt": None,
        "healthySince": None,
    }
    assert stat.S_IMODE(config.stat().st_mode) == 0o600

    assert module.update_runtime_intent(config, "running") is True
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["runtimeSupervision"]["desiredState"] == "running"


def test_runtime_intent_refuses_symlinked_helper_config(tmp_path: Path) -> None:
    module = load_module()
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    config = tmp_path / "helper-config.json"
    config.symlink_to(target)

    with pytest.raises(module.HelperIntentError, match="owner-controlled regular file"):
        module.update_runtime_intent(config, "stopped")
    assert target.read_text(encoding="utf-8") == "{}\n"


def test_cli_start_launch_stop_share_helper_runtime_intent() -> None:
    source = CLI.read_text(encoding="utf-8")
    start = source.rsplit("  start)", 1)[1].split("  stop)", 1)[0]
    launch = source.rsplit("  launch)", 1)[1].split("  install-helper)", 1)[0]
    stop = source.rsplit("  stop)", 1)[1].split("  snapshot)", 1)[0]

    assert "set_helper_runtime_intent running" in start
    assert start.index("set_helper_runtime_intent running") < start.index("bootstrap_components")
    assert 'VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT:-0' in start
    assert start.index(
        'VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT:-0'
    ) < start.index("set_helper_runtime_intent running")
    assert "set_helper_runtime_intent running" in launch
    assert 'VIVENTIUM_DETACHED_START:-false' in launch
    assert launch.index("set_helper_runtime_intent running") < launch.index("launch_stack_detached")
    assert "set_helper_runtime_intent stopped" in stop
    assert 'VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT:-0' in stop
    assert stop.index(
        'VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT:-0'
    ) < stop.index("set_helper_runtime_intent stopped")
    assert stop.index("set_helper_runtime_intent stopped") < stop.index(
        "viventium-librechat-start.sh"
    )
