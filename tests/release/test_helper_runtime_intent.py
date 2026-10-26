from __future__ import annotations

import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
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
    revision = payload["runtimeSupervision"].pop("intentRevision")
    assert len(revision) == 32
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
    assert payload["runtimeSupervision"]["intentRevision"] != revision
    previous = payload["runtimeSupervision"]["intentRevision"]
    assert module.update_runtime_intent(config, "running") is True
    assert json.loads(config.read_text())["runtimeSupervision"]["intentRevision"] != previous


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


@pytest.mark.parametrize("binding,allowed", [
    ("running", True), ("absent", True), ("stopped", False),
    ("unbound", False), ("foreign-repo", False), ("foreign-support", False),
    ("symlink", False),
])
@pytest.mark.parametrize("assert_quiesced", [False, True], ids=["ordinary", "unverified-quiesced-assertion"])
def test_automatic_start_requires_verified_same_owner_running_intent(
    tmp_path: Path, binding: str, allowed: bool, assert_quiesced: bool,
) -> None:
    repo, support = tmp_path / "repo", tmp_path / "support"
    repo.mkdir()
    support.mkdir(mode=0o700)
    config = support / "helper-config.json"
    value = {"repoRoot": str(repo), "appSupportDir": str(support),
             "runtimeSupervision": {"desiredState": "stopped" if binding == "stopped" else "running",
                                    "intentRevision": "b" * 32, "consecutiveLaunchAttempts": 7,
                                    "nextLaunchAttemptAt": "2026-07-24T10:00:00Z", "healthySince": None}}
    if binding == "unbound":
        value.pop("repoRoot")
        value.pop("appSupportDir")
    elif binding == "foreign-repo":
        value["repoRoot"] = str(tmp_path / "other-repo")
    elif binding == "foreign-support":
        value["appSupportDir"] = str(tmp_path / "other-support")
    before = (json.dumps(value) + "\n").encode()
    target = tmp_path / "unrelated.json"
    if binding == "symlink":
        target.write_bytes(before)
        config.symlink_to(target)
    elif binding != "absent":
        config.write_bytes(before)
        config.chmod(0o600)
    source = CLI.read_text()
    definition = "helper_runtime_intent_allows_start() {\n" + source.split(
        "helper_runtime_intent_allows_start() {\n", 1,
    )[1].split("\nruntime_owned_recovery_needed() {", 1)[0]
    script = definition + (
        f"\nAPP_SUPPORT_DIR={shlex.quote(str(support))}\n"
        f"REPO_ROOT={shlex.quote(str(repo))}\nPYTHON_BIN={shlex.quote(sys.executable)}\n"
        "helper_runtime_intent_allows_start\n"
    )
    assertions = {
        "VIVENTIUM_SUCCESSOR_VALIDATION_MODE": "quiesced",
        "VIVENTIUM_SUCCESSOR_VALIDATION_INTERNAL": "1",
        "VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL": "1",
        "VIVENTIUM_CLI_LOCK_HELD": "1",
        "VIVENTIUM_CLI_LOCK_DIR": str(tmp_path / "unverified-lock"),
        "VIVENTIUM_CLI_LOCK_OWNER_PID": "999999",
    } if assert_quiesced else {}
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=5,
                            env={**os.environ, **assertions})
    assert result.returncode == (0 if allowed else 1)
    assert result.stdout == result.stderr == ""
    if binding != "absent":
        assert config.read_bytes() == before
    if binding == "symlink":
        assert target.read_bytes() == before


@pytest.mark.parametrize("lock_state,allowed", [
    ("absent", False), ("dead", False), ("mismatch", False),
    ("self", False), ("verified-parent", True),
])
def test_quiesced_start_assertions_require_live_inherited_parent_lock(
    tmp_path: Path, lock_state: str, allowed: bool,
) -> None:
    source = CLI.read_text()
    lock = "verified_parent_cli_lock() {\n" + source.split(
        "verified_parent_cli_lock() {\n", 1,
    )[1].split("\nacquire_cli_lock() {", 1)[0]
    guard = "quiesced_helper_runtime_intent_allows_start() {\n" + source.split(
        "quiesced_helper_runtime_intent_allows_start() {\n", 1,
    )[1].split("\npreserve_active_quiesced_stop_intent() {", 1)[0]
    repo, support = tmp_path / "repo", tmp_path / "support"
    (repo / "scripts" / "viventium").mkdir(parents=True)
    support.mkdir()
    marker = tmp_path / "proof-called"
    proof = repo / "scripts" / "viventium" / "first_upgrade_bridge.py"
    proof.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    lock_pid = "424242" if lock_state != "mismatch" else "999999"
    script = lock + guard + f'''
APP_SUPPORT_DIR={shlex.quote(str(support))}
REPO_ROOT={shlex.quote(str(repo))}
PYTHON_BIN={shlex.quote(sys.executable)}
CLI_LOCK_DIR={shlex.quote(str(tmp_path / "cli-lock"))}
SUCCESSOR_VALIDATION_DISABLED_WRITERS=all-reviewed-writers
VIVENTIUM_SUCCESSOR_VALIDATION_DISABLED_WRITERS=$SUCCESSOR_VALIDATION_DISABLED_WRITERS
VIVENTIUM_SUCCESSOR_VALIDATION_MODE=quiesced
VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL=1
VIVENTIUM_SUCCESSOR_VALIDATION_INTERNAL=1
VIVENTIUM_CLI_LOCK_HELD={"0" if lock_state == "absent" else "1"}
VIVENTIUM_CLI_LOCK_DIR=$CLI_LOCK_DIR
VIVENTIUM_CLI_LOCK_OWNER_PID=424242
read_cli_lock_metadata() {{ printf '%s\\n' {lock_pid}; }}
cli_lock_active_owner() {{ [[ "{lock_state}" != dead ]]; }}
helper_runtime_intent_allows_start() {{ return 1; }}
'''
    if lock_state == "self":
        script += 'VIVENTIUM_CLI_LOCK_OWNER_PID=$$\nread_cli_lock_metadata() { printf "%s\\n" "$$"; }\n'
    result = subprocess.run(["bash", "-c", script + "automatic_runtime_intent_allows_start\n"],
                            capture_output=True, text=True, timeout=5, env=os.environ.copy())
    assert result.returncode == (0 if allowed else 1), result.stderr
    assert marker.exists() is allowed


@pytest.mark.parametrize("lock_state,preserved", [
    ("ordinary", False), ("dead", False), ("mismatch", False),
    ("foreign-command", False), ("self", False), ("verified-parent", True),
])
def test_public_stop_with_active_receipt_only_preserves_verified_parent_operation(
    tmp_path: Path, lock_state: str, preserved: bool,
) -> None:
    source = CLI.read_text()
    fixtures_path = REPO_ROOT / "tests" / "release" / "test_cli_upgrade.py"
    spec = importlib.util.spec_from_file_location("stop_intent_cli_fixtures", fixtures_path)
    assert spec and spec.loader
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    functions = "".join(fixture_module.extract_shell_function(source, name) for name in (
        "read_cli_lock_metadata", "cli_lock_active_owner", "verified_parent_cli_lock",
        "preserve_active_quiesced_stop_intent",
    ))
    repo, support = tmp_path / "repo", tmp_path / "support"
    (repo / "scripts" / "viventium").mkdir(parents=True)
    support.mkdir()
    helper = support / "helper-config.json"
    before = (json.dumps({
        "repoRoot": str(repo), "appSupportDir": str(support),
        "runtimeSupervision": {"desiredState": "running", "intentRevision": "a" * 32,
                               "consecutiveLaunchAttempts": 7, "nextLaunchAttemptAt": None},
    }) + "\n").encode()
    helper.write_bytes(before)
    helper.chmod(0o600)
    (repo / "scripts" / "viventium" / "first_upgrade_bridge.py").write_text(
        'print(\'{"status":"active"}\')\n'
    )
    lock = tmp_path / "cli-lock"
    lock.mkdir()
    (lock / "pid").write_text("424242\n")
    (lock / "command").write_text("upgrade\n")
    if lock_state != "foreign-command":
        (lock / "process_command").write_text("bash /synthetic/repo/bin/viventium upgrade\n")
    branch = source.rsplit("  stop)\n", 1)[1].split("    stop_status=0\n", 1)[0]
    script = functions + f'''
APP_SUPPORT_DIR={shlex.quote(str(support))}
REPO_ROOT={shlex.quote(str(repo))}
PYTHON_BIN={shlex.quote(sys.executable)}
CLI_LOCK_DIR={shlex.quote(str(lock))}
COMMAND=stop
set --
VIVENTIUM_CLI_LOCK_HELD={"0" if lock_state == "ordinary" else "1"}
VIVENTIUM_CLI_LOCK_DIR=$CLI_LOCK_DIR
VIVENTIUM_CLI_LOCK_OWNER_PID={"999999" if lock_state == "mismatch" else "424242"}
VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL=1
VIVENTIUM_SUCCESSOR_VALIDATION_MODE=quiesced
cli_lock_active() {{ [[ "{lock_state}" != dead ]]; }}
cli_lock_process_command() {{ printf '%s\\n' '{"unrelated-process" if lock_state == "foreign-command" else "bash /synthetic/repo/bin/viventium upgrade"}'; }}
acquire_cli_lock() {{ :; }}
set_helper_runtime_intent() {{ "$PYTHON_BIN" {shlex.quote(str(SCRIPT))} --config "$APP_SUPPORT_DIR/helper-config.json" --desired "$1"; }}
'''
    if lock_state == "self":
        script += 'VIVENTIUM_CLI_LOCK_OWNER_PID=$$\nprintf "%s\\n" "$$" >"$CLI_LOCK_DIR/pid"\n'
    result = subprocess.run(["bash", "-c", script + branch], capture_output=True, text=True,
                            timeout=5, env={key: value for key, value in os.environ.items()
                                          if key != "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT"})
    assert result.returncode == 0, result.stderr
    if preserved:
        assert helper.read_bytes() == before
    else:
        intent = json.loads(helper.read_text())["runtimeSupervision"]
        assert intent["desiredState"] == "stopped"
        assert intent["intentRevision"] != "a" * 32
        assert intent["consecutiveLaunchAttempts"] == 0


@pytest.mark.parametrize("start_kind", ["explicit", "automatic", "quiesced", "preserve"])
@pytest.mark.parametrize("newer_stop", [False, True])
def test_explicit_start_sets_intent_before_finalizer_without_overwriting_later_stop(
    tmp_path: Path, start_kind: str, newer_stop: bool,
) -> None:
    source = CLI.read_text()
    start = source.rsplit("  start)\n", 1)[1].split('    ensure_app_support_layout "$APP_SUPPORT_DIR"\n', 1)[0]
    assert start.count("set_helper_runtime_intent running") == 1
    helper = tmp_path / "helper-config.json"
    before = {"runtimeSupervision": {"desiredState": "stopped", "intentRevision": "a" * 32,
                                     "consecutiveLaunchAttempts": 7}}
    helper.write_text(json.dumps(before) + "\n")
    helper.chmod(0o600)
    seen = tmp_path / "finalizer-intent.json"
    value_true = "value_is_true() {\n" + source.split("value_is_true() {\n", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    script = value_true + f'''
COMMAND=start
set --
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
PYTHON_BIN={shlex.quote(sys.executable)}
VIVENTIUM_DETACHED_START={"1" if start_kind == "automatic" else "0"}
VIVENTIUM_SUCCESSOR_VALIDATION_MODE={"quiesced" if start_kind == "quiesced" else "full"}
VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT={"1" if start_kind == "preserve" else "0"}
verified_parent_cli_lock() {{ return 1; }}
acquire_cli_lock() {{ :; }}
inherit_quiesced_successor_validation_if_active() {{ :; }}
recover_interrupted_upgrade_before_runtime_start() {{ :; }}
recover_interrupted_helper_install() {{ :; }}
recover_interrupted_dev_runtime_activations() {{ :; }}
inherit_pending_postcommit_finalization_if_needed() {{ :; }}
automatic_runtime_intent_allows_start() {{ return 1; }}
set_helper_runtime_intent() {{ "$PYTHON_BIN" {shlex.quote(str(SCRIPT))} --config "$APP_SUPPORT_DIR/helper-config.json" --desired "$1"; }}
recover_pending_quiesced_upgrade_finalization() {{
  cp "$APP_SUPPORT_DIR/helper-config.json" {shlex.quote(str(seen))}
  {"set_helper_runtime_intent stopped" if newer_stop else ":"}
}}
'''
    result = subprocess.run(["bash", "-c", script + start], capture_output=True, text=True, timeout=5,
                            env={key: value for key, value in os.environ.items()
                                 if key not in {"DEV_RUNTIME_RECOVERY_PERFORMED", "VIVENTIUM_DETACHED_START",
                                                "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT"}})
    assert result.returncode == 0, result.stderr
    at_finalizer = json.loads(seen.read_text())["runtimeSupervision"]
    after = json.loads(helper.read_text())["runtimeSupervision"]
    assert at_finalizer["desiredState"] == ("running" if start_kind == "explicit" else "stopped")
    if start_kind != "explicit":
        assert at_finalizer == before["runtimeSupervision"]
    if newer_stop:
        assert after["desiredState"] == "stopped"
        assert after["intentRevision"] != at_finalizer["intentRevision"]
    else:
        assert after == at_finalizer


@pytest.mark.parametrize("was_running", [False, True])
@pytest.mark.parametrize("desired_state", ["running", "stopped"])
def test_upgrade_validation_keeps_current_running_intent_revision_and_counters(
    tmp_path: Path, was_running: bool, desired_state: str,
) -> None:
    source = CLI.read_text()
    tail = source.split('    upgrade_transaction_checkpoint "continuity_verified"\n', 1)[1].split(
        '    upgrade_transaction_checkpoint "continuity_and_runtime_intent_verified"\n', 1,
    )[0]
    helper = tmp_path / "helper-config.json"
    before = (json.dumps({"runtimeSupervision": {
        "desiredState": desired_state, "intentRevision": "e" * 32,
        "consecutiveLaunchAttempts": 7, "nextLaunchAttemptAt": "2026-07-24T10:00:00Z",
    }}) + "\n").encode()
    helper.write_bytes(before)
    helper.chmod(0o600)
    marker = tmp_path / "stopped-operational-state"
    script = f'''
UPGRADE_STACK_WAS_RUNNING={"1" if was_running else "0"}
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
PYTHON_BIN={shlex.quote(sys.executable)}
stop_stack_for_upgrade() {{ touch {shlex.quote(str(marker))}; }}
set_helper_runtime_intent() {{ "$PYTHON_BIN" {shlex.quote(str(SCRIPT))} --config "$APP_SUPPORT_DIR/helper-config.json" --desired "$1"; }}
'''
    result = subprocess.run(["bash", "-c", script + tail], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    if was_running:
        assert helper.read_bytes() == before
        assert not marker.exists()
    else:
        assert marker.exists()
        assert json.loads(helper.read_text())["runtimeSupervision"]["desiredState"] == "stopped"


@pytest.mark.parametrize("was_running", [False, True])
def test_upgrade_internal_pre_refresh_stop_preserves_saved_intent(tmp_path: Path, was_running: bool) -> None:
    source = CLI.read_text()
    marker = '    if [[ "$UPGRADE_STACK_WAS_RUNNING" == "1" ]]; then\n      echo "Running Viventium stack detected.'
    block = marker + source.split(marker, 1)[1].split('    if ! migrate_telegram_user_configs', 1)[0]
    helper = tmp_path / "helper-config.json"
    before = (json.dumps({"runtimeSupervision": {"desiredState": "running", "intentRevision": "a" * 32,
                                                 "consecutiveLaunchAttempts": 7}}) + "\n").encode()
    helper.write_bytes(before)
    helper.chmod(0o600)
    stopped = tmp_path / "operational-stop"
    script = f'''
UPGRADE_STACK_WAS_RUNNING={"1" if was_running else "0"}
PYTHON_BIN={shlex.quote(sys.executable)}
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
stop_stack_for_upgrade() {{
  touch {shlex.quote(str(stopped))}
  if [[ "${{VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT:-0}}" != 1 ]]; then
    "$PYTHON_BIN" {shlex.quote(str(SCRIPT))} --config "$APP_SUPPORT_DIR/helper-config.json" --desired stopped
  fi
}}
'''
    result = subprocess.run(["bash", "-c", script + block], capture_output=True, text=True, timeout=5,
                            env={key: value for key, value in os.environ.items()
                                 if key != "VIVENTIUM_PRESERVE_HELPER_RUNTIME_INTENT"})
    assert result.returncode == 0, result.stderr
    assert stopped.exists() is was_running
    assert helper.read_bytes() == before
